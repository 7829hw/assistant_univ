# -*- coding: utf-8 -*-
"""J4·J5 smoke 판정(모델 호출 없음). 기준은 셀을 돌리기 전에 여기 적었다(2026-10-15).

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/gpu/check_gpu_smoke.py j4 CELL.json OUT.json
    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/gpu/check_gpu_smoke.py j5 CELL.json OUT.json

- **j4**(Full 경로 회귀, 통합 뒤 코드의 selection_v2 vLLM-base 1표본, 회차 seed 20261101): pilot_prep_007 ``serving_vllm_fp8/runs/vllm-bf16-base_s1–4``
  (grounding_ok 74·72·72·76, 생성 token 중앙값 738·714.5·788·740.5)과 비교한다. 통과 = 다음 모두:
  문항 98개(같은 순서), 코드 지문 ``791c4a68``, planner prompt ``87048d0c``, grounding_ok ∈ [67, 81](기준 범위 ±5),
  호출당 생성 token 중앙값 ∈ [607, 906](기준 범위 ±15%). 같은 seed 표본(s1)과의 문항별 일치·생성 token은 보고만 한다(vLLM은 바이트 재현되지 않음, 결정 93).
- **j5**(Partial 경로 vLLM smoke 10문항, P0.3 prompt): 답한 문항마다 셀의 최종 grounding(Partial 응답 → completion → 조건 계층 → parse의 결과,
  Full 형태)을 trunk(Full) pipeline에 정답 planner로 넣어 돌린 Tool 호출 열(``EV._normalized``)이, 셀이 실제로 관찰한 Tool 호출 열과 같은가.
  답하지 않은 문항은 "비교 불가"로 센다. 첫 응답이 실제로 구조 필드(id·concept·role·source)를 생략했는지(Partial 형태)와
  completion 기록(``partial_grounding_completed``)이 남았는지도 센다(보고).
  통과 = 비교 가능한 문항에서 불일치 0, 그리고 셀 meta의 grounding_target이 partial이고 prompt가 ``8b157c9a``. 불일치가 있으면 R2를 시작하지 않는다.
  **2026-10-15 22:30 고침(결함, 기준을 엄격하게)**: 첫 J5S는 모든 요청이 HTTP 400(입력 8,729 + max_tokens 8,192 > max_model_len 16,384)이라 모델 호출 0건이었는데,
  비교 가능 0문항에서 "불일치 0"으로 통과했다(무효, ABORTED_*). 이제 비교 가능 문항 ≥ 8/10과 서버 요청 수 > 0도 요구한다.
"""
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
BASE = ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs/vllm-bf16-base_s{}.json"


def j4(cell):
    rows = cell["rows"]
    toks = [c["generated_tokens"] for r in rows for c in r["hf_calls"]]
    ok = sum(bool(r["grounding_ok"]) for r in rows)
    ref = json.loads(Path(str(BASE).format(1)).read_text(encoding="utf-8"))
    ref_rows = {r["id"]: r for r in ref["rows"]}
    agree = sum(bool(r["grounding_ok"]) == bool(ref_rows[r["id"]]["grounding_ok"]) for r in rows)
    checks = {"items_98_same_order": [r["id"] for r in rows] == [r["id"] for r in ref["rows"]],
              "fingerprint_791c4a68": cell["meta"]["code_fingerprint"].startswith("791c4a68"),
              "prompt_87048d0c": cell["meta"]["planner_prompt_sha256"].startswith("87048d0c"),
              "grounding_ok_in_[67,81]": 67 <= ok <= 81,
              "median_generated_tokens_in_[607,906]": 607 <= statistics.median(toks) <= 906}
    return {"pass": all(checks.values()), "checks": checks, "grounding_ok": ok, "items": len(rows),
            "median_generated_tokens": statistics.median(toks),
            "reference_s1_s4": {"grounding_ok": [74, 72, 72, 76], "median_generated_tokens": [738, 714.5, 788, 740.5]},
            "same_seed_s1_item_agreement(info)": f"{agree}/{len(rows)}",
            "same_seed_s1_generated_tokens_median(info)": statistics.median(c["generated_tokens"] for r in ref["rows"] for c in r["hf_calls"])}


def j5(cell):
    import evaluate_vendor100 as EV
    from geoflow.planner import parse_planner_json
    rows, results = cell["rows"], []
    for row in rows:
        observed = [[c["tool"], EV._normalized(c["tool"], c["args"])] for c in row.get("calls") or []]
        first_partial = None
        try:
            first = parse_planner_json(row["llm_calls"][0]["content"])
            concepts = first.get("concepts") or []
            first_partial = any(isinstance(c, dict) and not all(k in c for k in ("id", "concept", "role", "source")) for c in concepts)
        except Exception:  # noqa: BLE001 - JSON 없음
            pass
        completed = any(n.get("rule") == "partial_grounding_completed" for n in (row.get("grounding") or {}).get("normalizations") or []
                        if isinstance(n, dict))
        if row["outcome"] != "answered" or not row.get("grounding"):
            results.append({"id": row["id"], "comparable": False, "outcome": row["outcome"], "error_code": row["error_code"],
                            "first_response_partial": first_partial})
            continue
        try:
            replayed = EV.run_item(EV._pipeline(EV._GoldPlanner(row["grounding"])), row["question"])
            full_calls = [[c["tool"], EV._normalized(c["tool"], c["args"])] for c in replayed["calls"]]
        except Exception as error:  # noqa: BLE001
            full_calls = f"error: {type(error).__name__}: {error}"
        results.append({"id": row["id"], "comparable": True, "same": full_calls == observed, "first_response_partial": first_partial,
                        "completion_recorded": completed,
                        **({} if full_calls == observed else {"observed": observed, "full_path": full_calls})})
    comparable = [r for r in results if r["comparable"]]
    checks = {"grounding_target_partial": cell["meta"].get("grounding_target") == "partial",
              "prompt_8b157c9a": cell["meta"]["planner_prompt_sha256"].startswith("8b157c9a"),
              "fingerprint_791c4a68": cell["meta"]["code_fingerprint"].startswith("791c4a68"),
              "no_signature_mismatch": all(r["same"] for r in comparable),
              "comparable_at_least_8": len(comparable) >= 8,
              "server_requests_gt_0": (cell["meta"].get("vllm", {}).get("request_log") or {}).get("requests", 0) > 0}
    return {"pass": all(checks.values()), "checks": checks, "items": len(rows), "comparable": len(comparable),
            "first_response_partial": sum(bool(r.get("first_response_partial")) for r in results),
            "completion_recorded": sum(bool(r.get("completion_recorded")) for r in results),
            "mismatches": [r for r in comparable if not r["same"]], "not_comparable": [r for r in results if not r["comparable"]]}


def main():
    kind, cell_path, out = sys.argv[1:4]
    cell = json.loads(Path(cell_path).read_text(encoding="utf-8"))
    result = {"kind": kind, "cell": cell_path, **(j4(cell) if kind == "j4" else j5(cell))}
    Path(out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("kind", "pass", "checks")}, ensure_ascii=False))
    return 0 if result["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
