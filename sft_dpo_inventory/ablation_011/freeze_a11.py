# -*- coding: utf-8 -*-
"""ablation_011 측정 전 고정(결정 261, PLAN_A11 7절). 파일 sha256과 정한 값을 FREEZE_A11.json(학습 전) 또는 FREEZE_A11_tools.json(분석 도구, 평가 전)에 쓴다.

    python3 sft_dpo_inventory/ablation_011/freeze_a11.py plan    # -> FREEZE_A11.json
    python3 sft_dpo_inventory/ablation_011/freeze_a11.py tools   # -> FREEZE_A11_tools.json
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def files(globs):
    out = {}
    for g in globs:
        hits = sorted(ROOT.glob(g))
        if not hits:
            raise SystemExit(f"missing {g}")
        for p in hits:
            out[str(p.relative_to(ROOT))] = sha(p)
    return out


def main():
    which = sys.argv[1]
    A = "sft_dpo_inventory/ablation_011"
    if which == "plan":
        body = {"label": "ablation_011 FREEZE(결정 261) — 학습 전", "note": "진단, 판정 아님",
                "order_seeds": [1102, 211102, 2026113], "model_seed": 43, "bootstrap": {"reps": 10000, "rng": "numpy.random.default_rng(20261109), 비교마다 새로", "ci": "백분위 95%"},
                "e1": {"sets": ["refusal_dev v2", "valid98", "aux"], "k": 4, "round_seeds": "20261100 + k", "concurrency": 8, "reference_date": "2026-09-25"},
                "e2": "없음 — 30k 원천 llm-finetuning-30000.jsonl 없음(결정 261 실행 기록)",
                "files": files([f"{A}/PLAN_A11.md", f"{A}/build/build11.py", f"{A}/build/mask_audit11.py", f"{A}/build/build_summary.json", f"{A}/build/mask_audit11.json",
                                f"{A}/build/removed_A2.json", f"{A}/build/removed_A3.json", f"{A}/build/A*/full/*", f"{A}/build/orders/*.json",
                                f"{A}/train/train_a11.py", f"{A}/train/make_a11_configs.py", f"{A}/train/configs/*.yaml", f"{A}/train/configs/DIFF.md",
                                f"{A}/gpu/scheduler13.py", f"{A}/gpu/serve_a11.sh", f"{A}/gpu/make_jobs_a11.py", f"{A}/gpu/jobs_a11.json",
                                "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", "sft_dpo_inventory/pilot_010/build/V4/full/manifest.json",
                                "sft_dpo_inventory/pilot_007/train_data/train_b7b.py", "sft_dpo_inventory/pilot_007/train_data/order7b.py", "sft_dpo_inventory/pilot_007/train_data/order7.py",
                                "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py", "training/data/thinking.py"])}
        out = HERE / "FREEZE_A11.json"
    else:
        body = {"label": "ablation_011 FREEZE tools(결정 261) — 평가 전", "note": "진단, 판정 아님",
                "smoke": {"analyze_a11 --smoke": "pilot_010 V4 3 seed 올바른 거부 86.48·과잉 거부 2.17·개발 셋 71.81 = selection_s10.json; V8(A1 자리) − V4 짝 비교 동작",
                          "xtab_a11 --existing": "pilot_010 V4·V8·B2 F·P9 과잉 거부 2.17·4.24·0.98·10.68%, client10k V4 거부 112·169·148 = 기존 기록",
                          "completeness11": "pilot_010 셀 16개에서 completeness10.json 다시 돌리기 판단과 같음"},
                "amendments_to_plan": ["6절 3 유형 칸: type_target.profile 칸은 semantics가 필요한데 E1 gold에는 정답 호출만 있어 '분석 tool | 시간 단위 | 지역 유형'(xtab_a11.classify) 서명으로 묶고 문항 4개 이상 칸만 본다(smoke에서 59칸 중 13칸).",
                                       "6절 5 지역 유형: 광안리·동성로·동대구역·어린이대공원은 POI로 명시('리'는 읍면동 접미사로 쓰지 않음; E1·client10k 장소명 22종 확인).",
                                       "5절 다시 돌리기 판단의 서버 오류는 completeness_B.cell 정의(UNHANDLED_EXCEPTION + 연결 예외)를 쓴다; analyze_a11 속도표에는 서버 오류를 넣지 않는다."],
                "files": files([f"{A}/analysis/*.py", f"{A}/analysis/smoke_*.json", f"{A}/soup/soup11.py", f"{A}/soup/soup_check.json"])}
        out = HERE / "FREEZE_A11_tools.json"
    body["frozen_at"] = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    out.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out, len(body["files"]))


if __name__ == "__main__":
    main()
