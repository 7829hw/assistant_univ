# refusal_dev 초안 — 거부 개발 셋(pilot_008 P3, 결정 219)

작성: 2026-10-22. **승인이 아니다. 개발 셋이다 — 학습에 쓰지 않고, 최종 판정에도 쓰지 않는다.** 쓰임: pilot_008 seed·checkpoint 고르기와 거부 진단.
batch011과 따로 썼다(문장·장소·구조 조합이 다름). 보호 셋·개발 셋·n33 문장을 보지 않음. 장소는 mock gazetteer 이름만. 기준일 2026-09-25.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts_rdev.py` → `candidates_draft.yaml` | Claude 초안 60(거부 30 = 6범주 × 5, 근접 대조 30 = 6묶음 × 5) |
| `../../batch011/build_candidates11.py --set refusal_dev` → `candidates_checked.json`(60), `excluded.json`(0), `excluded_round1.json`(1차 rdev-051: batch011 b011-092와 Jaccard 0.75 → 바꿔 씀) | batch011과 같은 검사 + 대상에 batch011 초안 100 |
| `make_rdev_gold.py` → `rdev_gold.yaml`, `rdev_items_meta.json` | 평가 gold(거부: `gold: []`·`expected_outcome: unsupported`, 대조: 정답 호출) |
| `build_review_rdev.py` → `review/refusal_dev_review_v1.xlsx`, `review/summary.json` | 검토 시트(J-rdev 문항별 신호) |
| `../cells/rdev_{base,o11}_s1–4.json` | J-rdev 셀(base·F-o11 각 k=4, 진단용 초안 셀) |

## 2. 검사

- 거부 30: 질문·Jaccard만(정답 grounding 없음), 거부 target T2PC `unsupported` 30/30. 대조 30: 검증 사슬·Full 경로 답함 30/30, 결정 120 남김. 대상 최대 Jaccard 0.455.

## 3. J-rdev(진단, `../analysis/rdev_report.json`)

| | base | F-o11 | F-o11 − base [95% CI] |
|---|---:|---:|---|
| 거부 문항 올바른 거부 | 25.0%(30/120; 모델 5·프로그램 16·확인 9) | 10.0%(12/120; 모델 0·프로그램 11·확인 1) | −15.0 [−30.0, −0.8] |
| 대조 문항 과잉 거부 | 0.8%(1/120) | 0.0%(0/120) | −0.8 [−2.5, 0.0] |
| 대조 문항 정답 | 67.5% | 62.5% | −5.0 [−19.2, 7.5] |

범주별 올바른 거부(base / F-o11, %): 없는 지표 25 / 20, 없는 묶음 단위 60 / 25, 개인·차량 55 / 0, 예측 0 / 15, 다른 교통수단 0 / 0, 도메인 밖 10 / 0.
