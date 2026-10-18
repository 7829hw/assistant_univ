# -*- coding: utf-8 -*-
"""teacher v3d(세션 4 A2, 결정 164 T-v3d). pilot_006 teacher 모듈(``teacher6v3``)은 고치지 않고 가져다 쓴다.

- 지시: ``grounding/prompts/teacher_neutral_v3d.md``(smoke 전에 커밋, 뒤로 고치지 않음).
- user = 질문 + "\\n\\n[다섯 줄]\\n" + canonical 다섯 줄(``teacher6v3.conclusion_lines``; v3b·v3c의 "[결론]" 이름표만 바꿈).
- 검사: (a) ``teacher6v3.check_field_names``, (b) ``teacher6v3.check_conclusion``(v3c와 같다),
  (c) ``EXPOSURE_V3D`` = ``EXPOSURE_V3C`` + 새 이름표·받은 판단을 가리키는 말(실행 전 고정). pass = (a) ∧ (b) ∧ ¬(c).
- A2 유형: ``itemdata.concl_types``(i·ii·iii·iv)를 thinking에 적용해 따로 센다(pass와 별개).
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
sys.path.insert(0, str(HERE.parent))
import teacher6v3 as T3  # noqa: E402

PROMPT = ROOT / "grounding/prompts/teacher_neutral_v3d.md"
LABEL = "[다섯 줄]"
#: (c) 목록(실행 전 고정): v3c 목록 + v3d 이름표와 받은 판단을 가리키는 말.
EXPOSURE_V3D = T3.EXPOSURE_V3C + (LABEL, "다섯 줄과", "다섯 줄에", "다섯 줄을 보", "받은 판단", "주어진 줄", "받은 줄", "일치", "맞는지 확인")


def instruction_text():
    return PROMPT.read_text(encoding="utf-8").strip()


def instruction_sha256():
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()


def messages(question, semantics):
    return [{"role": "system", "content": instruction_text()}, {"role": "user", "content": question + "\n\n" + LABEL + "\n" + T3.conclusion_lines(semantics)}]


def check_exposure(thinking, content=""):
    text = (thinking or "") + "\n" + (content or "")
    found = sorted({w for w in EXPOSURE_V3D if w in text})
    return {"exposed": bool(found), "found": found}


check_field_names = T3.check_field_names
check_conclusion = T3.check_conclusion


def a2_types(thinking):
    from itemdata import concl_types
    return sorted(concl_types(thinking))
