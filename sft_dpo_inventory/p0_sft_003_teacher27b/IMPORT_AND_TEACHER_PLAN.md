# 27B 반입·teacher 생성 사전 등록

고정: 2026-10-14, pull 전. 결정 79·80. `GENERATION_PLAN.md`(`7617ba1`)를 따르고, 아래에서 실행 세부를 고정한다.

## 1. provenance

- registry manifest body의 raw bytes sha256이 `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`과 64 hex 전체가 같다.
- 결정 79로 이를 동일 artifact의 충분한 근거로 인정한다.
- 상태는 **PROVENANCE_REGISTRY_BODY_HASH_MATCH**다. 이전 판정 PROVENANCE_PARTIAL·PROVENANCE_UNRESOLVED는 기록으로 둔다.

## 2. 기준값

| 항목 | 값 |
|---|---|
| manifest digest | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` |
| config | `sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f` |
| model layer | `sha256:f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d`(16,810,714,464 B) |
| projector | `sha256:ac3714bfdddeca31351f2752bf1a63f266f4df87c0b68c895e44945ca704448e` |
| layer 합 | 17,741,871,939 B |
| 양자화 | Q4_K_M |
| capabilities | completion, vision, tools, thinking |
| context | 262,144(과거) |
| parameters | temperature 1, top_k 20, top_p 0.95, min_p 0, presence_penalty 0, repeat_penalty 1, draft_num_predict 4 |
| Ollama | 현재 0.40.3(과거 teacher 0.35.1) |
| 31문항 manifest | `p0_sft_003_recovery/teacher27b_manifest.json` sha256 `65a016e0a71905e45443e31c54a6ae59285f950fa33cac4905129766f5c07f38`, id 순서 hash `9850b727f361c8691b1c18295a1463e3d5fdbce35a49f0585834d85985d5a599` |
| quality_gate_v1 | `quality_gate_v1.py` sha256 `f57e2d3e1045fcf7cb00cfd577b5b8850281158bee52c6d3bd3787bd828bf392`(commit `0c42288`) |

## 3. 순서와 hard gate(FAIL이면 아래 단계는 하지 않음)

### G0 pull

- 사전 확인: GPU compute 프로세스 0(HF 0), Ollama `/api/ps` 빈 상태.
- `docker exec ollama ollama pull qwen3.8:27b`. 기존 컨테이너와 store(`/data/hwkim/ollama`)를 쓴다.
  - 컨테이너 재생성·설정 변경 없음. qwen3:8b는 건드리지 않는다.
- 기록: 시작·끝 시각, 출력 마지막 줄, store 크기 전후.

### G1 digest

- `/api/tags`의 `qwen3.8:27b` digest가 2절 manifest digest와 **전체 일치**해야 한다.
- 다르면 중단한다. 모델은 지우지 않고 상태만 보고한다.

### G2 metadata

`/api/show` 원문을 저장한다. 다음 중 하나라도 맞지 않으면 중단한다.

- quantization_level Q4_K_M
- capabilities에 thinking 포함(과거 4개와 비교)
- 모델 family qwen3 계열(architecture 원문 기록)
- template 원문에 thinking 처리(`<think>`)가 있음

다음은 기록하고 비교한다(차이는 deviation, 즉시 실패 아님).

- parameters
- 0.40.3 표시 형식 차이
- context_length: 첫 compatibility 호출 중 `/api/ps`에서 읽는다. 262,144와 다르면 deviation이다.
  - teacher 입력(P0 prompt 약 7–8천 token + 생성)이 들어갈 만큼인지(≥ 16,384) 확인한다. 부족하면 중단한다.

### G3 compatibility 10문항(`compat_check.py`)

- 문항: 결정 31 render check와 같은 선택 규칙의 v004 학습 질문 10개(v003 train 앞 4, v003 valid 앞 3, batch004 앞 3). 평가셋이 아니다.
- 요청:
  - P0 prompt messages, `/api/chat`, `think: true`, `options {"temperature": 0}`, stream 없음
  - `keep_alive: 0`(호출 뒤 내림)
  - num_predict 지정 없음
- 호출 전 `/api/ps`가 비어 있음을 확인한다(최대 60초 대기). 호출 중 2초마다 `/api/ps`를 읽어 size_vram·size·context_length를 기록한다.
- **PASS**(10/10 모두):
  1. HTTP 200, 오류 없음
  2. `message.thinking`이 비어 있지 않음
  3. `message.content`가 비어 있지 않고 `<think>`·`</think>`가 없음
  4. content가 `parse_planner_json`으로 JSON 객체로 읽힘
  5. done_reason stop(length면 비정상 truncation)
  6. 관측한 size_vram == size(CPU fallback 없음)
- 정답 여부는 참고로만 기록하고 PASS 기준에 넣지 않는다.
- 기록: thinking 표현, 응답 schema, done_reason, context_length, load_duration, prompt_eval_duration, eval_duration, eval_count, prompt_eval_count.
- **속도 기준**: 10문항의 eval_count / eval_duration 중앙값 × 0.5. teacher 생성 guard로 쓴다(compatibility 결과로 정하고 기록).
- FAIL이면 31문항 생성을 하지 않는다. parameter·prompt를 즉석에서 바꾸지 않는다(num_predict 포함).

### G4 31문항 생성(`teacher_generate.py`)

- 대상: manifest 순서 그대로 31문항(item_index 0–30). 추가·삭제 없음.
- 문항당 5호출:

| sample_index | options |
|---|---|
| 0(greedy) | temperature 0 |
| 1–4(sampling) | temperature 0.6, top_p 0.95, top_k 20, seed = 2026101500 + 10 × item_index + sample_index |

- `think: true`, P0 prompt(`d7f4c12a`), gold 미제공, num_predict 지정 없음. 최대 155 호출.
- **격리(결정 80)**:
  - teacher 데이터 수집은 호출마다 `keep_alive: 0`으로 모델을 내리고, 다음 호출 전 `/api/ps`가 빈 것을 확인한다.
  - unload_per_question보다 엄격하다. resident 계열은 쓰지 않는다.
- **guard**:
  - 호출 중 `/api/ps` size_vram == size
  - 호출의 eval_count / eval_duration ≥ G3 속도 기준
  - GPU compute 프로세스는 Ollama runner뿐(HF 0)
  - 어기면 그 호출에서 중단하고 출력을 ABORTED로 남긴다.
- **저장**(호출마다 jsonl):
  - item_id, item_index, sample_index, question
  - model, digest 전체, Ollama 버전, prompt hash, seed, options
  - thinking 원문, content 원문, done_reason
  - eval_count, prompt_eval_count, thinking 글자 수
  - total·load·prompt_eval·eval duration, 시각, guard 관측값
- **raw를 판정 전에 commit·push한다.**

### G5 판정·선택·검토

- 판정: `collect_p0_traces_hf.judge`(5범주), 후보는 EXACT_OR_SEMANTIC_MATCH만이다.
- 필터:
  - thinking 있음, done_reason stop
  - 결정 40-D 루프 아님
  - 결정 18 길이(Qwen3-8B tokenizer 기준 prompt + 원문 + 1 ≤ 12,887)
  - 학습 렌더링 문자열 왕복 바이트 일치
- 학습 원문 꼴: `<think>\n{thinking}\n</think>\n\n{content}`(기존 teacher trace와 같은 normalize_trace 형식).
- ranking: `quality_gate_v1.rank_key`(flag 수 → thinking 길이 → Wait·Hmm 수 → greedy 먼저 → sample index). 문항당 1개.
- 사람 검토는 전부 한다(APPROVE_TRACE / REJECT_TRACE, reason, quality_gate_v1 flag).
  - 거부는 TEACHER_RECOVERY_FAILED이며 다른 표본으로 바꾸지 않는다.
  - 기준: `p0_sft_003_recovery/PLAN.md` 4절. 중간 오판을 확정하고 철회하지 않으면 거부한다.
- quality_gate_v1은 바꾸지 않는다. 27B 판정과의 일치(FP·FN)는 참고로만 적는다.

### G6 coverage

- 83 + 승인 27B(unique item)/154.
- feature별: dt pickup·dropoff·both, od_ne_dt, Gap A·B, sido, bucket.
- 출처 구분:
  - HF Qwen3-8B R70
  - HF Qwen3-8B M2 회수
  - M3 기존 trace 회수
  - Ollama qwen3.8:27b teacher
- 최종 reasoning dataset은 freeze하지 않는다. 학습·DPO 0.

## 4. 그 밖

- pull한 모델은 지우지 않는다(사용자 결정).
- gate 실패 뒤 재-pull, tag 변경, 대체 모델 사용, 삭제·재시도를 하지 않는다.
