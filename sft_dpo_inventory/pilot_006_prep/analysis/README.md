# W8 분석(CPU만) — 추정이지 판정이 아니다

작성: 2026-10-15(pilot_006 준비 세션 1). `w8_analysis.py` → `power.json`, `latency.json`, `thinking.json`. 모델 호출 없음.
업체 100 문항·결과는 쓰지 않았다(지연 30문항은 selection_v2의 고정 지연 셋 `serving_vllm_fp8/latency_ids.txt`).

## 1. 검정력(`power.json`)

- pilot_005 selection_v2(98, k=4) 후보 7개, 쌍 21개의 정답률 차이 95% CI 반폭(문항 단위 쌍 bootstrap 10,000회, `default_rng(20261109)`):
  - SFT 후보끼리(v1 467·934, v2 934·1401, pilot_004 SFT 934): **3.44–4.85%p**(중앙값 4.34). v1_step467 대 v2_step934 = 4.21%p(D4 근거 4.1–4.3과 같음).
  - DPO(v3) 포함 전체: 3.44–5.10%p.
- 151문항(selection_v2 98 + holdout 53)의 예상 반폭: 해석적 2.81–3.83%p(중앙값 3.52), bootstrap 2.57–4.22%p(중앙값 3.35).
  **가정**: holdout 53문항의 문항별 차이 분산 = selection_v2(지시 W8).
- Gate A(P − F 95% CI 하한 ≥ −5%p) 통과 확률(모의실험 1,000회):

  | 진짜 차이 | n = 98(selection_v2만) | n = 151(주 셋) |
  |---:|---:|---:|
  | 0%p | 0.61 | **0.81** |
  | −1%p | 0.46 | 0.63 |
  | −2%p | 0.27 | 0.44 |

  **가정**: F−P의 문항별 차이 분포 = 같은 recipe의 SFT 후보끼리의 차이 분포(표현이 달라 실제 분산은 더 클 수 있음).
  진짜 차이가 0이어도 151문항에서 약 19%는 "판정 불가"(CI 하한 < −5%p)가 된다. 계획서 v2 11.3: 반폭이 마진보다 크면 불통과는 "열등"이 아니라 "판정 불가"로 보고한다.

## 2. 지연(`latency.json`)

| | base | pilot_005 고른 후보(v1_step467) |
|---|---:|---:|
| 문항 모델 시간 중앙값(순차 30문항) | 16.31초 | 25.55초(비 **1.566**) |
| 생성 token 중앙값 | 827 | 1,215 |
| thinking token 중앙값 / p90 | 626 / 1,101 | **944 / 1,828** |
| 최종 JSON token 중앙값 | 216 | 220 |
| 생성 속도 중앙값 | 50.7 tok/s | 47.6 tok/s |

- 지연 증가는 거의 모두 thinking에서 왔다(최종 JSON은 그대로).
- 같은 30문항 gold를 canonical → Full·Partial로 렌더링: 최종 JSON token 중앙값 157 → 69(문항당 중앙값 −87, 평균 −54.4%).
- **추정**(thinking 길이는 그대로라고 가정):
  - 추정 1(gold 렌더링 차이를 그대로 뺌): 지연 비 1.566 → **1.44**.
  - 추정 2(고른 후보의 실제 최종 JSON을 Partial로 바꿀 때의 감소 비율 적용, 문항당 중앙값 −107 token): **1.42**.
  - 1.5가 되려면 고른 후보 쪽에서 문항당 중앙값 약 1.08초, 즉 약 **51 token**(47.6 tok/s)이 줄어야 한다.
- 그러므로 "Partial만으로 1.567 → 1.5 이하"는 thinking이 Full arm만큼만 늘어날 때 가능하다는 추정이다. Partial arm의 thinking이 51 token 넘게 더 길어지면
  효과가 사라진다. Partial P0.3 입력은 1,459 token 길어 prefill이 늘 수 있다(순차 측정에서는 prefix cache로 대부분 재사용, 따로 재야 함).

## 3. thinking 길이(`thinking.json`)

| | thinking token p50 | p90 | 평균 |
|---|---:|---:|---:|
| pilot_004 데이터: teacher(`full_response`, 233) | 706 | 1,208 | 754 |
| pilot_004 데이터: 8b 자체(`json_only`, 234) | 698 | 1,382 | 849 |
| selection_v2 vLLM-base(호출 466) | 557 | 1,313 | 702 |
| v1_step467 | 748 | 1,531 | 861 |
| v1_step934 | 710 | 1,518 | 835 |
| v2_step934 | 717 | 1,421 | 818 |
| v2_step1401 | 738 | 1,535 | 868 |
| v3_step97(DPO 50%) | 853 | 1,677 | 973 |
| v3_step193(DPO 100%) | 945 | 1,953 | 1,076 |
| pilot_004 SFT 934 | 746 | 1,400 | 842 |

- SFT 후보의 thinking 중앙값은 base보다 150–190 token 길다(+28–34%). 학습 데이터의 thinking 중앙값(teacher 706, 8b 자체 698)이 base 출력(557)보다 길어서
  그 길이를 배운 것과 맞는다. teacher thinking만 손실에 들어가는데(결정 86), teacher 중앙값은 8b 자체와 거의 같고 p90은 더 짧다.
  따라서 "teacher thinking 학습이 thinking을 특히 길게 만든다"는 근거는 이 자료에서 약하다. 학습 데이터 전체의 thinking이 base보다 길다는 점이 더 직접적이다.
- DPO(v3)는 thinking을 더 늘린다(193 step에서 중앙값 945, p90 1,953).
- 다음 판 감시(결정 107): Partial arm thinking p90이 base 대비 30% 넘게 줄면 보고. base p90은 1,313(selection_v2), 1,101(지연 30문항).
