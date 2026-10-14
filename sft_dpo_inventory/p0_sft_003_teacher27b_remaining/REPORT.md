# P0 Reasoning Coverage 완성 — Remaining Teacher Recovery

2026-10-14. 계획 `PLAN.md`(커밋 `7f791a5`), 결정 83. 앞 단계: `p0_sft_003_teacher27b/TEACHER_RUN_RESUME_REPORT.md`(결정 79–82).

## 1. 결론

- 모델이 생성한 reasoning coverage가 **110/154 → 148/154(96.1%)**가 됐다.
- Track A(40문항, 27B 200호출) 결과:
  - EXACT_OR_SEMANTIC_MATCH 185/200
  - 정답이 있는 문항 39/40
  - 사람 승인 38, 거부 1
- 그룹별 승인: M1 P3 **28/28**, M2 실패 **9/11**, M3 실패 **1/1**.
- Track B(implicit-pickup 4문항, 모델 호출 0):
  - gold 4/4 CLEAR_GOLD다.
  - 기존 20 call의 실패는 모두 생략이다(dimension_target 14, od_role 15). 틀린 값은 0이다.
  - 실패 원인은 20/20 의미 이해 실패 + P0 prompt coverage gap이다. JSON 직렬화 누락은 0이다.
  - canonical rationale 후보 4개를 썼다. training_inclusion false, coverage 미포함.
- 남은 6문항 중 5문항은 같은 꼴이다. 승차·하차를 사건 동사로만 말한 질문에서 장소 제한 끝(od_role)이나 묶는 끝(dimension_target)을 빠뜨린다.
  - Track B 4문항(승차)과 Track A의 b006-19(하차)다.
  - 나머지 1문항(b006-34)은 top-1 거부다.
- dataset freeze 0, SFT·DPO 0, P0 prompt 변경 0. `qwen3.8:27b`는 store에 그대로 있다.

## 2. Git 무결성

- 시작 remote HEAD: `65eebd61356ec15014d69c7653572f1c2c2f9522`(작업 트리 깨끗함, local = remote).
  - fetch에서 보인 새 commit은 다른 branch(`geoflow/sft-dpo-t2pc`)뿐이라 이번 작업과 충돌이 없다.
- 작업 단위마다 commit → push → fetch 뒤 HEAD = `origin/geoflow/partial-grounding`을 확인했다. force push·amend 0.

| 단위 | commit |
|---|---|
| partition·Track A manifest·PLAN·결정 83(+ 스크립트 인자 추가) | `7f791a5` |
| Track B implicit-pickup 검토 | `fa95da2` |
| Track A raw freeze(판정 전) | `4419954` |
| Track A 자동 판정·선택 freeze(검토 전) | `f85126f` |
| Track A 사람 검토 | `e956940` |
| coverage·remaining manifest | `5c4efef` |
| 이 REPORT + 결정 84 | 이 커밋 |

## 3. 시작 coverage와 missing partition(`partition.json`)

- 코드로 다시 계산했다(`build_target_manifest.py`).
  - covered 110: R70 70, M2 회수 10, M3 회수 3, 27B P1/P2 27. 출처 간 중복 0.
  - missing 44 = M1 P3 28 + M2 실패 11 + M3 실패 1 + 27B 실패 4. **합·중복 검사 통과.**

## 4. Track A manifest(`target_manifest.json`)

- 40문항(A1 M1 P3 28, A2 M2 실패 11, A3 M3 실패 1). 순서는 A1 → A2 → A3, 그룹 안은 prep manifest 순서다.
- manifest sha256 `d8c1bd5d…`, item 순서 sha256 `0bdcf110…`. 둘 다 생성 직전에 확인했다.
- 구성:
  - source: v005 32, Gap A 6, Gap B 2
  - dimension_target: 없음 27, dropoff 10, pickup 2, both 1
  - od_ne_dt 6
- 문항마다 기록: 이전 8B 시도(p0_v006_hf 9표본, M2 8표본), 이전 27B 시도 0, 이전 실패 이유.

## 5. 27B generation

| 항목 | 값 |
|---|---|
| 시각 | 2026-10-14T11:26Z – 12:12:51Z(약 47분) |
| 호출 | 200(40 × greedy 1 + sampling 4), 실패·재시도 0 |
| 실행 조건 | G3 때와 같음: digest `aaee06c3…`, Ollama 0.40.3, GPU `GPU-d4308fbb…`, RENDERER/PARSER. G3 재실행 없이 호출마다 precheck |
| seed | 2026101600 + 10 × item_index + sample_index(200개 검증, 이전 batch와 겹침 없음) |
| 격리 | 호출마다 `keep_alive: 0`, `/api/ps` 빈 상태 + compute 프로세스 0 확인 뒤 다음 호출. resident 0 |
| guard | stop 200, HTTP 200, GPU 100% 200, tok/s 최저 131.34(기준 79.13), 컨테이너 restart 0 |
| raw | `generation/raw/traces.jsonl` sha256 `c6e0b316…`(판정 전 commit `4419954`) |

- 기록 이탈:
  - 200호출을 마친 뒤 summary를 쓰는 단계에서 스크립트가 상대 경로 manifest를 처리하지 못해 rc=1로 끝났다.
  - 호출과 raw에는 영향이 없다. summary는 raw에서 같은 필드로 다시 썼고(`generation_summary.json` note), 경로 처리는 고쳤다.

## 6. Automatic judge(`generation/judge.json`)

| 범주 | 수 |
|---|---:|
| EXACT_OR_SEMANTIC_MATCH | 185 |
| STRUCTURALLY_REPAIRABLE | 0 |
| SEMANTIC_MISMATCH | 15 |
| REFUSAL_MISMATCH | 0 |
| UNPARSEABLE | 0 |

- 문항 단위:
  - 정답 ≥ 1: 39/40
  - greedy 정답: 37
  - sampling으로만 회수: 2(b005-11, b005-45)
  - 정답 0: 1(b006-19)
- 정답 수 분포: 5/5 33, 4/5 4, 3/5 1, 1/5 1, 0/5 1.
- 필터로 빠진 정답 trace 0. top-1 선택 39(sample 31, greedy 8).
- quality_gate_v1(sha256 `f57e2d3e…`, 변경 0):
  - flag 붙은 trace는 200 중 1(UNRETRACTED_WRONG_AGGREGATION)이다.
  - 선택된 39는 모두 flag 0이다.

## 7. Human review(`generation/human_review.json`, `approved_traces.jsonl`)

- 검토 39: 승인 38, 거부 1. 대체 표본은 쓰지 않았다.
- tag 분포:
  - CLEAN_DIRECT 33
  - HESITANT 3, SELF_CORRECTED 3(탐색 뒤 근거와 함께 철회)
  - TEXT_SPAN_LOOSE 2(묶음 단위어 아님)
- **거부: b006-34**(A2, M2 실패)
  - thinking은 "H3 셀은 dimension이지 concept가 아니다"라고 했다. 그런데 최종 JSON은 measure concept의 text를 묶음 단위어 "H3 셀"로 적었다.
  - reasoning과 final이 충돌하고, 묶음 단위어를 concept text로 쓰는 꼴을 학습시킬 수 있다. 8B·M3 거부 사유와 같은 계열이다.
  - factor(pickup·h3·dropoff·bottom 2)는 맞았다. 규칙대로 TEACHER_RECOVERY_FAILED이고 다른 정답 표본으로 바꾸지 않았다.
- quality_gate_v1와 사람 판정:

| | 승인 | 거부 |
|---|---:|---:|
| flagged | 0 | 0 |
| unflagged | 38 | 1 |

- v1이 놓친 1건(concept text가 묶음 단위어)은 v1의 GROUPING_UNIT_AS_CONCEPT가 subtype만 본다는 한계다. v1은 고치지 않았고, v2 후보 항목으로 기록만 한다.

## 8. M1 P3 결과

| 그룹 | target | correct ≥ 1 | selected | approved |
|---|---:|---:|---:|---:|
| M1 P3 | 28 | 28 | 28 | **28** |

- 호출 단위 정답 132/140. P3는 aggregation·vicinity·rpm·공차율·bucket 같은 단순 단일 장소 질문이 많았고, 27B가 거의 다 맞혔다.

## 9. M2/M3 결과

| 그룹 | target | correct ≥ 1 | selected | approved |
|---|---:|---:|---:|---:|
| M2 failed | 11 | 10 | 10 | **9** |
| M3 failed | 1 | 1 | 1 | **1** |

- 8B가 "없는 규칙"이나 "묶음 단위어 concept" 때문에 거부됐던 문항이 27B에서는 깨끗하게 회수됐다.
  - 예: ann-f78087861d0826ae8a7f(answer bucket 지어냄), b005-58(시도 concept), b006-11(M3, 시군구 place).
- 실패 2:
  - b006-19: 정답 0. 5/5가 dimension_target dropoff는 맞히고 대구 od_role dropoff를 빠뜨렸다. Track B와 같은 꼴의 하차 쪽이다.
  - b006-34: top-1 거부(7절).

## 10. Feature별 recovery(Track A)

| feature | target | correct ≥ 1 | approved |
|---|---:|---:|---:|
| dimension_target pickup | 2 | 2 | 2 |
| dimension_target dropoff | 10 | 9 | 8 |
| dimension_target both | 1 | 1 | 1 |
| od_role ≠ dimension_target | 6 | 6 | 5 |
| Gap A | 6 | 5 | 5 |
| Gap B | 2 | 2 | 1 |
| h3 | 6 | 6 | 5 |
| sido | 5 | 5 | 5 |
| sigungu | 6 | 5 | 5 |
| emd | 5 | 5 | 5 |
| bucket | 1 | 1 | 1 |
| order | 13 | 12 | 11 |

## 11. Track B implicit-pickup review(`implicit_pickup/REVIEW.md`)

- 새 모델 호출 0(8B 0, 27B 0). 기존 27B 20 trace만 읽었다.
- gold 판정: 4/4 **CLEAR_GOLD**. LINGUISTICALLY_AMBIGUOUS 0, CONTRACT_DEPENDENT 0, GOLD_PROBLEM 0.
  - 장소 제한의 끝(od_role)과 묶는 끝(dimension_target)을 따로 판단했다. 두 slot 모두 pickup이다.
  - b006-05는 장소가 없어 dimension_target만 해당한다.
- P0 prompt(수정 없음)와의 연결:
  - dimension_target 예시는 "승차가 많은 읍면동", "출발 지역별" 같은 그룹 표현뿐이다. "탄/태운" 예는 없다.
  - od_role 예시는 "A에서 출발/B에 도착"뿐이다.
  - "'손님을 태운 운행'은 trip" 규칙을 27B가 끝 정보를 지우는 근거로 인용했다.
  - h3 + dimension_target 예가 없다(27B가 "행정구역에만"이라고 2번 추론).
  - 장소 제한 끝과 묶는 끝이 같은 예가 없다.

## 12. Existing 27B failure matrix(`implicit_pickup/failure_matrix.csv`)

| | correct | omitted | wrong | 해당 없음 |
|---|---:|---:|---:|---:|
| dimension_target(20) | 6 | 14 | 0 | 0 |
| od_role(장소 있는 15) | 0 | 15 | 0 | 5 |

- 둘 다 맞음 0, 하나만 틀림 11, 둘 다 틀림 9. 다른 factor는 20/20 gold와 같다.
- dimension_target을 맞힌 6은 b006-20 5(prompt 예시와 같은 꼴)와 b006-26 k=3 1이다.

| thinking tag | call 수 |
|---|---:|
| SEMANTIC_UNDERSTANDING_FAILURE | 20 |
| SERIALIZATION_OMISSION | 0 |
| OD_ROLE_DIM_TARGET_COLLAPSE | 1(b006-20 k=2) |
| PROMPT_COVERAGE_GAP | 20 |

## 13. Canonical rationale candidates(`implicit_pickup/canonical_rationale_candidates.jsonl`)

- CLEAR_GOLD 4문항에 각 1개, 모두 4개다. 형식: measure / place restriction / od_role / grouping dimension / dimension_target / order + 한두 문장 bridge.
- **training_inclusion = false, counted_in_coverage = false, replaces_teacher_trace = false.**
- b006-19(하차 쪽 같은 꼴)는 Track A 대상이었다. Track B 범위 밖이라 후보를 쓰지 않았다.

## 14. 최종 model-generated reasoning coverage(`coverage_after.json`)

- **110/154 → 148/154(0.714 → 0.961).** Track A 승인 38, 기존 110과 겹침 0. Track B 후보는 더하지 않았다.

| 출처 | 수 |
|---|---:|
| HF Qwen3-8B R70 | 70 |
| HF Qwen3-8B M2 회수 | 10 |
| M3 기존 trace 회수 | 3 |
| Ollama qwen3.8:27b P1/P2 | 27 |
| Ollama qwen3.8:27b remaining(Track A) | 38 |
| **합계** | **148** |

| feature(v006 전체) | v006 | 이전 | 이후 |
|---|---:|---:|---:|
| dt pickup | 35 | 29(83%) | 31(89%) |
| dt dropoff | 29 | 19(66%) | 27(93%) |
| dt both | 10 | 9(90%) | 10(100%) |
| dt 없음 | 80 | 53(66%) | 80(100%) |
| od_ne_dt | 31 | 25(81%) | 30(97%) |
| Gap A | 26 | 16(62%) | 21(81%) |
| Gap B | 17 | 15(88%) | 16(94%) |
| h3 | 28 | 21(75%) | 26(93%) |
| sido | 11 | 5(45%) | 10(91%) |
| sigungu | 21 | 13(62%) | 18(86%) |
| emd | 27 | 22(81%) | 27(100%) |
| bucket | 23 | 22(96%) | 23(100%) |
| order | 59 | 42(71%) | 53(90%) |
| aggregation | 40 | 31(78%) | 40(100%) |

## 15. 남은 missing(`remaining_manifest.json`)

| id | taxonomy | 원래 분류 | feature |
|---|---|---|---|
| b006-05 | IMPLICIT_PICKUP_REPEAT_FAILURE | M1 P1/P2 | dt pickup, Gap A, sido |
| b006-15 | IMPLICIT_PICKUP_REPEAT_FAILURE | M1 P1/P2 | dt pickup, Gap A, sigungu |
| b006-20 | IMPLICIT_PICKUP_REPEAT_FAILURE | M1 P1/P2 | dt pickup, Gap A, sigungu |
| b006-26 | IMPLICIT_PICKUP_REPEAT_FAILURE | M1 P1/P2 | dt pickup, Gap A, h3 |
| b006-19 | NO_CORRECT_27B_TRACE | M2 | dt dropoff, Gap A, sigungu(하차 쪽 같은 꼴) |
| b006-34 | TOP1_REJECTED | M2 | dt dropoff, od_ne_dt, Gap B, h3 |

- 6문항이 모두 Gap A·B의 dimension_target 문항이다. 5문항은 사건 동사로만 끝을 말하는 implicit-endpoint 꼴이다.
- 이 꼴은 승인된 148 trace에 거의 없다. teacher 데이터만으로는 학생이 배우기 어렵다.

## 16. 다음 dataset/SFT 추천

**판단: Path A(coverage ≥ 90%)와 Path B(남은 것이 거의 implicit-endpoint 하나)가 함께 해당한다.**

1. reasoning 데이터 후보:
   - 모델 생성 148 trace(8B 83 + 27B 65, provenance 유지)를 기본으로 한다. 아직 freeze하지 않았다.
   - 다음 결정에서 `reviewed_reasoning_v001` 후보로 묶을지 정한다.
2. implicit-endpoint 6문항은 세 선택지 중 하나를 다음 결정으로 정한다.
   - **(권장) teacher + canonical mixed**: Track B 4개 후보에 b006-19(하차) 후보를 더해 짧은 explicit rationale로 넣는다.
     - teacher를 흉내 낼 수 없는 경계이므로 짧은 semantic bridge가 더 맞는 supervision이다.
     - 학습 꼴이 teacher trace와 다르므로, canonical rationale 비율·형식이 `<think>` 첫 token과 thinking 길이 분포를 해치지 않는지 사전 점검이 필요하다(p0_sft_001·002 교훈).
     - b006-34는 다른 정답 표본이 있지만 규칙상 대체하지 않는다. 사람 작성 rationale 대상으로 둘지는 따로 정한다.
   - all-model-reasoning: 148만 쓰고 6은 비운다. 평가에서 implicit-endpoint 꼴이 약점으로 남을 위험이 있다.
   - P0 prompt에 사건 동사 예시를 추가한 뒤 teacher 재수집: prompt 변경은 평가 조건 전체를 바꾸므로 별도 실험으로만 한다.
3. quality_gate v2 후보 항목: concept text가 묶음 단위어인 경우(b006-34). v1은 바꾸지 않는다.
4. 8B 83 vs 27B 65의 reasoning 분포 차이(27B가 짧고 덜 망설임)는 혼합 비율 결정에서 다룬다.
5. 이번 단계 SFT·DPO 0. `qwen3.8:27b`는 store에 둔다(삭제 여부는 사용자 결정).
