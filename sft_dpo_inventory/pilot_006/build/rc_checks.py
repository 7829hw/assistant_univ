# -*- coding: utf-8 -*-
"""RC 빌드 검사(H8). GPU·모델 호출 없음(학습 코드의 dry-run·tokenizer-check와 CPU 렌더링 검사만).

    hfvenv/bin/python sft_dpo_inventory/pilot_006/build/rc_checks.py --rc RC1

- config: 시험 빌드 config(``configs/provisional_<arm>.yaml``, pilot_005 V1 사본)에서 데이터 경로·``max_seq_length``(12,288, 결정 125)·출력 위치만 바꾼
  ``configs/<rc>_<arm>.yaml``을 만든다(학습에 쓰는 config가 아니라 검사용; 세션 3 학습 config는 PLAN 고정 때 따로).
- 두 arm마다: ``training.train_sft --dry-run``, ``--tokenizer-check``, ``check_loss_tokens6.py``(출처별 손실 token), ``loss_mask_audit6.py``(마스크 audit).
- 결과: ``<rc>/checks.log``, ``<rc>/loss_tokens_<arm>.json``, ``<rc>/loss_mask_audit_<arm>.json``, ``<rc>/checks_summary.json``.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rc", required=True)
    p.add_argument("--max-seq-length", type=int, default=12288)
    a = p.parse_args()
    rc = HERE / a.rc
    env = {**os.environ, "HF_HOME": "/home/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false"}
    summary = {}
    log = open(rc / "checks.log", "w", encoding="utf-8")
    for arm in ("full", "partial"):
        cfg = yaml.safe_load((HERE / f"configs/provisional_{arm}.yaml").read_text(encoding="utf-8"))
        rel = f"sft_dpo_inventory/pilot_006/build/{a.rc}/{arm}"
        cfg["data"].update(train=f"{rel}/sft_train.jsonl", valid=f"{rel}/sft_valid.jsonl", manifest=f"{rel}/manifest.json", grounding_target=arm)
        cfg["training"].update(max_seq_length=a.max_seq_length, output_dir=f"/home/hwkim/sftdpo_work/pilot_006/{a.rc.lower()}_unused/{arm}")
        cfg["profiling"]["output"] = f"/home/hwkim/sftdpo_work/pilot_006/{a.rc.lower()}_unused/{arm}_profile.json"
        cpath = HERE / f"configs/{a.rc.lower()}_{arm}.yaml"
        cpath.write_text(f"# pilot_006 {a.rc} 검사용(학습에 쓰지 않음). provisional_{arm}.yaml에서 데이터·max_seq_length {a.max_seq_length}·출력 위치만 바꿈.\n"
                         + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        res = {}
        for name, cmd in (("dry_run", [PY, "-m", "training.train_sft", "--config", str(cpath), "--dry-run"]),
                          ("tokenizer_check", [PY, "-m", "training.train_sft", "--config", str(cpath), "--tokenizer-check"]),
                          ("loss_tokens", [PY, str(HERE / "check_loss_tokens6.py"), str(cpath), str(rc / f"loss_tokens_{arm}.json")]),
                          ("loss_mask_audit", [PY, str(HERE / "loss_mask_audit6.py"), str(cpath), str(rc / f"loss_mask_audit_{arm}.json")])):
            r = subprocess.run(cmd, cwd=str(ROOT), env=env, capture_output=True, text=True)
            log.write(f"## {arm} {name}\n{r.stdout[-3000:]}{r.stderr[-1500:] if r.returncode else ''}\nexit={r.returncode}\n")
            log.flush()
            res[name] = r.returncode == 0
        for k in ("loss_tokens", "loss_mask_audit"):
            f = rc / f"{k}_{arm}.json"
            if f.exists():
                d = json.loads(f.read_text(encoding="utf-8"))
                res[f"{k}_detail"] = {x: d.get(x) for x in ("records", "all_ok", "mismatches", "by_source") if x in d}
        summary[arm] = res
    (rc / "checks_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({arm: {k: v for k, v in r.items() if not k.endswith("detail")} for arm, r in summary.items()}))


if __name__ == "__main__":
    main()
