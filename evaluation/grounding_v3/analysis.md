# grounding과 코드의 책임 경계 재정렬 (grounding_v3)

비교 커밋은 `preregistration.md`에 고정했다:
- dev = `f984306`
- v2 전체 보정 = `3d72ec3`
- 측정 도구 = `2f21df9`
- 최종 = `cad3bb8`(P0: 의미 재해석 제거, od_role both, flat select, order→limit, prompt 238ac8d6)

 

## 1. 기준 구조와 현재 v2의 차이

기준(`geoflow/dev`): LLM이 개념·관계·조건·집계 의미를 grounding한다. 재사용 macro와 typed port가 의미 그래프를 합성한다. 코드가 계약 검증·operator mapping·컴파일·실행을 맡고, 답변은 실행 결과에 근거한다.

| 책임 | dev `f984306` | v2 전체 보정 `3d72ec3` | 최종 |
|---|---|---|---|
| 개념·관계·집계 의미 | LLM grounding | LLM grounding **+ 조건 계층이 질문을 다시 읽어 덮어씀** | LLM grounding |
| 조건 계층 기본값 | 꺼짐(선택 기능) | 켬 | 켬 |
| 조건 계층이 바꾸는 것 | 날짜, 택시 유형(장소는 근거 확인만) | + 운행 상태, 측정값·사건, 장소 역할·같은 지역 분할, dimension·dimension_target·order·limit, aggregation·rollup·bucket, 답의 대상(원문 패턴으로 거부) | 날짜, 택시 유형, 운행 상태(명시된 값만). 장소 근거 확인 |
| 근거 어휘 없음 → 삭제 | 택시 유형 | 택시 유형·운행 상태·집계·역할·target·bucket·rollup | 그 조건을 받을 Tool이 없는 측정값일 때만(Tool 계약) |
| 모델과 규칙이 다를 때 확인 요청 | 없음(날짜 모호만) | 측정값 말 충돌, 반대 방향 말, 묶는 끝 충돌 | 없음(날짜 모호만) |
| "그 값을 가진 주" | flat 표현 불가(structured만) | 원문 패턴으로 조기 거부 | flat `select`(집계 IR)로 표현, 실행 여부는 provider 계약 |
| 같은 지역 OD | 표현 가능(개념 둘), 조회 두 번 | 조건 계층이 원문으로 나눔 | `od_role: both` 한 개념, 조회 한 번 |
| 순위 개수 | 선택 | 조건 계층이 원문 "가장"으로 채움 | Tool 계약 짝(order→limit), 빠지면 factor 재질의 |

## 2. 실제 호출 경로에서 본 보정의 범주

`GeoFlowPlanner._validate_payload` → `conditions.reconcile_payload` → `parse_grounding`(정규화) → `drop_unsupported_regions`
→ composer(macro·typed port, 계약 검증) → compiler(lowering·provider 계약) → executor → 답변. 재질의 patch는 조건 계층을
다시 지나지 않고 `parse_grounding`부터 다시 통과한다.

| 규칙 | 위치 | 범주 | 최종 처리 |
|---|---|---|---|
| taxi_status 조건, get_billing_metrics scope·dimension 조합, 측정값별 집계 의미, 구간 위임·로컬 재계산 | composer·compiler·tims_contract·measures | v2 Tool 계약 | 유지 |
| attributes 안팎 od_role·vicinity, `{"holiday": true}`→date, 빈 name의 region, region=name, OBJECT/private→factor, 단위 말 장소(dimension 있을 때), 발화에 없는 region | grounding 정규화 | 의미 불변 형식 정규화 | 유지. dimension 없는 `dimension_target=both` 제거를 더함(기본값과 같음) |
| 장소 이름 근거(PLACE_NOT_IN_QUESTION), grounding 계약, factor 짝, UNCONSUMED_CONDITION, verify_lowering, CONDITION_LOST, 조회 재사용 | 조건 계층·factors·composer·compiler·executor | 타입·출처·조건 보존·실행 가능성 검증 | 유지. Tool 계약 짝 order→limit을 더함 |
| 날짜 문법(기준일로 계산), 택시 유형 말, 운행 상태 말 | 조건 계층 | 자연어 재해석(좁음) | **유지**(아래 정당화). 근거 없는 값 삭제는 Tool 계약으로 제한 |
| 측정값 말로 subtype 바로잡기·채우기·충돌 확인 요청, 사건 맞춤 | 조건 계층(v1·v2) | 자연어 재해석 | **삭제** |
| 장소 역할·같은 지역 분할·dimension·target·order·limit·aggregation·rollup·bucket·답의 대상 | `relations.py`(v2) | 자연어 재해석 | **삭제**(파일 삭제). 역할·both는 관계 재질의로, 답의 대상은 select 표현으로, 개수는 Tool 계약 짝으로 |

**남긴 재해석의 정당화.**
- dev에도 있던 기능이다. 값이 닫힌 enum(날짜 토큰·범위, 개인/법인/전체, 실차/공차/대기영업)이다.
- 질문에 그 값을 가리키는 말이 **있을 때만** 채우거나 바로잡는다(양의 근거).
- 정답 grounding 250개(개발셋 다섯)를 넣었을 때 바꾼 것은 0이다.
- 층별 평가에서 업체 100 +15, 기존 44 +7을 고쳤고 훼손은 0이다(4절).
- 새 독립셋 v4 정답 38개 중 3개를 날짜 모호(연도 없는 날짜)로 멈췄다. 이것은 dev 이래의 규칙이다(6절).

## 3. 표현과 실행 지원

- **구간 선택.**
  - 집계 IR(`AggregationSpec.select`)과 구조화 표기(`aggregation_plan.result.select`)는 이미 "가장 큰 값"과 "그 값을 가진 주"를 구분한다.
  - 과거 structured 평가(2026-09-26, qwen3:8b 30관측)는 정답 6 → 8이었지만 조용한 오답이 5 → 10으로 늘어 채택하지 않았다.
  - 늘어난 오답의 대부분은 장소·날짜·택시 유형 누락이었다. prompt 전체 교체가 원인이고, 집계 표현 자체가 원인이 아니다.
  - 그래서 가장 작은 변경으로 flat에 `select` 하나를 더했다. flat도 같은 IR에 닿고, 합성·lowering은 그대로다.
- **실행 가능 여부는 provider 계약이 정한다.**
  - reference provider(일 기록 계약 있음)는 로컬에서 구간을 고른다(동률 두 주).
  - TIMS legacy는 bucket/rollup 호출이 대표값만 돌려주고, 로컬 재계산 근거(day_records)가 계약에 없다. 그래서 `UNVERIFIED_TIMS_CONTRACT`이다.
- **prompt에는 `select`를 안내하지 않는다.**
  - 안내한 변형(`28c1139`, `d4f1c1f8`)의 업체 100 실측이 85였다(stage 1 재생 91).
  - 모델이 월별 최댓값에 select를 적었고, 무관한 문항에서 "실차 통행량"을 trip_count로 되돌렸다.
  - 안내 여부는 이후 격리 실측으로 정한다. 그 전까지 flat 경로의 "어느 주" 질문은 모델이 rollup 값을 적으면 여전히 값으로 답한다(남은 한계).

## 4. 층별 성능

grounding 층 평가는 기록된 원출력을 현재 코드에 다시 통과시킨다(재질의 전, LLM 없음). `layers_final.md`와 `layers_v2full_indepv4.md`, 그리고 v2 전체 보정 코드로 계산한 `layers_v2final.md`다.

"의미 정확"은 측정값·장소(이름·지역·역할)·scope·factor가 정답 grounding과 같은지를 본다(기본값 정규화). 형식 무효는 의미 정확으로 세지 않는다.

| 셋 | 원출력 | 형식 정규화 | 조건 보존 | v2 의미 재해석(참고) |
|---|---|---|---|---|
| 업체 100 | 57 | 63 (+6 / −0) | 78 (+15 / −0) | 99 (+21 / −0) |
| 기존 44 (/43) | 23 | 24 (+1 / −0) | 31 (+7 / −0) | 43 (+12 / −0) |
| 대조 31 (/30) | 14 | 18 (+4 / −0) | 21 (+3 / −0) | 30 (+9 / −0) |
| 1차 독립 40 (/39) | 12 | 15 (+3 / −0) | 18 (+3 / −0) | 30 (+12 / −0) |
| 2차 독립 40 (/38) | 13 | 13 (+1 / −1*) | 14 (+1 / −0) | 20 (+7 / −1: m22) |
| 새 독립 v4 40 (/38) | 15 | 18 (+3 / −0) | 19 (+1 / −0) | 22 (+5 / −1: k37) |

\* m02는 원출력 view가 맞지만 형식 무효(측정값 개념 둘)라 정규화 층에서 거부된다. 의미를 훼손한 것이 아니다.

**보정의 이득과 훼손.**

형식 정규화와 조건 보존은 여섯 셋에서 훼손이 0이다.

v2 의미 재해석의 이득은 규칙을 만든 셋에서 컸다(+21, +12, +9, +12). 규칙을 만든 뒤 처음 본 셋에서는 작았다:
- 2차 독립: +7 / −1
- 새 독립 v4: +5 / −1

정답 grounding을 보정 계층에 넣은 결과(`gold_audit_final.md`, `gold_audit_v2full_indepv4.md`)는 다음과 같다.

| 셋 | v2 전체 보정: 바뀜 / 멈춤 | 최종: 바뀜 / 멈춤 |
|---|---|---|
| 개발셋 다섯(250) | 3 / 1(2차 독립 m14·m22·m17) | 0 / 0 |
| 새 독립 v4(38) | 5 / 3(k28·k33·k35 limit 2→1, k34 target, k37 집계 단계 / 날짜 모호 3) | 0 / 3(날짜 모호) |

정답 grounding을 **실행기**에 넣은 평가(`runs/gold_final_*`)는 따로 센다. 최종 코드는 다음을 모두 정답 호출로 바꾼다:
- 업체 100: 100
- 기존 44: 41 + 정당한 거부 2
- 대조: 29 + 1
- 1차 독립: 35 + 4
- 2차 독립: 36 + 2
- v4: 36 + 2

(정답 grounding이 없는 문항 제외.)

## 5. 전체 보정 경로와 의미 덮어쓰기를 제한한 경로 (기록된 계획 응답 재생, 재질의만 실제 호출)

같은 원출력에 두 경로를 비교했다.
- 조건 계층 켬, 달력·장소 근거 확인 유지
- `--no-semantic`은 의미 재해석만 끈다

| 셋 | 전체 보정 | 재해석 끔 | stage 1(역할 재질의·both) | P0(+select 계약, order→limit) |
|---|---|---|---|---|
| 업체 100 | 99 | 88 | 91 | 92 |
| 기존 44 | 44 | 35 | 36 | 37 |
| 대조 31 | 31 | 25 | 25 | 26 |
| 1차 독립 40 | 33 | 21 | 23 | 24 |
| 2차 독립 40 | 24 | 18 | 19 | 20 |

재해석을 끈 경로가 잃은 문항과 원인은 다음과 같다(`replay_restricted/`).
- limit 누락: 7
- 한쪽 역할·같은 지역: 8
- 순위 방향 오류: 2
- 집계 누락·지어냄: 7
- dimension_target: 3
- 구간 선택 2, 측정값 1, 사건 1, bucket·rollup 형식 4

각 원인을 옮긴 계층은 다음과 같다.
- **Tool 계약 짝(order→limit) + factor 재질의:** limit
- **관계 재질의 요청문(사건 기준, both 선택지) + `od_role: both` 표현:** 역할
- **flat `select` 계약:** 구간 선택
- **형식 정규화:** dimension 없는 both target

순위 방향·측정값·dimension·집계 오독은 모델 오류다. 질문을 다시 읽지 않고는 알 수 없어 그대로 둔다.

**prompt로 옮기는 안은 채택하지 않았다.** stage 2(`28c1139`, `d4f1c1f8`)는 prompt에 select, 역할 판단 기준, both를 적었다. 업체 100 실측은 85였다(`runs/s2b_dev_*`). 대조 31은 23과 22였다(`runs/s2_contrast_*`, `runs/s2b_contrast_*`). 무관한 문항에서 "실차 통행량"을 trip_count로 되돌리는 변동이 생겼다. 최종 후보는 prompt를 `238ac8d6` 그대로 두었다.

## 6. 최종 실측 (qwen3:8b, 격리, 채점기 v2, `report_final.md`)

| 셋 | v2 전체 보정 → 최종 맞음 | 오답 | 부당한 거부 | 실행 실패 | 재질의 | 지연 중앙값 / p90 / 최대 / 합계(초) |
|---|---|---|---|---|---|---|
| **새 독립 v4(사전 등록)** | **25 → 24** | **6 → 4** | 5 → 7 | 4 → 5 | 3 → 8 | 12.7/15.6/315.9/844 → 12.7/18.2/315.8/866 |
| 업체 100(개발) | 99 → 93 | 0 → 3 | 1 → 1 | 0 → 3 | 0 → 15 | 12.0/18.0/316.2/1882 → 13.2/21.1/474.6/2514 |
| 기존 44(개발) | 44 → 36 | 0 → 7 | 0 → 1 | 0 → 0 | 0 → 7 | 11.9/17.1/39.3/584 → 12.4/18.7/82.0/700 |
| 대조 31(개발) | 31 → 26 | 0 → 2 | 0 → 1 | 0 → 2 | 0 → 5 | 12.3/20.8/30.8/447 → 13.1/22.8/31.0/483 |
| 1차 독립 40(개발) | 33 → 23 | 2 → 8 | 1 → 3 | 4 → 6 | 4 → 12 | 12.5/22.7/265.8/853 → 14.5/26.4/164.9/819 |
| 2차 독립 40(개발) | 24 → 21 | 9 → 9 | 1 → 2 | 6 → 8 | 8 → 13 | 12.2/18.8/411.3/936 → 13.0/20.4/409.6/979 |

- **사전 등록 가설(v4, 40문항, 사람 검토 없는 합성 평가):** H2·H3은 충족, H1은 부분 미충족이다.
  - H1: 최종 조건 계층은 정답 grounding을 바꾸지 않는다(0). 하지만 멈춤 0 가설과 달리 3개를 멈췄다(연도 없는 날짜를 모호로 보는 dev 이래 규칙, v2 전체 보정도 같음).
  - H2: 오답 6 → 4.
  - H3: 맞음 25 → 24(허용 −3 이내).
  - H4: 재질의 3 → 8, 합계 지연 +22초.
- **v4에서 바뀐 문항:**
  - 최종이 새로 맞음: k28, k37. v2 전체 보정이 "두 셀"의 limit을 1로, "주마다 평균 낸 뒤"의 구간 안 평균을 지웠던 문항이다.
  - 최종이 틀림:
    - k08: 관계 재질의 실패.
    - k36: 모델이 요일 그룹에 bucket을 함께 적었다. v2는 원문으로 bucket을 지웠다.
    - k40: "가장 낮았던 달". select가 prompt에 안내되지 않아 모델이 rollup 값을 적었다. v2는 원문 패턴으로 거부했다.
- **개발셋 하락은 규칙을 만든 셋에서 재해석이 맡던 몫이다.**
  - 업체 100에서 틀린 7: 006(dimension에 both, 측정값 없음), 007·040(dimension_target 누락, 관계 재질의 실패), 064(RPM을 speed로), 066(target만 적음), 093(같은 지역을 pickup 하나로), 095(장소명을 로마자로).
  - 모두 모델 grounding 오류이고, 최종 경로는 이를 고치지 않는다. 오답 3은 조용한 오답이다.
- **2차 독립셋의 m14·m22는 최종에서 맞는다.** 모델 grounding이 맞았고 덮어쓰지 않는다. m17은 모델 grounding이 틀려 실패한다(v2에서도 거부).

## 7. 남은 한계

**표현.**
- flat `select`는 계약과 IR에 있지만 production prompt에 안내하지 않았다. 그래서 "어느 주/달" 질문(g32·c08c·n24·m25·k40)은 모델이 rollup을 적으면 값으로 답한다(조용한 오답).
- 안내한 prompt는 qwen3:8b에서 다른 문항을 흔들었다. 더 큰 모델이나 구조화 표기에서 다시 재야 한다.

**모델.**
- qwen3:8b 원출력의 의미 정확은 업체 100에서 57/100, 새 독립 v4에서 15/38이다.
- 형식 정규화와 명시 조건 보존이 더하는 몫은 v4에서 +4다. 순위 방향·측정값·dimension·target·집계 오독은 이제 그대로 실행되거나 거부된다.

**날짜 정책.**
- dev 이래 연도 없는 날짜("9월 25일")를 모호로 보고 되묻는다. 기준일이 2026-09-25이면 대부분 올해다.
- v4 정답 38개 중 3개가 이 이유로 멈췄다. 정책(기준일 연도로 해석할지)은 사람이 정할 일이라 바꾸지 않았다.

**provider 실행.**
- TIMS legacy는 구간 선택을 실행하지 못한다(bucket/rollup은 대표값만, day_records 계약 없음).
- 구간 × 공간 그룹과 시간대별 그룹은 계약 밖이다.

**비용.**
- 역할·개수 판단을 재질의로 옮겨 재질의가 늘었다(업체 100 0 → 15).
- 300초 안팎 최대값은 timeout 뒤 재시도다. 긴 지연을 빼지 않았다.

**평가.**
- 모든 합성 셋은 Claude가 썼고 사람이 검토하지 않았다.
- 40문항에서 1~2문항 차이는 잡음 범위다. 일반 오류율로 읽지 않는다.

## 8. 재현

```bash
PY=python
$PY -m unittest discover -s tests -t .
git worktree add --detach /tmp/v2full 3d72ec3        # v2 전체 보정
S=evaluation/grounding_v3; G=$S/independent_v4_questions.yaml
# 실제 LLM 격리 실측
$PY evaluate_vendor100.py --gold $G llm --model qwen3:8b --condition-check --out $S/runs/final_indepv4.json
$PY evaluate_vendor100.py --code-root /tmp/v2full --gold $G llm --model qwen3:8b --condition-check --out $S/runs/v2full_indepv4.json
# 층별 grounding(원출력 → 형식 정규화 → 조건 보존), LLM 없음
$PY evaluate_vendor100.py layers --run v4 $S/runs/final_indepv4.json
# 정답 grounding → 실행기 / 정답 grounding → 보정 계층
$PY evaluate_vendor100.py --gold $G gold --out $S/runs/gold_final_indepv4.json
$PY evaluate_vendor100.py gold-audit evaluation/vendor100/gold.yaml $G
$PY evaluate_vendor100.py --code-root /tmp/v2full gold-audit $G
# 비교 표
$PY evaluate_vendor100.py report --items --pair v4 $S/runs/v2full_indepv4.json $S/runs/final_indepv4.json
# 기록된 계획 응답 재생(prompt hash가 같을 때만, 재질의는 실제 호출·비격리). 의미 재해석만 끈 v2 경로: 2f21df9 + --no-semantic
$PY evaluate_vendor100.py llm --model qwen3:8b --condition-check --replay-from evaluation/grounding_v2/runs/final_dev_qwen3_8b.json --out replay.json
```

기록 위치:
- `runs/`
  - 최종 실측: `final_*`
  - v2 전체 보정: `v2full_indepv4_*`
  - stage 2 prompt 실측: `s2*`
  - 정답 grounding: `gold_*`
- 재생: `replay_restricted/`, `replay_stage1/`, `replay_p0/`
- 층·감사·보고: `layers_*.md`, `gold_audit_*.md`, `report_final.md`
