# -*- coding: utf-8 -*-
"""M1(결정 129 F8, 결정 125 F4): 짧은 메모리 확인 학습. 스케줄러가 GPU 하나에서 단독으로 부른다(CUDA_VISIBLE_DEVICES는 스케줄러가 정함).

    hfvenv/bin/python m1_run.py --main /home/hwkim/assistant_univ --gpu-index N

- 설정: pilot_005 V1 config에 ``max_seq_length = L_req``(``PROVISIONAL/lengths.json``), 데이터 = arm별 가장 긴 레코드 10개(``PROVISIONAL/m1/<arm>``),
  ``--max-steps 10`` × 두 arm = 최대 20 step. arm마다 ``grounding_target``이 다르다(학습 코드 검사를 그대로 지난다).
- 기록: profiling의 ``max_memory_allocated``·``max_memory_reserved``(torch), 이 GPU의 ``nvidia-smi`` memory.used 최댓값(0.5초 간격), step 시간.
- F4 규칙: 두 arm의 nvidia-smi peak 최댓값이 46.0 GB 이하면 (A) ``max_seq_length = L_req``. 넘으면 ``L = 12,288``로 한 번 더(레코드가 12,288을 넘으면
  12,288 이하 가장 긴 것). 그래도 넘으면 (B'). 결과는 ``m1_result.json``(보고만, 세션 3 데이터 빌드에 적용).
- 끝나면 adapter·checkpoint(출력 디렉터리)를 지운다. 남기는 것은 메모리·시간 기록뿐(결정 129).
"""
import argparse
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import yaml

LIMIT_GB = 46.0
TMP = Path("/home/hwkim/sftdpo_work/pilot_006/m1_tmp")


def run_arm(main_dir, wt, arm, length, uuid, tag):
    build = wt / "sft_dpo_inventory/pilot_006/build"
    cfg = yaml.safe_load((wt / "training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml").read_text(encoding="utf-8"))
    d = build / "PROVISIONAL/m1" / arm
    cfg["data"] = {"train": str(d / "sft_train.jsonl"), "valid": str(d / "sft_valid.jsonl"), "manifest": str(d / "manifest.json"), "grounding_target": arm}
    out = TMP / f"{tag}_{arm}"
    cfg["training"].update(output_dir=str(out), max_seq_length=length, save_strategy="no", eval_strategy="no")
    cfg["training"].pop("save_steps", None)
    cfg["training"].pop("eval_steps", None)
    cfg["profiling"]["output"] = str(out / "profile.json")
    TMP.mkdir(parents=True, exist_ok=True)
    cpath = TMP / f"{tag}_{arm}.yaml"
    cpath.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    peak = {"mib": 0}
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            try:
                v = int(subprocess.run(["nvidia-smi", "-i", uuid, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                       capture_output=True, text=True).stdout.strip())
                peak["mib"] = max(peak["mib"], v)
            except ValueError:
                pass
            time.sleep(0.5)
    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t0 = time.perf_counter()
    log = main_dir / f"sft_dpo_inventory/pilot_006/build/m1_{tag}_{arm}.log"
    rc = subprocess.run(["/home/hwkim/sftdpo_work/hfvenv/bin/python", "-m", "training.train_sft", "--config", str(cpath), "--max-steps", "10"],
                        cwd=str(wt), stdout=open(log, "w"), stderr=subprocess.STDOUT).returncode
    stop.set()
    th.join()
    prof = json.loads((out / "profile.json").read_text(encoding="utf-8")) if (out / "profile.json").exists() else {}
    mem = [e for e in prof.get("events", []) if isinstance(e, dict)]
    torch_peak = max((e.get("max_memory_allocated") or 0 for e in mem), default=0)
    torch_reserved = max((e.get("max_memory_reserved") or 0 for e in mem), default=0)
    res = {"arm": arm, "max_seq_length": length, "exit": rc, "status": prof.get("status"), "optimizer_steps": prof.get("optimizer_steps"),
           "seconds_per_step": prof.get("seconds_per_step"), "step_seconds": prof.get("step_seconds"), "wall_seconds": round(time.perf_counter() - t0, 1),
           "torch_max_memory_allocated_gb": round(torch_peak / 1e9, 2), "torch_max_memory_reserved_gb": round(torch_reserved / 1e9, 2),
           "nvidia_smi_peak_gb": round(peak["mib"] * 1048576 / 1e9, 2), "nvidia_smi_peak_mib": peak["mib"], "log": str(log)}
    shutil.rmtree(out, ignore_errors=True)
    cpath.unlink(missing_ok=True)
    res["deleted_outputs"] = not out.exists()
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--gpu-index", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    wt = Path(__file__).resolve().parents[3]
    uuid = subprocess.run(["nvidia-smi", "-i", str(a.gpu_index), "--query-gpu=uuid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    lengths = json.loads((wt / "sft_dpo_inventory/pilot_006/build/PROVISIONAL/lengths.json").read_text(encoding="utf-8"))
    l_req = lengths["L_req"]
    runs = [run_arm(main_dir, wt, arm, l_req, uuid, f"Lreq{l_req}") for arm in ("full", "partial")]
    peak = max(r["nvidia_smi_peak_gb"] for r in runs)
    ok = all(r["exit"] == 0 for r in runs)
    result = {"decision": "125(F4)·129(F8)", "gpu_uuid": uuid, "L_req": l_req, "limit_gb": LIMIT_GB, "runs": runs, "peak_gb": peak}
    if ok and peak <= LIMIT_GB:
        result["conclusion"] = {"rule": "A", "max_seq_length": l_req}
    elif ok and l_req > 12288:
        runs2 = [run_arm(main_dir, wt, arm, 12288, uuid, "L12288") for arm in ("full", "partial")]
        result["runs_12288"] = runs2
        peak2 = max(r["nvidia_smi_peak_gb"] for r in runs2)
        result["conclusion"] = ({"rule": "3(12288, longer records by B')", "max_seq_length": 12288} if peak2 <= LIMIT_GB
                                else {"rule": "B'", "max_seq_length": None, "note": "12,288에서도 46.0 GB 초과"})
    elif ok:
        result["conclusion"] = {"rule": "B'", "max_seq_length": None, "note": f"L_req {l_req} ≤ 12,288인데 46.0 GB 초과"}
    else:
        result["conclusion"] = {"rule": "undetermined", "note": "M1 학습 실패(로그 확인)"}
    (main_dir / "sft_dpo_inventory/pilot_006/build/m1_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result["conclusion"], ensure_ascii=False), peak)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
