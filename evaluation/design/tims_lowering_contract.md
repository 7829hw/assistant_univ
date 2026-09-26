# TIMS lowering 계약, inner 미지정 감사, 구조화 grounding 비교

상태: 구현됨. 커밋하지 않은 작업 트리(기준 HEAD `1229b53`).
production 기본값은 바꾸지 않았다(flat grounding, prompt sha256 앞 8자리 `64bbceb4`).

## 1. 이전 구현(1229b53)에서 확인한 문제

| 문제 | 근거 |
|---|---|
| bucket/rollup 호출 하나로 합치는 조건이 Tool 인자 모양(enum)뿐이었다 | `compiler._can_fuse`. 주 시작일·부분 주·빈 구간은 계약에 없는데 병합했다 |
| 이전 문서가 병합의 경계 차이를 "답변에 경로·경계를 표시한다"로 넘겼다 | `semantic_aggregation_graph.md` 7절. 계산 불일치를 표시로 정당화할 수 없다 |
| 두 경로가 같다는 테스트가 동어반복이었다 | fake TIMS의 bucket을 로컬과 같은 정의(월요일, 경계에서 자름)로 구현 |
| 로컬 경로가 날짜 범위의 양 끝 포함을 가정했다 | 주별 `YYYYMMDD-YYYYMMDD` 호출. 계약에는 예시만 있다 |
| 기준일이 서버 시간대(`date.today()`)였다 | pipeline clock |
| 구조화 grounding을 쓰면 재질의 patch에서 `aggregation_plan`이 사라졌다 | `repair.apply_patch`가 `to_dict()` → `parse_grounding`으로 다시 읽음 |
| 평가: "golden·채점 유지"와 "inner 미지정은 거부 기대"가 섞여 있었다 | 아래 4절 |
| f03을 "golden 충돌이므로 거부가 맞다"로 분류했다 | 원문 기준 재분류에서 틀림(4절) |

재생 수치는 다시 계산해 이전 보고와 같음을 확인했다(M0 153/6/20, M2 156/8/24).

## 2. TIMS 계약 확인 상태 (`geoflow/tims_contract.py`)

근거로 인정한 것은 `schemas/*.yaml`과 `prompts/system.yaml` param_types(vendor parameter
정의)뿐이다. 저장소에는 실제 TIMS provider가 없다(`tool_handlers`는 mock만 허용). mock은
계약의 증거로 쓰지 않았다.

| 항목 | 상태 | 근거 |
|---|---|---|
| bucket이 있을 때 aggregation이 구간 안 집계 | 계약으로 확인됨 | param_types pt_bucket "pt_aggregation 형식의 파라미터가 1차 집계 방식을 제공" |
| rollup은 구간별 값에 가중 없이 적용(평균의 분모 = 구간 수) | 계약으로 확인됨 | pt_rollup "bucket 단위로 값을 산출한 뒤, 그 값들에 이 집계를 적용" |
| aggregation 기본값 avg | 계약으로 확인됨 | `_common.yaml` pt_aggregation default avg |
| `YYYYMMDD` 하나 = 그 하루 | 계약으로 확인됨 | pt_date "날짜 또는 날짜 범위. YYYYMMDD 또는 …" |
| 날짜 범위 양 끝 포함 | 구현·라벨에서만 관찰됨 | 예시 `20260601-20260605`와 프로젝트 라벨뿐. 문장 없음 |
| aggregation=avg의 분모(원시 단위) | 구현·라벨에서만 관찰됨 | metric 설명 "개별 택시 1일 영업간 집계"에서 택시·일 단위로 읽힐 뿐 |
| 주 시작일 | 알 수 없음 | "주 단위"만 적혀 있다 |
| 월·조회 기간 경계의 부분 구간 | 알 수 없음 | 없음 |
| 빈 구간을 빼는지 0으로 넣는지 | 알 수 없음 | 없음 |
| null·결측 반환 | 알 수 없음 | 반환은 "스칼라값"뿐 |
| 상대 날짜의 기준 시각·시간대 | 알 수 없음 | "현재 시점을 기준으로 하는 상대 날짜"뿐 |

## 3. lowering 경로

| 전략 | 필요한 계약 | 기본 계약에서 |
|---|---|---|
| `fused_bucket_rollup` (bucket/aggregation/rollup 호출 하나) | inner_is_aggregation, rollup_unweighted, bucket_week_start, bucket_partial, bucket_empty, relative_date_reference가 확인되고, 확인된 값이 의미 graph의 정의(월요일, 기간 경계에서 자름, 빈 구간은 정의되지 않음, Asia/Seoul 달력)와 같을 것 | **쓰지 않음** |
| `range_partition` (구간마다 날짜 범위 호출) | range_inclusive | **쓰지 않음** |
| `daily_partition` (하루마다 호출, 구간 값은 로컬에서 합침) | single_date, 그리고 구간 안 집계가 하루 값들로 정확히 다시 만들어질 것(sum, max, min) | **사용**. 하루 호출 상한 62번 |
| 그 밖 | — | `UNVERIFIED_TIMS_CONTRACT`(구조화된 지원 불가) |

- 구간 안 집계가 avg나 med인 두 단계 질문은 지원하지 않는다. 하루 평균에서 구간 평균을 만들려면
  표본 수가 필요하고, 범위 호출은 범위 계약이 확인되지 않았기 때문이다.
- 기간이 없거나(`UNRESOLVED_PERIOD`), 연속 기간이 아니거나(`UNSUPPORTED_PERIOD_FOR_GROUPING`),
  62일을 넘으면(`UNSUPPORTED_PARTITION_SIZE`) 지원 불가다.
- 하루 값이 null이면 0으로 채우지 않고 멈춘다(`EMPTY_GROUP_VALUE`). null의 뜻이 계약에 없기 때문이다.
- 기준일은 Asia/Seoul 날짜다. `last_month`를 로컬에서 날짜로 푸는 것은 TIMS 계약이 아니라
  설계 선택이다. 병합 경로를 쓰지 않으므로 TIMS의 상대 날짜 해석과 섞이지 않는다.
- 계약이 확인된 기존 단일 집계(구간 없음)는 그대로다. 사용자가 적은 날짜 범위도 그대로 넘긴다.
- 계약 항목이 확인되면 `TimsContract` 값만 바꾸면 해당 경로가 열린다. 테스트는
  `DEFAULT_CONTRACT.assuming(...)`으로 가정을 명시해 병합·범위 경로를 검증한다.

**`verify_lowering`이 검증하는 것(내부 일관성)**
- 모든 의미 단계가 실행 단계로 수행된다.
- 각 호출이 조건(기간·범위·택시 유형 등)을 그대로 갖는다.
- 쓴 전략이 계약에서 허용된 것이다.
- 일 단위 분할이 기간을 빈틈과 겹침 없이 덮는다.
- COLLECT의 구간 구성과 집계가 구간 안 집계와 같다.
- 병합 호출에서 구간 안/밖 집계가 뒤바뀌지 않았다.

**검증할 수 없는 것(외부 계약)**: TIMS가 각 단계의 `assumptions`(예: `single_date`)대로 동작하는지.
실행 계획의 step마다 이 가정이 남는다.

## 4. inner 미지정 사례 재분류

`evaluation/labels/aggregation_semantics_v2.yaml`(v2 라벨, v1은 수정하지 않음),
관측 단위 표: `inner_unspecified_audit.md`/`.json`(`aggregation_label_audit.py`로 생성).

**이전 설명 정리**
- "golden과 채점 규칙은 유지했다"는 corpus YAML과 `evaluate_prompt_ab`의 채점
  (`tool_arg_mismatches`, `final_category`)을 바꾸지 않았다는 뜻이었다. 그 경로에서 inner 미지정
  intent의 거부는 **오답**으로 센다.
- "inner 미지정은 거부를 기대한다"는 단위 테스트(`paraphrase_corpus.golden_inner_unspecified`를 쓰는
  계약 테스트)가 제품의 동작을 고정한 것이었다. 평가 점수가 아니다.
- 구버전 라벨 투영(`evaluate_planner.corpus_labels`, `paraphrase_corpus.legacy_bucket_call`)은
  REDUCE_GROUPS 계획만 옮긴다. macro/operator 라벨에는 원래 집계 값이 없었다. 구간 안/밖 집계는
  legacy 호출 인자(bucket·aggregation·rollup)에 그대로 남으므로 단계 정보는 사라지지 않는다.
  SELECT_GROUP 계획은 옮기지 않는다. 다만 v1 채점의 `tool_arg_mismatches`는 aggregation 생략을
  기본값 avg와 같게 보아 명시된 inner의 누락을 가린다(f02_p1). v2는 의미 계획을 직접 비교한다.

| intent | 원문(대표) | 판정 | 근거 | 수정 대상 |
|---|---|---|---|---|
| b21, b24, h12 | 주 단위로 **집계한** 수입의 평균/최대/최소 | 3 모호(+5 라벨, +4) | 수입의 원시 단위가 택시·일이라 "구간별 총합"과 "구간별 일평균"이 모두 성립한다. v1은 Tool 기본값을 정답으로 적었다 | 사용자 확인, 평가 라벨 |
| b21_p3, b24_p3, h12_p3 | 수입의 평균을 주 단위로 집계하면? 등 | 3 모호(모양 자체) | 구간 안 집계만 있고 구간별 값의 집계가 없다(목록으로도 읽힌다) | 사용자 확인 |
| f13 | 주 단위로 집계한 영업 횟수의 평균 | 3 모호(+5, +4) | 총 횟수와 택시·일당 평균이 모두 성립한다 | 사용자 확인, 평가 라벨 |
| f03 | 월 단위 영업 횟수의 **합계** | **2 뜻으로 정해짐**(+5, +4) | 구간별 값을 다시 합하므로 구간 값은 합계다. 이전 분류는 틀렸다. 거부는 안전하지만 정답이 아니다 | grounding, 평가 라벨 |
| f01 | 월 단위로 **합산한** 수입의 평균 | 1 LLM 누락(+4) | 질문이 sum을 명시한다. 모호한 질문으로 재분류하지 않는다 | grounding |
| f02 | 주 단위로 **평균 낸** 영업 시간의 최대값 | 1 LLM 누락(+4), f02_p1은 +5 | 명시된 avg를 모델이 빠뜨린 관측을 v1 채점이 기본값 동일로 정답 처리했다 | grounding |

공통 +4: 이 질문들은 모두 기간이 없다. 의미가 확정되어도 현재 계약에서는 실행할 수 없다.

관측 단위 결과(현재 코드, 재생):

| | M0 qwen3:8b | M2 qwen3.8:27b |
|---|---|---|
| 관측 | 32 | 32 |
| v1 기준선 정답 | 21 | 31 |
| v2 결과 일치 | 5 | 28 |
| v2 계획 일치(최종 grounding) | 5 | 24 |
| 오류 단계 grounding | 27 | 5 |
| 모호한 질문에 inner를 지어냄 | 15 | 0 |

M0는 모호한 질문 15건에서 inner를 지어냈다. 그중 avg는 v1에서 기본값과 같아 정답으로 셌다. 현재는
avg면 계약 미확인으로, max/min이면 기간이 없어 멈춘다. 기간이 있었다면 max/min을 지어낸 관측은
조용한 오답이 된다. 결정적 계층은 flat grounding이 지어낸 inner를 구분할 수 없다.

## 5. 구조화 grounding (설정으로 선택)

- `GeoFlowPlanner(aggregation_grounding="flat" | "structured")`, `GeoFlowPipeline.create(...)`,
  CLI `--aggregation-grounding structured`. 기본값은 flat이다.
- structured(S1)는 `factors.aggregation_plan`에 `bucket{unit, reducer|unspecified}`와
  `result{reducer}|{select}`를 적는다. "최댓값"(reducer)과 "최댓값을 가진 주"(select)를 구분한다.
- flat factor와 함께 오면 뜻이 같을 때만 받는다(`source=structured+flat`). 다르면
  `AGGREGATION_SOURCE_CONFLICT`로 거부한다. flat은 select를 표현할 수 없으므로 select와 flat
  rollup은 늘 충돌이다.
- inner가 unspecified면 `AMBIGUOUS_INNER_AGGREGATION`이며, context에
  `needs_clarification=true`, `clarify=inner_reducer`, `choices`가 담긴다. pipeline의
  `outcome=needs_clarification`, CLI는 `NEEDS_CLARIFICATION`으로 표시한다. 재질의로 채우지 않는다.
- 재질의 patch는 구조화 집계를 보존한다. 구조화 집계가 있는 grounding에 flat 집계 factor를 붙이는
  patch는 거부한다.
- prompt는 정의에서 조립한다(`geoflow/structured_grounding.py`). flat prompt는 byte 단위로 같다.

## 6. 평가

### A. 결정적 계층(정답 grounding, LLM 없음)

`tests/test_geoflow_aggregation_graph.py` 71건, 전체 743건 통과. 기대값은 docstring 표에서 손으로
계산했다.
- 표본 수가 다른 구간과 부분 주: 1150/6, 390, W3 ≠ W2, 620/6, 1150/38
- fake bucket이 부분 주를 버리면 같은 인자로 272.5가 나와 의미 graph(191.67)와 다르다. 기본 계약은 병합하지 않으므로 의미 graph대로 계산한다.
- 빈 날(null) 거부, 기간·지역·택시 유형 보존
- 모호/미지원 구분, flat·구조화 충돌, 구조화 경로 end-to-end, CLI 옵션

### B. 기존 원문 재생(LLM 호출 없음, development census)

`lowering_contract_replay.json`. 기준선(c547e5c) 재판정이 원래 census와 같음을 확인했다(M0).
M1 census는 run이 중단되어 무결성 검사에서 제외했다. **결정적 계층 변경의 영향이며 grounding
방식의 성능이 아니다.**

| | M0 (210) | M2 (211) |
|---|---|---|
| v1 결과 c547e5c → 현재 | CORRECT 159 → 138, SILENT 11 → 3 | CORRECT 180 → 149, SILENT 8 → 7 |
| 정답 → 거부 | 21 | 31 |
| 오답 → 거부 | 8 | 1 |
| 오답 → 정답 | 0 | 0 |
| 현재 결과 종류 | answered 141, needs_clarification 11, unsupported 19, failed 39 | answered 156, needs_clarification 24, unsupported 10, failed 21 |

v1 기준의 "정답 → 거부"는 모두 두 단계 질문이다. 이 가운데 v2에서 거부가 맞는 경우와 틀린 경우는
4절과 같다. 기간 없는 두 단계 질문은 의미가 맞아도 현재 계약으로 실행할 수 없다.

### C. 새 LLM 비교(flat vs structured)

run `evaluation/structured_grounding/20260926_123506_eval_v1_flat_vs_s1`. 판정 규칙은 측정 전에
고정했다(`evaluation/prompt_ab/variants/structured_grounding_decision_rule.md`). 조건은 다음과 같다.
- 평가 셋: fresh 30문항
- 모델: qwen3:8b, temperature 0
- 관측마다 모델 unload와 cold load 확인, 질문마다 arm 순서 교대
- 무효 0

| 지표 | flat | structured |
|---|---|---|
| 정확한 답을 실제로 반환 | 6/30 | 8/30 |
| 의미 계획 정확 | 11 | 16 |
| 조용한 오답 | 5 | 10 |
| 답할 수 있는 질문의 거부 | 10/18 | 2/18 |
| 모호한 질문의 확인 요청 | 1/5 | 0/5 |
| 조건 누락(관측 수) | 10 | 10 |
| 실행 실패 | 10 | 3 |
| LLM 호출 / Tool 호출 | 37 / 202 | 30 / 454 |
| 관측 지연 중앙값 | 9.6초 | 7.1초 |

**판정: Case F(채택 근거 없음)**. 규칙 1(조용한 오답 structured ≤ flat)을 어긴다.

structured의 조용한 오답 10건은 다음과 같다.
- 조건 오류 4건: 장소 누락, 택시 유형 누락, "지난달"을 2026-05·2026-04로 지어냄
- 구간 단위 오류 1건
- 구간 누락 1건
- inner 오류 2건: 명시된 max를 sum으로, 모호한 질문에 sum을 지어냄
- 채점상 불일치 2건(e13, e28): 집계어 없는 질문에 avg를 적었거나 그 반대인 경우로, 실행 호출은 Tool 기본값과 같다. 엄격 기준으로는 오답이며, 빼도 8 > 5다.

구간 선택 질문(e07, e08, e30)은 structured만 답했다. 다만 qwen3:8b는 모호한 질문에서
`unspecified`를 한 번도 쓰지 않았다. 이 평가 셋은 측정 후 development로 바꿨다
(`evaluation/corpus_registry.yaml` question_sets).

## 7. 남은 제한과 다음 단계

- vendor에 확인해야 할 계약 항목은 다음 다섯 가지다. 확인되면 `TimsContract`만 바꾸면 된다.
  - 주 시작일
  - 부분 구간
  - 빈 구간
  - 범위 양 끝
  - 상대 날짜 기준
- 계약이 없는 동안 두 단계 질문은 명시 기간과 sum/max/min inner가 있을 때만 답한다. 호출 수가
  하루 단위로 늘어난다(한 달 31회).
- structured grounding의 주요 실패는 조건(날짜·장소·택시 유형)과 모호성 표현이다. 이는
  structured 계약 자체보다 모델 능력과 prompt의 문제다. 다음 측정은 모델을 바꾸지 않고
  조건 보존을 따로 재는 실험이 되어야 한다.
- flat grounding이 모호한 질문에 지어낸 inner는 결정적 계층이 구분할 수 없다(M0 15건).
- v2 라벨은 이번 감사 대상 intent만 다룬다. 다른 aggregation corpus(a*, l*, v*)의 v2 라벨은 아직 없다.

## 8. 재현

```bash
python -m unittest discover -s tests -t .

# B. 재생(세 버전)
git worktree add --detach /tmp/base c547e5cb1f4561f783b0e201cf1d3891416d3d57
cp geoflow_replay_compare.py /tmp/base/
RUN=$PWD/evaluation/prompt_ab/20260925_171514_model_M0_census
(cd /tmp/base && python geoflow_replay_compare.py $RUN --out /tmp/base.json)
python geoflow_replay_compare.py $RUN --out /tmp/head.json
python aggregation_label_audit.py --label M0 /tmp/base.json /tmp/head.json --out-md /tmp/audit.md

# C. 새 LLM 비교(Ollama, qwen3:8b)
python structured_grounding_eval.py run evaluation/structured_grounding/eval_questions_v1.yaml --name NAME
python structured_grounding_eval.py score evaluation/structured_grounding/<run_dir>

# CLI 구조화 경로
python assistant_cli.py --agent-mode geoflow --aggregation-grounding structured \
  --model qwen3:8b --query "지난달 대구 개인택시 매출 합계가 가장 큰 주는?"
```
