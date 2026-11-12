# Follow-up 사전등록 — 2026-11-13 KST

이 계획은 새 GPU 결과가 전혀 없는 시점에 동결한다. 기존 A/B의 S1–S4, 후속 반복 연구의 판정 기준 및 원본은 수정하지 않는다. CT10K와 H-dev는 개발 평가다. H-final은 사용하지 않는다.

- **H1 (LR × ordering):** `(D−C)−(B−A)`. A/B는 선형 원본을 재사용, C/D는 각각 동일한 A/B 순서에서 상수 LR + 동일한 1-step warmup. 1 epoch, batch=accum=1, 1,984 optimizer steps. HF scheduler의 pre-update 값: linear step 1은 0, step 2는 2e-4, step 1984는 2e-4/1983. 합 0.1984. 상수 구간 1,983 step을 동일 합에 맞추는 LR은 `0.1984 / 1983 = 0.0001000504286434695…`. 최대 LR과 후반 LR은 schedule factor의 일부다.
- **H2 (fine weight):** F0=0.00, B=0.24, F48=0.48. F0−B, F48−B를 직접 비교하고 A는 보조 기준. 기존 알고리즘에서 0.00은 fine-deficit 항만 제거한다. fine 후보 구조와 tie-breaking은 그대로다. TRAIN-only labels, 동일한 레코드 집합, 질문 내부의 canonical teacher/trace 순서 및 max consecutive question 4를 모든 semantic 조건에 강제한다. 원본 A/C는 정확한 NumPy permutation을 유지하므로 canonical within-question 순서를 재정렬할 수 없다. A와 B의 차이는 그 차이도 포함하며, H2의 F0/B/F48 대비에서는 이를 통제한다.
- **H3 (재학습):** 최초 o2026131 반복 쌍과 이미 완료된 2 arms × 3 seeds × 3 runs의 H-dev 결과를 분석한다. 이 3 seed는 이전 연구가 사후 선택한 진단 표본이다. seed와 run을 다른 단위로 취급한다. 기존 결과 재사용으로 신규 반복은 0건. 추가 독립 반복은 이번 매트릭스에 포함하지 않는다.
- **H4 (coverage):** V4 vs 승인된 대체 corpus × O4′ vs semantic 0.24. 검증 도구와 승인 요건만 준비한다.

**Primary endpoint:** CT10K semantic_fine `Collapse20`(eligible n≥30, per-run, base 3회 평균보다 strictly >20pp 낮은 그룹 수). Primary contrasts 3개(H1 interaction, F0−B, F48−B)를 한 family로 지정한다. Paired order seed → shared template-cluster weights, 10,000회, NumPy `default_rng(20261108)`. 모두 양측; family-wise 5% Bonferroni, 각 98.333% percentile CI 및 해석 편의를 위한 95% CI. 방향은 사전 가정하지 않는다. 보정 CI가 0을 제외하면 해당 가설이 개발 평가에서 지지된 것으로 표시한다. 유효 contrast가 부족하거나 CI가 0을 포함해 실질 차이를 배제하지 못하면 INCONCLUSIVE. 효과가 0이라는 결론은 내리지 않는다. 유효한 모든 값과 실패를 보존한다.

Secondary: 전체/최저 그룹/bottom decile/Collapse30/T1/T5/seed SD, semantic group별 accuracy와 base-correct→wrong rate, 전체 및 그룹의 base 대비·기존 A 대비 효과. E1 refusal 및 오류 진단과 H-dev(eligible n≥20), truncation·latency는 보조. 반복 H-dev에서는 published run-level hierarchical bootstrap을 그대로 보고하고 raw EMS 성분과 within-cell SD를 별도 계산한다. Secondary CI는 명목 95%, 확인적 판정에는 사용하지 않는다. Eligible 그룹과 base threshold 정의는 동결 A/B 코드와 같다. 새 실험의 다중 비교는 기존 S1–S4와 합치지 않는다.

**순서·중단:** 고정 seed 1102, 211102, 2026113, 2026117, 2026131. 첫 3 seed는 기술적 검증 단계(12개 신규 train). 뒤 2 seed는 성능과 무관하게 동일 절차(8개). Primary는 다섯 seed 모두 유효한 대비에서만 계산한다. 불완전 셀은 완료된 대로 기술하고 사후 seed 선택을 하지 않는다. Train hash·config diff·order·sampler·mask·GPU UUID·타 사용자 프로세스·Ollama 확인에 실패하면 해당 작업은 시작하지 않는다. 신규 작업 시작 마감과 GPU UUID는 이번 실험에 대한 승인에 명시되어야 한다. OOM/NaN은 진단 보존 후 조건 그대로 최대 1회 재실행; 기존 잘림/서버 오류 재실행 규칙과 동일하게 같은 seed로 한 번만 실행하고 원본 보존. Checkpoint는 1,984 step 고정, 품질을 기준으로 재실행이나 checkpoint 교체하지 않는다.

**통제:** V4 1,984 records / 494 questions 그대로. Base Qwen3-8B revision b968826d9c46dd6066d109eabc6255188de91218, HF BF16, LoRA r16/alpha32/dropout .05/7 projections, optimizer adamw_torch, training/data seed 43, max sequence 12,288, thinking ON, by_source, 동일 full prompt 87048d0c…. 평가 모델은 BF16 vLLM/FlashInfer, 기존 harness와 샘플링, CT10K/H-dev k=1 동시 32, E1 k=4 동시 8, seed-base 20261100. 평가 입력은 학습 경로에서 허용하지 않는다.
