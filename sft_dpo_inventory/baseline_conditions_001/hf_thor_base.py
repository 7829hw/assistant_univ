# -*- coding: utf-8 -*-
"""thor 업체 100 Base 측정(vendor_100_baseline_001)을 이 장비의 GPU 2에서 thor 코드로 재현한다. 학습 없음.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 \
      python hf_thor_base.py --thor-root WT_THOR --out DIR [--condition-check]

- thor worktree(b314904)의 코드와, thor manifest에 보존된 frozen runner 원문(``protocol_runner_source``, sha256
  c18e8965…)을 그대로 쓴다. runner의 ``run_model('base')``를 호출한다(HFClient, BF16·SDPA, thinking 끔, greedy,
  max_new_tokens 1024, seed 42, 기준일 2026-09-25, mock·legacy, 기존 repair 정책).
- 바꾸는 것(메모리 안에서만, thor 파일 수정 없음):
  1. 출력 위치(DEST·RAW)를 ``--out``으로 돌린다. DEST에는 thor manifest·frozen_questions 사본을 둔다.
  2. ``verify()``를 부분 확인으로 바꾼다. thor의 immutable_inputs 중 adapter·ignored corpus(Base 측정에 쓰지 않음)는 이 저장소에
     없으므로 확인하지 못한 항목으로 기록한다. prompt hash, 존재하는 입력 hash(코드·업체 gold·XLSX), runner hash, 문항 순서는 확인한다.
  3. ``--condition-check``이면 runner가 고정한 ``condition_check=False``만 True로 바꾼다(그 밖의 인자 그대로).
- 업체 100 결과는 평가 전용이다.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
THOR_REF = "b3149040fb0fc57bedd1e8ff4436333f55d41e5a"
BASELINE = "training/evaluations/vendor_100_baseline_001"
XLSX = "evaluation/vendor100/질문 결과 및 정답 설명_100문항.xlsx"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--thor-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--condition-check", action="store_true")
    args = parser.parse_args()
    thor = Path(args.thor_root).resolve()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=thor, text=True).strip()
    if head != THOR_REF:
        raise SystemExit(f"thor worktree HEAD가 {THOR_REF}가 아닙니다: {head}")
    out = Path(args.out).resolve()
    dest, raw = out / "dest", out / "raw"
    dest.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "frozen_questions.json"):
        shutil.copyfile(thor / BASELINE / name, dest / name)
    manifest = json.loads((dest / "manifest.json").read_text())
    source = manifest["protocol_runner_source"]
    runner = thor / "training/runs/vendor_100_baseline_001/benchmark.py"   # thor의 ignored 경로(ROOT 계산용)
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_text(source, encoding="utf-8")
    if sha256(runner) != manifest["protocol"]["runner_sha256"]:
        raise SystemExit("runner sha256 불일치")

    sys.path.insert(0, str(runner.parent))
    import benchmark as B   # noqa: E402  (thor ROOT를 sys.path 앞에 둔다)
    B.DEST, B.RAW = dest, raw

    checked, unavailable, mismatched = {}, [], []
    original_verify = B.verify

    def partial_verify():
        assert hashlib.sha256(B.production_prompt().encode()).hexdigest() == manifest["prompt_hash"]
        for path, digest in manifest["immutable_inputs"].items():
            candidate = thor / path
            if not candidate.exists() and path == XLSX:
                candidate = REPO / path        # ignored XLSX는 worktree에 없다. 같은 bytes인지 원 저장소에서 확인
            if not candidate.exists():
                unavailable.append(path)
                continue
            if sha256(candidate) != digest:
                mismatched.append(path)
            checked[path] = digest
        assert not mismatched, f"Input drift: {mismatched}"
        assert sha256(B.__file__) == manifest["protocol"]["runner_sha256"]
        items = B.V.load_gold()["items"]
        frozen = json.loads((dest / "frozen_questions.json").read_text())
        assert [(r["id"], r["question"]) for r in items] == [(r["id"], r["question"]) for r in frozen]
        return manifest, items, {r["id"]: r["categories"] for r in frozen}

    B.verify = partial_verify
    if args.condition_check:
        real_create = B.GeoFlowPipeline.create

        class Pipeline:
            @staticmethod
            def create(**kwargs):
                assert kwargs.get("condition_check") is False
                kwargs["condition_check"] = True
                return real_create(**kwargs)
        B.GeoFlowPipeline = Pipeline

    B.run_model("base")
    receipt = {"thor_ref": head, "runner_sha256": manifest["protocol"]["runner_sha256"],
               "condition_check": bool(args.condition_check), "verify": "partial",
               "inputs_checked": len(checked), "inputs_unavailable": unavailable,
               "inputs_mismatched": mismatched, "original_verify_replaced": original_verify.__name__}
    (out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
