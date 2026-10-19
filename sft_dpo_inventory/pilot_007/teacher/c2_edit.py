# -*- coding: utf-8 -*-
"""c2 teacher 편집(결정 185 Q1): RC3(정리 전) teacher trace의 thinking에서 (ii) "받은·주어진 결론과 일치"류 문장을 **줄 단위로** 지운다. 모델 호출 없음.

규칙(세션 4 ``pilot_006/post/a2_cleaning.py`` C4 "strip-ii" 그대로):
- thinking을 줄로 나눠 ``itemdata.TYPE_II``에 걸리는 줄만 지운다. 다른 줄은 바이트 그대로(줄 끝 문자 포함) 둔다.
- 내용 손실 조건(C4와 같음): 지운 줄이 4줄 이상이거나, 지운 줄에 다섯 판단 줄(측정/끝/묶음/집계/주변 + 값)이 들어 있으면 손실로 보고 trace를 뺀다.
- 지운 뒤 다시 검사: (ii)(``itemdata.concl_types``)가 남거나 (a)(b)(c)(pilot_006 ``teacher6v3``, v3b 목록)에 걸리면 뺀다. 그 밖은 지운 채 남긴다.
- 영어 생각 trace는 그대로 둔다((d)(e) 검사는 적용하지 않음 — RC3와 같음).
- trace마다 기록: 지운 줄, 편집 전후 thinking sha256.
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/teacher", ROOT / "sft_dpo_inventory/pilot_006/post"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

FIELD = re.compile(r"(측정|끝|묶음|집계|주변)\s*[:：]\s*\S")  # a2_cleaning.py와 같음


def type_ii_line(line):
    from itemdata import TYPE_II
    return bool(TYPE_II.search(line))


def edit_thinking(thinking):
    """→ (새 thinking, 지운 줄 목록, 내용 손실 여부). 줄 끝(\\n)을 유지하며 지운 줄만 뺀다."""
    lines = thinking.splitlines(keepends=True)
    keep, gone = [], []
    for ln in lines:
        (gone if type_ii_line(ln) else keep).append(ln)
    lost = len(gone) >= 4 or any(FIELD.search(g) for g in gone)
    return "".join(keep), [g.rstrip("\n") for g in gone], lost


def split_record(content):
    """teacher 레코드 content = '<think>\\n' + thinking + '\\n</think>\\n\\n' + JSON 형식에서 thinking 부분과 앞뒤를 나눈다."""
    i, j = content.index("<think>") + len("<think>"), content.index("</think>")
    return content[:i], content[i:j], content[j:]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_after(thinking, content_lines, semantics):
    """편집 뒤 검사: (a)(b)(c)(v3b)와 (ii). content_lines = teacher 원 출력의 다섯 줄(b 검사용)."""
    import teacher6v3 as T3
    from itemdata import concl_types
    a = T3.check_field_names(thinking, content_lines)["pass"]
    b = T3.check_conclusion(content_lines, semantics)["pass"]
    c = not T3.check_exposure(thinking, content_lines, "v3b")["exposed"]
    ii = "ii" in concl_types(thinking)
    reasons = [k for k, ok in (("a", a), ("b", b), ("c", c), ("ii_remains", not ii)) if not ok]
    return {"a": a, "b": b, "c": c, "ii_remains": ii, "pass": not reasons, "reasons": reasons}
