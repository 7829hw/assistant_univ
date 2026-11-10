# 재학습 재현성 결과 (H-dev 2,000문항, k=1, 18 모델 = 2 arm × 3 order seed × 3 run)

18개 = 기존 8개(r1 6 + o2026131 r2 2) 재사용 + 신규 10개. 모든 수치는 `analysis/variance_results.json`, `tables/variance_per_model.csv`. 순서 seed 3개는 결과를 본 뒤 고른 진단 표본이며 무작위 표본이 아니다. H-dev만 사용(CT10K 재평가 없음, H-final 봉인).

## 모델별 전체 정확도 (%)
| arm | seed | r1 | r2 | r3 | 평균 | SD |
|---|---|---|---|---|---|---|
| A | o1102 | 91.95 | 88.45 | 90.75 | 90.38 | 1.78 |
| A | o211102 | 88.40 | 84.80 | 83.75 | 85.65 | 2.44 |
| A | o2026131 | 78.60 | 76.80 | 78.95 | 78.12 | 1.15 |
| B | o1102 | 76.90 | 84.10 | 83.55 | 81.52 | 4.01 |
| B | o211102 | 77.60 | 80.85 | 79.95 | 79.47 | 1.68 |
| B | o2026131 | 82.70 | 78.45 | 78.35 | 79.83 | 2.50 |

T1(요금) 정확도 (%): A-o1102 77.2/32.8/87.1, A-o211102 94.7/81.9/66.1, A-o2026131 50.9/27.5/29.2; B-o1102 19.3/81.9/33.9, B-o211102 9.9/45.6/26.9, B-o2026131 76.6/33.3/56.7.

## 핵심 수치
- 같은 데이터·순서·설정 재학습의 풀링 SD: 전체 **2.43pp**, T1 **22.63pp**, T5 3.44pp, worst-group 11.79pp, collapse20 1.45개, refusal 0.84pp, silent-wrong 1.98pp, tool-failure 1.28pp, truncation 0.48pp.
- T1 SD는 전체 SD의 **9.3배**.
- 같은 arm·같은 seed 재학습 쌍(18쌍)의 문항 불일치: 전체 13.96%, T1 37.1%, T5 19.8%. 같은 seed 다른 arm(27쌍) 18.4%/50.8%/24.3%; 같은 arm 다른 seed(54쌍) 17.6%/44.4%/24.8%. 재학습만으로도 arm·seed가 바뀐 경우 불일치의 대부분(전체 76%, T1 73%)이 이미 나타난다.
- arm 평균(9 run): 전체 A 84.72 / B 80.27(B−A −4.44); worst-group 30.3 / 16.2; collapse20 4.3 / 7.6; refusal 1.7 / 4.2; silent-wrong 5.0 / 6.8; tool-failure 8.6 / 8.6; truncation 0.6 / 1.2.
- 기존 r1 단일 run의 seed별 B−A(전체)는 −15.05, −10.8, +4.1이었으나 3 run 평균으로는 −8.87, −6.18, +1.72로 줄어든다(r1이 B에 불리한 쪽으로 뽑힌 seed 2개: 신규 run에서 B-o1102는 76.9→84.1/83.55). 단일 run 효과는 재학습 잡음을 상당히 포함한다.
- 잘림: B 셀이 A보다 큰 값(평균 1.21% vs 0.60%). 4건 자동 재평가 후 수치(원본은 `cells/replaced/`).

## 그림
`figures/fig1_retrain_overall.svg`, `fig1b_retrain_T1.svg`, `fig1c_retrain_T5.svg`(재학습 분포), `fig2_AB_mean_uncertainty.svg`, `fig3_T1_T5_variance.svg`, `fig4_arm_effect_per_seed.svg`, `fig5_T1_neighbour_position.svg`, `fig6_lr_weighted_exposure.svg`, `fig7_T1_error_types.svg`, `fig8_noise_vs_order.svg`. (fig5·fig6은 Stage 1의 학습 순서 통계이며 정확도가 아니다.)
