# 격리 확인 실험 실행 계획(AUDIT.md 4절의 실행본)

2026-10-13. 결과를 보기 전에 고정한다. 판정 기준은 AUDIT.md 4절을 그대로 쓰고, 결과를 본 뒤 바꾸지 않는다.

## 1. 목적

정확도 평가가 아니다. 모델 weights를 GPU에 둔 채로도 같은 질문의 출력이 앞 문항의 순서에 영향을 받지 않는지 확인한다.

## 2. 문항

- `items_gold.yaml`(`build_items.py`), 10문항, 판정에 쓰지 않는 승인 학습 gold(reviewed_gold_v005_t2pc SFT).
- AUDIT 4절의 "고정 seed로 고른다"에 실행 전 자격 조건을 하나 더했다.
  - 조건: 승인 Full gold를 mock 운영 경로에 넣어 재질의 없이 answered이고, Tool 호출이 있고, 장소 조회가 2개 이하인 문항(60문항).
  - 이유: harness 채점에 gold_text(정답 호출)가 필요하다. 결과를 보기 전에 정했다.
- 고른 문항(파일 순서): b005-32, b005-21, b004-24, b005-29, b005-40, b005-09, b005-22, ann-f78087861d0826ae8a7f, b005-15, b005-60.
  - `random.Random(20261013).sample(sorted(자격 문항), 10)`으로 골랐다.
- gold 확인: `evaluate_vendor100.py gold`에서 10/10 match다.
- 평가셋(vendor100·valid98·sel154·aux)은 쓰지 않는다. v005 학습 질문과 이들의 질문 겹침은 0이다(`../sft_p0/inventory.json`).

## 3. 조건

모든 조건에 공통으로 적용한다.

- prompt: Full(87048d0c).
- 모델: Ollama `qwen3:8b`(digest 500a1f06), 버전 0.40.3.
- 옵션: `--model-think auto`, `--condition-check`, 기준일 2026-09-25, `--record-thinking`(thinking 원문 저장).
- 실행 모드:

| 조건 | 셀 이름 | model-state | 문항 순서 |
|---|---|---|---|
| A | `A_{greedy,sample}` | unload_per_question(기존 방식) | file |
| B | `B_{greedy,sample}` | resident_isolated | file |
| B' | `Bp_{greedy,sample}` | resident_isolated | reverse |
| C | `C_{greedy,sample}` | resident(cache 재사용, 대조군) | file |
| C' | `Cp_{greedy,sample}` | resident | reverse |

- greedy: sampling 인자 없이 실행한다(기존 greedy 셀과 같음).
- sampling: temperature 0.6, top_p 0.95, top_k 20, `--seed 20261013`. 호출 seed는 `call_seed(round_seed, item_id, call_index)`이므로 문항 순서와 무관하다.

**실행 순서(`run_all.sh`):**

1. A_greedy → A_sample. 기존 방식대로 셀마다 빈 GPU 확인, 문항마다 unload, 셀 뒤 wait-empty.
2. 상주 블록(`resident_lib.sh`): `resident_begin`을 한 번 한다(빈 GPU 확인 → 판정 무관 warm-up 2호출 → 상주 감시 시작).
3. 상주 블록의 셀: B_greedy → Bp_greedy → C_greedy → Cp_greedy → B_sample → Bp_sample → C_sample → Cp_sample.
4. `resident_end`로 끝낸다. 셀 사이에 unload, wait-empty, 컨테이너 조작을 하지 않는다.

- 속도 guard: 77.6 tok/s(ab_p0_3과 같음). CLAUDE.md 13번의 GPU 확인을 따른다.
- isolation 요청(`PrefixCacheReset`)은 문항 기록의 llm_calls·점수·token 지표에 들어가지 않는다.

## 4. 비교와 판정

같은 질문, 같은 seed끼리 비교한다.

- **비교 항목:**
  1. 첫 계획 응답 원문(content)과 thinking 길이: AUDIT 4절의 사전 판정 항목.
  2. 보조 비교:
     - 모든 호출의 응답 원문과 thinking 원문
     - 최종 grounding
     - 채점 범주
     - error code
     - Tool 호출(이름·인자)
- **쌍:** B 대 B'(격리 상태의 순서 영향), C 대 C'(재사용 상태의 순서 영향), B 대 A, C 대 A.
- **사전 판정 기준(AUDIT.md 4절):**
  1. B = B'가 greedy 10/10, sampling 10/10(1번 항목)이면 문항 격리 성립.
  2. B = A까지 10/10이면 이전 unload_per_question 기록과 직접 비교 가능.
  3. B = B'이지만 B ≠ A이면, 격리는 되지만 이전 기록과는 따로 비교한다.
  4. B ≠ B'이면 resident_isolated를 쓰지 않는다. trace 수집으로 넘어가지 않고 보고한 뒤 멈춘다.
     - 이 경우 isolation 요청 횟수를 늘리거나 컨테이너를 재시작하면서 맞추지 않는다.
- **보고:** 순서 때문에 semantic 결과(범주), grounding, error code가 달라진 문항 수를 B 대 B', C 대 C'로 나란히 적는다.
- **상주 기록:** model unload·reload·컨테이너 재시작 수(residency.json), warm-up 호출 수, 셀별 reset_ok.
