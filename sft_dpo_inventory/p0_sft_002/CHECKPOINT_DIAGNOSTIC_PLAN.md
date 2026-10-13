# p0_sft_001 intermediate checkpoint 진단 계획

고정: 2026-10-13, 모델 호출 전. 새 학습 없음. `p0_sft_001` 결과·REPORT는 고치지 않는다.

## 1. 목적과 성격

- **사후(post-hoc) 진단이다. checkpoint selection이 아니다.** 평가셋 결과를 이미 본 뒤 하는 분석이다.
  - 중간 checkpoint가 더 좋아 보여도 그 checkpoint를 최종 모델로 고르지 않는다.
- 목적은 세 가지뿐이다.
  1. learning trajectory 이해
  2. thinking collapse 시점 확인
  3. overfitting 여부 확인
- 결과는 다음 실험(R70, 이후 full-data SFT)의 epoch·설계 근거로만 쓴다.

## 2. diagnostic panel(`build_panel.py` → `diagnostic_panel.json`, `diagnostic_panel_gold.yaml`)

- 모집단: p0_sft_001 평가 403문항(sel154, valid98, vendor100, aux_test_v1).
- gold metadata만 쓴다. 모델의 정답·오답은 쓰지 않았다.
- 주 stratum(우선순위 첫 해당): scope_reverse > refusal > od_ne_dt > dimension_target > bucket > ordinary. 정의는 p0_sft_001 analyze와 같다.
- stratum 안에서 `sha256("p0_sft_002:panel:" + key)` 오름차순으로 정렬해 앞에서 QUOTA만큼 고른다.

| stratum | 모집단 | QUOTA |
|---|---:|---:|
| scope_reverse | 9 | 6 |
| refusal | 20 | 8 |
| od_ne_dt | 35 | 10 |
| dimension_target(od_ne_dt 아님) | 54 | 10 |
| bucket(위 어디에도 없음) | 36 | 10 |
| ordinary | 249 | 12 |
| 합 | 403 | **56** |

- 셋 구성: sel154 25, vendor100 13, valid98 12, aux_test_v1 6.
- panel gold는 원 gold 항목을 그대로 복사하고 id만 `set:id`로 바꿨다. sha256 `bf35b82c…`.
  - 등가성 확인: p0_sft_001 Base 결과를 panel gold로 다시 채점하면 category·grounding_ok가 56/56 같다.
  - 분석 스크립트 점검 중 Base의 panel 집계(56문항 중 38 정답, thinking 56/56)가 출력됐다. panel 확정 뒤였고 panel·계획에 반영하지 않았다.

## 3. 실행(`run_checkpoint_diag.sh`)

- 대상: Gold-only·Clean-Hybrid의 checkpoint-77, checkpoint-154, checkpoint-231, checkpoint-308(8 run × 56문항).
- 순서: gold_only 77 → 154 → 231 → 308 → clean_hybrid 같은 순서.
- 조건: p0_sft_001과 같다(`p0_sft_001/eval_p0_hf.py` 그대로).
  - P0 prompt `d7f4c12a`, HF greedy, `enable_thinking=True`, max_new_tokens 8192
  - 조건 계층 켬, mock·legacy, 기준일 2026-09-25
- Base는 다시 재지 않는다. p0_sft_001 Base 결과의 panel 문항을 쓴다(같은 조건).
- checkpoint-308은 p0_sft_001 최종 adapter와 같다(adapter sha256 같음). 다시 재서 문항별 category 재현을 확인한다(greedy).
- cell마다 `cell_guard precheck --path hf`를 한다. Ollama는 부르지 않는다.

## 4. 측정(`analyze_checkpoints.py`, 결과 전 고정)

- `<think>` emission: 문항 첫 호출 원문에 `<think>`가 있는 비율
- 첫 assistant token 꼴: `<think>` / `{` / 기타
- thinking_chars 중앙값, 생성 token 중앙값, 생성 상한 도달 수
- semantic correctness, grounding failure, first-response structural error, malformed JSON(첫 응답)
- stratum별 정답 수(특히 bucket·dimension_target·od_ne_dt)
- 그 checkpoint까지 마지막 77 step의 평균 train loss

## 5. 해석 규칙(결과 전 고정)

| Case | 관측 | 해석 |
|---|---|---|
| A | checkpoint-77부터 `<think>` ≈ 0 | json_only objective가 thinking suppression을 매우 빠르게 학습했다 |
| B | 초기 checkpoint는 thinking하고 뒤에서 사라진다 | json_only pressure와 학습 기간·과적합이 함께 작용한다 |
| C | semantic correctness가 초기 checkpoint에서 더 높다 | 2 epoch 고정이 과도했다는 진단 근거다. 다음 실험 epoch 설계에만 쓴다 |

- 56문항 panel이라 checkpoint 간 차이는 기술 통계로만 본다.
