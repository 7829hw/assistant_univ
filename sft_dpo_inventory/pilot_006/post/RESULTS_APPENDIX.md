# pilot_006 RESULTS 부록(결정 160 N2) — RESULTS.md는 고치지 않는다

## A. F-s43 epoch 2 selection_v2(k=4 재계산)

- 원인: F-s43 e2 s1의 한 표본(contrast/c04b)이 concepts에 문자열 `"trip_count"`를 넣은 잘못된 JSON이다. planner는 이를 오류로 거부했고, 분석기
  `evaluate_vendor100._od_view`가 원문을 다시 읽을 때 concepts 값이 모두 dict라고 가정해 멈췄다.
- 고침: `post/robust_scoring.py`(공용 코드는 그대로, `_od_view`를 감싸 dict가 아닌 concept을 건너뜀). 판정 지표(ok·U 등)는 최종 grounding 기준이라 이 패치로 바뀌지 않는다.
- 재스캔(`post/a7_rescan.py` → `a7_rescan.json`): 셀 120개(pilot_006/cells 전부 + pilot_006_prep 비봉인 셀)를 원래 분석기로 읽어 멈추는 셀은 **이 하나뿐**.
- 재계산(k=4): F-s43 e1 82.65 → e2 **75.51**(표본별 75.51 · 73.47 · 78.57 · 74.49), e2 − e1 **−7.14 [−13.78, −1.02]**.
  RESULTS.md의 k=3 값(75.51, −7.14 [−13.52, −0.94])과 평균이 같다(빠졌던 s1 정답률이 나머지 평균과 같았다). epoch 2는 보고 항목이라 판정은 바뀌지 않는다.
