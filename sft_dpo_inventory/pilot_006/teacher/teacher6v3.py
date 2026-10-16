# -*- coding: utf-8 -*-
"""pilot_006 teacher v3a·v3b 공통 모듈(결정 144 K7, P3). v1·v2 파일은 그대로 둔다.

- v3a: ``grounding/prompts/teacher_neutral_v3a.md``(T0V2_REPORT 수정 제안 반영) + user = 질문. teacher는 정답을 보지 않는다.
- v3c(결정 151): v3b + 주변 표현(부근·인근·근방), 영어 생각 금지 보강, "결론"이라는 말·대조 문장 금지. (c) 목록은 ``EXPOSURE_V3C``.
- v3b: ``teacher_neutral_v3b.md`` + user = 질문 + "[결론]" 다섯 줄(canonical에서 ``conclusion_lines``로 만듦; 형식은 (b) parser와 같음).
- 검사: (a) ``teacher6v2.check_field_names``(thinking + 결론 줄, 영문자 경계), (b) ``teacher6v2.check_conclusion``(결론 다섯 줄 = canonical),
  (c) ``check_exposure``(v3b만): thinking과 결론 줄에 정답 노출 문구(``EXPOSURE``, 실행 전 커밋)가 있으면 노출.
- ``to_arm_records``: v2와 같은 형식, 지시 이름·sha256만 v3a/v3b.
"""
import hashlib
import re
from pathlib import Path

import teacher6v2 as V2

ROOT = Path(__file__).resolve().parents[3]
PROMPTS = {"v3a": ROOT / "grounding/prompts/teacher_neutral_v3a.md", "v3b": ROOT / "grounding/prompts/teacher_neutral_v3b.md",
           "v3c": ROOT / "grounding/prompts/teacher_neutral_v3c.md"}
#: 정답 노출 문구(결정 144 (c), 실행 전 고정). 결론을 받았다는 사실이 드러나는 표현.
EXPOSURE = ("주어진 결론", "확정된 결론", "참고 결론", "정답", "힌트", "위 결론", "위의 결론", "제시된 결론", "받은 결론", "결론이 주어", "결론을 받", "[결론]",
            "이미 정해진", "주어진 판단", "확정된 판단", "주어진 다섯", "주어진 답")
#: v3c 전용 (c) 목록(결정 151, 실행 전 고정): 결정 144 목록 + v3b 읽기 검사(V3B_READ.md)에서 본 받은 결론 의식 표현.
EXPOSURE_V3C = EXPOSURE + ("결론", "conclusion", "Conclusion", "일치한다", "대조")


def instruction_text(variant):
    return PROMPTS[variant].read_text(encoding="utf-8").strip()


def instruction_sha256(variant):
    return hashlib.sha256(PROMPTS[variant].read_bytes()).hexdigest()


def conclusion_lines(semantics):
    """canonical → 결론 다섯 줄(``teacher6v2.parse_conclusion``이 그대로 읽는 형식)."""
    e = V2.expected(semantics)
    m = e["측정"]["measure"] + (f", 상태 {e['측정']['status']}" if e["측정"]["status"] else "")
    g = e["묶음"]
    parts = []
    if g["units"]:
        parts.append(f"{g['units'][0]}별" + (f", {g['side']}" if g["side"] else ""))
    if g["bucket"]:
        parts.append(f"{g['bucket']} 단위로 먼저 집계")
    a = e["집계"]
    agg = [a["agg"] or "없음"] + ([f"다시 {a['rollup']}"] if a["rollup"] else []) + ([f"순위 {a['order']} {a['limit']}"] if a["order"] else [])
    return "\n".join([f"측정: {m}", f"끝: {e['끝']}", f"묶음: {' / '.join(parts) or '없음'}", f"집계: {', '.join(agg)}", f"주변: {'예' if e['주변'] else '아니오'}"])


def messages(variant, question, semantics=None):
    user = question if variant == "v3a" else question + "\n\n[결론]\n" + conclusion_lines(semantics)  # v3b·v3c
    return [{"role": "system", "content": instruction_text(variant)}, {"role": "user", "content": user}]


def check_exposure(thinking, content="", variant="v3b"):
    text = (thinking or "") + "\n" + (content or "")
    found = sorted({w for w in (EXPOSURE_V3C if variant == "v3c" else EXPOSURE) if w in text})
    return {"exposed": bool(found), "found": found}


def check_field_names(thinking, content=""):
    return V2.check_field_names(thinking, content)


def check_conclusion(content, semantics):
    return V2.check_conclusion(content, semantics)


def to_arm_records(trace, semantics, question, record_id, variant):
    recs = V2.V1.to_arm_records(trace, semantics, question, record_id)
    for r in recs.values():
        r["metadata"]["teacher_instruction_sha256"] = instruction_sha256(variant)
        r["metadata"]["teacher_instruction"] = f"teacher_neutral_{variant}"
    return recs
