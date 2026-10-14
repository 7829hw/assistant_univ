# p0_sft_004 — P0 Full-Reasoning SFT 1차 사전 등록

고정: 2026-10-14, 학습 전. 결정 86. 이 문서의 기준은 결과를 보고 바꾸지 않는다.

## 1. 질문

154문항 모두에 reasoning이 있을 때, reasoning text 자체를 supervise하는 FULL154가 같은 semantic coverage의 JSON154보다 generalization에 도움이 되는가?

- 두 arm의 공통점: 같은 154 질문, 같은 reasoning text, 같은 최종 JSON, 같은 tokenizer·base·seed·LoRA·recipe.
- 차이: loss mask 하나뿐이다.
- p0_sft_001과 달리 답만 있는 레코드가 없어 첫 token confound(`{`)가 없다.

## 2. 데이터(고정)

| 항목 | 값 |
|---|---|
| dataset | `reviewed_reasoning_v001/dataset.jsonl` sha256 `071ccdbee8c74694a189e861bb572975c6198da9c79b7cc93a558f531decea49`, 순서 sha256 `8522deaa…`, 154 레코드 |
| arm 파일 | `datasets/full154.jsonl` = `datasets/json154.jsonl` = dataset(바이트 동일). valid 비어 있음 |
| 출처 | HF 8B 83(R70 70, M2 10, M3 3), 27B 65(P1/P2 27, remaining 38), manual canonical 6. 각 1회(oversampling 0) |
| audit | `datasets/loss_mask_audit.json` ok. input_ids 154/154 동일, 첫 assistant token `<think>` 154, `{` 학습 0 |

## 3. arm

| arm | config | loss_scope | supervised |
|---|---|---|---|
| FULL154 | `training/configs/qwen3_8b_p0_sft004_full154.yaml` | full_response | `<think>`·thinking·`</think>`·JSON·EOS(133,366 token) |
| JSON154 | `training/configs/qwen3_8b_p0_sft004_json154.yaml` | json_only | JSON·EOS(13,515 token). thinking은 context에만 있다 |

## 4. recipe(두 arm 같음, p0_sft_002 R70 recipe)

| 항목 | 값 |
|---|---|
| base | `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`. 두 arm 모두 base에서 독립 시작 |
| precision·attention | BF16, SDPA, gradient checkpointing |
| LoRA | r 16, alpha 32, dropout 0.05, q/k/v/o/gate/up/down_proj |
| optimizer·lr·scheduler | adamw_torch, 5e-5, linear(warmup_steps 1) |
| batch·GA | 1·1 |
| seed | 42 |
| epoch | 1 |
| 예상 step | 154(154 레코드 ÷ batch 1) |
| max_seq_length | 11,392. 관측 최대 8,995 token이라 truncation 0이고 변경 없음 |
| checkpoint | save_steps 0.25(약 39·78·117·154 step). primary는 최종 step(1.0 epoch)이다. 중간 checkpoint는 평가하지 않고 선택에도 쓰지 않는다 |
| 환경 | torch 2.11.0+cu128, transformers 4.56.2, trl 0.23.1, peft 0.17.1, GPU RTX PRO 6000 Blackwell `GPU-d4308fbb…` 1장 |
| 실행 | `run_phase.sh train full154` → commit → `run_phase.sh train json154` → commit. HF만, Ollama 호출 0 |

- 학습 중 데이터·canonical·레코드·LR·epoch는 바꾸지 않는다.
- 기반 장애(crash·OOM·NaN)는 멈추고 deviation으로 기록한다.

## 5. 평가셋(development benchmark, final holdout 아님)

- sel154·valid98·vendor100·aux_test_v1 = 403문항(p0_sft_001과 같은 gold 파일·순서).
- 과거 prompt·data 분석에 쓴 개발용 benchmark다. checkpoint 선택에 쓰지 않는다.
- 세 모델(Base, FULL154, JSON154)을 지금 같은 harness로 모두 잰다(403 × 3 = 1,209):
  - `p0_sft_001/eval_p0_hf.py`
  - P0 prompt `d7f4c12a`, `enable_thinking=True`, greedy, max_new_tokens 8192
  - 같은 parser·scorer·순서, `--condition-check --record-env`
- raw(thinking 원문 포함): `training/generated/p0_sft_004/eval_raw/`. 모델마다 403이 끝나면 raw부터 commit한다.
- 순서: Base → FULL154 → JSON154. 셋 안의 순서는 sel154 → valid98 → vendor100 → aux_test_v1.

## 6. smoke(전체 평가 전, `recall.py --items smoke`, `smoke_check.py`)

- 학습 문항 18(결과를 보지 않고 고정): canonical 6 + 출처별 sha256(item_id) 오름차순(R70 4, M2 1, M3 1, 27B P1/P2 3, remaining 3).
- 세 모델 모두 greedy, thinking 켬, P0. 기록: thinking emitted·글자, content, JSON parse, train recall 판정, 생성 token.
- hard failure(전체 평가 시작 안 함): 어댑터 load·생성 실패(행 수 ≠ 18), content 빈 응답 > 9/18, JSON parse 실패 > 9/18, UNPARSEABLE > 9/18.
- 낮은 thinking 비율은 모델 행동 결과이며 중단 사유가 아니다.

## 7. training recall(154, `recall.py --items all`)

- 세 모델, 같은 생성 조건. 판정은 trace 선택에 쓴 `collect_p0_traces_hf.judge`이고, EXACT_OR_SEMANTIC_MATCH = train recall 정답이다.
- 학습 목표 습득 진단이며 generalization으로 부르지 않는다.
- 보고:
  - 154 전체 정답·구조 오류·thinking rate
  - canonical 6 각각(implicit endpoint 5의 dimension_target·od_role, b006-34의 dimension h3와 measure text가 'H3 셀'이 아님)
- 순서: 403 평가 세 모델이 끝난 뒤 Base → FULL154 → JSON154.

## 8. 지표(`analyze.py`, 결과 전 고정)

- **primary: semantic correctness**(category ∈ {match, expected_refusal}, 403 pooled).
- secondary:
  - answerable semantic correctness, refusal correctness, execution completion, grounding failure
  - first-response structural error, malformed JSON(first·final)
- thinking(첫 plan 호출): emission rate, thinking 글자·token p50/p90, direct-JSON 첫 응답 비율, 생성 token, wall 시간.
- 부분집합(`subsets.json`, gold·질문만으로 결과 전 정의):
  - dt_any·pickup·dropoff·both, od_ne_dt, bucket, aggregation, order, h3, sido, sigungu, emd
  - gap_a_like(sel154 사건 표현 11), gap_b_like(= od_ne_dt), implicit_endpoint_all(76), implicit_endpoint_verb(32), scope_reverse, refusal
  - 표본 수를 항상 함께 적는다.
- 비교: FULL154−Base, JSON154−Base, FULL154−JSON154.
  - pp 차이, paired bootstrap 95% CI, permutation p, exact McNemar, 전이 4칸
  - 회귀·개선 문항 전부 자동 오류 tag(PLACE_OMISSION … OTHER)
- reasoning 표본: 모델마다 정답 10 + 오답 10(sha256 순, 결정적)을 사람이 읽는다.
  - 확인: reasoning-final 충돌, 근거 없는 내용, 묶음 단위 실수, endpoint 추론, aggregation 흔들림
- quality_gate_v1은 평가 판정에 쓰지 않는다. 기존 `_grounding_view`는 바꾸지 않는다.

## 9. gate(arm마다, Base는 같은 harness 측정값)

viable(모두 충족):

1. overall semantic correctness ≥ Base − 2.0pp
2. first-response structural error ≤ Base
3. dimension_target(dt_any) semantic correctness ≥ Base
4. bucket correctness ≥ Base − 5pp
5. thinking emission ≥ 95%
6. malformed JSON(first) ≤ Base

strong success: overall ≥ Base AND dt_any > Base AND structural < Base AND thinking ≥ 95%.
통계적 유의성(CI·McNemar)과 practical gate를 따로 보고한다.

## 10. candidate 규칙

- FULL154만 viable → FULL154. JSON154만 viable → JSON154.
- 둘 다 viable:
  - overall semantic이 높은 쪽을 고른다.
  - 차이 < 1.0pp면 tie다. tie-break 순서는 dt_any → structural error(적은 쪽) → bucket → implicit_endpoint_all.
- 둘 다 viable 아님 → **SFT candidate = NONE**, compression readiness = NOT_READY.
- 결과를 보고 2 epoch·LR·canonical·prompt를 바꾸는 재실험은 이 phase에서 하지 않는다.

## 11. 참고 비교

- 역사적 값(p0_sft_001 Gold-only 64.8%, Clean-Hybrid 65.5%, Base 73.0%)은 참고로만 표에 넣는다(paired 통계에 넣지 않음).
- p0_sft_002 R70-json·R70-full thinking 100%와 연결해 논의한다.

## 12. 하지 않는 것

- 새 teacher sampling, P0 prompt 수정, P0.4, DPO, 2 epoch, hyperparameter search
- structured pruning·quantization 실행, batch007, scope/refusal 증강
- `qwen3.8:27b` 삭제
