# batch010 후보 — P 약점 보강(pilot_007 A단계 C3, 결정 169)

작성: 2026-10-18. **승인이 아니다.** 초안 gold, 검증 사슬 통과, 겹침 검사 통과는 승인으로 다루지 않는다. 검토는 지금까지와 같이 Claude 2차 검토 → 사용자 결정.
보호 셋 문장을 보거나 바꿔 쓰지 않았다. 장소는 mock gazetteer 이름만(시도 4·시군구 8·읍면동 10). 학습·prompt·`SEMANTIC_CODE` 변경 없음(지문 `791c4a68`).
두 arm 공통 데이터다(B단계 RC4 = RC3c + batch010 승인분 + S-focus).

## 1. 파일

| 파일 | 내용 |
|---|---|
| `free_structures10.py` → `free_structures10.json` | 약점별 구조 854개의 family 키·현재 코드 응답 → 보호 넷(selection_v2·holdout·valid98·aux_test_v1)·selection_v1·thor 보호 family·확장 family와 겹치지 않고 현재 코드가 답하는 빈 구조 244개(문장 없음) |
| `write_drafts10.py` → `candidates_draft.yaml` | Claude 초안 55건(1차 50 + 2차 5). 질문·업체 형식 정답 호출·근거를 손으로 적음 |
| `build_candidates10.py` → `candidates_checked.json`(남은 50), `excluded.json`(빠진 5), `inputs_first_response.jsonl`, `inputs_self.jsonl` | batch009 검사 도구 사본(대상에 batch009 후보, 학습 비교 대상 승인 corpus v2) + 결정 120 분류 |
| `base_first_response.jsonl` | J-b010 base 첫 응답(vLLM BF16 greedy, 원문 없이 채점용) — GPU 큐에서 생성 |
| `build_review10.py` → `review/batch010_review_v1.xlsx` | 검토 시트(J-b010 뒤 생성) |

## 2. 설계(약점 셋, 결정 169 표)

| 약점 | 목표 | 근거(세션 4) | 구조 |
|---|---:|---|---|
| g1 "<지역> 소속 택시"에서 장소 유지 | 20 | P의 U 증가 +50 중 대부분이 장소 빠뜨림, 주로 "소속" 질문(`pilot_006/post/a3_u.json`); RC3c의 소속 teacher 질문 1개뿐 | 장소 하나(od 없음) + 결제 측정(활성 택시 대수·가동률·운행 일수·수입); 빈 구조가 집계만 4개라 나머지 16은 bucket 구조 |
| g2 "…으로 들어온·…에서 나간" 장소 유지 | 10 | 같은 실패의 둘째 묶음 | 실차 건수, 장소가 한 끝(들어온 = 하차, 나간 = 승차) + dimension; 빈 구조 13개가 모두 dimension 있음 |
| g3 bucket과 bucket ↔ dimension 대조 | 20 | bucket 문항은 주·개발 다섯 셋 모두 P 열세(`a4_a5.json`) | bucket 10(주별·월별 먼저 집계, 안쪽·바깥 집계를 둘 다 말함) + 대조 10(요일별·시도별 = 먼저 집계하지 않고 결과를 나눔) |

- 현재 코드 제약(빈 구조 찾기에서 확인): billing dimension은 장소(scope)와 함께 받지 않는다(`PARAM_VALUE_FORBIDS_INPUT`) → 대조 문항은 장소 없이 썼다.
  bucket + rollup은 안쪽 aggregation이 있어야 한다(`AMBIGUOUS_INNER_AGGREGATION`). 요금(trip_metrics)·공차율(drive_metrics)의 소속 구조는 모두 보호 넷 family였다.
- 표기: 장소 하나 = `get_place_scope` + `$resolve.scope`, 한 끝 장소 = `scope_pickup`/`scope_dropoff`. 기준일 2026-09-25.

## 3. 검사 결과(결정 120)

| 약점 | 작성(1차 + 2차) | 남김 | 빠짐 |
|---|---:|---:|---|
| g1 소속 | 20 + 3 | **20** | 3: Jaccard ≥ 0.5(valid98 s03c 0.517, 업체 100 098 0.50, 학습 ann-d983… 0.536) |
| g2 들어온·나간 | 10 + 1 | **10** | 1: b010-25 동성로동 H3 셀 — 검증 사슬 실패·Full 경로 `NOT_FOUND`(mock에 그 구역 H3 셀 없음) |
| g3 bucket | 10 | **10** | 0 |
| g3 bucket ↔ dimension | 10 + 1 | **10** | 1: b010-46 batch008·학습 데이터와 같은 grounding |
| 합계 | 55 | **50** | 5 |

- 남은 50건 모두 검증 사슬(Full·Partial 같은 판정·mock, 정답 호출과 일치)·T2PC 경로 답함, 결정 120 분류 "남김"(예외 없음).
- 측정 span을 찾지 못한 7건(g2: b010-21·23·24·26·27·28·30 — 질문에 "건수"가 없고 "세어줘/셌을 때/도착한" 등): 검토 시트에서 "수정(측정 span)" 권고 예정(batch009 b009-27·38과 같음).

## 4. 남은 일

- J-b010(base 첫 응답, 두 arm 표본 greedy 1 + 8)을 넣어 검토 시트를 만든다(`build_review10.py`).
- 사람 검토(Claude 2차 검토 권고 → 사용자 결정). 승인분은 B단계 RC4에 들어간다(두 arm 공통).
