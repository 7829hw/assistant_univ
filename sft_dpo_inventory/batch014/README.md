# batch014 후보 — 근접 대조 보강·OD 상위 N 초안(결정 263 D5, ablation_013)

작성: 2026-11-06. **승인이 아니다. 이번 세션에서 학습에 쓰지 않는다.** 초안 정답, 검증 사슬·겹침 검사 통과, Claude 2차 검토 권고는 승인으로 다루지 않는다. 승인은 사용자가 세션 뒤에 한다.
대상 유형은 `ablation_012/CONTRAST_PLAN_DRAFT.md`의 서명 수준 정보(tool·metric·aggregation·시간 단위·지역 유형)로만 정했다. CT10K·H-dev·E1·H-final의 문항 원문·template 문장은 열지 않았고 흉내 내지 않았다.
장소는 mock gazetteer 이름만. 기준일 2026-10-26(월, batch013과 같음). 학습·prompt·`SEMANTIC_CODE` 변경 없음.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `free_structures14.py` → `free_structures14.json` | T1–T5(+ 운행 요금 POI 주변) 구조 414개의 family 막힘·현재 코드 응답 확인(`batch013/free_structures13.py` 사본, 구조 목록만 바꿈) |
| `write_drafts14.py` → `candidates_draft.yaml` | Claude 초안 46건(T1v 12·T3 16·T4 6·T5 12). 2차에서 고친 20건은 줄 끝 주석에 1차 문장 |
| `build_candidates14.py` → `candidates_checked.json`(남은 46), `excluded.json`(0), `inputs_first_response.jsonl`, `inputs_self.jsonl` | `batch013/build_candidates13.py` 사본 + CT10K·H-dev·승인 corpus v6·batch013 초안 대상, PoolRule 정답 뼈대, H-final 내용 비공개 비교 |
| `excluded_round1.json` | 1차 검사에서 빠진 20 기록 |
| `build_review14.py` → `review/batch014_review_v1.xlsx`·`.md`, `jb014_draft_judgement.json`, `review/summary.json` | 검토 시트와 J-b014 진단(J-b014 원문이 생기면 다시 돌림) |
| `base_first_response.jsonl`, `v4_first_response_<seed>.jsonl` | J-b014 첫 응답(ablation_013 GPU 작업이 만든다). 표본 원문은 `training/generated/ablation_013/self/` |

## 2. 범위와 수량 — 지시(T1–T5, 80–110)와 다른 점

| 묶음 | 지시 | 작성·남김 | 이유 |
|---|---|---:|---|
| T1 운행 요금 × {avg, med, min, max} × {일, 기간, 주} × {시도, 없음} | 36–48 | **0** | 운행 요금(`get_trip_metrics fare`)의 장소 없음·시도·시군구 구조는 aggregation(없음·avg·med·min·max·sum) 모두 보호 넷(selection_v2·holdout·valid98·aux_test_v1)·selection_v1·확장·thor family에 걸린다(72/72, `free_structures14.json`). family 키는 날짜·장소 이름을 보지 않아 시간 단위·시도를 바꿔도 같다. 결정 120에 따라 쓸 수 없다. |
| T2 운행 요금 × 시군구·요일 유형 | 8–12 | **0** | 같은 이유(시군구 = 장소 있는 family와 같음, 요일 유형 = 날짜). |
| **T1v(대체, 지시 범위 밖)** 운행 요금 × **POI 주변**(`include_vicinity`) × {avg, med, min, max} × {일, 기간, 주} | – | 12 | family에 vicinity가 들어가 막히지 않는 유일한 운행 요금 구조(6 family 모두 빔, 코드가 답함). 승인 때 이 묶음을 따로 고를 수 있게 나눴다. 분석의 T1–T5 서명(지역 POI)에는 들지 않는다. |
| T3 요금 지표 × 시도 × {일, 월}, 차원 sido·dayofweek | 16–24 | 16 | 빈 구조: 장소 있는 시도는 활성 대수 max·med와 가동률 min·med뿐(수입은 장소 있으면 모두 막힘), 장소 없는 sido·dayofweek 차원은 대부분 빔. batch013 c1에 같은 family가 많아 하한으로 쓰고 하루 날짜·다른 장소를 골랐다. |
| T4 실차 건수 × 하루 × {지역 없음, POI} | 8–12 | 6 | 빈 구조는 **POI 주변 도착** 하나뿐(장소 없음·POI 출발은 막힘). |
| T5 OD 상위 N(출발·도착 역할, dimension_target, limit) | 12–16 | 12 | 빈 family 44. 승인 corpus의 OD 상위 N 정답 문항 26개가 V4에서 빠져 있어(4절) 하한으로 썼다. |
| 합계 | 80–110 | **46** | |

- T1v·T3·T4는 문항마다 "짝지을 거부 패턴"을 `pair_refusal_memo`(메모 열)에 적었다. teacher 입력에는 넣지 않는다(결정 248). `gap`은 batch011–013과 같은 이름.
- 거부 패턴(`pilot_009/protected_final_v2_pc_patterns.md`)은 쓰지 않았다: P-1(통행 지표에 택시 유형), P-a(요금 지표 장소 + 시도 차원), P-b(장소 없는 H3 요금 차원), P-e·P-h(통행 건수 월 묶음·택시 유형), P-i(요금 지표 운행 상태), 묶음·rollup C 패턴. 남은 46은 모두 mock Full 경로에서 답한다.

## 3. 검사(`candidates_checked.json` summary)

- 결정 120 규칙(batch013과 같음): 정규화 질문 일치, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding(대상 전부), thor 보호 질문·id → 뺌; 보호 넷 family → 뺌; selection_v1·thor family·확장 family → 분류 밖(뺌).
- 대상: `validate_pf2.targets()`(RC5–RC7·batch007–012·refusal_dev v1·v2·승인 corpus v4·v5·보호 셋·개발 셋(valid98·aux)·pg·aug300) + **승인 corpus v6·batch013 초안·CT10K 10,000·H-dev 2,000**.
- **정답 뼈대(D6)**: 다시 만든 PoolRule(`ablation_012/e2/build_e2.py` `skeleton` = 날짜를 뺀 정답 호출)이 CT10K·H-dev·H-final과 같으면 뺀다. 일치 0.
- **H-final(봉인)**: 내용을 보여 주지 않는 비교(`HiddenFinal`)로 정규화 질문·Jaccard ≥ 0.5·같은 grounding·뼈대의 **여부**와 family 같은 **개수**만 후보마다 적었다(id·문장·Jaccard 값 없음). 일치 0, family 같은 문항 0(46문항 모두).
- 1차 → 2차: 1차 20 빠짐(연도 없는 날짜 → `DATE_AMBIGUOUS` 18, Jaccard ≥ 0.5 2 — RC5 등 pg-b006-29 0.50, batch013 b013-070 0.63)을 고쳤다(고친 수 20). 2차 46/46 남김, Jaccard 최대 0.48.
- CT10K·H-dev와의 family 겹침도 0이다(CT10K는 template으로 만든 셋이라 family가 50개뿐이고 모두 보호 넷 family와 겹치는 구조다).

## 4. 승인 corpus 확인(지시 3.2) — V4에서 빠진 운행 요금·OD 상위 N 정답 문항

| 유형 | 승인 corpus v6 | V4에 있음 | 빠진 경로 |
|---|---:|---:|---|
| 운행 요금(`get_trip_metrics fare`) | 44(aug300 32·trunk 6·pg 6) | **0** | RC1–RC4에는 20–24문항이 있었고 RC5 18 → RC6 15 → RC7 13으로 줄었다. RC7의 13은 V4 빌드의 유형 상한 C-1에서 batch013 새 문항에 자리를 내줬다(`existing_questions_displaced`). RC7 이전에 빠진 31의 단계별 사유는 이번에 추적하지 않았다. |
| OD 상위 N(`get_trip_count` + dimension + limit) | 81 | 55 | V4 밖 26(batch009 11·aug300 10·batch010 4·batch008 1): RC7에 있던 8은 V4 C-1에서 밀림, 나머지 18은 RC7 전에 빠짐. |

- 그래서 batch014에서 T5를 하한(12)으로 줄였다. 운행 요금은 새로 쓸 수 있는 구조가 POI 주변(T1v)뿐이므로, **이미 승인된 운행 요금 44문항을 다시 넣는 것**(유형 상한 규칙 변경)이 운행 요금 과잉 거부 보강의 더 큰 경로다(사용자 결정, `ablation_013/QUESTIONS.md`).

## 5. 진단 열(J-b014, 학습 아님)

- J-b014-base: base Qwen3-8B greedy 첫 응답 + 표본(greedy 1 + 8, round seed 20261015, `EV.call_seed`) — batch013 J-b013과 같은 규칙. base 정답 표본은 승인 뒤 자체 출처(`json_only`) 후보가 될 수 있어 원문을 보존한다.
- J-b014-v4: V4 o1016·o7·o43 + A0 o1102·o211102·o2026113 첫 응답(greedy).
- teacher 수집(T-C3·TEACH-C14)은 하지 않았다: Ollama 컨테이너가 없다(결정 263 실행 기록).
- 결과 요약(`review/summary.json`, 초안 gold 기준, 진단·판정 아님):

| 묶음 | 문항 | base 첫 응답 일치 / 거부 | base 표본 일치 / 거부(표본 수) | 정답 표본이 있는 문항 | V4 6 seed 첫 응답 일치 · 오답 · 거부 |
|---|---:|---|---|---:|---|
| T1v 운행 요금 POI 주변 | 12 | 1 / 0 | 9 / 2 (108) | 3 | 66.7% · 30.6% · 6.9% |
| T3 요금 지표 | 16 | 12 / 2 | 98 / 25 (144) | 15 | 90.6% · 5.2% · 6.2% |
| T4 실차 건수 POI 도착 | 6 | 2 / 2 | 19 / 8 (54) | 5 | 83.3% · 16.7% · 0% |
| T5 OD 상위 N | 12 | 1 / 2 | 18 / 16 (108) | 10 | 65.3% · 34.7% · 0% |

- **T1v**: base는 운행 요금 POI 주변 문항에서 정답 표본이 거의 없다(108 중 9, 3문항). 승인되어도 자체 표본(`json_only`)으로는 레코드가 3문항분밖에 생기지 않는다(teacher 필요). V4 o43은 12 중 3만 맞다(다른 seed 4–11).
- **T5**: V4 오답은 주로 장소 없는 OD(od_none 5문항: 일치 36.7%)에서, 응답이 장소 끝(od_role)을 덧붙이는 형태다(od_diff 22/30). base 표본은 dimension_target이 초안과 다른 표본 23, 장소 끝이 다른 표본 27.
- **T3**: V4가 이미 강하다(90.6%). base도 15/16 문항에 정답 표본이 있다.
- 2차 검토 권고 "수정" 4: b014-003·032("동성로 일대" — 모델은 '일대'를 POI 주변으로 읽지 않음, '근처'·'주변'으로 바꾸기 권고), b014-036·039(장소 없는 OD; base·V4 모두 일치 ≤ 1).
