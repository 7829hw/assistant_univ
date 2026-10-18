# -*- coding: utf-8 -*-
"""pilot_007 teacher 검사(결정 166, O2). 기존 (a)(b)(c)(``pilot_006/teacher/teacher6v3``)에 (d)(e)와 A2 (ii)를 더한다. 모델 호출 없음.

- (a) 필드 이름 없음, (b) 다섯 줄 = canonical, (c) 정답 노출 문구(v3b 목록 ``EXPOSURE``) — pilot_006 그대로.
- (d) 한국어: 생각 부분의 한글 비율 ≥ 0.5. 한글 비율 = 한글 음절 수 / (한글 음절 수 + 두 글자 이상 영문 단어의 글자 수)(세션 4 A2·T-v3d와 같은 계산).
  생각이 비어 있으면 통과하지 않는다(teacher trace에는 생각이 있어야 한다).
- (e) 영어 노출·메타: 생각에 ``EXPOSURE_EN``(받은 줄·결론을 영어로 가리킴, 영어 "conclusion" 포함) 또는 ``META_EN``(풀이를 쓰는 과정 자체를 말함) 패턴이 있으면 걸림.
- (ii) "결론과 일치"류: ``pilot_006/post/itemdata.concl_types``의 (ii)(세션 4 A2 규칙 그대로).
- 정리 규칙(O2): (a)–(e) 하나라도 불통과이거나 (ii)가 있으면 trace를 통째로 뺀다(문장 편집 없음).
패턴은 이 파일에서 고정하고 적용 전에 커밋한다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/teacher", ROOT / "sft_dpo_inventory/pilot_006/post"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

HANGUL = re.compile(r"[가-힣]")
LATIN_WORD = re.compile(r"[A-Za-z]{2,}")
KOREAN_MIN = 0.5
#: (e) 영어 노출: 입력에 붙은 줄(결론·다섯 줄)을 영어로 가리키는 말.
EXPOSURE_EN = re.compile(
    r"\bconclusions?\b|five lines|given (lines|answer|judg)|provided (five|lines|answer)|lines (say|provided|given)|"
    r"match(es)? the (given|provided|five|lines|expected)|all match|verify (against|with) the|the \[(결론|다섯 줄)\]|expected (answer|output|lines)",
    re.I)
#: (e) 메타: 생각 안에서 풀이를 쓰는 과정 자체를 말함.
META_EN = re.compile(r"write (the|my) (thinking|reasoning|analysis)|\bin Korean\b|forbidden words|required (format|structure)|"
                     r"(the )?instructions? (say|says|tell)|system prompt", re.I)


def korean_ratio(thinking):
    h = len(HANGUL.findall(thinking or ""))
    e = sum(len(w) for w in LATIN_WORD.findall(thinking or ""))
    return h / (h + e) if h + e else 0.0


def check_korean(thinking):
    r = korean_ratio(thinking)
    return {"pass": bool(thinking) and r >= KOREAN_MIN, "korean_ratio": round(r, 4)}


def check_english_exposure_meta(thinking):
    exp = sorted({m.group(0).lower() for m in EXPOSURE_EN.finditer(thinking or "")})
    meta = sorted({m.group(0).lower() for m in META_EN.finditer(thinking or "")})
    return {"pass": not exp and not meta, "exposure": exp, "meta": meta}


def has_type_ii(thinking):
    from itemdata import concl_types  # 세션 4 A2 규칙
    return "ii" in concl_types(thinking or "")


def check_all(thinking, content, semantics):
    """(a)–(e)와 (ii). keep = 모두 통과이고 (ii) 없음."""
    import teacher6v3 as T3
    a = T3.check_field_names(thinking, content)
    b = T3.check_conclusion(content, semantics)
    c = T3.check_exposure(thinking, content, "v3b")
    d = check_korean(thinking)
    e = check_english_exposure_meta(thinking)
    ii = has_type_ii(thinking)
    reasons = [k for k, ok in (("a", a["pass"]), ("b", b["pass"]), ("c", not c["exposed"]), ("d", d["pass"]), ("e", e["pass"]), ("ii", not ii)) if not ok]
    return {"a": a["pass"], "b": b["pass"], "c": not c["exposed"], "d": d, "e": e, "ii": ii, "keep": not reasons, "reasons": reasons}
