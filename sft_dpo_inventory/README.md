# SFT·DPO 자산의 T2PC 이식성 조사 (sft_dpo_inventory)

작성: 2026-10-05. 조사와 설계만 했다. 학습, GPU 사용, 모델 호출, prompt 변경은 하지 않았다.

## 0. 요약

**질문 1: thor의 자산을 현재 T2PC 조건(qwen3:8b + T2PC 코드·prompt 87048d0c, 조건 계층 켬)으로 옮길 수 있는가.**
- **라벨 자체는 현재 계약에서 유효하다.** reviewed gold SFT 35건은 parse → compose → validate를 normalize=False와 True에서 모두 통과했다. DPO 32쌍의 chosen도 모두 통과했고, thor가 기록한 판정은 35/35, 32/32 그대로 재현됐다.
- **데이터 파일은 그대로 쓸 수 없다.**
  - prompt가 바뀌어 학습 입력이 레코드마다 542 token 늘었다. 67건 모두 pilot003 한도(7040)를 넘는다.
  - thor 도구는 실행 중 prompt hash를 계산해 manifest와 대조하므로, v003 복원(`assembly_recipe`)은 87048d0c에서 거부된다. 새 판으로 다시 만들어야 한다.
- **도구는 대부분 재사용할 수 있다.** 단 thor가 production 파일 `geoflow/aggregation.py`에 `to_flat`을 추가했다. 합치면 실행 의미 코드 지문이 `97efa866…`에서 `1d3f133c…`로 바뀐다. 그러면 T2PC 검증 명세와 맞지 않게 된다.
- **조건 계층이 DPO 쌍 일부의 의미를 바꾼다.**
  - 3쌍은 조건 계층을 거치면 rejected가 chosen과 같아진다.
  - 1쌍은 parse에서 실패하던 rejected가 조건 계층의 날짜 교정 뒤 실행 가능해진다. 장소를 버린 다른 의미의 답이다.

**질문 2: 옮기면 무엇이 부족한가.**
- qwen3:8b + T2PC 기록(136문항)의 실제 오류는 thor coverage와 거의 겹치지 않는다.
- **용납할 수 없는 실패 16건**의 중심:
  - 통행량을 실차 구간으로 오독(passage_count→trip_count, 5건)
  - taxi_status 누락(7건)
  - dimension_target 오류(8건)
  - od_role 오류
- **조용한 오답** 중 U가 아닌 6건: dimension 단위(시군구↔읍면동)와 질문에 없는 집계를 지어낸 경우.
- **reviewed gold에 없는 것**:
  - passage_count 측정값: 0건
  - taxi_status 조건: 0건
  - time 조건: 0건
  - 지원 불가 질문에 대한 T2PC식 target(조건을 grounding으로 적고 코드가 멈추는 것): 0건
  - dimension_target: train 4건, DPO negative는 validation에만 있음
  - "집계어 없음 → 집계를 적지 않음"과 dimension 단위를 다루는 negative 종류: 없음
- 평가 조건도 맞지 않는다.
  - thor 기준선은 HF BF16, thinking 끔, 조건 계층 끔이다.
  - dev-v2 qwen3:8b 기록은 Ollama Q4_K_M, think 미지정(실제로 100% thinking 생성), 조건 계층 켬이다.
  - 같은 prompt 522aa3b1과 같은 지표인데 업체 100 기준 35 대 84로 다르다(6절). 원인은 정하지 않았다.

## 1. 작업 조건과 재현

| 항목 | 값 |
|---|---|
| 브랜치 | `geoflow/sft-dpo-t2pc`. `git fetch origin` 후 `origin/geoflow/dev-v2`에서 생성. 같은 이름이 로컬·원격에 없음을 확인했다 |
| 시작 commit | `a64eb50b9a46b9b65e826c26a96eca14f0bd5e58` (작업 트리 깨끗함 확인) |
| thor 참고 commit | `b3149040fb0fc57bedd1e8ff4436333f55d41e5a`(origin/geoflow/sft-dpo-thor, base `65e9ea2`). `git show`와 detached worktree로만 읽었다. merge·rebase·cherry-pick 없음 |
| 실행 의미 코드 지문(전) | `97efa866391a370a9fed797686e24b15ccdcafd398d71ecc51db704b8f7f2015` (64 files) |
| 실행 의미 코드 지문(후) | `97efa866391a370a9fed797686e24b15ccdcafd398d71ecc51db704b8f7f2015` (64 files). 같음 |
| prompt hash(계산으로 확인) | dev-v2 `87048d0c…`(15,579자), thor worktree `522aa3b1…`(14,628자) |
| Python 환경 | 세션 scratch venv(requirements.txt + transformers 4.56.2, torch 없음) |
| tokenizer | Qwen/Qwen3-8B@`b968826d…`의 tokenizer 파일 4개만 받음(weights 없음). `tokenizer.json`·`tokenizer_config.json` sha256과 chat template sha256이 thor 영수증과 같다 |

스크립트는 모두 `sft_dpo_inventory/`에 있다. 산출물은 `sft_dpo_inventory/generated/`에 쓰며 커밋하지 않는다(로컬 `.gitignore`).

```bash
python sft_dpo_inventory/check_reviewed_gold.py
python sft_dpo_inventory/token_lengths.py --tokenizer-dir DIR [--thor-root THOR_WORKTREE]
python sft_dpo_inventory/error_types.py && python sft_dpo_inventory/coverage_gap.py
python sft_dpo_inventory/leakage_recheck.py --thor-root THOR_WORKTREE
python sft_dpo_inventory/policy_scale.py
python sft_dpo_inventory/vendor_compare.py
```

| 산출물(커밋 안 함) | sha256 |
|---|---|
| generated/reviewed_gold_check.json | `56fb907ef086c79fc14fd65c14a35d6df7eec3732631ca6152a52ee17a6f678a` |
| generated/token_lengths_87048d0c.json | `8609f27386d7012513b39115968f868ec57fe5d52612edfa061214dec4bd7d1e` |
| generated/error_types_v13_model_name_only.json | `1967d9124bc797d484cae5804ebb822b41088121551fdf7a6252aeba5f88a44e` |
| generated/coverage_gap.json | `2f2107a5f2b4f20de0432903caa3181806853319b88f715e110fd5cc04fc39bd` |
| generated/leakage_recheck_v003.json | `db407dc06be0a80cc4d2c81b98e9dcf38c5a5df03fc9689e13220efb6eb3dea6` |
| generated/policy_scale.json | `473b76d3dadd772b4ead05f46a86a05ddeb0e07fc0ebc5cdbeff40455e406b86` |
| generated/vendor_compare.json | `07595224936cc68dc17c0dce7f0f47b3bbe0d2951f40fc615408e435a455afa7` |

산출물에는 보호 대상 질문 문장을 넣지 않았다. 남긴 것은 문항 id, 건수, 라벨 값(측정값 이름, od_role 등)뿐이다. thor reviewed gold의 질문(thor가 작성한 비보호 문항)은 `reviewed_gold_check.json`에 들어 있지 않다. id만 있다.

## 2. thor 브랜치 조사

### 2.1 재사용할 수 있는 도구와 입력 가정

| 도구 | 진입점 | 입력 가정 | dev-v2 의존성 | T2PC에서의 판정 |
|---|---|---|---|---|
| target 직렬화 | `training/data/canonicalize.py` `serialize_planner_target`, `check_shape`, `semantic_key`, `flatten_source` | flat 계약(`concepts`/`factors`) 또는 structured(`aggregation_plan`) dict. 계약 필드만 꺼내고 local id를 c1…로 바꾼다 | `flatten_source`가 structured source에서 `geoflow.aggregation.to_flat`(thor 전용)을 부른다 | flat source만 쓰면 그대로 쓸 수 있다. structured source를 쓰려면 `to_flat`이 필요하다. production 파일에 두면 지문이 바뀌므로 training 쪽으로 옮겨야 한다 |
| SFT builder | `python -m training.data.build_sft` (`sft_record`, `build`) | question-graph store(structured) 또는 flat YAML list(`parent_intent`/`family`, `reviewed_by`). `--strict` | system prompt는 실행 시점의 `GeoFlowPlanner(client=None).system_prompt()`(87048d0c가 자동 반영). 판정은 `assess(normalize=False)` | 재사용 가능. 다만 `assess`는 **조건 계층을 거치지 않는다**. 조건 계층이 의미를 바꾸는 target을 놓친다(3.3절. 이 조사의 `check_reviewed_gold.py` C/D 경로가 보완한다) |
| DPO builder | `python -m training.data.build_dpo` (`dpo_pair`, `build`), `negative_mutations.mutations` | SFT manifest의 `prompt_hash`가 실행 시점 prompt와 같아야 한다. prediction 파일도 같은 hash여야 한다 | `assess`로 semantic/constraint를 판정한다(조건 계층 없음) | 재사용 가능. 기존 v001–v003 manifest(522aa3b1)는 거부되므로 새로 만들어야 한다. negative 범주는 T2PC 경로에서 달라질 수 있다(3.3절) |
| leakage·split | `training/data/split.py`(`question_key`, `template_key`, `assign_groups`, `split_records`, `check_split`), `data/common.py`(`reserved_sources`, `protected_questions`, `check_source`), `annotations/inventory.py` `Protection` | 보호 원본 = registry corpus·question set과 부모, root `*questions*.yaml`, `stub_query*.yaml`, `evaluation/**/*.yaml`. 정규화 질문·id·template·semantic family로 막는다 | 순수 함수. ROOT 기준 경로 | 재사용 가능. 다만 vendor 형식 셋(`gold`/`gold_text`)은 `golden`/`grounding` 키가 없어 **template·family 지문을 만들지 않는다**. 질문·id만 보호된다(3.5절) |
| annotation inventory·candidates·mining·review batch | `annotations/inventory.py`, `candidates.py`(`blueprints`, `mine_predictions`, `failure_driven_candidates`, `semantic_negative_candidates`), `workflow.py`(`prepare`/`decide`/`import_reviewed`), `review_batch.py`(XLSX, compile 진단) | queue·decision JSONL, reviewer 기록. mining은 같은 prompt hash의 SFT 예측 | review_batch의 compile 진단은 mock·legacy, 기준일 2026-09-25를 쓰고 조건 계층은 거치지 않는다 | 재사용 가능. 추천·PASS를 승인으로 보지 않는 흐름이 이미 들어 있다. mining 입력은 새 prompt로 다시 생성해야 한다 |
| token 검증 | `data/analyze_tokens.py`, `trainer_common.render_records`/`render_prompt`, `v003_token_smoke.py`(Thor GPU) | config의 `chat_template_kwargs`(`enable_thinking: false`), 한도, +1 guard | 없음 | 측정 방식은 그대로 쓸 수 있다(이 조사에서 thor 기록 67/67 재현). 한도는 새 prompt에서 모두 초과한다(3.4절) |
| v003 복원 | `records/corpora/reviewed_gold_v003/assembly_recipe.py --restore-from` | prompt hash가 manifest(522aa3b1)와 같아야 한다 | 실행 시점 prompt | 87048d0c에서는 `Production prompt drift`로 멈춘다. 새 판(v004 등)으로 다시 만들어야 한다 |
| 평가·추론 | `evaluate_checkpoint.py`, `inference.HFClient`, `predict_groundings.py`, `pilot.evaluate` | HF 모델, `enable_thinking=False`, greedy | `GeoFlowPlanner(client=client)`(condition_check 기본 False). thor가 바꾼 `evaluate_planner.evaluate_once` 사용 | T2PC 평가에는 맞지 않는다. condition_check·기준일 고정이 없고, dev-v2의 `evaluate_vendor100` v4 축·U 정의와 지표가 다르다(5·6절) |

### 2.2 thor가 바꾼 production·공용 파일과 merge 가능성

| 파일 | 변경 | SEMANTIC_CODE |
|---|---|---|
| `geoflow/aggregation.py` | `to_flat(spec)` 추가(+21). 직렬화 전용 | 포함. **지문이 97efa866 → 1d3f133c로 바뀐다**(merge-tree 결과를 풀어 계산) |
| `evaluate_planner.py` | +161: client `chat` 관찰 래퍼, `composed`·`validation_codes`·`checked_rules` 기록, `execution_profile` 인자, `score_raw_grounding`, `summarize_grounding_metrics` | 미포함 |
| `.gitignore` | `training/generated/` 등 5줄 | 미포함 |
| `AGENTS.md` | 신규(브랜치·커밋 정책) | 미포함 |
| `tests/test_training_*.py` | 신규 10개 | 미포함 |

- `git merge-tree --write-tree origin/geoflow/dev-v2 origin/geoflow/sft-dpo-thor`의 결과는 **충돌 없음**이다(tree `44badfa`, `.gitignore`만 자동 병합).
- dev-v2는 65e9ea2 이후 `evaluate_planner.py`와 `geoflow/aggregation.py`를 바꾸지 않았다.
- 텍스트 충돌은 없지만 의미 충돌은 있다.
  - aggregation.py가 바뀌면 `assistant_cli.py`의 T2PC `code_fingerprint`와 달라진다. 그러면 CLI 머리말이 "다름"을 표시하고 `tests/test_cli_run_settings.py`의 지문 확인도 실패한다.
  - thor 테스트를 dev-v2 위에서 실행하지는 않았다. 특히 v003 token 한도 테스트는 새 prompt에서 통과하지 못할 것으로 보이지만 확인하지 않았다.

### 2.3 실행 조건 차이

| 항목 | thor pilot·업체 100 기준선 | dev-v2 B 기록(qwen3:8b, grounding_v9) | dev-v2 q8_T2PC 기록(grounding_v13) | 현재 T2PC 기본 |
|---|---|---|---|---|
| base commit | 갈라진 지점 65e9ea2. 기준선 시작 2872c36 | c1f2a08(65e9ea2의 조상) | 2f53c72 worktree | a64eb50(geoflow/·prompts/는 b62f6dc와 같음) |
| prompt hash | 522aa3b1 | 522aa3b1 | 87048d0c | 87048d0c |
| 모델·client | HF transformers `Qwen/Qwen3-8B@b968826d`, BF16·SDPA, Jetson AGX Thor | Ollama 0.34.4 `qwen3:8b` digest 500a1f06, Q4_K_M GGUF | 같음 | Ollama `qwen3.8:27b` digest aaee06c3 |
| thinking | 끔(`enable_thinking=False`, chat template에 빈 think block) | think 미지정(auto). 기록상 plan 호출 100/100에서 thinking 생성(`thinking_chars` 중앙값 2,264) | 미지정. heldout plan 호출 48/48에서 thinking 생성(중앙값 2,399) | 미지정 |
| condition_check | 끔 | 켬 | 켬(+`inherent_conditions`) | 켬 |
| 기준일 | 2026-09-25(compile. 조건 계층 끔) | 2026-09-25 | 2026-09-25 | harness 2026-09-25, CLI는 실제 날짜(명세 밖) |
| 재질의 | 기존 production pipeline repair, 같은 HF 모델 | pipeline repair 1회, 같은 Ollama 모델 | 같음 | 같음 |
| decoding | greedy, max_new_tokens 1024, repetition_penalty 1.0 | temperature 0(나머지는 Modelfile: top_k 20, top_p 0.95) | 같음 | 같음 |
| 격리 | 프로세스 안 HF 생성 | 문항마다 모델 내림 | 같음 | 평가는 문항마다 내림, CLI는 연속 실행 |
| provider | 기준선 mock·legacy. pilot은 synthetic reference provider(`pilot.py`) | mock·legacy | mock·legacy | mock·legacy |

출처:
- thor: `training/evaluations/vendor_100_baseline_001/REPORT.md`, `RESULTS.json` runtime, `training/configs/qwen3_8b_thor_pilot_003_*.yaml`, `training/pilot.py:121,235`
- dev-v2: 각 run의 `meta`, `assistant_cli.py` `GEOFLOW_VERIFIED_SPECS`

## 3. reviewed gold v001–v003의 현재 계약 유효성

v003은 누적 판이다. v001 14건과 v002 17건은 v003에 같은 질문·grounding으로 모두 들어 있다(14/14, 17/17). 그래서 v003의 SFT 35건(v001 14 + v002 3 + v003 18)과 DPO 32쌍을 검사했다. 학습 target은 `dataset_index.json`의 assistant 문자열이다. 35건 모두 YAML grounding과 같다.

### 3.1 parse → compose → validate

| 대상 | A: normalize=False | B: normalize=True | thor 기록 재현 | 정규화가 의미를 바꾼 것 |
|---|---:|---:|---:|---:|
| SFT 35 | 35 통과 | 35 통과 | 35/35 | 0 |
| DPO chosen 32 | 32 통과 | 32 통과 | 32/32 | 0 |
| DPO rejected 32 | (의도된 실패 포함) | – | 32/32(실패 단계·코드까지 같음) | – |

**현재 계약에서 실패한 reviewed gold는 없다.** 고칠 항목도 없다.

### 3.2 T2PC 운영 경로(stub client → planner → compose → validate → compile)

- **compile에서 17건이 멈춘다.** 코드는 `compile:UNVERIFIED_TIMS_CONTRACT`이고, 조건 계층을 켜도 꺼도 같다.
  - 해당 문항은 주·월 구간(bucket)과 rollup을 함께 쓰는 집계다.
  - mock·legacy 계약에서 "구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았다"로 멈춘다.
  - 라벨 결함이 아니라 실행 계약의 한계다. compiler는 65e9ea2 이후 바뀌지 않았다.
  - 이 17건은 SFT target으로는 유효하다. 하지만 실행 benchmark에서는 정상 답변이 될 수 없다.
- **조건 계층이 SFT gold를 바꾼 것은 없다**(의미 변경 0, 결과 변경 0, 교정·채움 기록 0).
- 현재 prompt 설명과 어긋날 수 있는 라벨 형태도 0건이다. 확인한 형태는 세 가지다.
  - trip_count·fare 측정값에 `taxi_status=occupied`
  - 질문에 그룹 단서가 있는데 bucket만 있음
  - trip 그룹에 dimension_target 생략

### 3.3 DPO 쌍의 T2PC 경로 결과

| 범주 \| T2PC chosen \| T2PC rejected | 쌍 수 |
|---|---:|
| semantic \| ok \| ok | 12 |
| semantic \| compile 정지 \| compile 정지 | 8 |
| semantic \| compile 정지 \| ok | 1 |
| constraint \| ok \| plan:MISSING_CONCEPT_VALUE | 5 |
| constraint \| ok \| compose:UNSUPPORTED_AGGREGATION_COMBINATION | 1 |
| constraint \| ok \| compose:UNDEFINED_MEASURE_AGGREGATION | 1 |
| constraint \| compile 정지 \| plan 또는 compose 실패 | 3 |
| **constraint \| ok \| ok** | **1** |

조건 계층(켬과 끔의 비교)이 바꾸는 쌍:

| chosen 출처 id / negative_type | 조건 계층 끔 | 조건 계층 켬 | 의미 |
|---|---|---|---|
| ann-cc38d74754ba7eab68a8 / factor_omission_taxi_type (semantic, train) | rejected ok, taxi_type 없음 | rejected에 taxi_type 채움 → **chosen과 같아짐** | 운영 경로에서 이 선호는 차이가 없다 |
| ann-56366f545130c8b38940 (RB003-03) / date_factor_relative_confusion (semantic, valid) | rejected last_week | last_month로 교정 → **chosen과 같아짐** | 같음 |
| ann-5c88583c249cfeba80ef (RB003-04) / date_factor_range_omission (semantic, valid) | rejected 날짜 없음 | 날짜 채움 → **chosen과 같아짐** | 같음 |
| ann-da98b3941dfa1c7ce800 / actual_model_multi_field_grounding_error (constraint, train) | rejected `plan:INVALID_FACTOR`(date '202608') | 날짜 교정 + taxi_type 채움 → **실행 가능(ok)** | chosen과 다르다: 장소 나래구 빠짐, answer=value 추가. 운영 경로라면 장소 조건을 버린 답이 실행된다. 범주가 constraint에서 실질적인 semantic으로 바뀐다 |
| 같은 chosen / actual_model_multi_field_grounding_error 두 번째 쌍 | `plan:INVALID_FACTOR` | `compose:UNSUPPORTED_AGGREGATION_COMBINATION` | 실패는 유지되지만 단계·코드가 다르다(장소 빠짐, dimension 추가) |
| ann-914c48dad91bc9a62ab4 (RB002-04) / actual_measure_date_source_grounding_error | `compose:UNUSED_CONCEPT` | 같음(날짜는 채워짐) | 결과는 같고 rejected의 date 값만 달라진다 |

### 3.4 token 길이(87048d0c)

측정 방식은 thor `analyze_tokens`와 같다(생성 prefix, JSON+EOS, +1 guard). 522aa3b1로 같은 측정을 하면 thor `token_lengths.jsonl`과 67/67 일치한다.

| | 522aa3b1 (thor) | 87048d0c (현재) |
|---|---|---|
| prompt token(SFT·DPO) | 6,739–6,789 | 7,281–7,331 (레코드마다 +542) |
| completion 최대 | 190 | 190(같음) |
| SFT total 최대 | 6,977 | 7,519 |
| DPO total 최대 / prompt 최대 | 6,978 / 6,789 | 7,520 / 7,331 |
| pilot003 한도(7040/6816/256) 초과 | 0 / 67 | **67 / 67** |
| pilot001·002 한도(6912/6784/256) 초과 | 7 / 67 | 67 / 67 |

새 최소 한도는 SFT 7519, DPO total 7520 / prompt 7331 / completion 188이다. Thor memory smoke는 7040까지만 검증됐다. 새 한도에서는 메모리 확인을 다시 해야 한다(이번에는 하지 않음).

### 3.5 보호 대상 재대조(thor 정책, dev-v2 기준 보호 원본 52개)

- **thor 정책 그대로: 0/35건이 걸린다.** 65e9ea2 이후 추가된 보호 셋 6개(v10 heldout·status, v12 final·measure, v13·v14 cli check)를 포함한 결과다.
- **확장 대조: 11/35건이 거친 semantic template·family를 공유한다.** 확장 대조는 vendor 형식 셋의 정답 호출을 `gold_grounding`으로 역산해 같은 지문을 만든 것이다.
  - 3건(ann-0d51b49a…, ann-9b222bf8…, ann-e645cbc1…)은 65e9ea2 이후 추가된 셋과 겹친다.
  - 3건은 업체 100과 겹친다.
  - thor family 기준은 측정값·OD·집계 factor만 보는 거친 기준이다. 겹침이 공통 부모의 증거는 아니다.
  - 다만 thor 정책은 vendor 형식 셋의 family를 아예 만들지 않는다는 점을 기록해 둔다.

## 4. 실제 오류 유형과 coverage

### 4.1 오류 분포(grounding_v13 같은 136문항, `model_name_only_report.json`의 분류를 그대로 재현)

| 분류 | B (qwen3:8b, 522aa3b1) | T2PC (27b) | **qwen3:8b + T2PC 코드·prompt** |
|---|---:|---:|---:|
| 정상 답변 | 77 | 107 | 77 |
| 조용한 오답(v4 "오답") | 12 | 0 | 22 |
| 그중 용납할 수 없는 실패 U | 7 | 0 | 16 |
| U가 아닌 조용한 오답 | 5 | 0 | 6 |
| 안전한 실패(실행 실패 + 부당한 거부) | 30 | 11 | 22 |
| 정당한 거부 | 17 | 18 | 15 |
| 정책·모호 라벨을 뺀 조용한 오답 | 10 | 0 | 20 |

qwen3:8b + T2PC 세부. 문항 id만 적는다. 이 기록의 질문 문장은 보호 대상이며 학습·annotation 후보로 쓰지 않는다.
- **U 16:**
  - 목록: c10b, heldout v12·v24, indepv2 n26, indepv4 k25, measure m02·m13·m14·m15·m16, od o01a·o01b·o02c, status s15·s26·s29
  - 표시: U2:dimension_target 8, U2:scope_pickup 7, U1:taxi_status 7, U2:scope 5, U3:tool 5, U2:scope_dropoff 2, U4:time 1
- **U가 아닌 조용한 오답 6:** heldout v27·v31·v46, indepv2 n11, measure m05·m08. m05·m08은 정책 라벨이다.
- **측정값 오독:**
  - passage→trip 5건: v12, m13–m16
  - trip→passage 2건: s13, s15
  - 기타 1건: m18
- **조건 계층:** 놓친 채움 3건(m13·m14·m16). 이는 trip 오독이 앞선 결과다.
- **거부 정확성:** 19건 중 14건. 조건을 버린 답 2건.

grounding 차이 키(정상이 아닌 문항, 최종 grounding 기준. 괄호는 첫 응답 기준):

| 키 | q8_T2PC 최종 (첫 응답) | B 최종 (첫 응답) |
|---|---:|---:|
| places(대부분 od_role) | 16 (24) | 14 (28) |
| factor:aggregation_spec | 15 (18) | 9 (13) |
| factor:dimension_target | 12 (13) | 6 (7) |
| factor:taxi_status | 8 (10) | 8 (12) |
| measure | 8 (8) | 6 (9) |
| factor:dimension | 7 (7) | 5 (6) |
| no_grounding | 5 | 12 |
| factor:date | 0 (21) | 1 (20) |

- 첫 응답에서 최종까지의 grounding 단계:
  - q8_T2PC: 차이→같음 27, 차이 유지 61
  - B: 차이→같음 40
- 날짜 차이(첫 응답 21건)는 최종에서 0건이다. 조건 계층이 질문 표현으로 교정했다.

q8_T2PC 세부 값(라벨 값만):
- dimension_target: pickup→없음 6, 없음→dropoff 3, 없음→pickup 2, pickup→dropoff 1
- od_role: 없음→pickup 5(통행량 질문을 trip으로 읽은 경우), dropoff→pickup 3
- 집계: 질문에 없는 집계를 지어냄 14, 바뀜 1
- taxi_status: occupied→없음 5, vacant→없음 1, 없음→occupied 2
- dimension: sigungu↔emd 4, 없음→단위 3

### 4.2 thor coverage와의 비교

| 실제 오류 유형(q8_T2PC) | 건수(최종 차이) | reviewed gold SFT train / valid | DPO negative train / valid | 비어 있는 곳 |
|---|---:|---|---|---|
| passage_count ↔ trip_count 측정값 | 7(U 6) | passage_count 0 / 0 | 0 / 0 (fare↔revenue, speed↔rpm만 valid에 1씩) | **passage_count gold 없음**. "실차 택시 통행량" 같은 표현도 없음 |
| taxi_status 누락·추가 | 8(U1 7) | taxi_status 0 / 0 | 0 / 0 | **taxi_status gold 없음**(occupied·vacant·stationary 모두) |
| dimension_target | 12(U2 8) | pickup 2·dropoff 2 / both 2·pickup 2·dropoff 2 | 0 / 4 | train negative 없음. 생략(=both) target은 valid에만 있음 |
| place od_role | 11 | od_role 장소 6개(4건) / 6개(3건) | od_role_confusion 2 / place_role 1 | "OD 역할 없는 장소"(통행량)와 "pickup으로 잘못 붙임"의 대조가 없음 |
| 지어낸 집계(집계어 없음) | 14 | 집계 없는 target 4 / 6 | 0 / 0 (stage swap·rollup 누락만) | **"집계어 없음 → 적지 않음" negative 없음** |
| dimension 단위(sigungu↔emd) | 7 | dimension 5 / 6 | 0 / 0 | 단위 대조 negative 없음 |
| time 조건 | 1 | 0 / 0 | 0 / 0 | **time gold 없음** |
| 날짜(첫 응답) | 21(최종 0) | 상대 4·범위 15 / 1·15 | 0 / 2 | 조건 계층이 최종에서 교정한다. 학습 대상으로 둘지는 판단이 필요하다 |
| 지원 불가·확인 요청(T2PC식: 조건을 grounding으로 적고 코드가 멈춤) | 부당한 거부 8, 조건 버린 답 2 | 0 / 0 | supported_false_refusal 등은 라이브러리에만 있고 v003에 0 | **T2PC 계약의 정지 target 없음.** 명시적 `{"unsupported":true}` gold도 0 |
| vacant_ratio, passage_count 측정값 | – | 0 / 0 | – | thor README가 적은 공백 그대로 |

참고:
- thor synthetic 라이브러리(`negative_mutations.py`)에는 measure_confusion, concept_confusion, event_subtype_confusion, role_*, factor_hallucination·omission, temporal_scope_confusion, vicinity_omission, od_pickup_dropoff_swap, od_role_confusion·omission, location_omission·confusion, region_hallucination, aggregation_confusion, bucket_confusion·omission, aggregation_stage_swap, rollup_omission, supported_false_refusal, unsupported_forced_support, source_confusion이 있다.
- dimension_target, dimension 단위, taxi_status, time 변형은 없다.
- 라이브러리는 source에 해당 필드가 있을 때만 negative를 만든다. 그래서 passage_count gold가 없으면 passage→trip negative도 생기지 않는다.

## 5. 정책을 바꿀 경우의 규모(계산만. 정책은 바꾸지 않았다)

대안: 개발 셋 일부를 family 단위로 학습에 쓴다. 정책·모호 라벨 제외는 measure m05·m08, final f08·f10·f16·f28·f49·f56의 8문항이다. 근거는 dev_report `policy_ambiguous`, label_audit의 policy_ambiguous·ambiguous·questionable, decisions.md D1–D4다.

| 셋 | 작성 | 문항(중복 제외) | family | 정책·모호 제외 후 | 유효 target(답 / 정지) | 정답 grounding 없음 | 거친 의미 family | v13 비교 셋 |
|---|---|---:|---:|---:|---|---:|---:|---|
| vendor100 | 업체(보호) | 100 | 100 | 100 | 100 / 0 | 0 | 53 | dev |
| old44 (v1 holdout) | Claude | 44 | 44 | 44 | 41 / 2 | 1 | 37 | old44 |
| contrast (v2) | Claude | 31 | 10 | 31 | 29 / 1 | 1 | 24 | contrast |
| indepv2 | Claude | 40 | 40 | 40 | 35 / 4 | 1 | 36 | indepv2 |
| indepv3 | Claude | 40 | 40 | 40 | 36 / 2 | 2 | 34 | indepv3 |
| indepv4 | Claude | 40 | 40 | 40 | 36 / 2 | 2 | 34 | indepv4 |
| at (v4) | Claude | 16 | 5 | 16 | 13 / 3 | 0 | 16 | at |
| stage_v7 | Claude | 15 | 4 | 15 | 12 / 3(확인 요청 포함) | 0 | 15 | – |
| heldout_v8 | Claude | 40 | 40 | 40 | 40 / 0 | 0 | 32 | – |
| od_v8 | Claude | 15 | 5 | 15 | 15 / 0 | 0 | 13 | od |
| heldout_v9 | Claude | 48 | 48 | 48 | 45 / 0 | 3 | 39 | – |
| heldout_v10 | Claude | 48 | 48 | 48 | 41 / 0 | 7 | 31 | heldout |
| status_v10 | Claude | 33 | 33 | 33 | 23 / 10 | 0 | 17 | status |
| measure_v12 | Claude | 20 | 20 | 18 | 16 / 2 | 0 | 13 | measure |
| final_v12 | Claude(하위 에이전트 라벨 점검) | 56 | 56 | 50 | 42 / 0 | 8 | 29 | final |
| cli_check_v14 | 다른 셋의 사본 | 0 | 0 | 0 | – | – | – | – |

- family 수는 id 줄기와 `contrast` 값으로 묶은 수다. 대조 셋이 아니면 문항마다 1 family이므로 상한에 가깝다.
- "유효 target"의 기준: 정답 호출에서 역산했거나 명시된 grounding이, 현재 계약에서 기대 결과와 맞게 통과하거나 멈추는 문항이다.
  - 역산 grounding의 source·implicit 관례는 평가 코드의 관례이며 사람이 검토한 annotation이 아니다(thor REPORT도 같은 경고를 남겼다).

시나리오(합계):

| 시나리오 | 문항 | family | 유효 target | 남는 평가 셋 기준 thor family 보호에 걸림 | 걸리지 않음 |
|---|---:|---:|---:|---:|---:|
| S0: Claude가 쓴 vendor 형식 셋 전부(업체 100 제외) | 486 | 433 | 453 | 268 (모두 업체 100 family와 겹침) | 185 |
| S1: v13 비교에 안 쓴 셋만(stage_v7, heldout_v8, heldout_v9) | 103 | 92 | 100 | 65 (업체 100과 42) | 35 |
| S2: v13 개발 셋에서 업체 100·final 제외 | 327 | 285 | 311 | 232 (업체 100과 198) | 79 |

- **남는 셋과 잃는 셋.**
  - S1은 grounding_v13 개발 비교(428문항)와 최종 56문항의 비교 기반을 잃지 않는다. 대신 v8·v9 이력 비교를 잃는다.
  - S2는 v13 개발 비교 셋 10개(old44, contrast, indepv2–4, at, od, heldout, status, measure)를 평가에서 잃는다. 남는 평가 셋은 업체 100과 final 56뿐이다.
  - S2에서 같은 셋을 family 단위로 반만 쓰면, 남은 반은 이전 기록과 같은 문항 집합이 아니게 된다. 과거 B·T2PC 기록과는 남은 family로 제한해야 비교할 수 있다.
  - final 56은 이미 결과를 본 기록이다. 최종 검증으로 다시 내세울 수 없으므로, 어느 시나리오든 새 평가 셋이 필요하다.
- **paraphrase corpus(registry 7개).**
  - 규모는 525문항, 155 intent다.
  - 그중 54 intent의 golden이 `{"unsupported":true}`다. 현재 T2PC 계약은 "표현할 수 있으면 grounding을 적는다"이므로 이 라벨은 다시 봐야 한다.
  - 현재 flat 계약을 통과하는 intent golden은 86이다.
- **structured_grounding·reference·retrieval·stub_v2 셋.** 134문항이고 라벨 형식이 달라 수만 셌다.

## 6. 평가 조건 차이가 결과에 미치는 영향(기존 기록만)

### 6.1 비교 가능 범위

- **같은 지표를 쓴다.** thor의 "vendor grounding semantic match"는 dev-v2 `evaluate_vendor100.grounding_check`를 최종 grounding에 적용한 값이고, dev-v2 기록의 `grounding_ok`와 같다.
  - dev-v2 v9 기록을 현재 코드로 다시 계산해도 84로 같다.
  - thor는 `evaluate_vendor100.py`를 바꾸지 않았다.
- **thor는 문항별 원응답을 저장소에 남기지 않았다**(ignored raw). 그래도 Base의 일치 문항 35개는 커밋된 목록에서 정확히 복원된다. Base 35 = 세 arm 중 하나라도 일치한 문항 수 = `all_fail` 65의 여집합이기 때문이다.
- thor의 다른 지표는 dev-v2 v4 축·U 정의와 다르다. 그래서 정상·조용한 오답·U로는 thor 결과를 다시 셀 수 없다.
  - contract pass(첫 응답), strict inverse exact, mock vendor-call match 등이 그런 지표다.

| | thor Base | dev-v2 grounding_v9 B (`runs/full/q8_cur/dev.json`) |
|---|---:|---:|
| 최종 grounding 일치 | 35 | 84 |
| 첫 응답 grounding 일치(정규화·조건 계층·재질의 전) | 기록 없음 | 50 |

| 같은 문항 비교(최종) | 문항 |
|---|---:|
| 둘 다 일치 | 34 |
| thor만 일치 | 1 (044) |
| dev-v2만 일치 | 50 |
| 둘 다 불일치 | 15 |

dev-v2만 일치한 50문항의 내역:
- 첫 응답에서 이미 일치: 28
- 조건 계층이 날짜·유형·상태를 교정하거나 채움: 14
- 재질의 호출 있음: 7

이 50문항의 세 내역은 서로 겹칠 수 있다.

grounding_v11 재실행 기록(4c66f4d)도 같은 84이고 같은 표가 나온다.

### 6.2 결과 차이를 만들 수 있는 조건 후보(원인은 정하지 않는다)

- **thinking:** thor는 끔이다. dev-v2는 think 미지정이고, 기록상 모든 plan 호출에서 thinking이 생성됐다.
- **condition_check:** thor는 끔이다. dev-v2는 켬이다. dev-v2 기록에서 교정·채움이 25건 있다(taxi_status 10, date 9, taxi_type 6).
- **client와 수치 형식:** HF transformers BF16 대 Ollama GGUF Q4_K_M. 생성 설정도 다르다. thor는 HF greedy이고, dev-v2는 temperature 0에 Modelfile 기본값(top_k 20, top_p 0.95)이 기록돼 있다.
- **prompt:** 두 쪽 모두 522aa3b1이다. 렌더링은 다르다. HF는 thor의 `render_prompt`와 빈 think block을 쓰고, Ollama는 자체 template을 쓴다.
- **재질의:** 정책은 같지만 재질의하는 모델이 각 쪽의 모델이다.
- **코드:** thor 기준선은 2872c36(65e9ea2 + to_flat), dev-v2 기록은 c1f2a08과 4c66f4d다. 조건 계층 수정 전이다.

### 6.3 학습 결과를 현재 운영 조건으로 평가하려면 필요한 것

1. **Ollama 등록 경로.**
   - adapter merge(thor `merge_adapter`) → GGUF 변환 → 양자화 선택 → Modelfile(학습과 같은 chat template) → `ollama create`.
   - 양자화 효과를 학습 효과와 분리해야 한다. Base Qwen3-8B도 같은 변환·양자화로 함께 재야 한다.
2. **think 설정.**
   - 학습은 thinking 끔으로 했다. 운영 경로의 think 미지정은 qwen3에서 thinking을 만든다.
   - 평가 harness `evaluate_vendor100.py`는 think를 auto로 고정한다(`evaluate_vendor100.py:1078`). think=false 선택지를 넣는 harness 수정이 필요하다. 이 파일은 평가 코드이며 SEMANTIC_CODE가 아니다.
   - 비교 기준인 qwen3:8b Base도 think=false로 다시 재야 한다. 지금 있는 B·q8_T2PC 기록은 think 미지정이다.
3. **조건 고정.** condition_check 켬, 기준일 2026-09-25, mock·legacy, 문항마다 모델 내림, prompt 87048d0c가 학습 prompt와 바이트 단위로 같을 것.
4. **검증 명세 추가.** 측정 후 `GEOFLOW_VERIFIED_SPECS`에 새 조합을 넣는다(모델 digest, prompt, 코드 지문, think 포함 settings). 지금 qwen3:8b + T2PC는 "검증하지 않은 조합"으로 표시된다.
5. **지표 정렬.** v4 축과 U1–U4(grounding_v13 `report.py`)로 판정한다. thor 지표는 참고로 함께 낸다.
6. **평가 셋.** 학습에 노출된 family를 뺀 개발 비교와, 실행 전에 기대 결과를 고정한 새 held-out이 필요하다.
7. **자원.** 이 서버에서 쓸 수 있는 GPU는 GPU 3 하나다. 학습은 thor 장비(Jetson AGX Thor)에서 했다.

## 7. 사람 검토가 필요한 항목

1. **현재 계약에서 실패한 reviewed gold:** 없음. 다음은 판단이 필요하다.
   - compile에서 멈추는 SFT gold 17건(bucket+rollup)을 SFT에 유지할지, 실행 benchmark에서 뺄지.
   - **조건 계층을 거치면 rejected = chosen이 되는 DPO 3쌍**(factor_omission_taxi_type, RB003-03, RB003-04)을 유지할지, 뺄지, 재분류할지. 원응답 수준의 선호는 여전히 다르다. 운영 경로의 최종 grounding에서는 차이가 없다.
   - **constraint로 분류된 1쌍**(chosen ann-da98b394…, rejected date '202608'). T2PC 경로에서는 rejected가 장소를 버린 채 실행된다. semantic 재분류가 필요한지 정해야 한다. 같은 chosen의 다른 쌍은 실패 단계가 바뀐다.
2. **보호 정책의 범위.** vendor 형식 셋의 template·family를 보호에 넣을지 정해야 한다. 넣으면 v003 11건이 걸린다(3건은 새 셋, 3건은 업체 100). 넣지 않으면 지금처럼 질문·id만 보호된다.
3. **판단이 애매한 제외.**
   - 확인 요청 기대 문항(stage_v7 3건 등)을 정지 target으로 쓸지. thor는 clarification을 SFT에서 뺐다.
   - 정답 호출이 없는 거부 문항 25건과 `{"unsupported":true}` golden 54 intent. T2PC 계약에 맞는 grounding을 사람이 새로 적어야 쓸 수 있다.
   - D1–D4의 같은 유형 표현이 다른 셋에도 있을 수 있다. 이번 제외는 목록에 있는 8문항만이다.
   - 날짜 오류(첫 응답 21건, 최종 0건)처럼 조건 계층이 교정하는 오류를 학습 대상으로 둘지.
4. **coverage 공백을 채울 새 annotation 유형.** 평가 셋에서 파생하지 않는 독립 family여야 한다.
   - passage_count 측정값. "실차 택시 통행량"처럼 상태어가 붙은 통행량과, OD 역할이 없는 장소를 포함한다.
   - taxi_status 조건(occupied·vacant·stationary). trip 정의에 들어 있는 "실차"와 별도 조건인 경우를 대조한다.
   - dimension_target의 train 측 대조(pickup·dropoff·생략=both)와 장소 od_role의 독립.
   - 집계어가 없는 질문(집계 factor 없음)과 그 대조 negative.
   - dimension 단위 대조(sido·sigungu·emd).
   - time 조건.
   - 지원 불가·확인 요청 질문의 T2PC식 target(조건을 grounding으로 적고 코드가 멈춤).
   - vacant_ratio.

## 8. 다음 단계 선택지(필요 자료와 비용만. 효과는 추정하지 않는다)

| | (a) thor 자산을 T2PC로 옮기고 annotation 보강 | (b) 정책을 바꿔 개발 셋 일부를 학습에 사용 | (c) 학습 보류 |
|---|---|---|---|
| 필요한 결정 | 7절 1–3의 판정(DPO 4쌍, 보호 범위, 정지 target 사용 여부) | 정책 변경 승인. 어느 셋을 학습으로 보낼지(S0–S2), family 보호 규칙을 바꿀지 | 없음 |
| 필요한 자료 | 87048d0c로 다시 만든 새 판(v004). 7절 4의 유형별 독립 annotation과 사람 검토. 새 held-out(기대 결과 사전 고정) | 역산 grounding의 사람 검토(S1 100건, S2 311건 규모). 남는 평가 셋 재정의와 새 held-out. 이전 기록과의 비교 범위 재설정 | 재개 판단에 쓸 실제 사용 질문 표본(grounding_v13 6절: 300문항 규모 사람 라벨) |
| 코드 작업 | to_flat을 training 쪽으로 옮김(production 지문 유지). assess에 조건 계층 경로 추가. 한도 7519/7520/7331 config. harness think 선택지 | (a)의 코드 작업 + vendor 형식 → SFT target 변환기 | 없음 |
| 계산 비용 | Thor memory smoke 재실행(새 한도). SFT·DPO 학습. merge·GGUF 변환. 평가: qwen3:8b 기록상 문항당 중앙값 14.4초·p90 23.6초 → 136문항 약 35–55분, 428문항 약 1.7–2.8시간. Base 재측정(think=false) 포함 | (a)와 같음 + 학습 자료 규모에 비례한 학습 시간 | 없음 |
| 남는 위험(사실만) | 공백 유형의 annotation이 없으면 실제 오류 유형이 학습되지 않는다. 합성 문항 결과는 실제 사용 성능이 아니다 | S2는 v13 개발 비교 기반 10개 셋을 잃는다. 남는 평가는 업체 100과 이미 본 final 56이다. S0·S2는 업체 100 family와 겹치는 비율이 높다(268/453, 198/311) | qwen3:8b + T2PC는 지원하지 않는 조합으로 남는다(기본은 qwen3.8:27b) |

## 9. 한계

- 모든 수치는 기존 기록과 정적 검사에서 나왔다. 새 모델 출력은 없다.
- 오류 분포는 합성 문항 136개에서 센 것이다. 대부분 Claude가 썼고 사람 검토가 없다. 실제 사용자 질문의 분포로 일반화할 수 없다.
- 이 조사에서 정한 분류 기준은 사람 검토를 거치지 않았다: 오류 차원과 negative_type의 대응(`coverage_gap.py`), 정지 target 판정(`policy_scale.py`), 확장 보호 대조(`leakage_recheck.py`).
- thor 테스트 suite는 dev-v2 위에서 실행하지 않았다. 계획 단계(planning) 재질의 경로는 stub 검사에 넣지 않았다.
