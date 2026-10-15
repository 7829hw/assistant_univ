# -*- coding: utf-8 -*-
"""M1b(결정 125 F4 규칙 3, 결정 129): ``m1_run.py``(첫 M1)의 결함 두 가지를 고친 사본.
1. 12,288 재측정에 12,288을 넘는 레코드를 그대로 넣어 Partial이 길이 검사로 실패했다 → 12,288 이하 가장 긴 10개(``PROVISIONAL/m1_12288``).
2. torch 메모리 값을 profile 파일(출력과 함께 지워짐)에서 잘못 읽어 0으로 적었다 → 학습 로그의 ``memory_phase`` ``cuda`` 값에서 읽는다.
단위: pilot_004의 peak(nvidia-smi 43,900 MiB, "약 44 GB / 48 GB")와 같게 **GiB(MiB / 1024)**로 판정한다(46.0 GiB = 47,104 MiB).
12,800 결과는 첫 M1 로그(``m1_Lreq12800_*.log``)와 ``m1_result.json``의 nvidia-smi peak를 그대로 쓴다(다시 재지 않음).

    hfvenv/bin/python m1_run2.py --main /home/hwkim/assistant_univ --gpu-index N
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import m1_run as M

LIMIT_MIB = 46.0 * 1024


def torch_peaks(log):
    alloc = reserved = 0
    for m in re.finditer(r'"cuda": \{"memory_allocated": \d+, "memory_reserved": \d+, "max_memory_allocated": (\d+), "max_memory_reserved": (\d+)\}',
                         Path(log).read_text(encoding="utf-8", errors="replace")):
        alloc, reserved = max(alloc, int(m.group(1))), max(reserved, int(m.group(2)))
    return round(alloc / 2**30, 2), round(reserved / 2**30, 2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--main", required=True)
    p.add_argument("--gpu-index", required=True)
    a = p.parse_args()
    main_dir = Path(a.main)
    wt = Path(__file__).resolve().parents[3]
    uuid = subprocess.run(["nvidia-smi", "-i", str(a.gpu_index), "--query-gpu=uuid", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    first = json.loads((main_dir / "sft_dpo_inventory/pilot_006/build/m1_result.json").read_text(encoding="utf-8"))
    rows = []
    for r in first["runs"]:
        al, rs = torch_peaks(r["log"])
        rows.append({**{k: r[k] for k in ("arm", "max_seq_length", "exit", "optimizer_steps", "seconds_per_step", "nvidia_smi_peak_mib")},
                     "nvidia_smi_peak_gib": round(r["nvidia_smi_peak_mib"] / 1024, 2), "torch_max_allocated_gib": al, "torch_max_reserved_gib": rs,
                     "source": "첫 M1(12,800)"})
    # 12,288: 12,288 이하 레코드 세트
    orig = M.run_arm.__code__
    for arm in ("full", "partial"):
        res = run_12288(main_dir, wt, arm, uuid)
        al, rs = torch_peaks(res["log"])
        rows.append({**{k: res[k] for k in ("arm", "max_seq_length", "exit", "optimizer_steps", "seconds_per_step", "nvidia_smi_peak_mib")},
                     "nvidia_smi_peak_gib": round(res["nvidia_smi_peak_mib"] / 1024, 2), "torch_max_allocated_gib": al, "torch_max_reserved_gib": rs,
                     "deleted_outputs": res["deleted_outputs"], "source": "M1b(12,288 이하 레코드)"})
    del orig
    peak = {L: max(r["nvidia_smi_peak_mib"] for r in rows if r["max_seq_length"] == L) for L in (first["L_req"], 12288)}
    ok12 = all(r["exit"] == 0 for r in rows if r["max_seq_length"] == 12288)
    if peak[first["L_req"]] <= LIMIT_MIB:
        concl = {"rule": "A", "max_seq_length": first["L_req"]}
    elif ok12 and peak[12288] <= LIMIT_MIB:
        concl = {"rule": "3 (L = 12,288; 12,288을 넘는 레코드는 B'처럼 처리)", "max_seq_length": 12288}
    elif ok12:
        concl = {"rule": "B'", "max_seq_length": None, "note": "12,288에서도 46.0 GiB 초과"}
    else:
        concl = {"rule": "undetermined", "note": "12,288 측정 실패"}
    out = {"decision": "125(F4)·129(F8)", "gpu_uuid": uuid, "L_req": first["L_req"], "limit": "46.0 GiB = 47,104 MiB(nvidia-smi peak, pilot_004와 같은 기준)",
           "runs": rows, "peak_mib": {str(k): v for k, v in peak.items()}, "conclusion": concl,
           "note": "m1_result.json(첫 M1)은 decimal GB와 torch 0 기록 결함이 있어 이 파일로 대신한다. 첫 M1의 12,288 Partial 실패는 레코드 길이 결함."}
    (main_dir / "sft_dpo_inventory/pilot_006/build/m1_result_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(concl, ensure_ascii=False), out["peak_mib"])


def run_12288(main_dir, wt, arm, uuid):
    """m1_run.run_arm과 같고 데이터만 PROVISIONAL/m1_12288."""
    import yaml
    build = wt / "sft_dpo_inventory/pilot_006/build"
    src = build / "PROVISIONAL/m1"
    alt = build / "PROVISIONAL/m1_12288"
    # run_arm은 PROVISIONAL/m1/<arm>을 읽으므로, 같은 worktree 안에서 m1을 m1_12288로 바꿔 부른다(worktree는 작업 뒤 지운다)
    tmp = build / "PROVISIONAL/m1__first"
    if not tmp.exists():
        src.rename(tmp)
        alt.rename(src)
    return M.run_arm(main_dir, wt, arm, 12288, uuid, "M1b_L12288")


if __name__ == "__main__":
    main()
