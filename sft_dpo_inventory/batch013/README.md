# batch013 후보 — 요금 지표 중심 근접 대조 초안(pilot_010 준비 P2, 결정 243 AA3)

작성: 2026-10-27. **승인이 아니다.** 초안 정답, 검증 사슬·겹침 검사 통과는 승인으로 다루지 않는다. 검토는 2차 검토 → 사용자 결정(이번 세션 뒤).
보호 셋·개발 셋·protected_final 문장을 보지 않고 새로 썼다. 장소는 mock gazetteer 이름만. 학습·prompt·`SEMANTIC_CODE` 변경 없음(지문 `791c4a68`). 기준일 2026-10-26(월).

## 1. 파일

| 파일 | 내용 |
|---|---|
| `free_structures13.py` → `free_structures13.json` | c2(요금 지표 밖 tool) 구조의 family 막힘 확인(`batch010/free_structures10.py` 사본, 구조 목록만 바꿈) |
| `write_drafts13.py` → `candidates_draft.yaml` | Claude 초안 80건(c1 50, c2 30), 모두 답하는 문항(`kind: r2_contrast`). 2차에서 바꾼 22건은 줄 끝 주석에 1차 문장 |
| `build_candidates13.py` → `candidates_checked.json`(남은 77), `excluded.json`(빠진 3), `inputs_first_response.jsonl`, `inputs_self.jsonl` | `batch012/build_candidates12.py` 사본: 겹침 대상 = `validate_pf2.targets()`(RC7·batch011·012·refusal_dev v1·v2·승인 corpus v4·v5·보호 셋·개발 셋 등) + 기간·묶음 길이 검사 |
| `excluded_round1.json` | 1차 검사에서 빠진 22 기록 |

## 2. 설계와 검사

- `gap` = 겉모습이 비슷한 거부 범주(batch011·012 r2와 같은 이름). TEACH-C 지시의 "가까운 거부 범주"로 쓴다.
- **c1 요금 지표 50**(`get_billing_metrics`, batch010 빈 구조에서만):
  - 묶음(bucket + rollup) 14 — 분기·반기·하루·시간 단위 묶음 거부와 짝. 월별은 작년·올해·2026년 3–8월·5–7월, 주별은 지난달·이번 달·2026년 9월.
  - 장소 없는 요일별·시도별 차원 10 — 시간 단위 나눔·기사·회사별 거부와 짝(현재 코드는 요금 지표의 장소와 차원을 함께 받지 않음).
  - 택시 유형(개인·법인) 10 — 기사·회사·차량별 거부와 짝.
  - 일 단위 값의 집계 8 — "하루 최댓값·하루 중간값·하루 평균"(`aggregation`). b011-015·b012-001·039(개별 단위·날짜별 나열 거부)의 답할 수 있는 짝.
    장소가 있는 `active_taxi_count`·`active_taxi_ratio`의 평균·합계는 보호 넷 family라 장소 있는 문항은 최댓값·최솟값·중간값, 평균은 시도별·요일별로 썼다.
  - 지난 기간 기록·실적 8 — 예측 거부와 짝.
- **c2 다른 tool 30**: RPM 최솟값 4(시간대 조건 2 포함), 통과량 건수 H3 셀별 8, 실차 건수 차원 18.
  - 통과량 속도·운행 지표(공차율)·통행 지표(요금)는 넣지 않았다. 거부 패턴(합계)이 아닌 구조는 모두 보호 넷(selection_v2·holdout·valid98·aux_test_v1)·확장·thor family에 걸린다
    (`free_structures13.json`: family가 막히지 않은 요금 지표 밖 구조는 RPM 최솟값, 통과량 건수 H3 셀별, 실차 건수 차원뿐).
  - mock 조합: 통과량 건수 H3 셀별은 대구 장소(대구·수성구·중구·달서구·동구)만 답하고, 실차 건수 출발·도착 짝(`dimension_target=both`)은 읍면동만 답한다(1차에서 확인).
- **거부 패턴 제외**(`protected_final_v2_pc_patterns.md`): 속도·RPM·공차율의 합계, 순위에 개수 없음, 요금 지표의 장소와 차원을 함께, bucket에 집계·rollup 빠짐,
  통행 건수·요금 지표에 운행 상태, 통행 건수에 택시 유형 — 쓰지 않았고, 남은 77은 모두 Full 경로 mock에서 답함(`t2pc_outcomes_kept` answered 77).
- **겹침 검사**(결정 120 규칙): 정규화 질문·문자 3-gram Jaccard ≥ 0.5·같은 정답 grounding(대상 전부)·보호 넷 family·thor·확장 family → 뺌. 남은 77의 최대 Jaccard 0.471, 77건 모두 "남김"(결정 54식 예외 없음).
- **기간·묶음 길이**: 월별 ≥ 2개월, 주별 ≥ 2주(`period_bucket`). 위반 0.

| 묶음 | 작성 | 남김 | 빠짐(최종) |
|---|---:|---:|---|
| c1 묶음·차원·택시 유형·일 단위·실적 | 14 · 10 · 10 · 8 · 8 | 14 · 10 · 10 · 7 · 7 = **48** | 2(같은 정답 grounding: b013-040 RC6·batch011, b013-043 RC5–7·batch010) |
| c2 RPM·통과량 건수·실차 건수 | 4 · 8 · 18 | 4 · 8 · 17 = **29** | 1(같은 정답 grounding: b013-072 batch010) |

- **1차 → 2차**: 1차 22 빠짐(Jaccard ≥ 0.5 7 — batch011·012·refusal_dev v1 문장과 문형이 비슷; 같은 정답 grounding 5; mock 조합 10 — 통과량 건수 H3 셀별 6, 실차 건수 짝 4)을 바꿨다.
  2차에서 같은 정답 grounding 3이 남아 뺐다(다시 쓰지 않음).

## 3. J-b013·J-p9-b013·J-b2f-b013(진단, 판정 아님)

GPU 작업이 끝난 뒤 `build_review13.py`로 채운다.
