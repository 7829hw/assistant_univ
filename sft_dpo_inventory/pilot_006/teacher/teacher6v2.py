# -*- coding: utf-8 -*-
"""pilot_006 teacher v2 공통 모듈(결정 131 G1, H1). v1(``teacher6.py``)은 그대로 둔다.

- 요청: teacher 전용 system prompt ``grounding/prompts/teacher_neutral_v2.md``(형식 어휘 없음, 생각은 한국어, 출력은 우리말 결론 다섯 줄) + user = 질문.
  planner prompt(87048d0c)를 붙이지 않는다. 최종 JSON을 쓰게 하지 않는다(두 arm의 답 JSON은 canonical 렌더로 붙인다).
- (a) ``check_field_names(thinking, content)``: v1과 같은 단어 목록이 thinking과 결론 줄 어디에도 없다. 단어 경계는 영문자·숫자·밑줄 기준
  (``FIELD_WORDS_V2``). v1의 ``\b``는 한글 조사가 바로 붙은 경우("dimension_target은")를 놓쳐서 v2에서 더 엄격하게 고쳤다(실행 전).
- (b) ``check_conclusion(content, semantics)``: 결론 다섯 줄(``parse_conclusion``)이 canonical semantics에서 정한 기대값(``expected``)과 모두 같다.
  - 측정: view(semantics)의 측정 subtype → 우리말 이름. 운행 상태(factors.taxi_status)가 있으면 같아야 하고, 없으면 적지 않아야 한다
    (실차 운행 건수에 "상태 실차"를 덧붙인 것은 같은 뜻이라 허용).
  - 끝: 장소·scope 노드의 od_role 집합 → 없음 / 승차 / 하차 / 승차와 하차(both, 또는 pickup과 dropoff가 함께).
  - 묶음: dimension 단위(시도·시군구·읍면동·H3 셀·요일)와 dimension_target(승차 쪽·하차 쪽·승차·하차 짝), bucket(주·월).
  - 집계: aggregation, rollup("다시"), order·limit("순위 상위|하위 N").
  - 주변: factors.vicinity.
- ``to_arm_records``: v1과 같은 형식(통과 trace의 thinking + canonical Full/Partial JSON), metadata의 지시 sha256만 v2.
"""
import hashlib
import json
import re
from pathlib import Path

import teacher6 as V1

ROOT = Path(__file__).resolve().parents[3]
INSTRUCTION = ROOT / "grounding/prompts/teacher_neutral_v2.md"
MEASURE = {"passage_count": "통행량", "trip_count": "실차 운행 건수", "fare": "요금", "revenue": "수입", "speed": "속도", "rpm": "RPM",
           "vacant_ratio": "공차율", "active_taxi_ratio": "가동률", "active_taxi_count": "활성 택시 대수", "operating_days": "운행 일수",
           "place": "장소 이름", "scope": "장소 이름"}
STATUS = {"occupied": "실차", "vacant": "공차", "stationary": "대기"}
UNIT = {"sido": "시도", "sigungu": "시군구", "emd": "읍면동", "h3": "H3 셀", "dayofweek": "요일"}
SIDE = {"pickup": "승차 쪽", "dropoff": "하차 쪽", "both": "승차·하차 짝"}
AGG = {"avg": "평균", "sum": "합계", "max": "최대", "min": "최소", "med": "중간값"}
ORDER = {"top": "상위", "bottom": "하위"}
LABELS = ("측정", "끝", "묶음", "집계", "주변")
FIELD_WORDS_V2 = re.compile(r"(?<![A-Za-z0-9_])(" + V1.FIELD_WORDS.pattern[len(r"\b("):-len(r")\b")] + r")(?![A-Za-z0-9_])")


def instruction_text():
    return INSTRUCTION.read_text(encoding="utf-8").strip()


def instruction_sha256():
    return hashlib.sha256(INSTRUCTION.read_bytes()).hexdigest()


def messages(question):
    return [{"role": "system", "content": instruction_text()}, {"role": "user", "content": question}]


def check_field_names(thinking, content=""):
    found = sorted(set(m.group(1) for m in FIELD_WORDS_V2.finditer((thinking or "") + "\n" + (content or ""))))
    return {"pass": not found, "found": found}


def parse_conclusion(content):
    """결론 다섯 줄 → 정규화된 dict. 줄이 없거나 읽을 수 없으면 그 항목은 None."""
    lines = {}
    for raw in (content or "").splitlines():
        m = re.match(r"^\s*[-*]?\s*\**\s*(측정|끝|묶음|집계|주변)\s*\**\s*[:：]\s*(.+?)\s*$", raw)
        if m:
            lines[m.group(1)] = m.group(2).strip().strip("*").strip()
    out = {k: None for k in LABELS}
    if "측정" in lines:
        t = lines["측정"]
        name = next((v for v in sorted(set(MEASURE.values()), key=len, reverse=True) if t.startswith(v)), None)
        st = re.search(r"상태\s*(실차|공차|대기)", t)
        out["측정"] = {"measure": name, "status": st.group(1) if st else None}
    if "끝" in lines:
        t = lines["끝"].replace(" ", "")
        out["끝"] = ("승차와 하차" if ("승차와하차" in t or ("승차" in t and "하차" in t)) else "승차" if "승차" in t else "하차" if "하차" in t
                    else "없음" if "없음" in t else None)
    if "묶음" in lines:
        t = lines["묶음"]
        units = sorted({v for v in UNIT.values() if f"{v}별" in t or f"{v} 별" in t})
        side = next((v for v in ("승차·하차 짝", "승차 쪽", "하차 쪽") if v in t or v.replace("·", "") in t.replace("·", "")), None)
        if side is None and "짝" in t:
            side = "승차·하차 짝"
        bucket = "주" if re.search(r"주\s*단위", t) else "월" if re.search(r"월\s*단위", t) else None
        out["묶음"] = {"none": t.startswith("없음"), "units": units, "side": side, "bucket": bucket}
    if "집계" in lines:
        t = lines["집계"]
        again = re.search(r"다시\s*(평균|합계|최대|최소|중간값)", t)
        head = t[: again.start()] if again else t
        first = next((v for v in AGG.values() if v in re.split(r"순위", head)[0]), None)
        rank = re.search(r"순위\s*(상위|하위)\s*(\d+)", t)
        out["집계"] = {"agg": first, "rollup": again.group(1) if again else None, "order": rank.group(1) if rank else None,
                     "limit": int(rank.group(2)) if rank else None}
    if "주변" in lines:
        t = lines["주변"]
        out["주변"] = True if t.startswith("예") else False if t.startswith("아니") else None
    return out


def expected(semantics):
    from grounding.canonical import view
    f = semantics.get("factors") or {}
    v = view(semantics)
    m = (v.get("measure") or {}).get("subtype")
    roles = {(n.get("attributes") or {}).get("od_role") for n in semantics.get("nodes") or [] if n.get("subtype") in ("place", "scope")} - {None}
    end = "없음" if not roles else "승차와 하차" if ("both" in roles or {"pickup", "dropoff"} <= roles) else "승차" if roles == {"pickup"} else "하차"
    return {"측정": {"measure": MEASURE.get(m), "status": STATUS.get(f.get("taxi_status"))},
            "끝": end,
            "묶음": {"none": not f.get("dimension") and not f.get("bucket"), "units": [UNIT[f["dimension"]]] if f.get("dimension") else [],
                   "side": SIDE.get(f.get("dimension_target")), "bucket": {"week": "주", "month": "월"}.get(f.get("bucket"))},
            "집계": {"agg": AGG.get(f.get("aggregation")), "rollup": AGG.get(f.get("rollup")), "order": ORDER.get(f.get("order")),
                   "limit": int(f["limit"]) if f.get("limit") is not None and f.get("order") else None},
            "주변": bool(f.get("vicinity"))}


def check_conclusion(content, semantics):
    got, exp = parse_conclusion(content), expected(semantics)
    item = {}
    g, e = got["측정"], exp["측정"]
    item["측정"] = bool(g) and g["measure"] == e["measure"] and (g["status"] == e["status"] or
                                                               (e["status"] is None and g["status"] == "실차" and e["measure"] == "실차 운행 건수"))
    item["끝"] = got["끝"] == exp["끝"]
    g, e = got["묶음"], exp["묶음"]
    item["묶음"] = bool(g) and g["units"] == e["units"] and g["side"] == e["side"] and g["bucket"] == e["bucket"] and (g["none"] == e["none"])
    item["집계"] = got["집계"] == exp["집계"]
    item["주변"] = got["주변"] == exp["주변"]
    parsed = all(got[k] is not None for k in LABELS)
    return {"pass": parsed and all(item.values()), "parsed_all_lines": parsed, "items": item,
            "got": got, "expected": exp}


def to_arm_records(trace, semantics, question, record_id):
    recs = V1.to_arm_records(trace, semantics, question, record_id)
    for r in recs.values():
        r["metadata"]["teacher_instruction_sha256"] = instruction_sha256()
        r["metadata"]["teacher_instruction"] = "teacher_neutral_v2"
    return recs
