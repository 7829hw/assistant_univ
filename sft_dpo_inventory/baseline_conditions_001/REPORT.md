# qwen3:8b 업체 100 기준선: 실행 조건별 재측정 (baseline_conditions_001)

작성: 2026-10-06. 측정과 환경 준비만 했다. 학습, prompt 변경, SEMANTIC_CODE 변경은 없다. 업체 100 결과는 평가 전용이며 학습·checkpoint 선택·annotation 후보에 쓰지 않는다.

## 0. 요약

- **thor Base 35와 dev-v2 q8_cur 84의 차이는 대부분 thinking과 조건 계층이 함께 설명한다.** 같은 Ollama 경로에서 단계별로 바뀐다.
  - A(think auto, 조건 계층 켬) 84
  - → B(think off) 54
  - → C(think off, 조건 계층 끔) 28
  - thor 조건(HF, thinking 끔, 조건 계층 끔)을 이 장비에서 재현한 값은 37이다. thor가 맞힌 35문항은 모두 재현됐다.
- **실행 경로 차이(C 28 ↔ HF 37)는 이보다 작지만 문항 단위로는 크다.** 25문항의 결과가 바뀌었다(8건 잃고 17건 얻음).
  - 템플릿도 같지 않다. Ollama think=false 요청은 HF `enable_thinking=False`보다 모든 문항에서 4 token 길다.
- **학습 모델의 비교 기준(nonthinking, T2PC)은 F다:** grounding_ok 57, 정상 55, 용납할 수 없는 실패 4, U가 아닌 조용한 오답 2, 안전한 실패 39.
  - 같은 prompt·코드에서 thinking을 켠 E는 79(정상 84)다.
- **현재 코드의 미처리 예외를 발견했다.** think off 셀(B·C)의 문항 057에서 모델 출력이 `geoflow/grounding.py` `hoist_condition_concepts`의 TypeError를 일으켰다. 현재 HEAD에도 같은 경로가 있다. 고치지 않았다.
- 셀마다 한 번만 실행했다. 다만 A와 D(3일 간격, 별도 실행)의 첫 응답은 100/100 같았고, B와 C도 100/100 같았다.

## 1. 실행 명세

| 셀 | 경로 | prompt / code root | think | 조건 계층 | 출처 |
|---|---|---|---|---|---|
| A | Ollama qwen3:8b `500a1f06` Q4_K_M, 0.34.4 | 522aa3b1 / c1f2a08 | 미지정(auto) | 켬 | `evaluation/grounding_v9/runs/full/q8_cur/dev.json`(2026-10-03, 재사용) |
| B | 같음 | 522aa3b1 / c1f2a08 worktree | off(think=false) | 켬 | `runs/B.json` |
| C | 같음 | 522aa3b1 / c1f2a08 worktree | off | 끔 | `runs/C.json` |
| D | 같음 | 522aa3b1 / c1f2a08 worktree | auto | 끔 | `runs/D.json` |
| E | 같음 | 87048d0c / HEAD ad96729 worktree(T2PC, 지문 97efa866) | auto | 켬 | `runs/E.json` |
| F | 같음 | 87048d0c / 같음 | off | 켬 | `runs/F.json` |
| HF | HF transformers `Qwen/Qwen3-8B@b968826d`, BF16·SDPA, GPU 2 | 522aa3b1 / thor b314904 worktree | `enable_thinking=False` | 끔 | `hf/base/` |
| HFcc | 같음 | 같음 | 같음 | 켬(그 인자만 바꿈) | `hf/base_cc/` |

공통 조건:
- 업체 100, temperature 0(HF는 greedy, max_new_tokens 1024, seed 42), 기준일 2026-09-25, mock·legacy, 문항마다 모델 내림(Ollama).
- q8_cur의 기준일도 2026-09-25이므로 thor 기준일과 같다.
- Ollama 셀은 harness `evaluate_vendor100.py`(이 브랜치)로 실행했다. 각 셀의 code root와 실행 명세는 `runs/*.spec.json`과 결과 meta에 있다.

**확인한 것.**
- A를 재사용한 근거: Ollama qwen3:8b digest(`500a1f06…`)와 버전이 q8_cur와 같다. 이번에 잰 D의 첫 응답이 A와 100/100 같다.
- `--model-think`를 추가해도 기본 요청은 바뀌지 않았다(`request_check_*.json`).
  - 첫 계획 messages hash가 q8_cur와 99/99 같다. 073은 첫 호출 timeout으로 hash가 없다.
  - 기본 auto payload에는 think key가 없다.
  - 실행 의미 코드 지문은 작업 전후 `97efa866…`로 같다.
- GPU 분리: Ollama 컨테이너는 `GPU-48f798cc`(host 3)를 쓰고, `CUDA_VISIBLE_DEVICES=2` torch의 `cuda:0`은 `GPU-a644de12`(host 2)다. 측정 전 GPU 2 사용량은 2 MiB였다(`env/gpu_uuid_check.txt`).
- HF와 Ollama 측정은 순서대로 했다. Ollama 셀이 모두 끝난 뒤 HF 셀을 실행했다.

**HF 환경** (`env/hf_environment.json`, 저장소 밖 `/home/hwkim/sftdpo_work`):
- torch 2.11.0+cu128, transformers 4.56.2, peft 0.17.1, trl 0.23.1, accelerate 1.15.0.
- GPU 2는 NVIDIA RTX 6000 Ada Generation 48GB다.
- thor는 Jetson AGX Thor(aarch64, torch 2.13.0+cu130, accelerate 1.14.0)였다. 모델 config·tokenizer 파일 hash는 thor 영수증과 같다.

**계획에서 벗어난 점(그대로 기록).**
1. **B·C 이어 실행.** 첫 실행이 문항 057에서 평가 대상 코드의 미처리 예외로 중단됐다(56문항 기록).
   - harness에 "미처리 예외를 문항 실패(`UNHANDLED_EXCEPTION`)로 기록"을 추가했다(8b55a1c, SEMANTIC_CODE 아님).
   - 같은 실행 명세 hash로 이어 실행했다(session 2, 44문항). 057은 이어 실행에서도 같은 예외로 실패했다.
   - 이 두 셀은 두 세션으로 구성된 기록이다.
2. **HF의 verify는 부분 확인이다.** thor manifest의 입력 중 32개(코드, 업체 gold, XLSX, runner hash, 문항 순서)는 hash가 같았다. adapter와 ignored corpus 61개는 저장소에 없어 확인하지 못했다. 둘 다 Base 측정에는 쓰지 않는다(`hf/*/receipt.json`).
3. **HFcc는 thor runner가 고정한 `condition_check=False`만 True로 바꿨다.** thor 코드가 이 인자를 지원하므로 건너뛰지 않았다.

## 2. 셀별 결과(같은 기준으로 채점)

- grounding_ok는 현재 `evaluate_vendor100.grounding_check`로 최종 grounding을 다시 채점한 값이다. 기록값과 모두 같다.
- 분류는 v4 축과 grounding_v13 U1–U4 정의를 따른다. U가 우선한다.
- 첫 응답 층은 첫 응답을 현재 HEAD 코드로 다시 통과시킨 값이다(raw = 계약 그대로, preserved = + 조건 계층, 재질의 없음).

| 셀 | grounding_ok | 정상 | U | 조용한 오답(U 아님) | 안전한 실패 | 첫 응답 raw 유효 / 일치 | 첫 응답 + 조건 계층 일치 | 지연 중앙값 / p90(초) | thinking(첫 계획, 중앙값 자) | 재질의 호출 |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|---:|
| A 522·auto·켬 | **84** | 88 | 0 | 3 | 9 | 87 / 50 | 70 | 12.7 / 25.6 | 2,264 (100/100) | 23 |
| B 522·off·켬 | 54 | 53 | 4 | 0 | 43 | 69 / 20 | 46 | 7.1 / 7.7 | 0 | 11 |
| C 522·off·끔 | 28 | 28 | 23 | 0 | 49 | 69 / 20 | 46 | 7.1 / 7.8 | 0 | 10 |
| D 522·auto·끔 | 69 | 70 | 16 | 3 | 11 | 87 / 50 | 70 | 12.4 / 24.9 | 2,264 (100/100) | 23 |
| E 870·auto·켬 | 79 | 84 | 3 | 1 | 12 | 92 / 59 | 73 | 11.9 / 17.1 | 2,101 (100/100) | 17 |
| **F 870·off·켬** | **57** | **55** | **4** | **2** | **39** | 77 / 24 | 49 | 7.3 / 8.2 | 0 | 14 |
| HF thor 재현 | 37 | 36 | 16 | 1 | 47 | 66 / 23 | 43 | 6.8 / 9.0 | 0 | 15 |
| HFcc | 52 | 50 | 3 | 1 | 46 | 66 / 23 | 43 | 6.8 / 8.9 | 0 | 15 |

U 종류:
- B: U2 4
- C: U1 10, U4 14, U2 3
- D: U1 8, U4 8, U2 1, U3 1
- E: U1 2, U2 3, U3 2
- F: U2 4
- HF: U1 7, U4 7, U2 3
- HFcc: U2 3

## 3. 조건별 비교(같은 100문항, 문항 단위 전이)

전체 문항 목록은 `comparison.json`의 `pairs`에 있다. O는 grounding_ok, X는 불일치다.

| 비교 | 바뀐 조건 | O→O | O→X | X→O | X→X | 보고 분류가 바뀐 문항 |
|---|---|---:|---:|---:|---:|---:|
| A→B | thinking 끄기 (522, 조건 계층 켬) | 48 | **36** | 6 | 10 | 45 |
| B→C | 조건 계층 끄기 (522, think off) | 28 | **26** | 0 | 46 | 26 |
| C→HF | 실행 경로: Ollama Q4_K_M·Ollama template·Ollama client → HF BF16·HF template (thinking 끔, 조건 계층 끔) | 20 | 8 | **17** | 55 | 41 |
| E→F | thinking 끄기 (870, 조건 계층 켬) | 48 | **31** | 9 | 12 | 46 |
| D→C | thinking 끄기 (522, 조건 계층 끔) | 26 | **43** | 2 | 29 | 60 |
| A→D | 조건 계층 끄기 (522, think auto) | 69 | 15 | 0 | 16 | 19 |
| HF→HFcc | 조건 계층 켜기 (HF 경로) | 37 | 0 | 15 | 48 | 14 |
| B→F | prompt·코드 522·c1f2a08 → 870·T2PC (think off) | 43 | 11 | 14 | 32 | 29 |
| A→E | prompt·코드 522·c1f2a08 → 870·T2PC (think auto) | 70 | 14 | 9 | 7 | 19 |

해석은 큰 차이에 한정한다. 셀당 1회 실행이므로 몇 문항 차이는 해석하지 않는다.

- **thinking.** 끄면 두 prompt 모두 크게 떨어진다(522: −30, 870: −22).
  - 첫 응답의 계약 유효성이 87→69(522), 92→77(870)로 떨어진다.
  - 실패한 문항의 grounding 차이 키는 `no_grounding`(B 19, F 18)과 dimension_target·places가 많다.
  - think off 셀에서 많은 실패 코드: UNGROUNDED_SCOPE, NO_OPERATOR, INVALID_CONCEPT, MISSING_CONCEPT_VALUE, UNUSED_CONCEPT.
- **조건 계층.** think off에서 끄면 −26이고, 바뀐 문항은 모두 O→X다.
  - C의 불일치 키는 factor:date 28, taxi_type 8, taxi_status 7이다. U4(조건 값 변경) 14, U1(조건 누락) 10이 생겼다.
  - think auto에서 끄면 −15다(A→D). HF 경로에서 켜면 +15다.
  - 조건 계층은 모델 출력 뒤에서 동작하므로 첫 응답은 같다(A=D, B=C 100/100).
- **실행 경로(C→HF).** 순 +9이지만 25문항이 바뀌었다.
  - 첫 응답의 raw 유효성은 69 대 66, 일치는 20 대 23으로 비슷하다.
  - 같은 thinking 끔 조건이라도 두 경로의 출력은 문항마다 다르다.
  - 원인 후보는 양자화(Q4_K_M 대 BF16), chat template 차이(아래 4 token), 생성 구현(Ollama 대 HF greedy)이다. 셋을 이 측정으로 나눌 수 없다.
- **함께 작용.**
  - think auto는 조건 계층이 없어도 69다(D). think off는 조건 계층이 있어도 54다(B).
  - 두 조건의 효과는 서로 독립적이라고 볼 수 없다. 예를 들어 thinking이 날짜·상태 표현을 스스로 맞히면 조건 계층이 교정할 몫이 줄어든다.
  - 그래서 "35 대 84"를 조건 하나의 효과로 나눠 적지 않는다.

### 3.1 thor 기준선 재현(HF)

- 이 장비의 재현값은 37이고 thor 기록은 35다. thor가 맞힌 35문항은 모두 이번에도 맞았다. 추가로 맞은 문항은 001, 065다.
- thor가 Base 원응답을 커밋한 5문항(001, 002, 004, 008, 084)을 비교했다.
  - 3문항은 첫 응답이 바이트 단위로 같다.
  - 001은 이번 응답에 `date: weekend`가 더 있다. 그래서 정답과 일치했다.
  - 002는 concepts만 다르고 결과는 같다(둘 다 불일치).
- 같은 모델 revision, 코드, prompt, decoding에서 greedy 출력이 일부 다르다. 원인 후보는 장치·커널 수치 차이(Thor sm_110 대 Ada sm_89), torch 2.13 대 2.11, SDPA 구현 차이다. 원인은 정하지 않았다.

### 3.2 chat template 불일치(토큰 수 수준)

`template_token_check.json`: 첫 계획 호출에서 Ollama `prompt_eval_count`와 HF `apply_chat_template` 토큰 수를 비교했다.
- think off(Ollama `think=false` 대 HF `enable_thinking=False`): Ollama가 100/100문항에서 **4 token 더 길다**.
- think 미지정(Ollama) 대 HF 기본 template: 100/100문항에서 2 token 더 길다.
- 두 template은 같지 않다. 바이트 단위 차이는 Ollama가 렌더링 결과를 돌려주지 않아 확인하지 못했다.
- 학습은 HF template(`enable_thinking=False`)으로 한다. 이 차이를 해결하거나 측정하기 전에는, Ollama에서 잰 학습 모델 결과를 학습 조건과 같은 조건이라고 할 수 없다.

### 3.3 미처리 예외(현재 코드)

- think off의 문항 057 첫 응답이 `geoflow/grounding.py:423` `hoist_condition_concepts`에서 `TypeError: unhashable type: 'dict'`를 일으켰다.
  - subtype 없는 OBJECT 개념의 dict `value`를 set 멤버십으로 검사하는 부분이다.
- 이 파일은 c1f2a08 이후 바뀌지 않았다. 기록된 원출력을 현재 HEAD 코드로 다시 통과시켜도 같은 예외가 난다.
- 운영 경로에서는 PlannerError가 아닌 예외로 올라온다.
- SEMANTIC_CODE이므로 고치지 않았다.

## 4. 학습 모델의 비교 기준

thor처럼 nonthinking으로 학습한다면 같은 조건의 기준은 **F**(qwen3:8b + T2PC 코드·prompt 87048d0c, think=false, 조건 계층 켬, Ollama Q4_K_M)다.

| 지표 | F |
|---|---:|
| grounding_ok | 57/100 |
| 정상 답변 | 55 |
| 용납할 수 없는 실패 | 4 (모두 U2) |
| U가 아닌 조용한 오답 | 2 |
| 안전한 실패 | 39 |
| 정당한 거부 | 0 |
| 지연 중앙값 / p90 | 7.3 / 8.2초 |

- 참고로 같은 prompt·코드에서 think 미지정인 E는 79(정상 84)다.
- 학습 결과를 HF로 평가한다면 HF 경로의 87048d0c 셀이 필요하다. 이번에는 thor 재현(522aa3b1)만 HF로 쟀다.

## 5. 학습 결과를 운영 조건으로 평가하려면 아직 필요한 것

1. **GGUF 변환과 Ollama 등록.**
   - merged HF → GGUF(llama.cpp `convert_hf_to_gguf.py`) → 양자화(qwen3:8b와 같은 Q4_K_M을 쓸지 선택) → Modelfile → `ollama create`.
   - `ollama create`는 공유 Ollama 서버의 상태를 바꾸므로 실행 전 승인이 필요하다.
   - 양자화 효과를 분리하려면 Base Qwen3-8B@b968826d도 같은 변환·양자화로 등록해 F와 비교한다. Ollama 라이브러리 qwen3:8b가 같은 revision의 변환인지는 알 수 없다.
2. **chat template 일치 확인.**
   - Modelfile template을 HF `enable_thinking=False` 렌더링과 바이트 단위로 맞춘다. 현재 4 token 차이가 있다.
   - 확인 방법: 같은 messages의 Ollama `prompt_eval_count`와 HF 토큰 수 비교(이번 방법), 가능하면 raw 모드 요청으로 렌더링 결과를 대조한다.
3. **think 설정.** 평가 harness의 `--model-think off`(이번에 추가). CLI의 `--model-think off`도 같은 조건이어야 한다.
4. **검증 명세 추가.** 측정한 뒤 `GEOFLOW_VERIFIED_SPECS`에 새 조합을 넣는다(모델 digest, prompt 87048d0c, 코드 지문, settings에 think off). 지금 settings의 think는 None(미지정)이다.
5. **HF 기준 셀.** 학습 직후 HF로 평가하려면 HF·87048d0c·조건 계층 켬 셀(Base)이 필요하다. thor runner는 522aa3b1 prompt hash를 검증하므로 그대로 쓸 수 없다.
6. **반복 측정.** 셀당 1회다. 학습 효과를 판단할 때 문항 단위 차이를 해석하려면 같은 셀의 재실행 변동을 따로 재야 한다. 이번에는 A와 D의 첫 응답 일치(100/100)만 확인했다.

## 6. 선택지 (a)·(b)·(c) 판단에 바뀌는 것

학습 효과는 추정하지 않는다. 이 측정이 바꾸는 판단 자료만 적는다.

- **(a)·(b) 공통.**
  - nonthinking 학습의 비교 기준은 79·84가 아니라 F 57이다.
  - 같은 모델에서 thinking만 켜도 79다(E). 그래서 "nonthinking 학습 모델 대 thinking Base(E)"와 "nonthinking 학습 모델 대 nonthinking Base(F)" 중 어느 비교로 채택을 판단할지 정해야 한다.
  - 운영 지연은 think off가 짧다(중앙값 7초 대 12초).
- **(a).**
  - thor 기준선(35)은 이 장비에서 거의 그대로 재현된다(37, thor 35문항 전부 포함). thor의 평가 경로를 HF 비교 기준으로 쓸 수 있다.
  - 다만 HF와 Ollama의 결과가 문항 단위로 다르고(25문항) template도 4 token 다르다. HF 결과를 운영 결과로 옮겨 말할 수 없다. 5절 1·2가 선행 조건이다.
- **(b).** 바뀌는 것 없다. 정책 결정과 평가 셋 재정의가 여전히 선행 조건이다.
- **(c).** 현재 기본(qwen3.8:27b T2PC)은 이 측정의 대상이 아니다. qwen3:8b + T2PC는 think 설정과 관계없이 검증하지 않은 조합으로 남는다.

## 7. 산출물

| 경로 | 내용 |
|---|---|
| `check_request_bytes.py`, `request_check_522aa3b1.json`, `request_check_87048d0c.json` | 기본 요청 불변 확인 |
| `run_ollama_cells.sh`, `runs/` | Ollama 셀 실행과 기록(B·C는 `*_resume.log` 포함) |
| `hf_thor_base.py`, `run_hf_cells.sh`, `hf/` | HF 셀 실행, thor runner raw·runtime·receipt, 변환한 `dev.json` |
| `compare_cells.py`, `comparison.json` | 같은 기준 채점과 셀 쌍 전이 표(문항 id 포함) |
| `template_token_check.json` | Ollama·HF 프롬프트 토큰 수 비교 |
| `env/` | GPU UUID 확인, HF 환경과 모델 파일 hash, pip freeze |

model weights, venv, HF cache는 저장소 밖 `/home/hwkim/sftdpo_work`에 있으며 커밋하지 않았다.
