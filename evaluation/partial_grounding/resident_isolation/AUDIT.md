# Ollama 상주 실행의 문항 격리 감사

2026-10-13. 모델 호출 없음.

- 방법: 코드 경로 추적, 컨테이너 설정 읽기(`docker logs`의 서버 설정 줄), 기존 sel154 raw의 호출 시간 분석.
- 기계 판독용 요약: `audit.json`.

## 1. 결론

- **클라이언트(harness) 쪽 논리 상태는 문항마다 완전히 새로 만든다.**
  - 이전 질문의 messages·응답·session·context handle을 다음 질문에 넘기는 경로는 없다.
  - 재질의만 같은 문항 안에서 그 문항의 첫 응답을 붙인다. 의도된 동작이다.
- **서버 쪽에는 문항 사이에 남는 상태가 하나 있다. Ollama runner의 KV cache다.**
  - 설정: `OLLAMA_NUM_PARALLEL:1`, slot 하나.
  - runner는 직전 요청의 token을 cache에 남기고, 다음 요청과 겹치는 앞부분은 다시 계산하지 않는다.
  - 모든 문항이 같은 system prompt(약 8,000 token)를 쓰므로, 모델을 내리지 않으면 다음 문항은 앞 문항이 계산한 system prompt KV를 재사용한다.
  - 이 재사용은 이전 질문의 **내용**을 넘기지 않는다. 겹치는 부분은 같은 token이다.
  - 그러나 **계산 경로**(어느 token을 어느 batch에서 계산했는가)가 직전 요청에 따라 달라진다. grounding_v14의 관측("같은 요청의 출력이 직전 처리 이력에 따라 달라짐, temperature 0 포함")과 맞는다.
- **결정 62의 `--model-state resident`는 이 cache 재사용을 막지 않는다.** 문항 격리가 보장되지 않으므로 판정용 run에 쓰지 않는다.
- **최소 수정안(harness 수준, code fingerprint `ab88a19e` 그대로): `--model-state resident_isolated`.**
  - 문항 시작 전에 chat template 첫 token과 겹치지 않는 짧은 raw 요청을 보낸다(`PrefixCacheReset`).
    - 요청: `/api/generate`, `prompt "#"`, `raw: true`, `num_predict 1`.
    - keep_alive를 보내지 않으므로 모델을 내리지 않는다.
  - 그러면 다음 문항은 cache와 겹치는 앞부분 없이 처음부터 prefill한다. 모델을 막 올린 상태와 같은 계산 경로를 기대한다.
  - **이 동등성은 아직 실측하지 않은 가정이다.** 다음 모델 run 전에 4절의 작은 실험으로 확인한다.
- **상주(weights)와 격리(요청 상태)는 따로 기록한다.**
  - `cell_guard.py residency`: unload, reload, 컨테이너 재시작만 본다.
  - 격리: 셀 행마다의 `reset_ok`, `resident_lib.sh`가 셀마다 `isolation: reset_ok N / M`으로 남긴다.

## 2. 상태별 감사

| 상태 | 문항 간 재사용? | 기대 | 근거(코드 위치) |
|---|---|---|---|
| model weights | 예 | 예 | 상주 모드는 `unload_all_models`를 부르지 않는다(`evaluate_vendor100.py:1236`) |
| GPU 할당 | 예 | 예 | 같은 runner 프로세스. `residency`가 runner PID 변화를 reload로 센다 |
| system prompt | 같은 내용 | 예 | 문항마다 `GeoFlowPlanner.messages()`가 같은 prompt로 새로 만든다(`geoflow/planner.py:307`) |
| user message 객체 | 아니오 | 아니오 | `messages()`가 `[system, user]` 새 list를 돌려준다 |
| 이전 assistant message | 아니오 | 아니오 | 재질의(`geoflow/planner.py:421`)는 같은 문항의 첫 응답만 붙인다. 문항이 바뀌면 pipeline·planner를 새로 만든다(`evaluate_vendor100.py:1271`) |
| 예시 선택 cache | 아니오 | 아니오 | `_retrievals`는 planner 인스턴스에 있고 문항마다 새 인스턴스다 |
| Ollama context/session | 아니오 | 아니오 | `/api/chat` payload는 model·messages·stream·options(·think)뿐이다(`ollama_client.py:188`). context·session 필드가 없다 |
| client request 객체 | 아니오 | 아니오 | payload를 호출마다 새로 만든다. `client.options`는 sampling에서 호출마다 덮어쓴다(`_SeededClient`) |
| random seed | 규칙에 따름 | 확인됨 | sampling seed = `call_seed(round_seed, item_id, call_index)`(`evaluate_vendor100.py:156`). 문항 순서·앞 문항과 무관하다. greedy는 temperature 0 |
| 서버 KV cache(내용) | 같은 token prefix만 | 아니오 | 겹치는 부분은 현재 요청과 같은 token이다. 이전 질문 내용이 문맥에 들어가지 않는다 |
| 서버 KV cache(계산 경로) | **예(resident)**, 아니오(resident_isolated, 가정) | 아니오 | 5절의 시간 근거. resident_isolated는 `PrefixCacheReset`(`evaluate_vendor100.py:177`) |
| 서버 sampler 상태 | 아니오(예상) | 아니오 | seed를 요청마다 넣는다. 서버 내부는 조사하지 않았다 |

## 3. 서버 KV cache 재사용의 근거(기존 기록, 모델 호출 없음)

sel154 Full·P0.3 sampling r1–r2의 성공 호출. 회귀식은 (duration − load) = 절편 + 기울기 × eval_count다.

| 호출 | 관측 | prompt token 중앙값 | 절편(ms) | ms/token |
|---|---:|---:|---:|---:|
| 문항 첫 계획 호출(모델을 막 올린 상태) | 616 | 8,017 | 809 | 5.58 |
| 같은 문항의 재질의(직전 요청과 prefix 공유) | 155 | 9,276 | −190 | 6.22 |

- 재질의는 prompt가 더 긴데도 prefill 비용(절편)이 없다. 직전 요청의 KV를 재사용한 것이다.
- `prompt_eval_count`는 재사용해도 전체 길이로 보고된다. grounding_v14가 "재사용 흔적이 없다"고 본 이유다.
- `OLLAMA_NUM_PARALLEL:1`, `OLLAMA_KEEP_ALIVE:5m0s`(컨테이너 로그의 서버 설정).
- 지금까지의 `unload_per_question` 셀에서도 같은 문항 안의 재질의는 이 재사용을 해 왔다. 이 부분은 이번 감사의 범위(문항 사이)가 아니다.

## 4. 확인 실험 설계(이번에 실행하지 않음)

- **목적:** 정확도가 아니라 같은 질문의 출력 안정성과 문항 순서 영향을 본다.
- **문항:** 판정에 쓰지 않는 10문항. 승인 gold corpus v005 SFT 질문에서 고정 seed로 고른다. 평가셋(vendor100·valid98·sel154·aux)은 쓰지 않는다.
- **조건:** Full prompt(87048d0c), qwen3:8b, 0.40.3, thinking auto. greedy 1회 + sampling 1회(seed 20261013, 같은 call_seed 규칙).

  | 조건 | model-state | 문항 순서 |
  |---|---|---|
  | A | unload_per_question | file |
  | B | resident_isolated | file |
  | B' | resident_isolated | reverse |
  | C | resident(cache 재사용) | file |
  | C' | resident | reverse |

  - B, B', C, C'는 한 상주 run 안에서 잰다(warm-up 1회, 셀 사이 unload 없음).
  - A는 기존 방식으로 따로 잰다. CLAUDE.md 13번 GPU 확인과 속도 guard를 따른다.
- **비교:** 문항별 첫 계획 응답 원문(content)과 thinking 길이가 같은가.
- **사전 판정 기준:**
  1. B = B'(순서 영향 없음)가 greedy 10/10, sampling 10/10이면 문항 격리 성립.
  2. B = A까지 10/10이면 이전 unload_per_question 기록과 직접 비교 가능.
  3. B = B'이지만 B ≠ A이면, 격리는 되지만 이전 기록과는 따로 비교한다. 이후 모든 arm을 resident_isolated로 다시 잰다.
  4. B ≠ B'이면 resident_isolated를 쓰지 않는다. 원인을 보고하고 unload_per_question으로 돌아갈지 사용자가 정한다.
  - C와 C'는 대조군이다. 재사용이 실제로 순서 영향을 만드는지(grounding_v14 재현) 확인한다.
- **비용:** 10문항 × 5조건 × 2(greedy·sampling) = 100 문항 실행, 약 15분.

## 5. 남은 불확실성

- `PrefixCacheReset` 뒤의 prefill이 모델을 막 올린 상태와 비트 단위로 같은지는 runner 내부 동작(cache 잘라내기, batch 분할)에 달렸다. 4절 실험 전에는 주장하지 않는다.
- 서버 내부(llama.cpp 커널 선택, 메모리 배치)는 조사하지 않았다.
- `PrefixCacheReset`은 문항마다 짧은 요청 1회를 더한다(생성 1 token). 속도 guard는 이 요청을 보지 않는다(문항 기록의 llm_calls에 없음).
