# -*- coding: utf-8 -*-
"""pilot_002 운영 경로 U 문항 검토 문서(``U_REVIEW.md``)를 기록에서 만든다. 모델을 부르지 않는다. 판정을 바꾸지 않는다.

    python sft_dpo_inventory/pilot_002/u_review/build_u_review.py

- 대상: 업체 100 Ollama-최종의 U 9문항, 참고로 Ollama-SFT에만 있는 U 문항(044, 085).
- 셀: E, B-conv(``pilot_prep_003/ollama``), HF-최종, Ollama-최종(``pilot_002/vendor100``), 참고 Ollama-SFT.
  참고 문항(044, 085)에는 같은 adapter의 HF-SFT도 붙인다.
- 분류: ``baseline_conditions_001/compare_cells.py``(judge.py와 같은 코드). U 근거는 ``grounding_v13/report.unacceptable``의 flag와
  그 flag를 만든 ``v4_checks``(도구 일치 ``tool_ok``, gold 대비 인자 불일치 ``arg_mismatches``)다.
- thinking 원문은 넣지 않는다. 길이(호출별 ``thinking_chars``)만 적는다.
결과: ``U_REVIEW.md``, ``u_review.json``.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
P2 = HERE.parent
ROOT = P2.parents[1]
INV = ROOT / "sft_dpo_inventory"
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("compare_cells", INV / "baseline_conditions_001/compare_cells.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
import evaluate_vendor100 as EV  # noqa: E402

CELLS = {"E": INV / "pilot_prep_003/ollama/E.json", "B-conv": INV / "pilot_prep_003/ollama/B-conv.json",
         "HF-최종": P2 / "vendor100/HF-final.json", "Ollama-최종": P2 / "vendor100/Ollama-final.json",
         "Ollama-SFT": P2 / "vendor100/Ollama-sft.json", "HF-SFT": P2 / "vendor100/HF-sft.json"}
MAIN = ["013", "016", "026", "037", "040", "041", "054", "074", "093"]
SFT_ONLY = ["044", "085"]
OVERLAP = json.loads((P2 / "data/overlap.json").read_text(encoding="utf-8"))["sets"]["vendor100"]
FAMILY = {o["eval_id"] for o in OVERLAP["family"]}
TEMPLATE = {o["eval_id"] for o in OVERLAP["template"]}
U_CLASS = "용납할 수 없는 실패"
SHORT = {"정상 답변": "정상", "안전한 실패": "안전한 실패", U_CLASS: "**U**", "조용한 오답(U 아님)": "조용한 오답",
         "정당한 거부": "정당한 거부"}


def rel(path):
    return str(Path(path).relative_to(ROOT))


def load(path):
    with tempfile.TemporaryDirectory() as empty:     # load_arm의 기본 arm 자리(빈 디렉터리), judge.py의 .empty_arm과 같다
        return C.R.C.load_arm(Path(empty), None, {"dev": str(path)})


def grounding_text(g):
    if not g:
        return "(없음)"
    parts = []
    for c in g.get("concepts") or []:
        od = (c.get("attributes") or {}).get("od_role")
        role = c.get("role") + (f", {od}" if od else "")
        value = f"={json.dumps(c['value'], ensure_ascii=False)}" if c.get("value") is not None else ""
        parts.append(f"{c.get('concept')}/{c.get('subtype')}[{role}]{value}")
    factors = ", ".join(f"{k}={v}" for k, v in (g.get("factors") or {}).items())
    agg = {k: v for k, v in (g.get("aggregation") or {}).items() if v not in (None, "flat")}
    text = "; ".join(parts) + f" | factors: {factors or '-'}"
    return text + (f" | aggregation: {json.dumps(agg, ensure_ascii=False)}" if agg else "")


def call_text(call, with_result=False):
    args = ", ".join(f"{k}={v}" for k, v in (call.get("args") or {}).items())
    text = f"{call.get('tool')}({args})"
    if with_result:
        result = json.dumps(call.get("result"), ensure_ascii=False)
        text += f" → {result[:160]}{'…' if len(result) > 160 else ''}"
    return text


def error_types(flags, checks, gold_tool, got_tool):
    names = {f.split(":", 1)[1] for f in flags}
    types = []
    if "taxi_status" in names or "taxi_type" in names:
        types.append("조건 누락(" + ", ".join(sorted(n for n in names if n in ("taxi_status", "taxi_type"))) + ")")
    if "U3:tool" in flags:
        types.append(f"측정값(도구 {gold_tool} → {got_tool})")
    scope = sorted(n for n in names if n in ("scope", "scope_pickup", "scope_dropoff"))
    if scope:
        types.append("범위·장소(" + ("도구 변경에 따른 scope 인자" if "U3:tool" in flags else "출발·도착 역할") + ")")
    if "dimension_target" in names:
        types.append("집계(묶음 끝점 dimension_target 누락)")
    if "U3:metric" in flags:
        types.append("측정값(metric)")
    if any(f.startswith("U4:") for f in flags):
        types.append("조건 값 바뀜")
    if any(f in ("U2:provenance", "U2:vicinity") for f in flags):
        types.append("범위·장소(출처·주변)")
    dims = [m for m in checks.get("arg_mismatches") or [] if m[0] == "dimension"]
    if dims:
        types.append(f"집계(dimension {dims[0][1]} → {dims[0][2]}, U 아님)")
    return types


def main():
    gold = {i["id"]: i for i in EV.load_gold(None)["items"]}
    data = {name: load(path) for name, path in CELLS.items()}
    out = {"cells": {n: rel(p) for n, p in CELLS.items()}, "items": {}}
    for item_id in MAIN + SFT_ONLY:
        key = f"dev/{item_id}"
        g = gold[item_id]
        entry = {"question": g["question"], "expected_outcome": g.get("expected_outcome", "answered"),
                 "gold_calls": g["gold_text"].split("\n"), "gold_grounding": EV.gold_grounding(g),
                 "family": item_id in FAMILY, "template": item_id in TEMPLATE, "cells": {}}
        for name, (rows, raw) in data.items():
            row, src = rows[key], raw[key]
            flags = C.R.unacceptable(key, row, src)
            regraded, diffs = EV.grounding_check(g, src.get("grounding"))
            checks = row.get("v4_checks") or {}
            entry["cells"][name] = {
                "report_class": C.report_class(row, flags), "u_flags": flags, "grounding_ok": bool(regraded),
                "grounding_diff_keys": sorted({d if isinstance(d, str) else d[0] for d in diffs}),
                "outcome": src.get("outcome"), "error_code": src.get("error_code"), "grounding": src.get("grounding"),
                "tool_ok": checks.get("tool_ok"), "arg_mismatches": checks.get("arg_mismatches"),
                "calls": src.get("calls") or [], "final_answer": src.get("final_answer"),
                "thinking_chars": [c.get("thinking_chars") for c in src.get("llm_calls") or []],
                "call_kinds": [c.get("kind") for c in src.get("llm_calls") or []]}
        out["items"][item_id] = entry
    (HERE / "u_review.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "U_REVIEW.md").write_text(render(out), encoding="utf-8")
    return 0


def shape(g, cell):
    g = g or {}
    measure = ",".join(c.get("subtype") for c in g.get("concepts") or [] if c.get("role") == "MEASURE") or "-"
    od = ",".join(str((c.get("attributes") or {}).get("od_role") or "-") for c in g.get("concepts") or []
                  if c.get("concept") == "LOCATION") or "-"
    f = g.get("factors") or {}
    text = f"{measure} / od {od} / dt {f.get('dimension_target') or '-'} / status {f.get('taxi_status') or '-'}"
    if cell is not None:
        text += f" / {cell['outcome']}" + (f":{cell['error_code']}" if cell["error_code"] else "")
    return text


def last_tool(calls):
    tools = [c.get("tool") for c in calls if c.get("tool") != "get_place_scope"]
    return tools[-1] if tools else None


def render(out):
    items = out["items"]
    lines = ["# pilot_002 운영 경로 U 문항 검토", "",
             "`build_u_review.py`가 기록에서 만든다(모델 호출 없음, 판정은 바꾸지 않음). 사람 검토용이다. thinking 원문은 넣지 않았다.", "",
             "- 대상: 업체 100 Ollama-최종의 U 9문항. 참고로 Ollama-SFT에만 있는 U 2문항(044, 085)을 붙였다.",
             "- 셀 기록: " + ", ".join(f"{n} `{p}`" for n, p in out["cells"].items()) + ".",
             "- 분류 코드는 `vendor100/judge.py`와 같다(`baseline_conditions_001/compare_cells.py`, `evaluation/grounding_v13/report.py`의 `unacceptable`).",
             "  - U1: 정답 호출에 있는 모집단 조건(date·time·taxi_type·taxi_status·dimension)을 버리고 답함. 또는 그 조건 때문에 멈춰야 하는 문항에서 답함.",
             "  - U2: 범위 인자(scope, scope_pickup, scope_dropoff, dimension_target)가 정답 호출과 다름, 또는 장소 출처·주변 오류.",
             "  - U3: 측정 도구(tool) 또는 metric이 정답 호출과 다름. U4: 모집단 조건 값이 바뀜.",
             "  - 판정은 기대 결과가 answered인 문항에서 모델이 answered로 끝났을 때 최종 Tool 호출을 정답 호출과 비교한 결과다.",
             "- family: 결정 54 겹침 검사(`data/overlap.json`)에서 pilot_002 학습 질문과 family가 같은 업체 100 문항. template 겹침도 따로 적었다.", "",
             "## 요약", "",
             "| 문항 | 질문 | family(결정 54) | E | B-conv | HF-최종 | Ollama-최종 | Ollama-SFT | 오류 유형(Ollama 셀) | 같은 adapter의 HF 셀은 U 아님·Ollama만 U |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for item_id, e in items.items():
        cells = e["cells"]
        ref = "Ollama-최종" if item_id in MAIN else "Ollama-SFT"
        c = cells[ref]
        types = error_types(c["u_flags"], {"arg_mismatches": c["arg_mismatches"]},
                            next((t.split("(")[0] for t in reversed(e["gold_calls"]) if not t.startswith("get_place_scope")), None),
                            last_tool(c["calls"]))
        fam = ("안" + (", template" if e["template"] else "")) if e["family"] else "밖"
        hf = "HF-최종" if item_id in MAIN else "HF-SFT"     # 같은 adapter의 HF 셀
        only = "✔" if cells[hf]["report_class"] != U_CLASS and c["report_class"] == U_CLASS else ""
        only += "" if item_id in MAIN else f"(HF-SFT {SHORT.get(cells[hf]['report_class'])})"
        label = item_id if item_id in MAIN else f"{item_id}(SFT만, 참고)"
        lines.append(f"| {label} | {e['question']} | {fam} | " + " | ".join(
            SHORT.get(cells[n]["report_class"], cells[n]["report_class"]) for n in ("E", "B-conv", "HF-최종", "Ollama-최종", "Ollama-SFT"))
            + f" | {'; '.join(types)} | {only} |")
    main_only = [i for i in MAIN if items[i]["cells"]["HF-최종"]["report_class"] != U_CLASS]
    lines += ["", f"- **같은 adapter인데 HF-최종에서는 U가 아니고 Ollama-최종에서만 U인 문항: {len(main_only)}/9**({', '.join(main_only)}).",
              "  HF-최종에서 이 문항들의 분류: " + ", ".join(
                  f"{i} {SHORT.get(items[i]['cells']['HF-최종']['report_class'])}" for i in main_only) + ".",
              "- Ollama-최종 U 9문항 중 직접 변환한 base(B-conv)에서도 U인 문항: " + ", ".join(
                  i for i in MAIN if items[i]["cells"]["B-conv"]["report_class"] == U_CLASS) + ".",
              "- E에서도 U인 문항: " + ", ".join(i for i in MAIN if items[i]["cells"]["E"]["report_class"] == U_CLASS) + ".", "",
              "## 같은 adapter의 HF와 Ollama grounding 비교(기록 그대로)", "",
              "측정 대상(MEASURE subtype), 장소의 출발·도착 역할(od_role), 묶음 끝점(factors.dimension_target), taxi_status, 결과.",
              "SFT 참고 문항은 HF-SFT와 Ollama-SFT를 비교한다. 원인 판단은 하지 않는다.", "",
              "| 문항 | gold | HF | Ollama |", "|---|---|---|---|"]
    for item_id, e in items.items():
        pair = ("HF-최종", "Ollama-최종") if item_id in MAIN else ("HF-SFT", "Ollama-SFT")
        lines.append(f"| {item_id} | {shape(e['gold_grounding'], None)} | " +
                     " | ".join(f"{n}: {shape(e['cells'][n]['grounding'], e['cells'][n])}" for n in pair) + " |")

    def factor(item_id, name, key):
        return ((items[item_id]["cells"][name]["grounding"] or {}).get("factors") or {}).get(key)

    def pair_of(item_id):
        return ("HF-최종", "Ollama-최종") if item_id in MAIN else ("HF-SFT", "Ollama-SFT")
    dt_lost = [i for i in items if (items[i]["gold_grounding"].get("factors") or {}).get("dimension_target")
               and factor(i, pair_of(i)[0], "dimension_target") and not factor(i, pair_of(i)[1], "dimension_target")]
    status = [i for i in MAIN if (items[i]["gold_grounding"].get("factors") or {}).get("taxi_status")]
    lines += ["", "기록에서 보이는 사실(원인 판단 아님):", "",
              f"- 정답에 묶음 끝점(dimension_target)이 있고 HF grounding에는 있는데 Ollama grounding에서 빠진 문항: {', '.join(dt_lost)}.",
              f"- 정답이 `passage_count` + `taxi_status=occupied`(실차 통행량)인 문항: {', '.join(status)}.",
              "  - HF-최종: " + ", ".join(
                  f"{i} " + ("정답 구조로 답함" if items[i]["cells"]["HF-최종"]["grounding_ok"] else
                             f"{items[i]['cells']['HF-최종']['outcome']}:{items[i]['cells']['HF-최종']['error_code']}")
                  for i in status) + ".",
              "  - Ollama-최종: " + ", ".join(
                  f"{i} {shape(items[i]['cells']['Ollama-최종']['grounding'], None).split(' / dt')[0]}로 "
                  f"{items[i]['cells']['Ollama-최종']['outcome']}" for i in status) + ".",
              "", ""]
    for item_id, e in items.items():
        cells = e["cells"]
        ref = "Ollama-최종" if item_id in MAIN else "Ollama-SFT"
        title = f"## {item_id}" + ("" if item_id in MAIN else " (참고: Ollama-SFT에만 U)")
        fam = ("family 안" + (", template도 겹침" if e["template"] else "")) if e["family"] else "family 밖"
        lines += [title, "", f"- 질문: {e['question']}", f"- 결정 54: {fam}",
                  f"- 기대 결과: {e['expected_outcome']}",
                  "- 정답 호출: " + " → ".join(f"`{t}`" for t in e["gold_calls"]),
                  f"- gold grounding: `{grounding_text(e['gold_grounding'])}`", "",
                  "| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |",
                  "|---|---|---|---|---|---|---|---|"]
        for name in ("E", "B-conv", "HF-최종", "Ollama-최종", "Ollama-SFT") + (() if item_id in MAIN else ("HF-SFT",)):
            c = cells[name]
            think = ", ".join(f"{k}:{t}" for k, t in zip(c["call_kinds"], c["thinking_chars"])) or "-"
            lines.append(f"| {name} | {SHORT.get(c['report_class'], c['report_class'])} | {'O' if c['grounding_ok'] else 'X'} "
                         f"| {c['outcome']} | {c['error_code'] or '-'} | {', '.join(c['grounding_diff_keys']) or '-'} "
                         f"| {think} | {', '.join(c['u_flags']) or '-'} |")
        lines += ["", "셀별 grounding:", ""]
        for name in ("E", "B-conv", "HF-최종", "Ollama-최종", "Ollama-SFT") + (() if item_id in MAIN else ("HF-SFT",)):
            lines.append(f"- {name}: `{grounding_text(cells[name]['grounding'])}`")
        c = cells[ref]
        lines += ["", f"{ref}의 Tool 호출과 최종 답:", ""]
        lines += [f"{n}. `{call_text(call, with_result=True)}`" for n, call in enumerate(c["calls"], 1)] or ["- (Tool 호출 없음)"]
        answer = (c["final_answer"] or "(없음)").replace("\n", " / ")
        lines += ["", f"- 최종 답: {answer}", "", f"U로 분류된 이유({ref}):", ""]
        if c["tool_ok"] is False:
            lines.append(f"- 측정 도구가 정답과 다르다(`tool_ok` false → U3:tool): 정답 마지막 호출 "
                         f"`{e['gold_calls'][-1].split('(')[0]}`, 모델 `{last_tool(c['calls'])}`.")
        for name, want, got in c["arg_mismatches"] or []:
            flag = next((f for f in c["u_flags"] if f.endswith(":" + name)), "U 아님")
            lines.append(f"- 인자 `{name}`: 정답 `{want}` → 모델 `{got}` ({flag}).")
        if item_id in MAIN and cells["Ollama-SFT"]["report_class"] == U_CLASS:
            lines.append(f"- Ollama-SFT도 U({', '.join(cells['Ollama-SFT']['u_flags'])}).")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
