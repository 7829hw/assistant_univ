# -*- coding: utf-8 -*-
"""결정 43의 두 미확인 실험 비교. 모델을 부르지 않는다(기록만 읽는다).

    python sft_dpo_inventory/pilot_001_analysis/decision43/compare.py

1. HF 경로의 장치 일치: pilot_001 SFT step 124 valid98을 GPU 3 기록(``pilot_001/valid98/runs/sft_step124.json``, 원문
   ``training/generated/pilot_001/sft_step124_raw.jsonl``)과 GPU 2 재측정(``sft_step124_gpu2.json``, 원문
   ``training/generated/pilot_001_analysis/sft_step124_gpu2_raw.jsonl``)으로 비교한다.
   - 첫 응답(호출 0)의 원문 바이트 일치 수, 모든 호출의 일치 수, grounding_ok, 생성 상한에 걸린 호출 수, 결과 종류.
   - 다르면 pilot_001 SFT 선택(``selection_sft.json``)에 장치가 섞였을 수 있는 범위를 적는다. 선택 결과는 바꾸지 않는다.
2. 변환 경로 영향: valid98에서 HF-base(``pilot_prep_003/valid100/runs/base.json``의 valid98 문항)와 B-conv(Ollama),
   HF-최종(``pilot_001/valid98/runs/dpo_step212.json``)과 Ollama-최종을 같은 문항으로 비교한다.
   - grounding_ok, b·c(HF→Ollama), McNemar 정확 검정 양측 p, 불일치 문항 수, 첫 응답 JSON 일치 수, 결과 종류.
   - 학습 전(base 쌍)과 학습 뒤(최종 쌍)의 HF−Ollama 차이와 불일치 수를 나란히 둔다. 두 차이의 차이는 검정하지 않고 수만 적는다.
   - 참고로 경로 안의 학습 효과(HF base → 최종, B-conv → Ollama-최종)의 b·c도 적는다.
- 결과: ``comparison.json``.
"""
import json
import math
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))
from analyze import split_think  # noqa: E402  (pilot_001 분석과 같은 함수)
import evaluate_vendor100 as EV  # noqa: E402

GEN = ROOT / "training/generated"
V98 = ROOT / "sft_dpo_inventory/pilot_001/valid98"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 4)


def median(values):
    values = sorted(values)
    n = len(values)
    return round((values[n // 2] + values[(n - 1) // 2]) / 2, 2) if n else None


def valid_ids():
    return [f"{r['set']}/{r['id']}" for r in read_json(V98 / "valid98_items.json")["items"]]


def hf_rows(path):
    return {r["id"]: r for r in read_json(path)["rows"]}


def raw_calls(path, label=None):
    out = {}
    for r in read_jsonl(path):
        if label and r.get("label") != label:
            continue
        out.setdefault(r["id"], {})[r["call"]] = r
    return out


def device_check(ids):
    old = read_json(V98 / "runs/sft_step124.json")
    new = read_json(HERE / "sft_step124_gpu2.json")
    ro, rn = {r["id"]: r for r in old["rows"]}, {r["id"]: r for r in new["rows"]}
    co = raw_calls(GEN / "pilot_001/sft_step124_raw.jsonl")
    cn = raw_calls(GEN / "pilot_001_analysis/sft_step124_gpu2_raw.jsonl")
    first_equal, all_equal, differs, ok_changed = 0, 0, [], []
    first_divergence = {}
    for i in ids:
        a, b = co.get(i, {}), cn.get(i, {})
        if a.get(0, {}).get("raw_sha256") == b.get(0, {}).get("raw_sha256") and 0 in a:
            first_equal += 1
        else:
            ta, tb = a.get(0, {}).get("raw_text", ""), b.get(0, {}).get("raw_text", "")
            n = next((k for k, (x, y) in enumerate(zip(ta, tb)) if x != y), min(len(ta), len(tb)))
            first_divergence[i] = {"first_diff_char": n, "len_gpu3": len(ta), "len_gpu2": len(tb),
                                   "tokens_gpu3": a.get(0, {}).get("generated_tokens"),
                                   "tokens_gpu2": b.get(0, {}).get("generated_tokens")}
        if [a[k]["raw_sha256"] for k in sorted(a)] == [b[k]["raw_sha256"] for k in sorted(b)]:
            all_equal += 1
        else:
            differs.append(i)
        if ro[i]["grounding_ok"] != rn[i]["grounding_ok"]:
            ok_changed.append({"id": i, "gpu3": ro[i]["grounding_ok"], "gpu2": rn[i]["grounding_ok"]})
    b = sum(1 for i in ids if not ro[i]["grounding_ok"] and rn[i]["grounding_ok"])
    c = sum(1 for i in ids if ro[i]["grounding_ok"] and not rn[i]["grounding_ok"])
    sel = read_json(ROOT / "sft_dpo_inventory/pilot_001/selection_sft.json")
    cands = [{"label": x.get("label"), "grounding_ok": x.get("grounding_ok")} for x in sel.get("candidates", [])]
    devices = {}
    for x in sel.get("candidates", []):
        path = V98 / "runs" / f"{x['label']}.json"
        devices[x["label"]] = read_json(path)["meta"]["device_uuid"] if path.exists() else None
    return {
        "meta": {"gpu3": {k: old["meta"][k] for k in ("device_uuid", "adapter_sha256", "code_fingerprint", "planner_prompt_sha256", "torch", "finished_at")},
                 "gpu2": {k: new["meta"][k] for k in ("device_uuid", "adapter_sha256", "code_fingerprint", "planner_prompt_sha256", "torch", "finished_at")}},
        "items": len(ids), "first_response_byte_equal": first_equal, "all_calls_equal": all_equal,
        "items_any_call_differs": differs, "first_response_divergence": first_divergence,
        "grounding_ok": {"gpu3": old["summary"]["grounding_ok"], "gpu2": new["summary"]["grounding_ok"], "b(gpu3 X→gpu2 O)": b,
                         "c(gpu3 O→gpu2 X)": c, "mcnemar_p": mcnemar(b, c), "changed_items": ok_changed},
        "truncated_calls": {"gpu3": old["summary"]["truncated_calls"], "gpu2": new["summary"]["truncated_calls"]},
        "first_raw_ok": {"gpu3": old["summary"]["first_raw_ok"], "gpu2": new["summary"]["first_raw_ok"]},
        "outcomes_equal": sum(1 for i in ids if (ro[i]["outcome"], ro[i]["error_code"]) == (rn[i]["outcome"], rn[i]["error_code"])),
        "seconds_total": {"gpu3": old["summary"]["seconds"], "gpu2": new["summary"]["seconds"]},
        "selection_sft(기록, 바꾸지 않음)": {"selected": sel.get("selected", {}).get("label"), "candidates": cands,
                                          "devices": devices},
    }


def first_json(text):
    from geoflow.planner import parse_planner_json
    try:
        return json.dumps(parse_planner_json(text), ensure_ascii=False, sort_keys=True)
    except Exception:  # noqa: BLE001
        return None


def path_pair(ids, hf_path, hf_raw, hf_label, ollama_path):
    hf = hf_rows(hf_path)
    ol = {r["id"]: r for r in read_json(ollama_path)["rows"]}
    calls = raw_calls(hf_raw, hf_label)
    b = sum(1 for i in ids if not hf[i]["grounding_ok"] and ol[i]["grounding_ok"])
    c = sum(1 for i in ids if hf[i]["grounding_ok"] and not ol[i]["grounding_ok"])
    disagree = [i for i in ids if bool(hf[i]["grounding_ok"]) != bool(ol[i]["grounding_ok"])]
    first_equal = 0
    for i in ids:
        h = calls.get(i, {}).get(0, {}).get("raw_text")
        hj = first_json(split_think(h)[1]) if h else None
        oc = [x for x in ol[i].get("llm_calls") or [] if x.get("kind") == "plan"]
        oj = first_json(oc[0].get("content") or "") if oc else None
        first_equal += bool(hj is not None and hj == oj)
    return {"items": len(ids), "grounding_ok": {"hf": sum(bool(hf[i]["grounding_ok"]) for i in ids),
                                                "ollama": sum(bool(ol[i]["grounding_ok"]) for i in ids)},
            "b(HF X→Ollama O)": b, "c(HF O→Ollama X)": c, "mcnemar_p": mcnemar(b, c),
            "disagree": len(disagree), "disagree_items": disagree, "first_json_equal": first_equal,
            "outcomes": {"hf": dict(Counter(f"{hf[i]['outcome']}:{hf[i]['error_code']}" for i in ids)),
                         "ollama": dict(Counter(f"{ol[i]['outcome']}:{ol[i]['error_code']}" for i in ids))},
            "truncated_calls": {"hf": sum(d == "length" for i in ids for d in hf[i]["done_reasons"]),
                                "ollama_length_or_failed": sum(1 for i in ids for x in ol[i].get("llm_calls") or []
                                                               if x.get("done_reason") == "length" or x.get("failed"))},
            "latency_median_s": {"hf(문항 seconds)": median([hf[i]["seconds"] for i in ids]),
                                 "ollama(run_cost total_ms)": median([(EV.run_cost(ol[i])["total_ms"] or 0) / 1000 for i in ids])},
            "sources": {"hf": str(Path(hf_path).relative_to(ROOT)), "ollama": str(Path(ollama_path).relative_to(ROOT))}}


def within(ids, before_path, after_path):
    """같은 경로 안에서 학습 전 → 뒤의 grounding_ok b·c(valid98, 보조 기록)."""
    x = {r["id"]: r for r in read_json(before_path)["rows"]}
    y = {r["id"]: r for r in read_json(after_path)["rows"]}
    b = sum(1 for i in ids if not x[i]["grounding_ok"] and y[i]["grounding_ok"])
    c = sum(1 for i in ids if x[i]["grounding_ok"] and not y[i]["grounding_ok"])
    return {"before": sum(bool(x[i]["grounding_ok"]) for i in ids), "after": sum(bool(y[i]["grounding_ok"]) for i in ids),
            "b(전 X→뒤 O)": b, "c(전 O→뒤 X)": c, "mcnemar_p": mcnemar(b, c)}


def main():
    ids = valid_ids()
    out = {"1_hf_device": device_check(ids) if (HERE / "sft_step124_gpu2.json").exists() else "not run"}
    paths = {}
    if (HERE / "valid98_B-conv.json").exists():
        paths["base: HF-base → B-conv"] = path_pair(ids, ROOT / "sft_dpo_inventory/pilot_prep_003/valid100/runs/base.json",
                                                   GEN / "pilot_prep_003/valid100_base_raw.jsonl", None, HERE / "valid98_B-conv.json")
    if (HERE / "valid98_Ollama-final.json").exists():
        paths["final: HF-최종 → Ollama-최종"] = path_pair(ids, V98 / "runs/dpo_step212.json", GEN / "pilot_001/dpo_step212_raw.jsonl",
                                                       None, HERE / "valid98_Ollama-final.json")
    if len(paths) == 2:
        a, f = paths["base: HF-base → B-conv"], paths["final: HF-최종 → Ollama-최종"]
        paths["학습 전후 나란히(검정 없음)"] = {
            "hf_minus_ollama": {"base": a["grounding_ok"]["hf"] - a["grounding_ok"]["ollama"],
                                "final": f["grounding_ok"]["hf"] - f["grounding_ok"]["ollama"]},
            "disagree": {"base": a["disagree"], "final": f["disagree"]},
            "first_json_equal": {"base": a["first_json_equal"], "final": f["first_json_equal"]}}
        paths["경로 안 학습 효과(참고)"] = {
            "HF: base → 최종": within(ids, ROOT / "sft_dpo_inventory/pilot_prep_003/valid100/runs/base.json", V98 / "runs/dpo_step212.json"),
            "Ollama: B-conv → 최종": within(ids, HERE / "valid98_B-conv.json", HERE / "valid98_Ollama-final.json")}
    out["2_conversion_path"] = paths
    (HERE / "comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
