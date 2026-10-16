# -*- coding: utf-8 -*-
"""pilot_006 PLAN 고정(세션 3에서 실행, 세션 2b H9에서 만들기만 함 — **지시 4절: 이 세션에서는 실행하지 않는다**).

    hfvenv/bin/python sft_dpo_inventory/pilot_006/freeze.py --rc RC2 [--plan PLAN.md] [--out FREEZE.json]
    hfvenv/bin/python sft_dpo_inventory/pilot_006/freeze.py --rc RC2 --dry-run   # 세션 2c: FREEZE_DRYRUN.json만, 고정하지 않음

PLAN·gate 도구·지연 도구·빌드 도구·RC 데이터의 커밋과 sha256을 한 번에 기록한다. 기록 뒤 사용자가 커밋하면 그 커밋이 사전 등록 시점이다.
- 작업 트리가 깨끗해야 한다(추적 파일 수정 없음, 대상 파일이 모두 커밋됨). 아니면 exit 2.
- 대상 파일마다: 저장소 경로, sha256, 그 파일을 마지막으로 바꾼 커밋(``git log -1``). HEAD 커밋과 원격 일치 여부.
- RC 데이터: 두 arm ``sft_train.jsonl``·``manifest.json``·``build_summary.json``·``lengths.json``·``questions.json`` sha256, 두 arm 질문 목록 sha256(같아야 함).
- 지문: ``SEMANTIC_CODE``(``execution_spec.code_fingerprint``) ``791c4a68``, Full prompt ``87048d0c``, Partial system prompt sha256.
- 이미 출력 파일이 있으면 덮어쓰지 않는다(``--dry-run``은 ``FREEZE_DRYRUN.json``을 덮어쓴다).
- ``--dry-run``: 고정될 파일 목록과 sha256, 작업 트리 상태(수정·미커밋 파일)를 적기만 한다. ``FREEZE.json``을 만들지 않고 exit 0.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TOOLS = {
    "plan": "sft_dpo_inventory/pilot_006/PLAN.md",
    "gate_tool": "sft_dpo_inventory/pilot_006/gates/compute_gates.py",
    "latency_tool": "sft_dpo_inventory/pilot_006/latency/latency6.py",
    "build_tool": "sft_dpo_inventory/pilot_006/build/build6rc.py",
    "build_checks": "sft_dpo_inventory/pilot_006/build/rc_checks.py",
    "loss_tokens_check": "sft_dpo_inventory/pilot_006/build/check_loss_tokens6.py",
    "loss_mask_audit": "sft_dpo_inventory/pilot_006/build/loss_mask_audit6.py",
    "approved_corpus": "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl",
    "approved_holdout": "sft_dpo_inventory/pilot_006_prep/approved/approved_holdout_v1.jsonl",
    "holdout_gold": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
    "training_config_base": "training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml",
    "judge_tool": "sft_dpo_inventory/pilot_006_prep/self_samples/judge6.py",
    "teacher_module": "sft_dpo_inventory/pilot_006/teacher/teacher6v3.py",
    "protected_final_spec": "sft_dpo_inventory/pilot_006/protected_final_v1_SPEC.md",
    "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md",
}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rc", required=True)
    p.add_argument("--plan", default=None, help="고정할 PLAN 파일(기본 PLAN_DRAFT.md)")
    p.add_argument("--out", default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = Path(a.out) if a.out else HERE / ("FREEZE_DRYRUN.json" if a.dry_run else "FREEZE.json")
    if out.exists() and not a.dry_run:
        raise SystemExit(f"{out} exists; not overwriting")
    tools = dict(TOOLS)
    if a.plan:
        tools["plan"] = a.plan
    rc = f"sft_dpo_inventory/pilot_006/build/{a.rc}"
    data = {f"rc:{arm}:{f}": f"{rc}/{arm}/{f}" for arm in ("full", "partial") for f in ("sft_train.jsonl", "manifest.json")}
    data.update({f"rc:{f}": f"{rc}/{f}" for f in ("build_summary.json", "lengths.json", "questions.json", "checks_summary.json")})
    files = {**tools, **data}
    dirty = git("status", "--porcelain", "--untracked-files=no")
    untracked = [v for v in files.values() if git("ls-files", "--error-unmatch", v) == ""]
    if (dirty or untracked) and not a.dry_run:
        print(json.dumps({"dirty": dirty.splitlines(), "not_committed": untracked}, ensure_ascii=False))
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT))
    import execution_spec
    from training.trainer_common import expected_system_prompt
    man = {a2: json.loads((ROOT / f"{rc}/{a2}/manifest.json").read_text(encoding="utf-8"))["sft"] for a2 in ("full", "partial")}
    qsha = {a2: m["question_list_sha256"] for a2, m in man.items()}
    record = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
              "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
              "dry_run": a.dry_run, "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
              "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)}
                        for k, v in files.items()},
              "rc": {"label": a.rc, "question_list_sha256": qsha, "question_lists_equal": len(set(qsha.values())) == 1,
                     "records": {a2: m["train_count"] for a2, m in man.items()}, "max_seq_length": {a2: m.get("max_seq_length") for a2, m in man.items()}},
              "fingerprints": {"semantic_code": execution_spec.code_fingerprint(ROOT)["sha256"],
                               "full_prompt_sha256": hashlib.sha256(expected_system_prompt("full").encode()).hexdigest(),
                               "partial_system_prompt_sha256": hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest()}}
    ok = (record["rc"]["question_lists_equal"] and record["fingerprints"]["semantic_code"].startswith("791c4a68")
          and record["fingerprints"]["full_prompt_sha256"].startswith("87048d0c") and record["head"] == record["remote_head"])
    record["ok"] = ok
    out.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": ok, "dry_run": a.dry_run, "head": record["head"], "rc": record["rc"]}, ensure_ascii=False))
    raise SystemExit(0 if (ok or a.dry_run) else 1)


if __name__ == "__main__":
    main()
