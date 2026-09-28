# -*- coding: utf-8 -*-
"""v2 run 기록(observations.jsonl)을 보고서(report.md, report.json)로 다시 집계한다. 채점하지 않는다.

채점은 evaluate_v2.py가 관측마다 이미 했다(사전 등록 규칙, evaluation/v2/preregistration_v2.md).
여기서는 그 범주를 문장 단위와 intent 단위로, 기대 결과·절(section)·복원 대상·stage-swap별로
나눠 센다. 모든 비율은 건수와 분모를 함께 적는다.

    python evaluation/v2/report_v2.py evaluation/v2/runs/<run_id>
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

import paraphrase_corpus as P  # noqa: E402

HOLDOUT = BASE_DIR / "evaluation" / "v2" / "paraphrases_holdout_v2.yaml"
OUTCOMES = ("answered", "needs_clarification", "unsupported", "failed")
SECTIONS = {
    "A": ("aggregation holdout 복원", range(1, 11)),
    "B": ("local aggregation holdout 복원", range(11, 21)),
    "C": ("verifier holdout 복원", range(21, 28)),
    "D": ("v2 거부", range(28, 35)),
    "E": ("v2 경계", range(35, 43)),
}


def fraction(count, total):
    return {"count": count, "of": total, "rate": None if not total else round(count / total, 4)}


def text(value):
    return "-" if value["of"] == 0 else f"{value['count']}/{value['of']} ({value['rate']:.1%})"


def section_of(intent_id):
    if not intent_id or not intent_id.startswith("w"):
        return None
    number = int(intent_id[1:3])
    return next(key for key, (_, numbers) in SECTIONS.items() if number in numbers)


def outcome_of(record):
    return record.get("outcome") if record.get("outcome") in OUTCOMES else "failed"


def load(run_dir):
    rows = [json.loads(line) for line in
            (Path(run_dir) / "observations.jsonl").read_text(encoding="utf-8").splitlines() if line]
    meta = json.loads((Path(run_dir) / "meta.json").read_text(encoding="utf-8"))
    return meta, rows


def stage_swap_intents():
    """순서를 바꾸면 다른 값이 되는 두 단계 intent(구간 안 집계 지정, 구간 안 ≠ 구간별)."""
    names = set()
    for intent in P.load_corpus(HOLDOUT):
        semantic = intent.get("aggregation")
        if (isinstance(semantic, dict) and "bucket" in semantic
                and semantic["inner"] not in ("unspecified", semantic["final"])):
            names.add(intent["intent"])
    return names


def block(rows):
    valid = [r for r in rows if r.get("measurement") == "valid"]
    answerable = [r for r in valid if r["expected_outcome"] == "answered"]
    refusal = [r for r in valid if r["expected_outcome"] != "answered"]
    return {
        "sentences": len(rows), "valid": len(valid),
        "semantic_correct": fraction(sum(r["category"] == "correct" for r in valid), len(valid)),
        "execution_completion": fraction(sum(r["outcome"] == "answered" for r in answerable),
                                         len(answerable)),
        "answerable_correct": fraction(sum(r["category"] == "correct" for r in answerable),
                                       len(answerable)),
        "refusal_strict": fraction(sum(r["category"] == "correct" for r in refusal), len(refusal)),
        "refusal_lenient_not_answered": fraction(
            sum(r["outcome"] != "answered" for r in refusal), len(refusal)),
        "categories": dict(Counter(r["category"] for r in rows)),
    }


def intent_block(rows):
    """intent 단위: 문장이 모두 correct면 intent 정답(all), 과반이면 majority."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["intent_id"]].append(row["category"] == "correct")
    return {
        "intents": len(groups),
        "all_paraphrases_correct": fraction(sum(all(v) for v in groups.values()), len(groups)),
        "majority_correct": fraction(sum(sum(v) * 2 > len(v) for v in groups.values()), len(groups)),
        "any_correct": fraction(sum(any(v) for v in groups.values()), len(groups)),
    }


def analyze(run_dir):
    meta, rows = load(run_dir)
    swap = stage_swap_intents()
    report = {"run_id": meta.get("run_id"), "all": block(rows), "all_intents": intent_block(rows)}
    report["by_expected_outcome"] = {
        outcome: {"sentences": block([r for r in rows if r["expected_outcome"] == outcome]),
                  "intents": intent_block([r for r in rows if r["expected_outcome"] == outcome])}
        for outcome in ("answered", "needs_clarification", "unsupported")}
    cross = {want: dict(Counter(outcome_of(r) for r in rows if r["expected_outcome"] == want))
             for want in ("answered", "needs_clarification", "unsupported")}
    report["crosstab_sentences"] = cross
    report["by_section"] = {}
    for key, (label, _) in SECTIONS.items():
        part = [r for r in rows if section_of(r.get("intent_id")) == key]
        if part:
            report["by_section"][key] = {"label": label, "sentences": block(part),
                                         "intents": intent_block(part)}
    swapped = [r for r in rows if r.get("intent_id") in swap]
    report["stage_swap"] = {
        "intents": sorted(swap),
        "answered_expected": {"sentences": block([r for r in swapped
                                                  if r["expected_outcome"] == "answered"]),
                              "intents": intent_block([r for r in swapped
                                                       if r["expected_outcome"] == "answered"])},
        "all": {"sentences": block(swapped), "intents": intent_block(swapped)},
    }
    report["unsupported_detail"] = {
        "error_codes_when_not_answered": dict(Counter(
            f"{r['outcome']}:{r.get('error_code')}"
            for r in rows if r["expected_outcome"] == "unsupported" and r["outcome"] != "answered")),
    }
    report["by_intent"] = {}
    for row in rows:
        entry = report["by_intent"].setdefault(row["intent_id"], {
            "expected_outcome": row["expected_outcome"], "restores": row.get("restores"),
            "section": section_of(row.get("intent_id")), "results": []})
        entry["results"].append({"id": row["id"], "outcome": row["outcome"],
                                 "category": row["category"], "error_code": row.get("error_code")})
    report["failures"] = [
        {"id": r["id"], "intent_id": r["intent_id"], "question": r["question"],
         "expected_outcome": r["expected_outcome"], "outcome": r["outcome"],
         "category": r["category"], "error_code": r.get("error_code"),
         "stage": r.get("stage"),
         "arg_mismatches": (r.get("checks") or {}).get("arg_mismatches"),
         "want_aggregation": r.get("semantic_aggregation"),
         "got_aggregation": (r.get("plan_facts") or {}).get("aggregation"),
         "final_tool": (r.get("plan_facts") or {}).get("final_tool"),
         "final_tool_args": (r.get("plan_facts") or {}).get("final_tool_args"),
         "tools": r.get("tools"), "final_answer": r.get("final_answer"),
         "initial_llm_output": next((c.get("content") for c in r.get("llm_calls") or []), None)}
        for r in rows if r["category"] != "correct"]
    return meta, report


def markdown(meta, report):
    lines = [f"# v2 평가 보고서: {report['run_id']}", "",
             "잠정치: 평가셋은 사람이 검토하지 않았다(registry review.status unreviewed). mock 고정값으로 실행했으므로 "
             "수치의 정확성이 아니라 요청 인자·집계 의미·결과 종류를 채점했다.", "",
             f"- 커밋 {meta['git']['commit']} (dirty {meta['git']['dirty_paths']}), 명령 `{meta['command']}`",
             f"- 모델 {meta['model']} digest {meta['model_digest']} {meta['model_details']}, Ollama {meta['ollama_version']}",
             f"- 설정 {json.dumps(meta['pipeline'], ensure_ascii=False)}, chat timeout {meta['chat_timeout']}",
             f"- 기준일 {meta['reference_date']} (Asia/Seoul), 시작 {meta['started_at']}",
             f"- planner prompt sha256 {meta['planner_prompt_sha256']}",
             f"- 입력 sha256 {json.dumps(meta['inputs'], ensure_ascii=False)}", "",
             "## 전체 (문장 단위)", "", "| 지표 | 값 |", "| --- | --- |"]
    overall = report["all"]
    for key, label in (("semantic_correct", "의미 정답(전체)"),
                       ("execution_completion", "실행 완료(answered 기대 문장 중 답함)"),
                       ("answerable_correct", "의미 정답(answered 기대 문장)"),
                       ("refusal_strict", "거부 정확도 strict(기대 종류로 멈춤)"),
                       ("refusal_lenient_not_answered", "보조: 거부 기대 문장에서 답하지 않음")):
        lines.append(f"| {label} | {text(overall[key])} |")
    intents = report["all_intents"]
    lines += ["", f"intent 단위({intents['intents']}개): 모든 문장 정답 {text(intents['all_paraphrases_correct'])}, "
              f"과반 문장 정답 {text(intents['majority_correct'])}.", "",
              "## 기대 결과별", "",
              "| 기대 결과 | 문장 정답 | intent(모든 문장) 정답 | intent(과반) 정답 |", "| --- | --- | --- | --- |"]
    for outcome, value in report["by_expected_outcome"].items():
        lines.append(f"| {outcome} | {text(value['sentences']['semantic_correct'])} | "
                     f"{text(value['intents']['all_paraphrases_correct'])} | "
                     f"{text(value['intents']['majority_correct'])} |")
    lines += ["", "## 기대 결과 × 실제 결과 (문장)", "",
              "| 기대 \\ 실제 | " + " | ".join(OUTCOMES) + " |", "| --- |" + " --- |" * len(OUTCOMES)]
    for want, counts in report["crosstab_sentences"].items():
        lines.append(f"| {want} | " + " | ".join(str(counts.get(o, 0)) for o in OUTCOMES) + " |")
    lines += ["", "## 절별", "", "| 절 | 문장 정답 | 실행 완료 | 거부 strict | intent(모든 문장) |",
              "| --- | --- | --- | --- | --- |"]
    for key, value in report["by_section"].items():
        s = value["sentences"]
        lines.append(f"| {key} {value['label']} | {text(s['semantic_correct'])} | "
                     f"{text(s['execution_completion'])} | {text(s['refusal_strict'])} | "
                     f"{text(value['intents']['all_paraphrases_correct'])} |")
    swap = report["stage_swap"]["answered_expected"]
    lines += ["", f"stage-swap 대상 두 단계 answered intent {swap['intents']['intents']}개: 문장 정답 "
              f"{text(swap['sentences']['semantic_correct'])}, intent(모든 문장) {text(swap['intents']['all_paraphrases_correct'])}.",
              "", "## 범주", "", "| 범주 | 문장 |", "| --- | --- |"]
    for key, count in sorted(overall["categories"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {key} | {count} |")
    lines += ["", "unsupported 기대 문장에서 답하지 않은 경우의 결과·코드: "
              + json.dumps(report["unsupported_detail"]["error_codes_when_not_answered"],
                           ensure_ascii=False), "", "## intent별", "",
              "| intent | 기대 | p0 | p1 | p2 |", "| --- | --- | --- | --- | --- |"]
    for name, entry in report["by_intent"].items():
        cells = [f"{r['category']}" + (f" ({r['error_code']})" if r["error_code"] else "")
                 for r in entry["results"]]
        lines.append(f"| {name} | {entry['expected_outcome']} | " + " | ".join(cells) + " |")
    lines += ["", "## 실패 목록", ""]
    for item in report["failures"]:
        lines.append(f"- `{item['id']}` {item['question']} — 기대 {item['expected_outcome']}, 실제 "
                     f"{item['outcome']} / {item['category']} / {item['error_code']}; "
                     f"인자 차이 {item['arg_mismatches']}; 집계 {item['got_aggregation']} (기대 "
                     f"{item['want_aggregation']}); tools {item['tools']}")
    return "\n".join(lines) + "\n"


def main(run_dir):
    meta, report = analyze(run_dir)
    run_dir = Path(run_dir)
    (run_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    (run_dir / "report.md").write_text(markdown(meta, report), encoding="utf-8")
    print(run_dir / "report.md")


if __name__ == "__main__":
    main(sys.argv[1])
