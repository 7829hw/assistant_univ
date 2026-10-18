# -*- coding: utf-8 -*-
"""A7(결정 160 N2): 분석기 견고성 패치. ``evaluate_vendor100._od_view``가 concepts 안의 값이 모두 dict라고 가정해, 모델이 낸 잘못된 JSON
(예: concepts에 문자열 ``"trip_count"``)의 원문을 다시 읽을 때 ``AttributeError``로 멈춘다. 공용 코드는 고치지 않고, 이 모듈의 ``patch()``가
``_od_view``를 감싸 dict가 아닌 concept을 건너뛴다(그 원문은 어차피 planner가 거부한 출력이라 판정 값은 바뀌지 않는다: ok·U 등은 최종 grounding 기준).

    import robust_scoring; robust_scoring.patch()   # compute_gates.load_arm 등을 부르기 전에
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
_PATCHED = False


def patch():
    global _PATCHED
    if _PATCHED:
        return
    import evaluate_vendor100 as EV
    orig = EV._od_view

    def safe(payload, trip=True):
        if isinstance(payload, dict) and isinstance(payload.get("concepts"), list):
            if any(not isinstance(c, dict) for c in payload["concepts"]):
                payload = {**payload, "concepts": [c for c in payload["concepts"] if isinstance(c, dict)]}
        return orig(payload, trip)
    EV._od_view = safe
    _PATCHED = True
