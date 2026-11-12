# 통계 분석

원 실험의 5 paired seeds × template-cluster bootstrap 결과를 변경하지 않는다. CT10K fine group의 eligibility n≥30, H-dev n≥20. Base는 CT10K 3회와 H-dev 2회 correctness 평균. Collapse는 base 대비 **엄격히** 20/30pp 초과 하락이다. Worst는 seed별 최저 그룹을 먼저 구하고, bottom decile은 seed별 최하위 ceil(0.1×G) 그룹 평균을 사용한다.

| 원래 CT10K fine 지표 | A | B | B−A | 원래 95% CI |
|---|---:|---:|---:|---:|
| Overall, % | 88.12 | 82.19 | −5.93pp | [−13.58, +0.57]pp |
| Worst-group, % | 20.57 | 13.47 | −7.09pp | [−29.05, +9.17]pp |
| Bottom decile, % | 45.16 | 29.57 | −15.60pp | [−42.15, +9.09]pp |
| Collapse20, count | 10.4 | 18.6 | +8.2 | [0.0, +12.8] |
| Collapse30, count | 8.4 | 13.4 | +5.0 | [−2.2, +11.6] |
| Overall across-seed SD, pp | 4.67 | 5.70 | +1.03pp | [−3.47, +5.38]pp |

최초 동일 seed 반복 pair: H-dev ΔA=−1.80pp, ΔB=−4.25pp; correctness discordance 각각 9.10%와 16.65%(원본 정밀값은 [JSON](tables/original_repeat_pair.json)). 같은 seed에서 B−A는 +4.10pp에서 +1.65pp로 바뀌었다. 서로 다른 예측 표현 전체의 불일치가 아니라 정답 여부의 불일치다. 별도로 scoring category와 exact action signature(outcome, error code, ordered tool names and arguments)의 불일치도 [표](tables/repeat_discordance.csv)에 있다. 18개 반복 쌍의 exact action signature 불일치는 전체 17.91%, T1 46.98%, T5 26.78%였다. 인수의 문자·수치 차이도 세므로 의미적 비동치의 판정으로 사용하지 않는다.

병합된 기존 반복 결과(사후 고른 3개 order seed; 각 seed×arm에 독립 학습 3개)의 within-cell pooled SD는 H-dev 전체 2.43pp, T1 22.63pp, T5 3.44pp. 18 same-arm/same-seed pair의 correctness discordance는 13.96% / 37.10% / 19.84%. 반복평균 B−A와 기존 run-level hierarchical 95% CI: 전체 −4.44 [−10.18,+1.83]pp, T1 −18.13 [−55.56,+21.64]pp, T5 −1.48 [−14.17,+10.87]pp. 이 CI는 order seed → within-arm training run → template cluster를 공동 재표집했다. 같은 순서를 반복해도 결과가 달라지지만, 효과가 전부 재학습 변동에서 비롯되었다는 뜻은 아니다. 재학습과 별도 평가 세션 변동은 완전히 분리되지 않았다.

[반복 집계](tables/repeat_summary.csv)에는 balanced ANOVA의 raw variance components가 있다(arm 고정, order seed와 arm×seed 임의, arm×seed 내 run 잔차). within-cell df=12, seed/arm×seed는 각각 df=2. T1의 음수 seed component는 검정력 부족 및 경계 불안정으로 해석한다. 세 seed 밖 모집단의 재학습 분산 또는 다른 모델에서의 noise floor는 추정하지 않는다. CT10K에 반복 학습 평가가 없어 CT10K 분산 성분은 분리할 수 없다.

신규 대비는 동결 계획의 3개 primary contrast와 98.333% family CI를 사용한다. `analyze_new.py`는 조건·seed별 유효 셀 확인 후에만 5-seed 대비를 산출한다. 점추정은 run 지표의 paired 평균, CI는 seed 및 공유 template clusters의 10,000회 bootstrap이다. Bootstrap에서 해당 그룹의 문항이 빠진 경우 per-group CI에 그 replicate를 포함하지 않고 유효 횟수를 기록한다. Overall 및 worst와 group-specific base-correct→wrong rate는 secondary다. 기존 A/B-only 재계산은 도구 검증용이며 기존 동결 CI를 대체하지 않는다.

### 평가 장치가 다른 경우

5문항 probe에서 GPU 간 응답 바이트가 달랐다. 같은 seed의 신규 조건을 한 GPU에 고정했고, 기존 A/B는 그 GPU에서 평가한 셀을 재사용한다. 일치하지 않는 셀은 원래 A/B adapter를 사용해 다시 평가한다. 같은 GPU를 사용한 A/B와 신규 결과에 동결된 통계 절차를 적용하고, 원래 A/B를 사용한 분석을 민감도 결과로 보존한다. Base collapse threshold, seed, endpoint 및 bootstrap 방식은 사전등록과 같다. Probe는 별도 serving session을 사용했으므로 하드웨어 차이와 serving 비결정성을 분리하지 못한다.
