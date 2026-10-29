# -*- coding: utf-8 -*-
"""pilot_010 근접 대조 teacher 추론 2판(결정 248 AB2). ``teacher_contrast10``(v1, 그대로)의 함수를 가져다 쓰고 지시·user 메시지·검사 (c) 목록만 바꾼다. 모델 호출 없음.

- 지시: ``grounding/prompts/teacher_contrast_v2.md``(실행 전 커밋, 뒤로 고치지 않음). v1과 다른 점: user 메시지에 이름표("가까운 거부 범주" 등)가 없고
  (질문 + "\\n\\n[결론]\\n" + canonical 다섯 줄만), 비슷한 거부 질문과의 차이는 이름표 없이 한 줄로 묻고, 출력은 결론 다섯 줄만.
- 검사(실행 전 고정): v1과 같다((a)·(b)·(d)·(e)·(ii)·(f')·결정 235 거르기). (c)만 넓힌다: v3b ``EXPOSURE`` + v1 이름표 + 이름표 변형 ``LABELS_V2``.
- c2 정리·trace 통과·학습 레코드 형식은 v1과 같다(지시 이름·sha256만 ``teacher_contrast_v2``).
"""
import hashlib
from pathlib import Path

import teacher_contrast10 as T1

V2 = T1.V2
T3 = T1.T3
K7 = T1.K7
F9 = T1.F9
C2 = T1.C2
ROOT = T1.ROOT
PROMPT = ROOT / "grounding/prompts/teacher_contrast_v2.md"
TAG = "teacher_contrast_v2"
REFUSAL = T1.REFUSAL
#: (c) 넓힌 목록(결정 248, 실행 전 고정): v1 이름표 + T-C에서 본 변형("가까운 거부:", "거부 범주와 견주어", "… 범주:")과 같은 계열.
LABELS_V2 = ("가까운 거부", "거부 범주", "범주:", "범주 :", "근접 대조", "대조 범주", "거부 질문 범주", "답할 수 없는 범주")
EXPOSURE_C2 = T1.EXPOSURE_C + LABELS_V2


def instruction_text():
    return PROMPT.read_text(encoding="utf-8").strip()


def instruction_sha256():
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()


def forbidden_sections(student_prompt=None):
    """결정 235 규칙: 이 지시의 절 이름 중 학생 Full prompt에 같은 문구가 없는 것."""
    if student_prompt is None:
        from training.trainer_common import expected_system_prompt
        student_prompt = expected_system_prompt("full")
    return F9.rule(student_prompt, {"contrast_v2": PROMPT})["contrast_v2"]["forbidden"]


def user_message(question, semantics):
    return question + "\n\n[결론]\n" + T3.conclusion_lines(semantics)


def messages(target):
    return [{"role": "system", "content": instruction_text()}, {"role": "user", "content": user_message(target["question"], target["semantics"])}]


def check_exposure_c2(thinking, content=""):
    text = (thinking or "") + "\n" + (content or "")
    found = sorted({w for w in EXPOSURE_C2 if w in text})
    return {"exposed": bool(found), "found": found}


def checks_contrast(thinking, content, semantics, forbidden):
    from itemdata import concl_types
    a = T1.check_field_names_c(thinking, content)
    b = V2.check_conclusion(content, semantics)
    c = check_exposure_c2(thinking, content)
    d = K7.check_korean(thinking)
    e = K7.check_english_exposure_meta(thinking)
    ii = "ii" in concl_types(thinking or "")
    f = T1.check_f_prime(content, semantics)
    s = F9.cites(thinking, forbidden)
    reasons = [k for k, ok in (("a", a["pass"]), ("b", b["pass"]), ("c", not c["exposed"]), ("d", d["pass"]), ("e", e["pass"]), ("ii", not ii),
                               ("f'", f["pass"]), ("s235", not s)) if not ok]
    return {"a": a, "b": b["pass"], "c": c, "d": d, "e": e, "ii": ii, "f'": f, "s235": s, "pass": not reasons, "reasons": reasons}


def evaluate(target, thinking, content, forbidden):
    """원본 검사 → c2 정리((ii) 줄만) → 다시 검사. pass = c2 뒤 모두 통과이고 내용 손실 없음(v1과 같은 규칙)."""
    run = lambda th: checks_contrast(th, content, target["semantics"], forbidden)  # noqa: E731
    raw = run(thinking)
    edited, removed, lost = C2.edit_thinking(thinking or "")
    after = run(edited) if removed else raw
    return {"raw": raw, "c2": {"removed_lines": removed, "content_lost": lost, "thinking_sha256_before": C2.sha(thinking or ""),
                               "thinking_sha256_after": C2.sha(edited)},
            "after": after, "pass": after["pass"] and not lost, "thinking_after_c2": edited}


def to_arm_records(trace, semantics, question, record_id):
    """통과 trace → arm 레코드(``teacher6v3.to_arm_records`` 형식, 지시 이름·sha256만 이 지시)."""
    recs = V2.V1.to_arm_records(trace, semantics, question, record_id)
    for r in recs.values():
        r["metadata"]["teacher_instruction_sha256"] = instruction_sha256()
        r["metadata"]["teacher_instruction"] = TAG
    return recs


target_sha256 = T1.target_sha256
