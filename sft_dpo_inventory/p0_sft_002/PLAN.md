# p0_sft_002 사전 등록: R70 json_only vs full_response(thinking loss mechanism)

고정: 2026-10-13, R70 학습 시작 전. 이 커밋 뒤에는 데이터·hyperparameter·probe·gate를 고치지 않는다. 결정 69.

## 1. 질문

같은 70개 reasoning 데이터, 같은 모델, 같은 recipe, 같은 seed에서 손실 범위만 json_only와 full_response로 바꾸면 thinking 행동이 실제로 달라지는가?

- R70-json은 causal control이다. 예상은 thinking suppression이다.
- R70-full은 예상이 thinking 유지·학습이다.
- 이 실험은 성능 최대화가 아니다. R70 모델은 최종 candidate가 아니다(teacher가 맞춘 70문항에 치우친 데이터).

## 2. 데이터(`r70_dataset_manifest.json`)

| 항목 | 값 |
|---|---|
| 파일 | `training/generated/p0_sft_002/r70/sft_train.jsonl` sha256 `fa073a3f…`(두 arm이 같은 파일) |
| 출처 | p0_sft_001 Clean-Hybrid의 reasoning 레코드 70(trace_review 승인 70), 원래 순서. 새 trace 없음 |
| 구성 | v005 54, Gap A 5, Gap B 11 |
| item ID | 70개, 목록 hash `261dfec2…` |
| thinking hash | `fbd5e380…`(승인 trace thinking 원문과 일치 확인) |
| 최종 P0 JSON hash | `5e9f629b…`(canonical target과 일치 확인) |
| 쓰지 않는 것 | 답만 있는 84문항, STRUCTURALLY_REPAIRABLE, 새 trace, synthetic thinking |
| 레코드 형식 | `<think>\n{승인 thinking}\n</think>\n\n{canonical P0 JSON}` |

## 3. 학습 설정(두 arm 동일, p0_sft_001 recipe)

- config: `qwen3_8b_p0_sft002_r70_json.yaml`(`a1683670…`), `qwen3_8b_p0_sft002_r70_full.yaml`(`41e95fe8…`).
  - 다른 것은 `thinking.loss_scope`, output, profile 경로뿐이다(diff 확인).
- base `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`, BF16, SDPA, gradient checkpointing
- LoRA r16, α32, dropout 0.05, q/k/v/o/gate/up/down_proj
- AdamW lr 5e-5 linear, warmup 1 step, batch 1, accum 1, seed 42, max_seq_length 11,392
- **epoch 1 = 70 step**
  - 근거: checkpoint 진단(`CHECKPOINT_DIAGNOSTIC.md`)에서 thinking collapse는 0.5 epoch에서 이미 일어났다. epoch는 mechanism에 결정적이지 않았다.
  - 70문항뿐이다. p0_sft_001은 1 epoch 뒤 train loss가 거의 0이었다.
- 저장 0.25마다(18, 35, 53, 70 예상). 평가는 최종 adapter(1 epoch 끝)만 한다. early stopping 없음.
- 손실 범위:
  - R70-json = `json_only`
  - R70-full = `full_response`
  - 실제 label tensor 검증: `LOSS_MASK_AUDIT.md`. 70/70 기대와 일치, input_ids 동일.

## 4. 학습 순서(`run_train.sh`, `e3b55a14…`)

1. R70-json → 기록 commit·push
2. GPU idle·precheck
3. R70-full → 기록 commit·push

- HF만 쓴다. Ollama 호출은 없다.

## 5. mechanism probe(`run_probe.sh probe`, `574cb243…`)

- panel: checkpoint 진단과 같은 56문항(`diagnostic_panel_gold.yaml`, `bf35b82c…`).
- 대상:
  - Base(p0_sft_001 결과 재사용, 같은 조건)
  - R70-json 최종 adapter
  - R70-full 최종 adapter
- 조건(세 모델 같음): P0 prompt `d7f4c12a`, `enable_thinking=True`, greedy, max_new_tokens 8192, `p0_sft_001/eval_p0_hf.py` 그대로.
- 순서: R70-json → R70-full.

## 6. 지표(`analyze_probe.py`, `5ac0db1a…`)

- **주 지표:** `<think>` emission rate(문항 첫 호출 원문에 `<think>`가 있음).
- 함께:
  - thinking_chars 중앙값
  - 첫 token이 `{`인 비율(direct-JSON)
  - semantic correctness
  - malformed JSON
  - 생성 token 중앙값
  - structural error
  - stratum별 정답

## 7. mechanism gate(practical threshold, 통계 gate 아님)

| 판정 | 조건 |
|---|---|
| PASS | R70-full emission ≥ 80%, R70-full − R70-json ≥ 50%p, R70-full thinking_chars 중앙값 > 0 |
| PARTIAL | R70-full − R70-json ≥ 20%p, PASS 아님 |
| FAIL | 그 밖(R70-full도 thinking이 거의 없음) |

- **FAIL:** full evaluation으로 넘어가지 않는다. chat template, assistant token 경계, enable_thinking 상호작용, LoRA target, renderer, generation parser를 조사한다.
- **PARTIAL:** 결과를 보고하고 full evaluation은 사용자 결정으로 남긴다.

## 8. gate PASS일 때만: 403문항 진단 평가(`run_probe.sh full403`, `analyze_full.py` `06881d35…`)

- R70-json·R70-full을 p0_sft_001과 같은 4셋(403문항)에 잰다. Base는 p0_sft_001 결과를 재사용한다.
- 분석은 p0_sft_001 `analyze.py` 정의 그대로다. 모델 쌍: base·r70_json, r70_json·r70_full, base·r70_full.
- 결과는 **진단용**이다. R70은 v006 전체 분포가 아니다.
- 볼 trade-off:
  - overall semantic correctness
  - bucket, dimension_target, od_role ≠ dimension_target, scope 역조회, refusal
  - structural error
  - p0_sft_001에서 좋아진 dimension_target·structural 개선을 유지하면서 bucket·general semantics 하락을 줄이는가

## 9. 중단·이탈 규칙

- 기반 장애(crash, OOM, NaN, GPU 오류)면 멈추고 기록한다. 원인을 고친 뒤 그 단계만 같은 명세로 다시 한다(이탈 기록).
- 결과를 보고 데이터·epoch·hyperparameter·gate를 바꾸지 않는다.
- 작업 단위마다 commit·push하고 원격 HEAD 일치를 확인한다.

## 10. 하지 않는 것

- 27B teacher 반입, 새 trace, STRUCTURALLY_REPAIRABLE, Gap C, 새 prompt, P0.4, DPO, pruning, quantization, synthetic thinking.
