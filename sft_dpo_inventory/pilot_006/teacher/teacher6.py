# -*- coding: utf-8 -*-
"""pilot_006 teacher(표현 중립) 공통 모듈(C5): 요청 messages, 자동 검사 (a)(b), 두 arm 레코드 변환.

- 요청: Full planner messages(prompt 87048d0c)의 system 뒤에 ``grounding/prompts/teacher_neutral_v1.md``를 붙인다(teacher 수집 전용, 학습 레코드의 system은 arm 자신의 prompt).
- (a) ``check_field_names(thinking)``: trace(thinking)에 arm 전용 필드 이름·기호가 없다(``FIELD_WORDS``).
- (b) ``check_conclusion(thinking, payload, semantics)``: trace의 결론이 canonical semantics와 같다.
  1. 최종 답(teacher의 Full JSON)이 canonical과 같다(``evaluate_vendor100.grounding_check``, 조건 계층 전): dt, od_role, measure, aggregation, vicinity, bucket/dimension 등.
  2. thinking에 판단 근거가 드러난다(휴리스틱, 우리말·영문 단서): 측정 종류, 끝(od_role 또는 dimension_target이 있으면 승차/하차 단서),
     묶음(dimension이 있으면 묶음 단서, bucket이 있으면 주·월 단위 단서), 집계(aggregation이 있으면 집계어), 주변(vicinity가 있으면 근처·주변).
  두 조건 모두 통과해야 (b) 통과다.
- ``to_arm_records(trace, semantics, question)``: 통과한 trace 하나의 thinking에 Full JSON(``render_full``)과 Partial JSON(``render_partial``)을 붙여
  두 arm의 SFT 레코드(system = arm prompt, ``loss_scope`` full_response, ``source`` teacher)를 만든다. 형식은 trunk ``training.data.thinking.normalize_trace``와 같다.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INSTRUCTION = ROOT / "grounding/prompts/teacher_neutral_v1.md"
INSTRUCTION_SHA256 = "a750b31ae6ddaf3b1a412435f7c970f2e57d4a028b780bde5342cdbd50bc8997"
FIELD_WORDS = re.compile(r"\b(concepts?|subtype|role|source|MEASURE|SUPPORT|SUBCOND|COND|EVENT|EXTENT|implicit|od_role|dimension_target|"
                         r"factors?|aggregation_plan|rollup|bucket|taxi_status|taxi_type|vicinity|LOCATION|AMOUNT|PROPORTION|passage_count|trip_count)\b")
CUES = {
    "passage": ("통행", "지나간", "지나간 양", "passage"), "trip": ("실차", "운행", "건수", "태운", "trip"),
    "pickup": ("승차", "태운", "태워", "탄 ", "출발", "시작", "pickup"), "dropoff": ("하차", "내려", "내린", "도착", "끝", "dropoff"),
    "group": ("묶", "나눠", "나누", "별로", "별 ", "기준으로"), "bucket": ("주 단위", "월 단위", "주별", "월별", "주마다", "월마다", "매주", "매월"),
    "agg": ("평균", "합계", "합", "최대", "최소", "중간", "중앙", "가장 큰", "가장 작은", "총"), "vicinity": ("근처", "주변"),
}


def instruction_text():
    data = INSTRUCTION.read_bytes()
    if hashlib.sha256(data).hexdigest() != INSTRUCTION_SHA256:
        raise ValueError("teacher instruction file drift")
    return data.decode("utf-8").strip()


def messages(question):
    from geoflow.planner import GeoFlowPlanner
    base = GeoFlowPlanner(client=None).messages(question)
    return [{"role": "system", "content": base[0]["content"] + "\n\n" + instruction_text()}, base[1]]


def check_field_names(thinking):
    found = sorted(set(m.group(1) for m in FIELD_WORDS.finditer(thinking or "")))
    return {"pass": not found, "found": found}


def _has(text, key):
    return any(c in text for c in CUES[key])


def check_conclusion(thinking, payload, semantics):
    import evaluate_vendor100 as EV
    from grounding.full_renderer import render_full
    gold = render_full(semantics)
    same, diffs = EV.grounding_check({"gold_grounding": gold, "gold": None}, payload) if payload else (False, ["no_json"])
    f = semantics.get("factors") or {}
    measure = next((n.get("subtype") for n in semantics.get("nodes") or [] if n.get("subtype") in ("passage_count", "trip_count")), None)
    roles = {(n.get("attributes") or {}).get("od_role") for n in semantics.get("nodes") or []} - {None}
    t = thinking or ""
    need = {}
    if measure == "passage_count":
        need["measure_passage"] = _has(t, "passage")
    if measure == "trip_count":
        need["measure_trip"] = _has(t, "trip")
    for end in ("pickup", "dropoff"):
        if end in roles or f.get("dimension_target") == end:
            need[f"endpoint_{end}"] = _has(t, end)
    if "both" in roles or f.get("dimension_target") == "both":
        need["endpoint_both"] = _has(t, "pickup") and _has(t, "dropoff")
    if f.get("dimension"):
        need["grouping"] = _has(t, "group")
    if f.get("bucket"):
        need["bucket"] = _has(t, "bucket")
    if f.get("aggregation"):
        need["aggregation_word"] = _has(t, "agg")
    if f.get("vicinity"):
        need["vicinity"] = _has(t, "vicinity")
    return {"pass": bool(same) and all(need.values()), "final_matches_canonical": bool(same),
            "diffs": [d if isinstance(d, str) else d[0] for d in (diffs or [])][:6], "cues": need}


def to_arm_records(trace, semantics, question, record_id):
    import grounding as GT
    from grounding.full_renderer import render_full
    from grounding.partial_renderer import render_partial
    from training.data.canonicalize import serialize_planner_target
    out = {}
    for arm, answer in (("full", serialize_planner_target(render_full(semantics))), ("partial", json.dumps(render_partial(semantics), ensure_ascii=False))):
        system = GT.make_planner(arm, client=None).messages(question)[0]["content"]
        content = "<think>\n" + trace["thinking"] + "\n</think>\n\n" + answer
        out[arm] = {"messages": [{"role": "system", "content": system}, {"role": "user", "content": question},
                                 {"role": "assistant", "content": content}],
                    "metadata": {"source_record_id": record_id, "source": "teacher", "loss_scope": "full_response", "grounding_target": arm,
                                 "trace_id": trace["trace_id"], "trace_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                                 "thinking_sha256": hashlib.sha256(trace["thinking"].encode("utf-8")).hexdigest(),
                                 "teacher_model": trace.get("model"), "teacher_model_digest": trace.get("model_digest"),
                                 "teacher_instruction_sha256": INSTRUCTION_SHA256, "reasoning_human_reviewed": False,
                                 "answer": "canonical render (teacher thinking + arm JSON)"}}
    return out
