# Partial P0 SFT 준비(계획만, 학습 없음)

2026-10-13.

- 이번 단계에서 한 것: 모델 호출·학습·HF 평가 없이 inventory, 결정적 변환기, 변환 검사, 데이터 통계까지 만들었다.
- 산출물:
  - `inventory.json`(`inventory.py`)
  - `build_targets.py`
  - `conversion_report.json`
  - `manual_review.jsonl`(0건)
  - `targets_v005_sft_p0.jsonl`(P0 target 111건, 변환 결과 데이터)

## 1. 결론

- **P0 target 결정적 변환: 승인 gold SFT 111건 중 111건이 자동 통과했다.** 수동 검토는 0건이다.
  - Full과 P0를 같은 T2PC 운영 경로(parse, 조건 계층, compose, validate, compile)에 넣었다. 다음이 모두 같다.
    - 실행 결과와 operator 목록
    - EVENT를 뺀 의미 서명
    - 평가 비교 정규형(측정값·장소·od_role·scope·factor·집계)
- **평가셋 오염: 없다.** v005 학습 질문은 vendor100·valid98·sel154·aux_test_v1과 질문 문장이 하나도 겹치지 않는다.
  - sel154와는 template·family까지 0이다(이번에 처음 대조).
  - valid98·vendor100과의 template·family 겹침(각 4·3건)은 결정 54에서 이미 진행하기로 한 기존 사항이다.
- **dimension_target 학습 예제는 31건이다**(pickup 13, dropoff 11, both 7).
  - 25건이 "하차지별", "출발지-도착지 조합별"처럼 그룹 표현이 명시된 꼴이다.
  - P0.3·Full이 실패한 "같은 끝 장소 제한 + 사건 표현"("X에서 승차가 가장 많은 동", "X로 간 손님이 내린 위치를 셀 기준으로") 꼴은 0건이다.
  - 값 없는 답 장소(scope 역조회)도 0건이다.
  - 지금 데이터 그대로의 SFT는 sel154에서 본 주요 의미 실패를 직접 덮지 못한다.
- **P0를 Partial SFT 기준 contract로 두는 것은 근거가 있다.**
  - sel154에서 P0는 Full과 semantic correctness(71.30 vs 71.82%)와 dt 누락(26 vs 27%)이 같다.
  - 남은 오류의 약 1/3이 학습으로 직접 고칠 수 있는 출력 형식 오류다(6절).
  - 최종 확정은 사용자 결정이다.

## 2. P0 target 정의(prompt 기준)

`evaluation/partial_grounding/prompts/partial_p0.yaml`의 output_format에서 그대로 옮겼다.

| | 내용 |
|---|---|
| 최상위 key | `concepts`, `factors`. 표현할 수 없을 때만 `{"unsupported": true}` |
| concept에 적는 것 | `subtype`, 있을 때만 `text`·`value`·`attributes` |
| concept에서 지우는 것 | `id`, `concept`, `role`, `source`(parser가 subtype과 value로 채움) |
| 지우는 concept | 측정 대상 사건(EVENT: passage, trip, drive, operation). composer가 측정값 subtype으로 붙인다 |
| 그대로 두는 것 | `factors` 전체, 장소·scope의 `value`, `attributes.od_role`, 값 없는 답 장소 |

- 변환은 `replay_partial.to_partial`(STRUCTURAL_KEYS = id, concept, role, source와 EVENT concept 제거)을 쓴다. 자연어를 읽지 않는다.
- 111건에서 지운 필드는 828개, 지운 EVENT concept는 111개다.
- JSON 길이 평균: 457자 → 225자(−51%).

## 3. 데이터 inventory

| 데이터 | 건수 | split·용도 | Full target | P0 변환 | P0 SFT에 쓰기 |
|---|---:|---|---|---|---|
| reviewed_gold_v005_t2pc / sft_train | 111(v004 53, batch005 58) | train, 승인 gold(결정 13·47) | Full JSON(thinking 없음) | 111/111 자동 통과 | **주 입력** |
| reviewed_gold_v005_t2pc / dpo_train | 75쌍 | train(DPO) | chosen·rejected Full JSON | chosen 75/75 같음, rejected 59 같음·16 다름 | 아니오(DPO 단계 후보) |
| thinking_pilot002_t2pc / sft_train | 379(107질문) | train(pilot_002) | thinking + Full JSON | JSON 실행 379/379 같음. 의미 서명 340 같음, 39는 모델이 장소 role을 COND로 적은 차이(결정 25로 허용, P0에서는 role이 사라짐) | 그대로는 아니오(4절) |
| thinking_pilot002_t2pc / dpo_train | 288쌍 | train(DPO full_response) | thinking + JSON | 검사 안 함 | 아니오 |
| reviewed_gold_v003·v004_t2pc | 35·53 | 이전 판(v005에 포함) | Full JSON | v005로 대체 | 아니오 |

| 평가·보호 셋 | 건수 | 용도(결정) | v005 질문 겹침 | template·family 겹침 |
|---|---:|---|---:|---|
| vendor100 | 100 | 평가 전용(CLAUDE.md 8, 결정 36) | 0 | template 3, family(결정 15 허용분 포함) — 결정 54 |
| valid98 | 98 | 보조 기록, P0.x 설계에 씀(41·60) | 0 | template 4, family 7 — 결정 54 |
| selection_v1 | 100 | checkpoint 선택(46·53) | 0 | 0 |
| aux_test_v1 | 51 | 판정에 쓰지 않는 보조 시험(42) | 0 | 0 |
| sel154 | 154 | P0.3 판정(61, 1회) | 0 | 0 |

이 평가·보호 셋은 학습 target 생성에서 뺀다. 변환기는 겹치는 문항이 있으면 자동 통과에서 빼도록 되어 있다(이번에는 0건).

## 4. thinking 처리

- SFT는 thinking 켬, loss `json_only`다(결정 9·24). 기존 trace(pilot_002)의 thinking은 Full prompt에서 생성됐다.
- 379/379가 role·MEASURE·SUBCOND·EVENT 같은 Full 구조어를 쓴다(중앙값 9회).
- JSON만 P0로 바꾸면 "Full 구조를 계획한 thinking + P0 JSON"이라는 어긋난 레코드가 된다.
- **권장:** P0 prompt(`partial_p0.yaml`)로 trace를 다시 모은다.
  - 방식: HF base Qwen3-8B, enable_thinking=True, pilot_002와 같은 필터.
  - P0 target과 운영 경로 결과가 같은 trace만 채택한다.
  - 이 단계는 모델 호출이 필요하므로 이번에는 하지 않는다.
  - Ollama 경로를 쓴다면 문항 격리 확인(`../resident_isolation/AUDIT.md` 4절)이 먼저다.

## 5. P0 target 통계(v005 SFT 111건)

| factor·속성 | 분포 |
|---|---|
| dimension_target | 없음 80, pickup 13, dropoff 11, both 7(모두 dimension과 함께) |
| dimension | 없음 64, emd 23, sigungu 13, sido 5, dayofweek 3, h3 3 |
| bucket | 없음 88, week 14, month 9 |
| aggregation | 없음 71, avg 18, min 7, max 6, med 5, sum 4 |
| rollup | 없음 88, max 9, avg 7, min 7 |
| answer | bucket 4 |
| place | 값 있는 장소 94, 값 없는 답 장소 0 |
| scope | 2 |
| od_role | both 20(결정 47 표기, 두 장소 표기 0), dropoff 16, pickup 9 |
| target 종류 | answered 99, 정지 target 12(결정 14, MISSING_REQUIRED_INPUT 2, UNCONSUMED_CONDITION 10), unsupported 0, needs_clarification 0 |
| compile | 통과 82, compile 정지 17(결정 7로 포함), 정지 target 12 |

**dimension_target 31건의 질문 꼴:**

| 꼴 | 건수 |
|---|---:|
| 그룹 표현 명시(승차지별·하차지별·조합별·노선별 등) | 25 |
| 사건 표현(예: "승차가 가장 많은 시군구", "손님을 가장 많이 태운 시군구", "도착 건수가 가장 많은 읍면동") | 6 |
| 그중 같은 끝 장소 제한과 함께(sel154 실패 군집) | 0 |

**장소 제한과 grouping의 조합(dt 31건):**

| 조합 | 건수 |
|---|---:|
| 장소 없이 grouping | 8 |
| 장소와 다른 끝 grouping | 7 |
| 양 끝 제한(both)과 grouping | 5 |
| 같은 끝 | 4 |
| 짝 grouping | 7 |

## 6. SFT가 필요한 이유(sel154 P0 arm, sampling 5회 770관측)

| 구분 | 관측 | 비고 |
|---|---:|---|
| 정답 | 549(71.30%) | |
| 첫 응답 구조 오류 | 76 | 재질의로 회복 1. 형식·경계 오류: INVALID_FACTOR 24, INVALID_CONCEPT 21, UNKNOWN_FACTOR 4, UNKNOWN_ATTRIBUTE 4, UNKNOWN_KEY 1 = 54. 측정값 누락 NO_MEASURE 15 |
| 조용한 오답(answered_mismatch) | 72 | 의미 판단 |
| 거부 관련 오류 | 50 | refused_unsupported 36, answered_instead_of_refusal 11, wrong_refusal_kind 3 |
| dimension_target 누락(dt 20문항 100관측) | 26 | Full 27과 같음 |
| scope 역조회(n40, k21) | 1/10 실패 | P0는 거의 유지 |

- P0의 오류 가운데 출력 형식·경계 오류(54건, 첫 응답 기준)는 base 모델이 P0 형식을 한 번도 학습하지 않아 생긴 것이다. P0 target SFT가 직접 겨냥하는 부분이다. Full 첫 응답의 같은 종류 오류는 INVALID_FACTOR 22, INVALID_CONCEPT 3 등이다.
- 나머지(조용한 오답, 거부, dt 누락)는 Full과 같은 크기의 의미 판단 문제다. prompt 규칙을 더하는 방식은 이 부분에서 다른 곳을 나쁘게 했다(ROOT_CAUSE.md).
- SFT로 다룰 수 있지만, 5절의 데이터 공백(사건 표현 dt, scope 역조회)을 채우지 않으면 효과가 제한된다.

## 7. 다음에 정할 것(실행 안 함)

1. P0를 Partial SFT 기준 contract로 확정할지(사용자).
2. 데이터 보강: 사건 표현 같은 끝 dt, 양 끝 제한과 grouping이 다른 끝인 문항, scope 역조회 질문.
   - 결정 45와 같은 절차를 따른다: Claude 초안 → 사용자 승인.
   - 평가셋 문장은 쓰지 않는다(결정 36). sel154 실패 문항은 설계 근거로 쓰지 않는다(결정 61의 1회 판정).
   - 근거는 유형 수준(CONTRACT.md 4절의 조합표)으로만 둔다.
3. P0 prompt로 thinking trace 재수집(HF base). 필터는 pilot_002와 같고, P0 target과 운영 경로 결과 일치를 조건으로 한다.
4. checkpoint 선택 셋과 최종 평가.
   - selection_v1은 sel154 안에 있어 P0.3 판정에 쓰였다. prompt 설계에는 쓰이지 않았지만, 선택 셋으로 계속 쓸지 정한다.
   - 평가는 Full과 P0-SFT를 같은 조건으로 비교한다.
5. DPO 단계 여부(v005 DPO 75쌍은 chosen 75/75가 P0로 같게 변환된다).

## 8. 진행 상태(2026-10-13)

- 결정 64: P0를 SFT 기준 contract로 확정했다. 결정 65: `_grounding_view`는 고치지 않는다(평가 정규화 기술 부채).
- **resident_isolated 격리 확인 불통과**(`../resident_isolation/RESULT.md`). Ollama 상주 trace 수집은 시작하지 않는다.
- **batch006 보강 후보**(`AUGMENTATION_REVIEW.md`):
  - 초안 53(Gap A 26, B 17, C 10). 자동 검사 통과 43(A 26, B 17).
  - Gap C 10은 scope 역조회 family가 평가셋 4종과 겹쳐 전부 제외. 예외를 둘지는 사용자 결정이다.
  - 사람 승인 대기 중이다.
- **분포**(`dataset_stats.json`): 통과분이 모두 승인되면 dimension_target이 31 → 74(pickup 35, dropoff 29, both 10)로, od_role과 다른 끝 grouping이 15 → 31로 는다. scope 역조회는 0 그대로다.
- **준비된 도구:**
  - `collect_p0_traces.py`(dry-run 확인)
  - `trace_collection_plan.md`
  - `build_v006.py`(승인 파일이 없으면 멈춤)
- **사용자 결정이 필요한 것:**
  1. batch006 승인
  2. Gap C 예외 여부
  3. trace 수집 모델(HF base / Ollama qwen3:8b / 27b 반입)
  4. 수집 실행 방식(격리가 확인되지 않았으므로 unload_per_question 또는 HF)
