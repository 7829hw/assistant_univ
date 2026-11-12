# Experiment 0 — 기존 A/B 재분석

**EXPLORATORY:** 레코드 노출 균형이 실제 감독 토큰 노출 균형으로 같은 크기만큼 전달되지 않았다. 이 차이가 기능 회귀의 원인인지는 검증되지 않았다.

| 128-step window TV, 5 seed 평균 (%) | A coarse | B coarse | A fine | B fine |
|---|---:|---:|---:|---:|
| Record count | 9.16 | 1.21 | 50.37 | 38.45 |
| All input tokens | 9.13 | 1.37 | 50.54 | 38.66 |
| Loss-masked tokens | 10.37 | 9.83 | 54.60 | 44.20 |
| LR × record count | 9.36 | 1.36 | 50.75 | 39.28 |
| LR × loss-masked tokens | 10.70 | 10.51 | 55.07 | 45.20 |

TV는 각 128-step 비중 분포와 해당 arm·가중치의 전체 epoch 비중 분포 사이의 total variation을 뜻한다. 마지막 64-step 창도 하나의 창으로 포함했다. Fine 그룹은 249개이므로 절대 TV를 coarse와 곧바로 비교하면 안 된다. A는 NumPy로 재구성한 실제 O4′ 순서, B는 원본 파일의 순서다. 원래 B의 동결 수치를 변경하지 않는다.

총 입력 16,047,305 토큰, 실제 supervised labels 908,705개. Pinned Qwen tokenizer → 원래 trainer renderer → TRL preprocessing 및 completion-only collator → causal shift로 계산했다. 10개 원래 학습 로그에서 optimizer step마다 LR 및 입력 토큰 누계가 재구성한 순서와 일치했다. LR × loss token은 위치와 감독량을 합친 기술적 대리 지표다. 샘플별 loss 정규화, gradient 방향·크기, AdamW 상태, clipping을 반영하지 않는다.

CT10K T1(1,020문항): base 91.6%, A 77.4%, B 47.3%. 각 문항에서 세 base 회차의 correctness 평균을 사용하면 seed당 base-correct → SFT-wrong 가중 건수는 A 210.53, B 491.60이고, base-wrong → SFT-correct는 A 66.00, B 39.47이다. 네 전이 셀을 모두 표에 보존했다. 가중 건수는 분수일 수 있다. T1의 silent wrong(answered_mismatch)은 10.3% → 37.5%, unsupported refusal은 11.4% → 13.8%였다. 기존 전체 B−A의 95% CI는 0을 포함한다.

시간·감독량과 성능을 연결할 때 TRAIN의 view-derived 서명과 평가 gold-call 서명이 문자열로 같은 그룹만 사용했다. CT10K에서 eligible fine 95개 중 9개(1,794문항), coarse 10개 중 7개(7,317문항)가 일치했다. 불일치를 실제 training coverage 부재로 해석하지 않는다. N, base 정확도, TRAIN 그룹 크기 및 seed 효과를 제거한 기술적 순위 상관에서 B−A fine 정확도와 평균 gap 변화 +0.12, 최장 미노출 변화 −0.07, 마지막 위치 변화 +0.10, exit fraction 변화 +0.18, LR×loss share 변화 +0.09였다. Coarse의 exit fraction은 −0.28로 fine과 반대다. Loss tokens/record가 적을수록 B가 회귀한다는 방향은 관측되지 않았다(매칭 fine에서 B−base와 −0.52). 이 상관은 작은 매칭 표본, 서명 차이, 같은 그룹의 반복 측정, coarse/fine과 template 간 중첩, 기저 정확도의 한계 및 복수 탐색에 민감하다. p값을 사용해 발견을 선정하지 않았고, seed 하나씩 제외한 범위를 함께 보존했다.

- [그룹별 시간 노출](tables/exposure_by_group.csv): 1-based 위치, 분산, 최초/최종, 실제 step 차이의 히스토그램, 경계 포함 최대 미노출 길이, 유입·유출 전환, decile별 노출.
- [유효 감독](tables/effective_supervision.csv) 및 [step별 LR·loss](tables/exposure_by_step.csv)
- [기능별 전이](tables/group_regression.csv), [seed 간 변동](tables/group_seed_variation.csv), [서명 연결](tables/signature_join.csv), [탐색 상관](tables/exploratory_associations.csv)
- [Coarse 노출 그림](figures/exposure_coarse.svg), [fine 노출 그림](figures/exposure_fine.svg), [T1 seed 그림](figures/ct10k_T1.svg)
