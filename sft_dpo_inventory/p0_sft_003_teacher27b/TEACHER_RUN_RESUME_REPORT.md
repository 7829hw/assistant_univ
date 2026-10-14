# 27B Teacher Recovery 재개 결과

2026-10-14. 이전 중단 기록은 `TEACHER_RUN_REPORT.md`(G2 FAIL로 중단, `a2a4bbc`)에 그대로 있다. 이 문서는 결정 81(G2 기준 보완) 뒤 G3부터 재개한 결과다. 재개 계획은 `G2_SUPPLEMENT.md`.

## 1. 결론

- G3 compatibility **PASS**(10/10). G4 31문항 155호출을 모두 마쳤다(stop 155, GPU 100%, guard 위반 0).
- 자동 판정 결과:
  - EXACT_OR_SEMANTIC_MATCH 123/155, SEMANTIC_MISMATCH 32
  - STRUCTURALLY_REPAIRABLE·REFUSAL_MISMATCH·UNPARSEABLE 0
- 정답 trace가 1개 이상인 문항은 **27/31**이다. 문항당 top-1 27개를 사람 검토해 **27개 모두 APPROVE_TRACE**, 거부 0이다.
- reasoning coverage **83/154 → 110/154**(53.9% → 71.4%). 중복 id 0.
- 기존 약점이 크게 줄었다.
  - dt dropoff 41% → 66%
  - dt both 30% → 90%
  - sido 18% → 45%
  - od_ne_dt 39% → 81%
- 27B가 회수하지 못한 4문항은 모두 Gap A의 암시적 pickup 질문이다("택시를 탄", "손님을 태운", "승차가"). 5호출 모두 `dimension_target: pickup` 또는 장소의 `od_role: pickup`을 빠뜨렸다.
- 새 SFT·DPO 0. reasoning dataset freeze 0. `qwen3.8:27b`는 store에 그대로 있다.

## 2. Git 무결성

- 시작 remote HEAD: `a2a4bbc5f139863b0edc9b1104439a5d5fef63cd`(작업 트리 깨끗함, branch `geoflow/partial-grounding`, local = remote).
- 작업 단위마다 commit → push → fetch 뒤 HEAD = `origin/geoflow/partial-grounding`을 확인했다. force push·amend·history 변경 0.

| 단위 | commit |
|---|---|
| G2 보완 결정 81 + 재개 계획 | `4b5dc64` |
| G3 첫 실행 ABORTED 보존 + guard 순서 수정 | `c3627ed` |
| G3 compatibility raw·result·REPORT | `bf13b04` |
| G4 raw trace freeze(판정 전) | `e4a5ef1` |
| G5 자동 판정·선택 freeze(검토 전) | `36f992f` |
| 사람 검토 | `30c6a0b` |
| coverage 갱신 | `83a52c7` |
| 이 REPORT + 결정 82 | 이 커밋 |

## 3. G2 기준 보완(결정 81)

- 기존 G2 FAIL(template `{{ .Prompt }}`에 `<think>` 없음)은 `import/integrity.json`(`7258410`)에 그대로 남겼다.
- 보완 기준 G2_COMPATIBILITY_RULE_SUPPLEMENTED:
  - Route A: template에 `<think>`가 있음
  - Route B: RENDERER, PARSER, capability thinking이 모두 있음
  - 현재 모델은 Route B다(`RENDERER qwen3.8`, `PARSER qwen3.5`).
- `family = qwen35`, `general.architecture = qwen35`를 이 exact-digest artifact의 정상 qwen3 계열 metadata로 인정했다.
- digest를 다시 확인했다: `/api/tags`, 그리고 G3·G4 모든 호출의 `/api/ps` digest가 `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`이다.
- G3 이후 기준, generation 설정, quality_gate_v1, ranking은 바꾸지 않았다.
- 실행 전에 추가한 것: 호출 전 precheck, timeout 3600초·재시도 없음, raw 필드 `mode`·`parsed_output`. 모두 기록·guard이며 판정 기준이 아니다.

## 4. G3 compatibility(`compatibility/REPORT.md`)

- 첫 실행은 1호출 뒤 내 guard 순서 오류로 멈췄다. precheck가 직전 호출 뒤 종료 중이던 Ollama runner를 compute 프로세스로 봤다.
  - 출력은 `compatibility/raw/ABORTED_calls_run1.jsonl`로 남기고 판정에 쓰지 않았다.
  - guard 순서를 고쳐 처음부터 다시 측정했다. 무효 측정을 대체한 것이며 rerun이 아니다.
- 유효 측정: 실제 호출 10회. 기준 6개 모두 10/10이다.

| 기준 | 결과 |
|---|---|
| HTTP 200 | 10/10 |
| thinking 비어 있지 않음 | 10/10 |
| content 비어 있지 않고 think tag 없음(분리) | 10/10 |
| JSON 객체로 parse | 10/10 |
| done_reason stop | 10/10 |
| size_vram == size(GPU 100%) | 10/10 |

- 정답(참고): 10/10 EXACT_OR_SEMANTIC_MATCH. PASS 기준이 아니다.
- 속도 기준: tok/s 중앙값 158.26 × 0.5 = **79.13 tok/s**.

## 5. Ollama 0.40.3 thinking 동작

- `think: true` 요청에 대해 응답 `message`에 `thinking`·`content`·`role`이 오고, thinking은 content와 완전히 분리된다(PARSER). content에 `<think>`가 섞인 호출은 165호출(G3 10 + G4 155) 중 0이다.
- thinking 수준(low·medium·xhigh)을 알려 주는 응답 필드는 없다. `think: true`가 어느 수준인지는 관측되지 않았다. 요청은 `think: true`만 썼다.
- 새 응답 필드: `prompt_eval_cached_count`.
- context_length: `/api/ps` 262,144(모든 호출). num_predict는 지정하지 않았고 165호출 모두 stop으로 끝났다.
  - G4 eval_count는 최소 565, 중앙값 1,117, 최대 2,077이다.
- thinking 꼴: 영어로 질문을 항목별로 분해하고, factor 초안과 짝 규칙(✓)을 확인한 뒤 "This looks correct."로 끝난다.

## 6. G4 teacher generation

| 항목 | 값 |
|---|---|
| 시각 | 2026-10-14T10:11:37Z – 10:53:29Z(약 42분) |
| 호출 | 155(31문항 × greedy 1 + sampling 4), 실패·재시도 0 |
| manifest 검증 | sha256 `65a016e0…`, 순서 hash `9850b727…` 실행 직전 일치 |
| 설정 | P0 `d7f4c12a`, `think: true`, num_predict 미지정, sampling 0.6/0.95/20, seed 2026101500 + 10 × item_index + sample_index(155개 검증) |
| 격리 | 호출마다 `keep_alive: 0`, 다음 호출 전 `/api/ps` 빈 상태 + compute 프로세스 0 확인. resident 0 |
| guard | precheck 155/155, GPU 100% 155/155, tok/s 최저 133.12(기준 79.13), 컨테이너 restart 0 |
| raw | `training/generated/p0_sft_003_teacher27b/raw/traces.jsonl`, sha256 `9933052e…`(판정 전 commit `e4a5ef1`) |

## 7. Correct trace yield(`generation/judge.json`)

| 범주 | 수 |
|---|---:|
| EXACT_OR_SEMANTIC_MATCH | 123 |
| STRUCTURALLY_REPAIRABLE | 0 |
| SEMANTIC_MISMATCH | 32 |
| REFUSAL_MISMATCH | 0 |
| UNPARSEABLE | 0 |

- 문항 단위:
  - 정답 ≥ 1: 27/31
  - greedy 정답: 26
  - sampling으로만 회수: 1(b005-42)
  - 정답 0: 4(b006-05, b006-15, b006-20, b006-26)
- 정답 수 분포: 5/5 19문항, 4/5 5문항, 3/5 2문항, 2/5 1문항, 0/5 4문항.
- 필터(thinking, stop, 결정 40-D 루프, 결정 18 길이, 문자열 왕복, 중복)로 빠진 정답 trace는 0이다. 최대 길이는 9,029 token(기준 12,887).
- top-1 선택 27개: sample 24, greedy 3.

## 8. quality_gate_v1

- 코드 sha256 `f57e2d3e…` 그대로다(판정 전 확인, 변경 0).
- flag가 붙은 trace: 전체 155 중 4, EXACT 123 중 3(UNRETRACTED_WRONG_AGGREGATION 2, GROUPING_UNIT_AS_CONCEPT 1).
- ranking이 flag 수를 먼저 보므로 선택된 27개는 모두 flag 0이다.
- 사람 판정과 비교:

| | 승인 | 거부 |
|---|---:|---:|
| flagged | 0 | 0 |
| unflagged | 27 | 0 |

- 거부가 0이라 이번 batch로는 FP·FN을 잴 수 없다. v2 필요성은 이번 결과로 새로 생기지 않았다.
  - 다만 이번에 본 "concept text 범위가 넓음"(5건)은 v1이 보지 않는 항목이다. grounding 판정에 영향이 없어 거부 사유로 쓰지 않았다.

## 9. 사람 검토(`generation/human_review.json`, `approved_traces.jsonl`)

- 검토 27, **승인 27, 거부 0**. 후보가 없는 4문항은 TEACHER_RECOVERY_FAILED이고, 대체 표본은 쓰지 않았다(규칙).
- 기준: `p0_sft_003_recovery/PLAN.md` 4절, 그리고 탐색과 확정 오판의 구분.

| tag | 수 | 내용 |
|---|---:|---|
| CLEAN_DIRECT | 20 | 질문 표현마다 factor 근거를 적고 바로 결론 |
| HESITANT | 5 | "세어줘"가 sum인지 여러 번 망설임 |
| SELF_CORRECTED | 4 | 잘못된 값을 말했다가 근거와 함께 명시적으로 철회(b004-34 answer/bucket, b005-31·b005-35·b005-39 aggregation sum) |
| TEXT_SPAN_LOOSE | 5 | concept text가 넓음(예: "실차를...세어줘", "가장 많은") |

- 확정 오판이 남은 trace는 0이다. 확인한 항목: 묶음 단위어를 place·concept로 확정, 철회 없는 aggregation, od_role·dimension_target 혼동, 없는 schema rule, unsupported 결론, thinking·final 의미 충돌.
- `answer: value`(3건)는 P0 prompt 규칙("bucket이 있으면 answer, 값이면 value")과 맞아 없는 규칙이 아니다.

## 10. Feature별 recovery(31문항)

| feature | 대상 | 정답 후보 있음 | 사람 승인 |
|---|---:|---:|---:|
| dimension_target pickup | 12 | 8 | 8 |
| dimension_target dropoff | 7 | 7 | 7 |
| dimension_target both | 6 | 6 | 6 |
| dimension_target 없음 | 6 | 6 | 6 |
| od_role ≠ dimension_target | 13 | 13 | 13 |
| Gap A | 10 | 6 | 6 |
| Gap B | 3 | 3 | 3 |
| h3 | 6 | 5 | 5 |
| sido | 4 | 3 | 3 |
| sigungu | 3 | 1 | 1 |
| emd | 13 | 13 | 13 |
| bucket | 3 | 3 | 3 |
| order | 23 | 19 | 19 |

- 실패 4문항(모두 Gap A, dt pickup, order)의 공통점: 질문에 "승차지별·출발 지역별" 같은 그룹 표현이 없다. 승차를 사건 동사로만 말한다.

| id | 질문 | 27B 출력의 차이 |
|---|---|---|
| b006-05 | 지난달 택시를 탄 건수가 가장 많은 시도는? | 5/5 `dimension_target` 누락 |
| b006-15 | 2026년 8월 부산에서 손님을 태운 건수가 가장 적은 구 두 곳은? | 5/5 `dimension_target`·부산 `od_role` 누락 |
| b006-20 | 지난달 대구에서 승차가 가장 적었던 구는? | 5/5 dimension_target은 맞지만 대구 `od_role: pickup` 누락 |
| b006-26 | 이번 달 대구 수성구에서 손님을 가장 적게 태운 H3 셀 세 곳은? | 5/5 `od_role` 누락, 4/5 `dimension_target` 누락 |

## 11. Reasoning coverage 변화(`generation/coverage_after.json`)

- **83/154 → 110/154**(0.539 → 0.714). 27B 승인 27, 기존 83과 겹침 0.
- 출처별:
  - HF Qwen3-8B R70: 70
  - HF Qwen3-8B M2 회수: 10
  - M3 기존 trace 회수: 3
  - Ollama qwen3.8:27b: 27

| feature(v006 전체) | v006 | 이전 | 이후 |
|---|---:|---:|---:|
| dt pickup | 35 | 21(60%) | 29(83%) |
| dt dropoff | 29 | 12(41%) | 19(66%) |
| dt both | 10 | 3(30%) | 9(90%) |
| dt 없음 | 80 | 47(59%) | 53(66%) |
| od_ne_dt | 31 | 12(39%) | 25(81%) |
| Gap A | 26 | 10(38%) | 16(62%) |
| Gap B | 17 | 12(71%) | 15(88%) |
| h3 | 28 | 16(57%) | 21(75%) |
| sido | 11 | 2(18%) | 5(45%) |
| sigungu | 21 | 12(57%) | 13(62%) |
| emd | 27 | 9(33%) | 22(81%) |
| bucket | 23 | 19(83%) | 22(96%) |
| order | 59 | 23(39%) | 42(71%) |
| aggregation | 40 | 25(63%) | 31(78%) |

## 12. 남은 missing(44, unique item)

| 분류 | 수 |
|---|---:|
| M1 P1/P2 — 27B recovered | 27(회수됨, 남은 수에 포함 안 됨) |
| M1 P1/P2 — 27B failed | 4 |
| M1 P3 untouched | 28 |
| M2 failed(8B 회수 실패) | 11 |
| M3 failed(b006-11) | 1 |
| **남은 합계** | **44**(M1 32, M2 11, M3 1) |

- sido는 여전히 11문항 중 5문항만 덮인다(45%). dt dropoff도 66%다.

## 13. 8B vs 27B reasoning 특성(참고, 승인 여부와 무관)

| | HF 8B R70(70) | HF 8B M2·M3 회수(13) | 27B 승인(27) |
|---|---:|---:|---:|
| thinking 글자 수 중앙값 | 3,185 | 3,143 | 2,356 |
| Wait·Hmm 평균 | 4.40 | 4.15 | 2.48 |
| Wait·Hmm 있는 trace | 56/70 | 9/13 | 25/27 |
| quality_gate_v1 flag | 5 | 3 | 0 |

- 27B는 thinking이 약 26% 짧고 망설임이 적다. 질문 표현마다 factor를 대응시키는 형식이 일정하다.
- Wait·Hmm는 대부분 "Wait, let me re-read" 식 확인이고, 결론을 뒤집는 경우는 적다.
- 학습 분포 면에서는 8B 학생과 다른 모델의 추론이다(teacher 분포 차이). 섞어 쓸 비율은 다음 dataset 결정에서 정할 일이다.

## 14. 다음 단계

1. **M1 P3 28문항 27B 확대(권장, 별도 결정 필요)**:
   - P1/P2에서 문항 회수율 27/31(87%), 승인 27/27이었다.
   - 같은 manifest·설정·gate·검토 규칙으로 P3 28문항을 사전 등록해 돌리는 것을 권장한다. 이번 단계에서는 하지 않았다.
2. **M2 실패 11 + M3 실패 1을 27B로(권장, 별도 결정)**:
   - 8B가 정답은 냈지만 trace 품질로 거부됐거나 정답이 없던 문항이다.
   - 27B의 od_ne_dt·emd·both 성능이 높아 회수 가능성이 크다. 다만 Gap A 암시적 pickup 꼴은 27B도 실패하므로, 그런 문항은 낮게 기대해야 한다.
3. **Gap A 암시적 pickup 4문항**:
   - 27B가 5/5 같은 방식으로 틀렸다. teacher 표본을 늘려도 회수 가능성이 낮다.
   - 선택지: gold 해석을 다시 확인(이 꼴에서 dimension_target·od_role을 요구하는 규칙이 prompt에 충분히 드러나는지), 또는 사람 작성 reasoning(별도 결정).
4. 학습은 coverage 공백을 정리한 뒤 dataset 전략(8B·27B trace 혼합 비율, sido·dropoff 보강)을 정하고 진행한다. 이번 단계 SFT·DPO 0.
5. `qwen3.8:27b`는 위 확대에 쓸 수 있도록 store에 둔다. 삭제 여부는 사용자 결정이다.
