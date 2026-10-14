# 27B teacher 생성 사전 등록(실행하지 않음)

고정: 2026-10-14. 결정 74–77.

- 실행 조건:
  - provenance가 사용자 승인으로 해결됨
  - 반입한 모델이 아래 4절 검증을 모두 통과함
  - 사용자가 실행을 명시적으로 승인함
- 이 문서를 고친다면 실행 전에 별도 결정으로 한다.

## 1. 대상(변경 없음)

- `sft_dpo_inventory/p0_sft_003_recovery/teacher27b_manifest.json`을 참조한다(복제하지 않음).
  - sha256 `65a016e0a71905e45443e31c54a6ae59285f950fa33cac4905129766f5c07f38`
  - 31문항 = M1 ∩ {P1, P2}
- **item_index** = manifest 파일 안 순서(0–30). 그 id 순서 목록의 sha256은 `9850b727f361c869…`다.
- quality gate·provenance 결과로 대상을 바꾸지 않는다. 실패한 M2 11·M3 1은 넣지 않는다(후속 batch).

## 2. 모델과 요청

- **모델**: Ollama `qwen3.8:27b`. digest가 `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`과 **전체 값이 정확히 같아야** 한다. prefix 일치는 인정하지 않는다.
- **prompt**: P0(hash `d7f4c12a`), messages = `GeoFlowPlanner.messages(question)`의 [system, user]. gold 답은 주지 않는다.
- **요청**: `/api/chat`, `think: true`, stream 없음, 요청마다 대화 상태 없음.
- **표본**: 문항당 greedy 1 + sampling 4, 최대 31 × 5 = 155 호출.

| 표본 | options |
|---|---|
| greedy(sample_index 0) | temperature 0, seed 없음 |
| sampling(sample_index 1–4) | temperature 0.6, top_p 0.95, top_k 20 |

- **sampling seed** = `2026101500 + 10 × item_index + sample_index`. 과거 seed(20261006 계열, 2026101400 계열)와 겹치지 않는다.
- **num_predict**: 과거 teacher와 같게 지정하지 않는다.
  - 다만 0.40.3의 기본 생성 상한 동작이 과거(0.35.1)와 같은지 4절에서 먼저 확인한다.
  - 다르면 값을 조용히 바꾸지 않고 이탈로 기록한다. 사용자 결정이 필요한지 보고한다.

## 3. 격리·장비

- Ollama 데이터 수집이다. **unload_per_question**: 문항마다 모델을 내린다(`OllamaStateReset`, CLAUDE.md 14번). resident·resident_isolated는 쓰지 않는다.
- HF 프로세스 0인 상태에서만 한다. GPU 1장 공유(결정 56).
- 셀마다 다음을 확인한다:
  - 컨테이너 GPU 확인
  - 첫 문항 `/api/ps` size_vram == size(100% GPU)
  - context_length 기록
  - 생성 속도 guard. 기준은 4절 render check의 측정 분포 중앙값 × 0.5로 정하고 첫 셀 전에 PLAN_DEVIATIONS에 적는다.
- 기반 장애만 같은 명세로 다시 한다(이탈 기록). 결과를 보고 다시 돌리지 않는다.

## 4. 반입 직후 검증(모델 품질 평가 아님, compatibility check)

| 항목 | 기준 | 다르면 |
|---|---|---|
| digest | `/api/tags` = `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` 전체 일치 | 생성 시작하지 않음 |
| 양자화 | `/api/show` details.quantization_level = Q4_K_M | 보고·중단 |
| capabilities | completion, vision, tools, thinking(과거 기록) | 보고·중단 |
| parameters | temperature 1, top_k 20, top_p 0.95, min_p 0, presence_penalty 0, repeat_penalty 1, draft_num_predict 4(과거 기록) | 보고·중단 |
| template·system | `/api/show` template·system 원문의 sha256을 기록한다(과거 기록에 원문 hash가 없어 비교 기준이 없음을 함께 적는다) | 기록 |
| context_length | `/api/ps` 값. 과거 262,144 | 다르면 이탈로 기록하고 보고 |

**rendering 10문항**

- pilot_001 `render_check.py`의 10문항(v004 학습 질문, 같은 선택 규칙)을 쓴다. 평가셋이 아니며 결과를 보고 고르지 않는다.
- 요청은 P0 prompt와 2절 greedy 설정이다.
- 확인:
  1. think 지정 시 `message.thinking`이 비어 있지 않음
  2. `message.content`에 `<think>`·`</think>` 없음
  3. `prompt_eval_count`·`eval_count` 기록(27B tokenizer가 8B와 같은지 모르므로 HF 8B token 수 비교는 참고로만)
  4. `done_reason` 기록
- **num_predict 확인**: 10문항 중 생성이 끝까지 가지 않고 끊긴 것(done_reason length)이 있으면 0.40.3의 기본 상한을 의심해 보고한다.
- 모든 항목 통과 뒤에만 31문항 생성을 시작한다.

## 5. 판정·선택·검토(8B M2와 같고, ranking만 quality_gate_v1)

1. **판정**: `evaluation/partial_grounding/sft_p0/collect_p0_traces_hf.judge`(5범주). EXACT_OR_SEMANTIC_MATCH만 reasoning 후보로 둔다.
2. **필터**: thinking 있음, done_reason stop, 결정 40-D 루프, 결정 18 길이.
   - 결정 4 tokenize 왕복은 8B tokenizer 기준이라 27B 원문에는 적용하지 않는다.
   - 대신 학습 렌더링(Qwen3-8B tokenizer)에서 원문 문자열 왕복이 바이트 단위로 같은지 확인한다.
3. **ranking**: `quality_gate_v1.rank_key`(flag 수 → thinking 길이 → Wait·Hmm 수 → greedy 먼저 → sample index). 문항당 1개를 고른다.
4. **사람 검토**: 문항당 1개 전부 읽는다(APPROVE_TRACE / REJECT_TRACE, reason, quality tags, quality_gate_v1 flag 기록). 거부되면 다른 표본으로 바꾸지 않는다.
5. **provenance**(8B trace와 섞지 않음): teacher_model, digest, Ollama 버전, generation_batch, seed, sample_index, quality_gate_v1 flag, review_decision.

## 6. 산출물(실행 시)

- `training/generated/p0_sft_003_teacher27b/raw/traces.jsonl`
  - item_id, question, model·digest·Ollama 버전, prompt hash, options·seed, thinking 원문, 응답 원문, parsed, 판정
  - eval_count, prompt_eval_count, duration, load_duration
- 판정·검토 결과, coverage 갱신(83 + 승인 수)/154. 최종 reasoning dataset freeze는 별도 결정이다.
