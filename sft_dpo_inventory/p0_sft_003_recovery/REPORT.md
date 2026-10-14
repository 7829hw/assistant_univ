# P0 SFT 3차 데이터 완성 1단계

2026-10-14. 계획 `PLAN.md`(커밋 `fe59401`), 결정 72·73.

- 27B 반입·호출, SFT, DPO, 새 prompt, P0.4, pruning, quantization, R70 403 평가는 하지 않았다.
- 기존 p0_sft_001·002·003_prep 파일은 고치지 않았다.

## 1. 결론

- **M3 4:**
  - 4문항 모두 같은 문자열의 token 분할 차이(예: `-g`+`un` vs `-gun`)로 필터에서 빠졌다. 새 생성 없이 회수 가능했다.
  - 사람 검토에서 3개 승인, 1개 거부(b006-11: `시군구`를 place concept로 냄).
- **M2 21 × 8:**
  - 실제 호출 168. 17문항에서 새 정답 trace가 나왔고, 필터를 통과한 후보가 있는 문항은 16이다.
  - 문항당 1개 사람 검토에서 **10개 승인**, 6개 거부. 실패 11(거부 6, 후보 없음 5).
- **reasoning coverage: 70 → 83/154(53.9%).**
  - dimension_target pickup 31% → 60%, Gap A 19% → 38%.
  - dropoff·both는 그대로(41%·30%).
- **남은 hard subset:**
  - M1 59(변화 없음, 8B 추가 sampling 안 함), 남은 M2 11, M3 1.
  - 27B 대상은 M1 ∩ {P1, P2} = **31문항**(사전 규칙 그대로).
- **27B:**
  - 과거 승인 teacher는 Ollama `qwen3.8:27b`(digest `aaee06c3…`, Q4_K_M, 17.7 GB)다.
  - 현재 환경에는 없고 출처 기록도 없다. 반입하지 않았다.
- **추가 관찰:**
  - 사전 등록한 자동 clean ranking(wrong-value mention 기반)은 사람 판정과 거의 맞지 않았다.
  - 승인 10 중 자동 tier는 SELF_CORRECTED 9였다. 거부 6 중 3개는 CLEAN_DIRECT였다.
  - 정규식이 부정·rollup 언급을 오탐하고, 핵심 실패 유형(묶음 단위어를 concept로 냄)을 잡지 못하기 때문이다.

## 2. Git / 실행 무결성

- 시작: local = remote = `bdf0c96`, 작업 트리 깨끗함, branch `geoflow/partial-grounding`. 원격의 이 branch에 새 커밋은 없었다(`geoflow/sft-dpo-t2pc`만 갱신).
- 작업 단위마다 commit → push → fetch 뒤 HEAD = `origin/geoflow/partial-grounding`을 확인했다.

| 단위 | commit |
|---|---|
| 사전 등록(결정 72) | `fe59401` |
| M3 재검사 | `ee5af8a` |
| M2 sampling 원문 | `be149bd` |
| M2 판정·회수 trace | `2a2c82c` |
| coverage manifest | `fd9253b` |
| 27B manifest·반입 계획 | `d34362d` |
| REPORT(결정 73) | 이 커밋 |

- **M2 실행**: 14:01–14:28 KST(1,599초), precheck 통과(GPU 0 MiB, Ollama 모델 없음), RTX PRO 6000 Blackwell.
  - BF16·SDPA, `Qwen/Qwen3-8B@b968826d`(기존 cache, 새 다운로드 없음). Ollama 호출 없음.
  - 원문 sha256 `b611dd08…`.

## 3. M3 재검사(`m3_recovery.json`)

| 문항 | 정답 trace | 탈락 이유 | 불일치 | 판정 | 자동 tier | 사람 검토 |
|---|---:|---|---|---|---|---|
| b004-19 | 1 | 결정 4 왕복 | token 22: `-g`·`un` vs `-gun`(708 → 706) | RECOVERABLE | CLEAN_DIRECT | 승인 |
| b005-19 | 1 | 결정 4 왕복 | token 30: `or`·`ang` vs `orang`(694 → 688) | RECOVERABLE | MINOR | 승인 |
| b006-10 | 1 | 결정 4 왕복 | token 61: `-g`·`un` vs `-gun` | RECOVERABLE | SELF_CORRECTED | 승인 |
| b006-11 | 1 | 결정 4 왕복 | token 57: 같은 꼴 | RECOVERABLE | MINOR | **거부**(`시군구`를 place concept로) |

- 4개 모두 stop, `</think>` 닫힘, EOS 끝, 문자열 왕복이 바이트 단위로 같다. 내용 손실은 없었다.
- 기존 307개에 새 filter를 소급 적용하지 않았다.

## 4. M2 8B 추가 sampling(`m2_quality.json`)

- 호출 168(21 × 8, seed `2026101400 + m2_index`), truncation 0.

| 판정 범주 | 수 |
|---|---:|
| EXACT_OR_SEMANTIC_MATCH | 46 |
| STRUCTURALLY_REPAIRABLE | 30 |
| SEMANTIC_MISMATCH | 92 |

- 새 정답 trace가 있는 문항 17/21. 필터 후보가 있는 문항 16(b005-54는 정답 1개가 필터에서 빠짐).
- 후보 tier 합: CLEAN_DIRECT 7, MINOR_SELF_CORRECTION 8, SELF_CORRECTED 29.
- 선택(문항당 1): CLEAN_DIRECT 4, MINOR 1, SELF_CORRECTED 11.

## 5. M2 clean trace review(`m2_review.json`)

| 결과 | 수 | 문항 |
|---|---:|---|
| 승인(회수) | 10 | ann-29dc…, b004-18, b005-04, b005-34, b005-41, b006-04, b006-08, b006-13, b006-14, b006-28 |
| 거부 | 6 | ann-f780…(없는 규칙: answer bucket), b004-40(구를 SUBCOND 장소로), b005-33(aggregation sum 미철회), b005-58(`시도` concept + answer bucket), b006-02(`H3 셀` concept), b006-34(`H3 셀` concept) |
| 후보 없음 | 5 | b004-22, b005-36, b005-54, b006-18, b006-19 |

- 거부 6 중 4가 묶음 단위어를 concept·장소로 낸 경우다(p0_sft_002·003 분석의 주요 실패 유형과 같다).
- 자동 tier와 사람 판정:

| | CLEAN_DIRECT | MINOR | SELF_CORRECTED |
|---|---:|---:|---:|
| 승인 10 | 1 | 0 | 9 |
| 거부 6 | 3 | 1 | 2 |

- 자동 지표가 품질을 가르지 못했다. SELF_CORRECTED의 다수는 "aggregation 넣지 않음", "No unsupported elements" 같은 문장을 잘못 센 오탐이었다.

feature별 M2(21 중):

| feature | 문항 | 새 정답 | 후보 | 승인 |
|---|---:|---:|---:|---:|
| dimension_target | 15 | 11 | 11 | 8 |
| od_role ≠ dimension_target | 6 | 4 | 4 | 2 |
| Gap A | 7 | 5 | 5 | 4 |
| Gap B | 2 | 2 | 2 | 1 |
| bucket | 1 | 1 | 1 | 1 |
| aggregation | 3 | 3 | 3 | 1 |

## 6. reasoning coverage 변화(`coverage_manifest.json`)

- R70 70 + M3 3 + M2 10 = **83/154(53.9%)**(unique item).
- 남은 missing 71: M1 59, M2 11, M3 1.
- 회수 trace 13개는 provenance와 함께 `recovered_traces.jsonl`에 있다.
  - 남긴 필드: teacher_model, teacher_revision, generation_batch, seed, quality_tier, review_decision.
- 최종 reasoning dataset은 아직 freeze하지 않는다.

## 7. semantic feature별 coverage

| feature | v006 | R70 | 회수 뒤 | 비율 변화 |
|---|---:|---:|---:|---|
| dt pickup | 35 | 11 | 21 | 0.31 → 0.60 |
| dt dropoff | 29 | 12 | 12 | 0.41 → 0.41 |
| dt both | 10 | 3 | 3 | 0.30 → 0.30 |
| od_role ≠ dt | 31 | 10 | 12 | 0.32 → 0.39 |
| Gap A | 26 | 5 | 10 | 0.19 → 0.38 |
| Gap B | 17 | 11 | 12 | 0.65 → 0.71 |
| bucket | 23 | 18 | 19 | 0.78 → 0.83 |
| order | 59 | 17 | 23 | 0.29 → 0.39 |
| emd | 27 | 6 | 9 | 0.22 → 0.33 |
| sido | 11 | 2 | 2 | 0.18 → 0.18 |
| sigungu | 21 | 8 | 12 | 0.38 → 0.57 |
| h3 | 28 | 13 | 16 | 0.46 → 0.57 |

- R70 편향이 pickup·Gap A·sigungu·h3에서는 줄었다.
- dropoff·both·sido는 그대로다. 이 셋은 주로 M1(8B가 9/9 실패)에 남아 있다.

## 8. 남은 M1

- 59문항, 이번에 생성하지 않았다(규칙).
- 남은 M2 11, M3 1(b006-11)은 이번 규칙상 실패로 확정했다. 다른 표본으로 바꾸지 않았다.
- 27B 후보로 올릴지는 다음 단계 결정이다.

## 9. 27B teacher 대상(`teacher27b_manifest.json`)

- M1 ∩ {P1, P2} = **31**(P1 22, P2 9). 사전 규칙으로 계산했고 M2 결과와 무관하다.
- 출처: v005 18, Gap A 10, Gap B 3.
- dimension_target pickup 12, dropoff 7, both 6, 없음 6. od_role ≠ dt 13, bucket 3.
- measure: trip_count 25, speed 3, revenue·fare·active_taxi_ratio 각 1.
- 문항마다 8B 9표본의 판정 범주와 원 출력 diff 빈도를 "왜 8B가 실패했는지"로 남겼다.
- 계획: greedy 1 + sampling 4, 최대 155 호출.

## 10. 27B 반입 계획(`TEACHER27B_IMPORT_PLAN.md`)

| 항목 | 값 |
|---|---|
| 모델 | Ollama `qwen3.8:27b`, digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`, Q4_K_M |
| 크기·GPU | 17.7 GB, size_vram 약 17.3 GiB(context 262,144 기준) |
| 과거 경로 | 옛 장비 Ollama 0.34.4/0.35.1 컨테이너 |
| 현재 | Ollama 0.40.3, 저장소에 없음 → 새 반입이 필요 |
| 출처 | 기록 없음 → 사용자 지정 필요 |
| 무결성 | 반입 뒤 `/api/tags` digest = `aaee06c3…`, Modelfile·capabilities 일치, 렌더링 10문항 확인 |
| 실행 | unload_per_question, HF와 동시 실행 금지, GPU 확인·속도 guard |
| 삭제 | 사용자 결정 |

**실제 27B는 반입하지 않았다.** pull·download·copy를 하지 않았고 호출도 없었다.

## 11. scope/refusal 미해결 영역

- **scope 역조회**: v006 학습 예제 0.
  - 평가 보호 family와 겹쳐 Gap C 제외(결정 67)다.
  - 평가 독립성을 깨지 않는 방법이 정해지기 전에는 추가하지 않는다(`known_uncovered_family`).
- **refusal**: v006에 unsupported·needs_clarification 응답 target이 0이다.
  - 운영 경로 정지 target은 12개(UNCONSUMED_CONDITION 등)다. 계약상 정지 코드로 끝나는 grounding이지 거부 응답이 아니다.
  - reasoning 보충과 섞지 않는다.
- 둘 다 **batch007 후보**(scope 역조회·refusal coverage)로 남긴다. 생성하지 않았다.

## 12. 다음 단계

- **27B 반입을 추천한다. 범위는 M1 P1·P2 31문항이다.**
  - 이번 M2 회수로 8B 범위 문항은 10개 늘었지만, dropoff·both·sido coverage는 M1에 묶여 있어 8B로는 회복되지 않았다.
  - 사용자 결정이 필요하다: 반입 원본 지정, 반입 승인.
- **8B 추가 sampling은 M1의 대안이 아니다**(9/9 실패). 남은 M2 11의 재시도 여부는 별도 실험으로 정한다(sample 수를 즉석에서 늘리지 않음).
- **자동 clean ranking 개선을 권한다.**
  - 이번 결과로 wrong-value 정규식은 품질을 가르지 못했다.
  - 다음 수집(27B 포함) 전에 "묶음 단위어를 concept·장소로 냄", "없는 규칙(answer bucket)" 감지를 ranking 앞에 넣는 규칙을 결과 전에 사전 등록하는 것을 권한다.
- 최종 reasoning dataset freeze와 full-reasoning SFT는 27B 결과 뒤에 한다.
