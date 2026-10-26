# -*- coding: utf-8 -*-
"""pilot_009 teacher 거부 추론(결정 228 Y2). 기존 teacher 모듈(``pilot_006/teacher/teacher6v3``, ``pilot_007/teacher/teacher_checks7``·``c2_edit``)은 고치지 않고 가져다 쓴다. 모델 호출 없음.

- 거부 지시: ``grounding/prompts/teacher_refusal_v1.md``(v3b 바탕, 실행 전 커밋, 뒤로 고치지 않음).
  user = 질문 + "\\n\\n[결론]\\n지원하지 않음\\n\\n[이유 범주]\\n" + 범주 설명(``REASONS``, batch011·batch012 r1 gap).
- r2(근접 대조) 질문은 기존 v3b 지시 그대로(``teacher6v3.messages("v3b", …)``).
- 검사(실행 전 고정):
  - 거부: (a) 필드 이름(``teacher6v2`` 목록 + 거부 출력 필드 ``unsupported``), (c) 노출(v3b ``EXPOSURE`` + ``[이유 범주]``·``이유 범주``),
    (d) 한국어·(e) 영어 노출·메타(``teacher_checks7``), (ii) "결론과 일치"류(``itemdata.concl_types``), (f) 출력의 결론 줄이 모두 "지원하지 않음"(하나 이상).
    (b)(다섯 줄 = canonical)는 거부에 다섯 줄이 없어 (f)가 대신한다.
  - r2(v3b): ``teacher_checks7.check_all``((a)–(e)·(ii)) 그대로.
- c2 정리(결정 185): (ii) 줄만 줄 단위로 지우고(``c2_edit.edit_thinking``, 내용 손실 조건 그대로) 지운 뒤 같은 검사를 다시 한다.
  **trace 통과 = c2 정리 뒤 모든 검사 통과**(내용 손실이면 불통과). 원본 검사 결과도 함께 남긴다.
- 학습 레코드 형식(사용은 pilot_009 PLAN에서 정함): ``<think>\\n{c2 뒤 thinking}\\n</think>\\n\\n{"unsupported": true}``, 손실 범위 ``full_response``(teacher 출처, 결정 86).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/teacher", ROOT / "sft_dpo_inventory/pilot_006/post", ROOT / "sft_dpo_inventory/pilot_007/teacher"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import c2_edit as C2  # noqa: E402
import teacher6v2 as V2  # noqa: E402
import teacher6v3 as T3  # noqa: E402
import teacher_checks7 as K7  # noqa: E402

PROMPT = ROOT / "grounding/prompts/teacher_refusal_v1.md"
CONCLUSION = "지원하지 않음"
TARGET_JSON = '{"unsupported": true}'
#: 이유 범주 설명(user 메시지에 붙음). r1 gap 이름은 batch011·batch012 공통.
REASONS = {
    "r1_metric": "없는 지표: 묻는 값이 재는 값 목록에 없음",
    "r1_bucket": "없는 묶음 단위: 기간을 주·월이 아닌 단위로 나눔",
    "r1_entity": "개별 단위: 기사·차량·회사·승객 하나하나를 대상으로 함",
    "r1_forecast": "예측: 아직 오지 않은 기간의 값",
    "r1_mode": "다른 교통수단: 택시가 아닌 교통수단",
    "r1_domain": "도메인 밖: 택시 운행 기록 분석이 아님",
}
#: (a) 거부판: 기존 목록 + 거부 출력 필드 이름.
REFUSAL_FIELD = re.compile(r"(?<![A-Za-z0-9_])(unsupported)(?![A-Za-z0-9_])", re.I)
#: (c) 거부판 목록(실행 전 고정): v3b 목록 + 이 지시의 이름표.
EXPOSURE_R = T3.EXPOSURE + ("[이유 범주]", "이유 범주")
CONCL_LINE = re.compile(r"^\s*[-*]?\s*\**\s*결론\s*\**\s*[:：]\s*(.+?)\s*$")


def instruction_text():
    return PROMPT.read_text(encoding="utf-8").strip()


def instruction_sha256():
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()


def messages_refusal(question, gap):
    user = question + "\n\n[결론]\n" + CONCLUSION + "\n\n[이유 범주]\n" + REASONS[gap]
    return [{"role": "system", "content": instruction_text()}, {"role": "user", "content": user}]


def messages(target):
    if target["variant"] == "refusal_v1":
        return messages_refusal(target["question"], target["gap"])
    return T3.messages("v3b", target["question"], target["semantics"])


def check_field_names_r(thinking, content=""):
    base = V2.check_field_names(thinking, content)
    extra = sorted({m.group(1).lower() for m in REFUSAL_FIELD.finditer((thinking or "") + "\n" + (content or ""))})
    found = base["found"] + extra
    return {"pass": not found, "found": found}


def check_exposure_r(thinking, content=""):
    text = (thinking or "") + "\n" + (content or "")
    found = sorted({w for w in EXPOSURE_R if w in text})
    return {"exposed": bool(found), "found": found}


def check_conclusion_line(content):
    """(f) 출력의 결론 줄이 하나 이상이고 모두 "지원하지 않음"."""
    vals = [m.group(1).strip().strip("*").strip() for m in (CONCL_LINE.match(l) for l in (content or "").splitlines()) if m]
    return {"pass": bool(vals) and all(v == CONCLUSION for v in vals), "values": vals}


def checks_refusal(thinking, content):
    from itemdata import concl_types
    a = check_field_names_r(thinking, content)
    c = check_exposure_r(thinking, content)
    d = K7.check_korean(thinking)
    e = K7.check_english_exposure_meta(thinking)
    ii = "ii" in concl_types(thinking or "")
    f = check_conclusion_line(content)
    reasons = [k for k, ok in (("a", a["pass"]), ("c", not c["exposed"]), ("d", d["pass"]), ("e", e["pass"]), ("ii", not ii), ("f", f["pass"])) if not ok]
    return {"a": a, "c": c, "d": d, "e": e, "ii": ii, "f": f, "pass": not reasons, "reasons": reasons}


def checks_v3b(thinking, content, semantics):
    r = K7.check_all(thinking, content, semantics)
    return {**r, "pass": r["keep"]}


def evaluate(target, thinking, content):
    """원본 검사 → c2 정리((ii) 줄만) → 다시 검사. pass = c2 뒤 모두 통과이고 내용 손실 없음."""
    run = (lambda th: checks_refusal(th, content)) if target["variant"] == "refusal_v1" else (lambda th: checks_v3b(th, content, target["semantics"]))
    raw = run(thinking)
    edited, removed, lost = C2.edit_thinking(thinking or "")
    after = run(edited) if removed else raw
    return {"raw": raw, "c2": {"removed_lines": removed, "content_lost": lost, "thinking_sha256_before": C2.sha(thinking or ""),
                               "thinking_sha256_after": C2.sha(edited)},
            "after": after, "pass": after["pass"] and not lost, "thinking_after_c2": edited}


def to_record_content(thinking_after_c2):
    """거부 trace → 학습 레코드 assistant content(사용은 PLAN에서 정함)."""
    return "<think>\n" + thinking_after_c2.strip() + "\n</think>\n\n" + TARGET_JSON


def target_sha256(targets):
    return hashlib.sha256(json.dumps(targets, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
