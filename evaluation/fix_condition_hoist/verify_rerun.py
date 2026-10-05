# -*- coding: utf-8 -*-
"""grounding 정리 단계의 값 형식 수정이 기존 T2PC 기록의 결과를 바꾸지 않는지 기록 재적용으로 확인한다(모델 호출 없음).

    python evaluation/fix_condition_hoist/verify_rerun.py --old-root OLD_WORKTREE --work DIR

- 대상: 실행 의미 코드 지문 97efa866(커밋 2f53c72·e07ddd4·ad96729, 작업 트리 변경 없음)으로 만든 prompt 87048d0c 기록.
  sft-dpo-t2pc 브랜치의 E·F는 ``git show``로 작업 디렉터리에만 꺼낸다(이 브랜치로 복사하지 않는다).
- 문항마다 기록된 모델 응답(계획·재질의)을 순서대로 넣어 ``evaluate_vendor100.py rerun``으로 다시 실행한다.
  새 코드(이 저장소)와 수정 전 코드(``--old-root``, 대조)로 각각 실행한다.
- 원 기록과 비교: v3 범주(category), v4 분류, grounding_ok, 오류 코드, outcome. 재적용 행의 ``request_match``가 모두 참이고
  ``needs_live``가 0이어야 한다. 하나라도 다르면 그 문항을 적는다.
- 재적용 결과 파일은 ``--work``(저장소 밖)에 두고 sha256만 남긴다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RECORDS = [
    *[f"evaluation/grounding_v11/runs/full/t2pc/{s}.json"
      for s in ("at", "contrast", "dev", "indepv2", "indepv3", "indepv4", "od", "old44", "status")],
    "evaluation/grounding_v11/runs/heldout/t2pc/heldout.json",
    "evaluation/grounding_v12/runs/measure/t2pc/measure.json",
    "evaluation/grounding_v13/runs/final/t2pc/final.json",
    *[f"evaluation/grounding_v11/runs/small/t2pc/{s}.json"
      for s in ("contrast", "dev", "indepv2", "indepv3", "indepv4", "od", "old44", "status")],
    *[f"evaluation/grounding_v13/runs/small/q8_t2pc/{s}.json"
      for s in ("contrast", "dev", "heldout", "indepv2", "indepv3", "indepv4", "measure", "od", "old44", "status")],
    "evaluation/grounding_v14/runs/check/t2pc_eval_warm.json",
    *[f"evaluation/grounding_v14/runs/ops/t2pc/{s}.json" for s in ("C1", "W1", "W2", "W3")],
]
#: 다른 브랜치의 기록(읽기만). (이름, ref, 경로)
EXTERNAL = [("sft-dpo-t2pc/E", "origin/geoflow/sft-dpo-t2pc", "sft_dpo_inventory/baseline_conditions_001/runs/E.json"),
            ("sft-dpo-t2pc/F", "origin/geoflow/sft-dpo-t2pc", "sft_dpo_inventory/baseline_conditions_001/runs/F.json")]
EXPECTED_COMMITS = ("2f53c72", "e07ddd4", "ad96729")
GROUPS = {"grounding_v13 개발 428": RECORDS[:11], "grounding_v13 최종 56": RECORDS[11:12],
          "grounding_v11 small t2pc": RECORDS[12:20], "grounding_v13 q8_t2pc(qwen3:8b)": RECORDS[20:30],
          "grounding_v14 운영": RECORDS[30:35]}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rerun(code_root, source, gold, out):
    command = [sys.executable, "evaluate_vendor100.py", "--code-root", str(code_root), "--gold", gold,
               "rerun", str(source), "--out", str(out)]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    if done.returncode != 0:
        raise SystemExit(f"rerun 실패: {' '.join(command)}\n{done.stderr[-2000:]}")


def classes(path):
    import evaluate_vendor100 as EV
    _, rows = EV.axes_rows(str(path))
    return {row["id"]: row["v4"] for row in rows}


def compare(source, rerun_path):
    original = json.loads(Path(source).read_text(encoding="utf-8"))
    again = json.loads(Path(rerun_path).read_text(encoding="utf-8"))
    old_rows = {row["id"]: row for row in original["rows"]}
    v4_old, v4_new = classes(source), classes(rerun_path)
    diffs = []
    for row in again["rows"]:
        before = old_rows[row["id"]]
        changed = {key: [before.get(key), row.get(key)] for key in ("category", "grounding_ok", "error_code", "outcome")
                   if before.get(key) != row.get(key)}
        if v4_old[row["id"]] != v4_new[row["id"]]:
            changed["v4"] = [v4_old[row["id"]], v4_new[row["id"]]]
        if not row.get("request_match"):
            changed["request_match"] = [True, row.get("request_match")]
        if row.get("needs_live"):
            changed["needs_live"] = [False, row.get("needs_live")]
        if changed:
            diffs.append({"id": row["id"], "changed": changed})
    return {"items": len(again["rows"]), "source_items": len(original["rows"]),
            "needs_live": sum(bool(r.get("needs_live")) for r in again["rows"]),
            "request_mismatch": sum(not r.get("request_match") for r in again["rows"]),
            "differing_items": diffs}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-root", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent / "rerun_verification.json"))
    args = parser.parse_args()
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    sources = [(path, ROOT / path) for path in RECORDS]
    for name, ref, path in EXTERNAL:
        target = work / "external" / f"{name.replace('/', '_')}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT))
        sources.append((name, target))
    import execution_spec
    report = {"new_code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
              "old_code_fingerprint": execution_spec.code_fingerprint(Path(args.old_root))["sha256"],
              "records": {}}
    for label, source in sources:
        meta = json.loads(Path(source).read_text(encoding="utf-8"))["meta"]
        if meta.get("code_commit", "")[:7] not in EXPECTED_COMMITS or meta.get("code_dirty") \
                or meta.get("planner_prompt_sha256", "")[:8] != "87048d0c":
            raise SystemExit(f"대상 조건이 아닌 기록: {label} {meta.get('code_commit')}")
        entry = {"source_sha256": sha256(source), "model": meta.get("model"),
                 "code_commit": meta.get("code_commit"), "isolation": (meta.get("pipeline") or {}).get("isolation"),
                 "condition_check": (meta.get("pipeline") or {}).get("condition_check")}
        for code, root in (("new", ROOT), ("old", Path(args.old_root))):
            out = work / code / (label.replace("/", "_"))
            out.parent.mkdir(parents=True, exist_ok=True)
            rerun(root, source, meta["gold_file"], out)
            entry[code] = {**compare(source, out), "rerun_sha256": sha256(out)}
        report["records"][label] = entry
        print(label, entry["new"]["items"], "new diffs", len(entry["new"]["differing_items"]),
              "old diffs", len(entry["old"]["differing_items"]), "needs_live", entry["new"]["needs_live"], flush=True)
    groups = dict(GROUPS, **{"sft-dpo-t2pc E·F(qwen3:8b)": [name for name, _, _ in EXTERNAL]})
    report["groups"] = {name: {"records": len(paths), "items": sum(report["records"][p]["new"]["items"] for p in paths)}
                        for name, paths in groups.items()}
    report["total"] = {"records": len(report["records"]),
                       "items": sum(e["new"]["items"] for e in report["records"].values()),
                       "new_differing_items": sum(len(e["new"]["differing_items"]) for e in report["records"].values()),
                       "old_differing_items": sum(len(e["old"]["differing_items"]) for e in report["records"].values()),
                       "needs_live": sum(e["new"]["needs_live"] for e in report["records"].values()),
                       "request_mismatch": sum(e["new"]["request_mismatch"] for e in report["records"].values())}
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["total"], ensure_ascii=False))


if __name__ == "__main__":
    main()
