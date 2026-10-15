# -*- coding: utf-8 -*-
"""2b: W8 지연 추정 보완(``latency.json``은 덮어쓰지 않음). 추정이지 판정이 아니다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/analysis/latency_v2.py

- prefix caching: ``serve6.sh``/``serve6b.sh``는 인자로 정하지 않고, vLLM 0.30.0 기본값으로 켜져 있다(서버 로그 ``enable_prefix_caching=True``).
  pilot_005 순차 지연 측정 서버 로그의 ``Prefix cache hit rate``는 95.5%였다(같은 system prompt 재사용).
- prefill 속도: pilot_005 ``lat-base_s1``·``lat-final_s1``의 호출별 시간을 생성 token에 회귀하면 첫 호출(캐시 없음, 입력 7,272 token)의 잔차가 약 1.0초다
  → 캐시 없는 prefill ≈ 7,272 / 잔차 tok/s.
- Partial 입력 증가 1,459 token(8,729 − 7,270)의 비용:
  - 캐시 있음(순차 측정 조건, 같은 system prompt): 늘어난 부분은 공통 prefix라 첫 문항 뒤에는 적중한다 → 문항당 ≈ 0(질문 부분은 Full과 같은 길이).
  - 캐시 없음: 문항마다 1,459 / prefill 속도 초가 더해진다.
- 두 경우를 W8 추정 1·2(thinking 불변)에 더해 중앙값 비를 다시 낸다(문항별 시간에 더한 뒤 중앙값).
출력: ``latency_v2.json``.
"""
import json
import statistics
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXTRA = 8729 - 7270


def main():
    lat = json.loads((HERE / "latency.json").read_text(encoding="utf-8"))
    pre = {}
    for lab in ("base", "final"):
        d = json.loads((ROOT / f"sft_dpo_inventory/pilot_005/latency/lat-{lab}_s1.json").read_text(encoding="utf-8"))
        calls = [(c["generated_tokens"], c["server_seconds"], c["prompt_tokens"]) for r in d["rows"] for c in r["hf_calls"]]
        g, s = np.array([c[0] for c in calls], float), np.array([c[1] for c in calls], float)
        (a, b), *_ = np.linalg.lstsq(np.vstack([np.ones_like(g), g]).T, s, rcond=None)
        res = s - (a + b * g)
        pre[lab] = {"first_call_residual_s": round(float(res[0]), 3), "first_prompt_tokens": calls[0][2],
                    "prefill_tok_per_s(uncached)": round(calls[0][2] / float(res[0])), "median_abs_residual_s": round(float(np.median(np.abs(res))), 3)}
    rate = statistics.mean(v["prefill_tok_per_s(uncached)"] for v in pre.values())
    extra_uncached = EXTRA / rate
    base_med = lat["pilot005"]["base"]["median_model_seconds"]
    per = lat["per_item"]
    out = {"prefix_caching": {"serve_script_flag": "없음(vLLM 0.30.0 기본값 사용)", "server_log": "enable_prefix_caching=True",
                              "pilot005_sequential_hit_rate": "95.5%(server_8500 로그)"},
           "prefill_estimate": pre, "prefill_tok_per_s_used": round(rate), "extra_input_tokens": EXTRA,
           "extra_seconds_per_item": {"cached": 0.0, "uncached": round(extra_uncached, 3)}}
    for name, cut_key in (("estimate1", "render"), ("estimate2", None)):
        for mode, extra in (("cached", 0.0), ("uncached", extra_uncached)):
            times = []
            for i, r in per.items():
                if name == "estimate1":
                    dlt = (r["render"] or {}).get("delta", 0)
                    cut_s = dlt / r["tok_per_s"] if r["tok_per_s"] else 0
                else:
                    cut_s = None
                times.append((r, cut_s))
            if name == "estimate2":
                # latency.json에 문항별 추정 2 값이 없으므로 중앙값 비에서 역산한 문항당 절감(초)을 쓴다
                med2 = lat["estimate2_partial_ratio(actual final JSON, thinking unchanged)"] * base_med
                new = [r["model_seconds"] for r, _ in times]
                shift = statistics.median(new) - med2
                vals = [x - shift + extra for x in new]
            else:
                vals = [r["model_seconds"] - c + extra for r, c in times]
            out[f"{name}_{mode}_ratio"] = round(statistics.median(vals) / base_med, 3)
    out["summary"] = ("캐시 있음(순차 측정 조건)에서는 입력 증가 비용이 거의 없어 추정 비는 W8과 같다(1.44, 1.42). 캐시가 없으면 문항당 약 "
                      f"{extra_uncached:.2f}초가 더해져 비가 약 {extra_uncached / base_med:.3f} 오른다. 어느 경우든 thinking이 Full arm보다 51 token 넘게 길어지면 1.5를 넘는다.")
    out["note"] = "추정이지 판정이 아니다. Gate E는 다음 세션 실측(base·F·P 같은 GPU 연달아, 동시 요청 1)으로 판정한다."
    (HERE / "latency_v2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
