# 실제 수행 결과

새 GPU 학습 0건, 새 평가 0건. 신규 성능 숫자는 없다. 기존 A/B 및 이미 완료된 H-dev 반복 결과의 재분석, 순서 생성, scheduler와 tokenizer 검증을 수행했다.

| 비교 | 관측 자료 | 결과 | 판정 |
|---|---|---|---|
| Exp. 0: 기존 A/B, 5 paired seeds | CT10K | 전체 88.12→82.19%; B−A −5.93pp [−13.58,+0.57]. Collapse20 10.4→18.6, +8.2 [0.0,+12.8]. T1 77.4→47.3%. | 기존 S1–S4 미지지. 새 분해는 EXPLORATORY |
| Exp. 0: 기존 A/B | TRAIN, exact mask | coarse record TV 9.16→1.21%, loss TV 10.37→9.83%, LR×loss TV 10.70→10.51%. | 측정 확인. 회귀와의 관계는 EXPLORATORY |
| Exp. 1: C/D | CPU, 5 seed 설정씩 | 1,984 step; 동일 LR 합 0.1984. Interaction 성능 없음. | BLOCKED |
| Exp. 2: F0/B/F48 | CPU, 5 seed 순서씩 | fine record TV 54.70/38.45/38.50%; fine loss TV 59.07/44.20/44.19%. | 순서 측정 완료. 성능 BLOCKED |
| Exp. 3: 기존 반복 A/B | H-dev, 3 seed×3 run/arm | pooled SD 전체 2.43pp, T1 22.63pp. 평균 B−A −4.44 [−10.18,+1.83]pp, T1 −18.13 [−55.56,+21.64]pp. | 반복 변동 관측 SUPPORTED, 효과 분리 INCONCLUSIVE |
| Exp. 4: 대체 coverage | 설계·validator | 승인 corpus 미제공. | BLOCKED |

사전등록된 H1/H2에 대한 성능 검정을 시작하지 않았다. [훈련 순서의 기계적 비교](tables/planned_order_exposure.csv), [CT10K/H-dev run 및 오류/latency](tables/evaluation_per_run.csv), [E1 절대 지표](tables/followup_e1_per_run.csv), [E1 기존 대비](tables/followup_analysis.json), [반복군 결과](tables/repeat_summary.csv). 기존과 신규 manifest·설정 provenance는 [감사](DATA_AND_CONFIG_AUDIT.md)에 정리했다.
