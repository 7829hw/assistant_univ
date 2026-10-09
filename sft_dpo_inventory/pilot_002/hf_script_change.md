# 원격이 바꾼 HF 평가 스크립트 확인(2026-10-09)

모델 호출·측정 없음. 다른 세션의 커밋과 파일은 고치지 않았다. 비교 기준은 pilot_002 측정 때의 판(공통 조상 `b5f1423`)과 지금 판(`d0ac84a` 이후)이다.

## 1. 무엇이 바뀌었나

세 파일 모두 `ce2235d`(path_repeat_001, 결정 56: "평가 harness에 sampling·호출 seed 규칙·환경 기록 옵션") 한 커밋에서 바뀌었다.

| 파일 | pilot_002 측정 판(blob) | 지금 판(blob) |
|---|---|---|
| `sft_dpo_inventory/thinking_prep_001/hf_thinking.py` | `96307d14` | `c677d061` |
| `sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py` | `df0c88dc` | `4a76c286` |
| `evaluate_vendor100.py`(HF 스크립트가 import하는 채점 모듈, Ollama 평가 harness) | `71098dfe` | `0715b7a7` |

**`hf_thinking.py`**
- `ThinkingClient.chat`의 본문을 `chat_response(client, messages)` 함수로 옮겼다.
- `client.sampling_call`(`{"seed", "params"}`)이 있으면 `generate(..., sample=True, seed=, sampling=params)`로 표본을 뽑는다.
  없으면 예전과 같이 `generate(messages)`(greedy)다.
- `generate`에 `sampling=` 인자가 생겼다. sample일 때 `sampling or SAMPLING`을 쓴다. greedy 분기(`do_sample=False`)는 같다.
- 로그·응답에 `sampling_seed`는 sampling 호출에만 붙는다.

**`hf_eval_thinking.py`**
- 새 옵션: `--do-sample --temperature --top-p --top-k --seed`(모두 함께 줘야 함), `--record-env`.
- chat wrapper가 문항 안 호출 순번을 세고, sampling일 때만 호출마다 `EV.call_seed(회차 seed, 문항 id, 순번)`을 `client.sampling_call`에 넣는다.
  호출 뒤에는 `sampling_call = None`으로 되돌린다.
- 원문 기록 줄과 meta `decoding`은 sampling일 때만 달라진다(`sampling_seed`, sampling 설정). `--record-env`이면 meta에 `environment`가 더해진다.

**`evaluate_vendor100.py`**
- `SEED_RULE`, `call_seed`, `sampling_settings`, `_SeededClient`, `environment_record`, 새 옵션(`--temperature --top-p --top-k --seed --record-env`)을 더했다.
- 옵션을 주지 않으면 요청 options(`temperature 0`), 실행 명세(`run_spec`)와 그 hash, 기록은 예전과 같다(주석과 테스트).
- 채점 함수(`grounding_check`, `score`, `axes_rows`, `grounding_layers` 등)는 바뀌지 않았다.

## 2. 영향 판단

| 항목 | 기본(greedy, 새 옵션 없음) | 새 옵션을 줄 때 |
|---|---|---|
| 생성 입력(prompt 렌더링) | **영향 없음.** `render_prompt`·`training/inference.py`·chat template 설정은 바뀌지 않았다 | 영향 없음 |
| 생성 설정 | **영향 없음.** `do_sample=False`, max_new_tokens 8192, seed 42 그대로. Ollama는 `temperature 0`만 보낸다 | 바뀐다(sampling, 호출별 seed) |
| 출력 해석(thinking 분리, 응답 구성) | **영향 없음.** `split_thinking`과 응답 dict가 같다 | 기록에 `sampling_seed`가 더해질 뿐 해석은 같다 |
| 채점 | **영향 없음.** 채점 함수가 바뀌지 않았다 | 영향 없음 |

근거:
- 원격이 더한 테스트 `tests/test_path_repeat_sampling.py`(rebase 뒤 전체 1286개 통과):
  - `test_default_chat_is_greedy_as_before`: 옵션이 없으면 `generate`가 인자 없이 불리고 응답·로그가 예전 형식과 같다.
  - `test_default_requests_spec_and_records_are_unchanged`: Ollama 요청 options가 `{"temperature": 0}`뿐이고, `run_spec`과 hash, pipeline meta가 같다.
  - `test_e_record_spec_is_reproduced`: 기존 E 기록의 명세 hash를 지금 코드가 그대로 만든다.
- 이 작업에서 추가로 확인(모델 호출 없음):
  - pilot_002 Ollama 기록 4개(업체 100 Ollama-sft·Ollama-final, aux Ollama-final·E)의 `run_spec`을 지금 코드로 다시 만들었다. 명세와 hash가 모두 같았다.
  - pilot_002 판정(`vendor100/judge.py`)과 aux 비교(`aux_test/compare_aux.py`)를 지금 코드로 다시 채점했다. 내용이 같았다(`rebase_20261009.md` 3절).

**결론: 이 변경은 기본(greedy) 실행의 생성 입력·생성 설정·출력 해석·채점 어디에도 영향을 주지 않는다.**
- 그래서 이 스크립트 변경 때문에 HF-E 기준값을 다시 잴 필요는 없다.
- 단, 앞으로 HF 경로를 **sampling 옵션으로** 비교한다면 그 비교는 greedy 기준값(HF-E 84)과 다른 조건이다. 같은 sampling 설정의 기준값이 따로 필요하다.
- 별개의 사실(스크립트 변경과 무관): path_repeat_001은 새 장비(RTX PRO 6000 Blackwell)에서 HF greedy 첫 응답이 기존과 0/100 일치했다고 기록했다(`3797d1e`).
  이것은 장비 변경 때문이며, 이 문서의 판단 대상이 아니다. 기존 장비(RTX 6000 Ada)의 기준값에는 해당하지 않는다.

## 3. 각 셀이 측정된 판

결과 meta의 `code_commit`은 측정 때의 HEAD다. pilot_002의 커밋은 그 뒤 rebase로 SHA가 바뀌었다(대응표: `rebase_20261009.md` 4절).
아래 blob은 그 커밋의 파일 내용이다.

| 셀 | 스크립트 | meta `code_commit`(측정 때) | rebase 뒤 같은 커밋 | `hf_eval_thinking.py` | `hf_thinking.py` | `evaluate_vendor100.py` | 장치 |
|---|---|---|---|---|---|---|---|
| HF-E(업체 100 기준값 84) | `hf_eval_thinking.py` | `0215c156` | 같음(원격에 있음) | `df0c88dc` | `96307d14` | `71098dfe` | GPU 2 |
| pilot_002 업체 100 HF-sft | `hf_eval_thinking.py` | `426cc8c` | `61caefe` | `df0c88dc` | `96307d14` | `71098dfe` | GPU 3 |
| pilot_002 업체 100 HF-final | `hf_eval_thinking.py` | `0c0b9a1` | `d439ba5` | `df0c88dc` | `96307d14` | `71098dfe` | GPU 3 |
| aux_test_v1 HF-E(기준값 27) | `pilot_prep_005/sets/eval_set.py` | 기록 없음(완료 2026-10-08 02:39) | – | – | `96307d14`(아래) | `71098dfe`(아래) | GPU 2 |
| pilot_002 aux HF-sft·HF-final | `eval_set.py` | 기록 없음(완료 2026-10-09 05:15·07:11) | – | – | `96307d14`(아래) | `71098dfe`(아래) | GPU 3 |
| pilot_002 selection_v1·valid98 | `eval_set.py`, `pilot_001/valid98/eval_valid98.py` | 기록 없음 | – | – | `96307d14`(아래) | `71098dfe`(아래) | GPU 2·3 |
| pilot_002 Ollama 셀 | `evaluate_vendor100.py` | `4e75021`(sft), `428ba40`(final) | `0a669e5`, `4a430f4` | – | – | `71098dfe` | Ollama GPU 2 |

- `eval_set.py` 결과 meta에는 커밋이 없다. 이 장비의 로컬 브랜치에는 2026-10-09 rebase 전까지 `ce2235d`가 없었고(원격 커밋은 다른 장비에서 만들어짐),
  그 사이 로컬 커밋의 `hf_thinking.py`·`evaluate_vendor100.py`는 모두 `96307d14`·`71098dfe`다. 그래서 위 셀도 바뀌기 전 판으로 쟀다고 본다.
  작업 트리의 커밋 안 된 수정 여부는 기록으로 확인할 수 없다.
- 모든 HF 셀의 실행 의미 코드 지문은 `791c4a68`이다(meta).
- `training/trainer_common.py`는 HF-E(`0215c156`)와 pilot_002 사이에 바뀌었지만(로컬 커밋 `2e557b3`, 학습 데이터 읽기), HF 생성이 쓰는 `render_prompt`는 같다.
