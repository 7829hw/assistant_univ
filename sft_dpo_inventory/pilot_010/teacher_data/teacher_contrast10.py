# -*- coding: utf-8 -*-
"""pilot_010 근접 대조 teacher 추론(결정 242 AA2). 기존 teacher 모듈(``pilot_006/teacher/teacher6v2``·``teacher6v3``, ``pilot_007/teacher/teacher_checks7``·``c2_edit``,
``pilot_009/build/teacher_filter9``)은 고치지 않고 가져다 쓴다. 모델 호출 없음.

- 지시: ``grounding/prompts/teacher_contrast_v1.md``(v3b·teacher_refusal_v1 바탕, 실행 전 커밋, 뒤로 고치지 않음).
  user = 질문 + "\\n\\n[결론]\\n" + canonical 다섯 줄(``teacher6v3.conclusion_lines``) [+ "\\n\\n[가까운 거부 범주]\\n" + 범주 설명(``NEAR``, 문항에 gap이 있을 때만)].
- 검사(실행 전 고정):
  (a) 필드 이름(``teacher6v2`` 목록 + 거부 출력 필드 ``unsupported``), (b) 결론 다섯 줄 = canonical(``teacher6v2.check_conclusion``),
  (c) 노출(v3b ``EXPOSURE`` + 이 지시의 이름표 ``EXPOSURE_C``), (d) 한국어·(e) 영어 노출·메타(``teacher_checks7``), (ii) "결론과 일치"류(``itemdata.concl_types``),
  (f') 출력에 결론 다섯 줄이 canonical과 같고(= (b)) "지원하지 않음"이 어디에도 없음,
  (s) 결정 235 거르기: 생각(c2 뒤)에 이 지시의 금지 절 이름(학생 Full prompt 87048d0c에 같은 문구가 없는 ``[이름]``)이 있으면 불통과.
- c2 정리(결정 185): (ii) 줄만 줄 단위로 지우고(``c2_edit.edit_thinking``, 내용 손실 조건 그대로) 지운 뒤 같은 검사를 다시 한다.
  **trace 통과 = c2 정리 뒤 모든 검사 통과**(내용 손실이면 불통과). 원본 검사 결과도 함께 남긴다.
- 학습 레코드(사용은 pilot_010 PLAN에서 정함): ``teacher6v3.to_arm_records``와 같은 형식(``<think>`` c2 뒤 생각 ``</think>`` + 각 arm canonical JSON, 이번 판 Full만),
  손실 범위 ``full_response``(teacher 출처, 결정 86), 지시 이름·sha256만 ``teacher_contrast_v1``.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/teacher", ROOT / "sft_dpo_inventory/pilot_006/post", ROOT / "sft_dpo_inventory/pilot_007/teacher",
          ROOT / "sft_dpo_inventory/pilot_009/build"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import c2_edit as C2  # noqa: E402
import teacher6v2 as V2  # noqa: E402
import teacher6v3 as T3  # noqa: E402
import teacher_checks7 as K7  # noqa: E402
import teacher_filter9 as F9  # noqa: E402

PROMPT = ROOT / "grounding/prompts/teacher_contrast_v1.md"
TAG = "teacher_contrast_v1"
REFUSAL = "지원하지 않음"
#: 가까운 거부 범주 설명(user 메시지에 붙음). gap 이름은 batch011·012 r2(``r2_*``)와 batch013(같은 이름)이 같다.
NEAR = {
    "r2_metric": "없는 지표: 재는 값 목록에 없는 값을 묻는 질문",
    "r2_bucket": "없는 묶음 단위: 기간을 주·월이 아닌 단위(시간·하루·분기·반기·연)로 나누는 질문",
    "r2_entity": "개별 단위: 기사·차량·회사·승객 하나하나를 대상으로 하는 질문",
    "r2_forecast": "예측: 아직 오지 않은 기간의 값을 묻는 질문",
    "r2_mode": "다른 교통수단: 택시가 아닌 교통수단을 묻는 질문",
    "r2_domain": "도메인 밖: 택시 운행 기록 분석이 아닌 질문",
}
#: (a) 기존 목록 + 거부 출력 필드 이름.
REFUSAL_FIELD = re.compile(r"(?<![A-Za-z0-9_])(unsupported)(?![A-Za-z0-9_])", re.I)
#: (c) 이 지시판 목록(실행 전 고정): v3b 목록 + 이 지시의 이름표.
EXPOSURE_C = T3.EXPOSURE + ("[가까운 거부 범주]", "가까운 거부 범주", "거부 범주")


def instruction_text():
    return PROMPT.read_text(encoding="utf-8").strip()


def instruction_sha256():
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()


def forbidden_sections(student_prompt=None):
    """결정 235 규칙: 이 지시의 절 이름 중 학생 Full prompt에 같은 문구가 없는 것."""
    if student_prompt is None:
        from training.trainer_common import expected_system_prompt
        student_prompt = expected_system_prompt("full")
    return F9.rule(student_prompt, {"contrast_v1": PROMPT})["contrast_v1"]["forbidden"]


def user_message(question, semantics, gap=None):
    user = question + "\n\n[결론]\n" + T3.conclusion_lines(semantics)
    return user + ("\n\n[가까운 거부 범주]\n" + NEAR[gap] if gap else "")


def messages(target):
    return [{"role": "system", "content": instruction_text()}, {"role": "user", "content": user_message(target["question"], target["semantics"], target.get("gap"))}]


def check_field_names_c(thinking, content=""):
    base = V2.check_field_names(thinking, content)
    extra = sorted({m.group(1).lower() for m in REFUSAL_FIELD.finditer((thinking or "") + "\n" + (content or ""))})
    found = base["found"] + extra
    return {"pass": not found, "found": found}


def check_exposure_c(thinking, content=""):
    text = (thinking or "") + "\n" + (content or "")
    found = sorted({w for w in EXPOSURE_C if w in text})
    return {"exposed": bool(found), "found": found}


def check_f_prime(content, semantics):
    """(f') 결론 다섯 줄이 canonical과 같고(= (b)) 출력 어디에도 "지원하지 않음"이 없음."""
    b = V2.check_conclusion(content, semantics)
    refusal = REFUSAL in (content or "")
    return {"pass": b["pass"] and not refusal, "conclusion_matches": b["pass"], "refusal_in_output": refusal}


def checks_contrast(thinking, content, semantics, forbidden):
    from itemdata import concl_types
    a = check_field_names_c(thinking, content)
    b = V2.check_conclusion(content, semantics)
    c = check_exposure_c(thinking, content)
    d = K7.check_korean(thinking)
    e = K7.check_english_exposure_meta(thinking)
    ii = "ii" in concl_types(thinking or "")
    f = check_f_prime(content, semantics)
    s = F9.cites(thinking, forbidden)
    reasons = [k for k, ok in (("a", a["pass"]), ("b", b["pass"]), ("c", not c["exposed"]), ("d", d["pass"]), ("e", e["pass"]), ("ii", not ii),
                               ("f'", f["pass"]), ("s235", not s)) if not ok]
    return {"a": a, "b": b["pass"], "c": c, "d": d, "e": e, "ii": ii, "f'": f, "s235": s, "pass": not reasons, "reasons": reasons}


def evaluate(target, thinking, content, forbidden):
    """원본 검사 → c2 정리((ii) 줄만) → 다시 검사. pass = c2 뒤 모두 통과이고 내용 손실 없음."""
    run = lambda th: checks_contrast(th, content, target["semantics"], forbidden)  # noqa: E731
    raw = run(thinking)
    edited, removed, lost = C2.edit_thinking(thinking or "")
    after = run(edited) if removed else raw
    return {"raw": raw, "c2": {"removed_lines": removed, "content_lost": lost, "thinking_sha256_before": C2.sha(thinking or ""),
                               "thinking_sha256_after": C2.sha(edited)},
            "after": after, "pass": after["pass"] and not lost, "thinking_after_c2": edited}


def to_arm_records(trace, semantics, question, record_id):
    """통과 trace → arm 레코드(``teacher6v3.to_arm_records`` 형식, 지시 이름·sha256만 이 지시). 사용은 PLAN에서 정함."""
    recs = V2.V1.to_arm_records(trace, semantics, question, record_id)
    for r in recs.values():
        r["metadata"]["teacher_instruction_sha256"] = instruction_sha256()
        r["metadata"]["teacher_instruction"] = TAG
    return recs


def target_sha256(targets):
    return hashlib.sha256(json.dumps(targets, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
