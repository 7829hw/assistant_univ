# 이식 대상 조사(W2) — `geoflow/partial-grounding`(ab9d215) → `geoflow/sft-dpo-t2pc`

작성: 2026-10-15(pilot_006 준비 세션 1). 코드 변경 없음. partial-grounding 브랜치는 `git show`로만 읽었다.
따르는 결정: 111(D6, `grounding_target` 뒤에 둠, Full 경로·`SEMANTIC_CODE` 지문 `791c4a68` 불변, 이름 바꿈), 지시 3절, 4절 W2·W3.

## 0. 범위와 "26개"

- 두 브랜치의 merge-base는 `d0ac84a`(2026-10-08, path_repeat_001)다(유일). 그 뒤 trunk 162커밋, partial-grounding 98커밋.
- **merge-base 기준으로 두 브랜치에서 모두 바뀐 파일은 6개다**: `CLAUDE.md`, `evaluate_vendor100.py`, `tests/test_operational_controls.py`,
  `sft_dpo_inventory/DECISIONS.md`, `sft_dpo_inventory/batch006/candidates_draft.yaml`, `sft_dpo_inventory/batch006/write_drafts.py`.
- 지시와 계획서 v2 4.2절의 "공통 파일 26개"는 이 기준으로 재현되지 않는다. v2가 함께 적은 `training/data/build_thinking.py`, `training/data/thinking.py`는
  partial-grounding에서 바뀌지 않았다(merge-base와 같음). `geoflow/grounding.py`, `geoflow/planner.py`, `training/trainer_common.py`, `training/inference.py`는
  partial-grounding에서만 바뀌었다(trunk는 merge-base와 같음). 아래 1절은 6개 공통 파일과 이 코드 4개, 그리고 테스트·설정 파일을 hunk 단위로 본다.
- trunk의 실행 의미 코드(`SEMANTIC_CODE` 범위 전체)는 merge-base 뒤로 바뀌지 않았다. 그래서 partial-grounding의 실행 의미 코드 = trunk + Partial 변경(grounding.py·planner.py)이다.
- `SEMANTIC_CODE`는 `geoflow/` 전체, `prompts/`, `schemas/` 등을 바이트로 지문에 넣는다. **이 범위 안에 파일을 고치거나 새로 더하기만 해도 지문이 바뀐다.**
  그래서 Partial 경로 코드는 지문 범위 밖(새 최상위 `grounding/` 패키지)에 둔다.

분류: (a) Partial 경로, (b) 학습 코드, (c) 평가·분석, (d) 기타. 처리: 가져옴 / 가져오지 않음 / 수동 반영.

## 1. 파일·hunk별

### 1.1 `geoflow/grounding.py`(partial-grounding만 변경, SEMANTIC_CODE)

| hunk | 내용 | 분류 | 처리 | 이유 |
|---|---|---|---|---|
| `parse_grounding` 첫머리 | `complete_grounding_payload(payload, notes)`를 hoist 전에 부름 | (a) | **수동 반영** | 원본 위치에 넣으면 Full 경로 함수가 바뀌고 지문이 바뀐다. Partial planner(`grounding/partial_planner.py`)가 parse 전에 completion을 부르게 한다. 완전한 payload에는 멱등이므로 Full 동작은 같다 |
| `_CONCEPT_OF_SUBTYPE`, `_inferred_fields`, `complete_grounding_payload` | subtype→concept, role, source, id 채움 | (a) | **가져옴(새 위치)** | `grounding/completion.py`로 옮긴다. 본문은 그대로, 머리 주석에 원본 경로·커밋 |
| `hoist_condition_concepts`의 `as_object` | concept이 비어 있으면 OBJECT로 본다(조건 값 개념을 factor로 옮김) | (a) | **수동 반영** | 원본 함수는 고치지 않는다. completion이 같은 조건(조건 값 subtype, 또는 subtype 없이 조건 값 value)에서 concept을 `OBJECT`로 채워, 기존 hoist가 같은 개념을 옮기게 한다. hoist가 옮기지 못하는 경우(같은 factor에 다른 값)는 원본에서 concept None, 이식본에서 OBJECT로 남아 거부 오류 코드가 다를 수 있다. W4 5 재현에서 문항 단위로 비교한다 |

### 1.2 `geoflow/planner.py`(partial-grounding만 변경, SEMANTIC_CODE)

| hunk | 내용 | 분류 | 처리 | 이유 |
|---|---|---|---|---|
| import | `complete_grounding_payload` | (a) | 가져오지 않음 | 1.1과 같음 |
| `_validate_payload` | 조건 대조(`reconcile_payload`) 전에 completion, notes를 `_parse`에 넘김 | (a) | **수동 반영** | `GeoFlowPlanner` 하위 클래스 `PartialPlanner._validate_payload`가 completion 뒤 부모를 부른다. 계획·재질의 모두 `_ask` → `_validate_payload`를 지난다 |
| `_parse(…, completion)` | `grounding.normalizations` 앞에 completion 기록 | (a) | **수동 반영** | 하위 클래스가 부모 결과의 `normalizations` 앞에 붙인다 |

### 1.3 `evaluate_vendor100.py`(두 브랜치 모두 변경)

| hunk(partial-grounding) | 분류 | 처리 | 이유 |
|---|---|---|---|
| `MODEL_STATES`에 `resident`, `resident_isolated`, `CONTINUOUS_STATES`, `RESIDENT_STATES` | (c) | 가져오지 않음 | Ollama resident 측정(PG-62·63). trunk는 결정 79의 연속 측정(`keep_loaded`)을 쓰고, PG 쪽 격리 검사는 불통과였다. pilot_006 평가는 vLLM 경로(결정 108) |
| `PrefixCacheReset` 클래스 | (c) | 가져오지 않음 | 같음 |
| `load_partial_rows`·`_continuity`의 resident 처리 | (c) | 가져오지 않음 | 같음 |
| `_RecordingClient(record_thinking)`·`--record-thinking` | (c) | 가져오지 않음 | Ollama trace 수집용. vLLM 수집(`collect6.py`)은 원문을 따로 남긴다 |
| `cmd_llm`의 `--planner-prompt`(`load_planner_prompt`) | (a)(c) | **수동 반영** | Partial prompt(P0.3)로 평가하려면 필요하다. vLLM 평가 client 사본(`pilot_006_prep/gpu/vllm_eval_partial6.py`)에 `--grounding-target`·`--planner-prompt`로 넣는다. `evaluate_vendor100.py`는 고치지 않는다 |
| `cmd_llm`의 시작 unload 분기(resident) | (c) | 가져오지 않음 | 같음 |
| trunk 쪽 변경(`--gold`, keep_loaded 기본, guard 등) | – | 그대로 | trunk 것을 유지 |

### 1.4 학습 코드

| 파일 | partial-grounding hunk | 분류 | 처리 | 이유 |
|---|---|---|---|---|
| `training/trainer_common.py` | `load_records`의 `contract == "p0"` 분기, `p0_system_prompt`, `_load_p0_records` | (b) | **가져오지 않음(이번 세션)** | 지시 W3: trunk 학습 코드 유지. pilot_006은 Full·Partial 두 arm이 같은 trunk 학습 코드(결정 86 by_source, `build_thinking`)를 쓴다. Partial arm에 필요한 것은 "system prompt가 Partial prompt인 thinking 레코드"를 trunk 검사에 통과시키는 분기 하나뿐이고, 그것은 데이터 판을 만드는 다음 세션(승인 뒤)에 `grounding_target` 설정 분기로 넣는다. `_load_p0_records`는 SFT만·답만 있는 레코드 혼합(Clean-Hybrid)을 전제로 해 결정 86 출처별 손실 범위와 맞지 않는다 |
| `training/inference.py` | `check_checkpoint_prompt`의 P0 adapter 분기 | (b) | 가져오지 않음(이번 세션) | 같은 이유. Partial adapter 평가는 vLLM 경로라 이 함수를 지나지 않는다 |
| `training/data/build_thinking.py`, `training/data/thinking.py` | 변경 없음 | – | – | partial-grounding에서 바뀌지 않음 |
| `training/configs/qwen3_8b_p0_sft00{1,2,4}_*.yaml` 6개 | p0_sft 실험 config | (b) | 가져오지 않음 | `contract: p0` 분기를 전제한다. 기록은 원 브랜치에 있다 |

### 1.5 테스트

| 파일 | 내용 | 처리 | 이유 |
|---|---|---|---|
| `tests/test_partial_grounding.py`(partial-grounding만) | completion 단위 테스트, pipeline 시험, EVENT 거부 회귀 | **수동 반영** | import 대상을 `grounding.completion`·`grounding.partial_planner`로 바꾼 새 파일 `tests/test_grounding_partial.py`. 원 테스트의 "parse_grounding이 직접 completion" 가정은 PartialPlanner 경유로 바꾼다 |
| `tests/test_operational_controls.py`(두 브랜치 모두) | PG: resident 상태·PrefixCacheReset 테스트, 지문 고정값 갱신 전제 | 가져오지 않음 | 1.3과 같다. trunk 쪽 변경은 그대로 둔다 |

### 1.6 문서·기타 공통 파일

| 파일 | 처리 | 이유 |
|---|---|---|
| `CLAUDE.md` | 가져오지 않음 | PG 규칙 "14. Resident Ollama runs"는 trunk 규칙 14(여러 세션)와 번호가 겹치고, trunk는 결정 79 연속 측정을 쓴다. PG 격리 검사 실패 기록은 `pg_imports` 참고 문서로만 남긴다 |
| `sft_dpo_inventory/DECISIONS.md` | 가져오지 않음(참조만) | PG 결정 57–87은 trunk 57–87과 **번호가 모두 겹친다**(지시 D6은 81–87만 적었다). 같은 원칙으로 PG 결정 57–87 전체를 `PG-57`–`PG-87`로 부른다. 원문은 `ab9d215:sft_dpo_inventory/DECISIONS.md`. pg_imports README에 대응표 |
| `sft_dpo_inventory/batch006/*`(같은 이름, 내용 다름) | **가져옴(이름 바꿈)** | PG batch006(Gap A·B 43 + Gap C 10, `approved.jsonl` 43행)은 `pg_imports/pg_batch006/`으로, id `b006-NN` → `pg-b006-NN`. trunk batch006(실차 대조 28건)은 그대로 |
| `sft_dpo_inventory/path_repeat_001/cell_guard.py`, `resident_lib.sh` | 가져오지 않음 | resident Ollama 도구 |

## 2. partial-grounding에만 있는 디렉터리

| 위치(ab9d215) | 파일 수 | 분류 | 처리 | 새 위치·이유 |
|---|---:|---|---|---|
| `evaluation/partial_grounding/replay_partial.py`, `analyze_replay.py`, `regression_event_refusal.yaml` | 3 | (c) | **가져옴(새 위치)** | `pilot_006_prep/integration/pg_tools/`. W4 5·6 재현에 쓴다. import는 `grounding.completion`으로 바꾼다(머리 주석에 원본·커밋) |
| `evaluation/partial_grounding/replay_result.json`, `replay_log.txt`, `analysis.txt` | 3 | (c) | 가져옴(참조 기록) | `pg_imports/replay/`. 재현 비교 기준(문항 단위) |
| `evaluation/partial_grounding/prompts/partial_p0*.yaml` | 4 | (a) | **가져옴(P0.3만 사용)** | `grounding/prompts/partial_p0_3.yaml`(SEMANTIC_CODE 밖). P0·P0.1·P0.2는 기록으로 `pg_imports/prompts/`에 둔다. R2 참고 셀(J5)과 Partial arm 표본(J6)은 P0.3 |
| `evaluation/partial_grounding/ab_p0_3/contract_check.py`, `ab_valid98/contract_check.py` | 2 | (c) | 가져옴(새 위치) | `pilot_006_prep/integration/pg_tools/`. 구조 오류(MULTIPLE_MEASURES, NO_MEASURE 등) 측정 |
| `evaluation/partial_grounding/ab_p0*/analyze.py`, `ab_valid98/analyze.py`, `explore_*.py`, `root_cause.py` | 6 | (c) | 가져옴(analyze 계열만, 새 위치) | failure taxonomy. 실행 기록(runs/raw 450여 개)은 가져오지 않는다(원 브랜치에 있음, 다른 장비·HF/Ollama 경로) |
| `evaluation/partial_grounding/ab_p0*/runs`, `raw`, `smoke`, `resident_isolation/` 등 | 600여 | (c) | 가져오지 않음 | 참고값(지시 1절: 다른 장비·경로). 필요하면 `git show`로 읽는다 |
| `evaluation/partial_grounding/contract_review/` | 5 | (d) | 가져오지 않음 | 계약 검토 기록. 참고 |
| `sft_dpo_inventory/p0_sft_004/define_subsets.py`, `subsets.json` | 2 | (c) | **가져옴(새 위치)** | `pilot_006_prep/integration/pg_tools/`. dimension_target·od_role·implicit endpoint 부분집합 정의 |
| `sft_dpo_inventory/p0_sft_004/analyze.py`, `recall.py` | 2 | (c) | 가져옴(새 위치) | 구조 오류·first-response 측정 |
| `sft_dpo_inventory/p0_sft_004/loss_mask_audit.py`, `p0_sft_002/loss_mask_audit.py` | 2 | (c) | 가져옴(새 위치) | loss-mask audit. `_load_p0_records`(가져오지 않음)를 부르는 부분은 trunk `load_records` 경로로만 쓸 수 있다고 머리 주석에 적는다 |
| `sft_dpo_inventory/p0_sft_00{1,2,3*,4}/` 나머지(PLAN·REPORT·학습 기록·평가 결과) | 약 200 | (d) | 가져오지 않음 | 기록은 원 브랜치에 있다. 보고서 두 개(p0_sft_004, batch006)만 `pg_imports/reports/`에 둔다 |
| `sft_dpo_inventory/reviewed_reasoning_v001/` | 11 | (d) 데이터 | **가져옴** | `pg_imports/reviewed_reasoning_v001/`(dataset.jsonl 154행, manifest, REPORT, canonical_* 포함). 승인 상태 그대로, 새 승인 아님 |
| `training/generated/reviewed_gold_v006_p0/` | 2 | (d) 데이터 | **가져옴** | `pg_imports/reviewed_gold_v006_p0/`(sft_train.jsonl 154행, manifest). trunk `reviewed_gold_v006_t2pc`와 같은 v006이지만 내용이 다르다 |
| `training/generated/p0_sft_00*/`, `thinking_traces/` | 50 | (d) | 가져오지 않음 | p0_sft 학습 판. 원 브랜치에 있다 |
| `sft_dpo_inventory/batch006/approved.jsonl` 등 | 10 | (d) 데이터 | 가져옴(이름 바꿈) | 1.6 |

## 3. 정리

- Full 경로 파일(`geoflow/`, `prompts/`, 학습 코드)은 하나도 고치지 않는다. Partial 경로는 `grounding/`(새 패키지)과 평가 client 사본에만 있다.
  기본값 `grounding_target: full`이면 새 코드는 불리지 않는다.
- 이식으로 Full 경로 변경이 꼭 필요한 hunk는 없다(지시 7절 멈춤 조건 아님). 차이가 생길 수 있는 곳은 1.1의 hoist 수동 반영 하나이고, W4 5에서 문항 단위로 확인한다.
- 이름 충돌: batch006(`pg_batch006`, `pg-b006-NN`), reviewed_gold_v006(`_p0`은 `pg_imports` 아래), 결정 번호(PG 57–87 전체를 `PG-NN`).
