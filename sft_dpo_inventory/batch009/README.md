# batch009 후보 — R2 약점 보강(pilot_006 준비 세션 2b, H3)

작성: 2026-10-16. **승인이 아니다.** 초안 gold, 검증 사슬 통과, 겹침 검사 통과는 승인으로 다루지 않는다. 검토는 결정 130과 같은 방식(Claude 2차 검토 → 사용자 결정)으로 한다.
보호 셋 문장, selection_v2 n33, aug300 문장을 보거나 바꿔 쓰지 않았다. 장소는 mock gazetteer 이름만 썼다. 학습·prompt·`SEMANTIC_CODE` 변경 없음(지문 `791c4a68`).

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts.py` → `candidates_draft.yaml` | Claude 초안 84건(1차 60 + 2차 24). 질문·업체 형식 정답 호출·근거를 손으로 적었다 |
| `free_structures.py` → `free_structures.json` | 2차 후보용: (od_role, dimension, dimension_target, order) 구조 180개의 family 키와 현재 코드 응답을 계산해 보호 넷·selection_v1·thor·확장 family와 겹치지 않는 구조 81개를 낸다(문장 없음) |
| `build_candidates.py` → `candidates_checked.json`(남은 43), `excluded.json`(빠진 41, 사유·분류), `inputs_first_response.jsonl`(J11), `inputs_self.jsonl`(J12) | batch008 검사 도구 사본 + 결정 120 분류(머리 주석에 결과 전 기준) |
| `build_review.py` → `review/batch009_review_v1.xlsx`, `review/summary.json`, `j12_draft_judgement.json` | 검토 시트(batch007 v2 형식 + Claude 2차 검토 권고 열), J11·J12 신호 |
| `base_first_response.jsonl` | J11(vLLM BF16 greedy 첫 응답, 원문 없이 채점·sha256) |
| `../pilot_006_prep/analysis/family_key.md`, `family_key_analysis.{py,json}` | family 키 분석 |

## 2. 설계(약점 네 가지, 지시 H3 표)

| 약점 | 목표 | R2 근거(`pilot_006_prep/analysis/r2_vs_base.json`) |
|---|---:|---|
| w1 value 없는 장소(답이 장소 이름, `get_scope_name`) | 20 | scope_reverse·valueless_place 문항에서 Partial ok 0%(MEASURE 없음) |
| w2 implicit endpoint 동사형 dimension_target | 20 | implicit_endpoint_verb에서 Partial dt 누락 증가 |
| w3 od_role ≠ dimension_target | 10 | od_ne_dt에서 Partial dt 누락 증가 |
| w4 순위 없는 dimension_target | 10 | dt 누락이 순위 질문에 가려지는 지름길 방지(batch008 g1과 같은 취지) |

- 표기: 지역 안 OD = 장소 하나 + `od_role: both`(`scope_pickup`·`scope_dropoff`에 같은 binding), 측정 source implicit(역산 기본값), vicinity는 factors(이번 후보에는 없음:
  vicinity와 dimension을 함께 쓰면 현재 코드가 거부).
- 2차 후보(b009-61–84): 1차 검사에서 보호 넷 family·현재 코드 거부로 빠진 만큼 `free_structures.py`의 빈 구조에서 다시 썼다. 1차 후보와 결과는 지우지 않았다.

## 3. 검사 결과(결정 120)

| 약점 | 작성 | 남김 | 보호 넷 family | 강한 겹침·검사 실패 | 분류 밖(빼 둠) |
|---|---:|---:|---:|---:|---:|
| w1 value 없는 장소 | 20 | **0** | 9 | 11(같은 scope grounding 9, Jaccard ≥ 0.5 6, 학습 데이터와 같은 grounding 3 — 중복 계수) | 0 |
| w2 동사형 dt | 32 | **24** | 5 | 0 | 3(확장 family) |
| w3 od≠dt | 16 | **10** | 2 | 3(현재 코드 `UNSUPPORTED_COMBINATION`) | 1(확장 family) |
| w4 순위 없는 dt | 16 | **9** | 4 | 3(현재 코드 `UNSUPPORTED_COMBINATION`) | 0 |
| 합계 | 84 | **43** | 20 | 17 | 4 |

- 남은 43건 모두 검증 사슬(Full·Partial 같은 판정·mock, 정답 호출과 일치)·T2PC 경로 답함. 측정 span을 찾지 못한 2건(b009-27, b009-38: 질문에 "건수"가 없음)은 검토 시트에서
  "수정(측정 span)" 권고.
- `UNSUPPORTED_COMBINATION` 6건: H3 셀 묶음을 mock gazetteer에 H3 하위 셀이 없는 구역(수영구·부산 등)과 함께 쓰거나, 구역보다 큰 단위(시도)로 묶은 경우.

## 4. w1(value 없는 장소)이 0건인 이유와 대안 — **사용자 결정**

- scope 이름 조회의 family 키는 측정 없음·OD 없음·factor 없음 하나뿐이다(`family_key.md` 3절). selection_v2·holdout·valid98·aux가 이미 이 family를 가지므로
  결정 120을 그대로 쓰면 어떤 문장으로 써도 빠진다. scope id도 mock gazetteer 안에 32개뿐이라 대부분이 보호 셋·aug300과 같은 grounding(같은 scope)이 된다.
- 지금 승인 corpus의 이 유형은 5질문(aug300 SCOPE_NAME, Full 8b 정답 5, Partial 8b 정답 0)이다(H4).
- 대안(고르지 않음):
  1. **결정 120 예외**: scope 이름 조회만 family 겹침을 허용하고 강한 겹침(같은 scope, Jaccard ≥ 0.5)만 뺀다. 1차 w1 20건 중 강한 겹침이 없는 9건(b009-01·03·04·05·09·10·13·19·20)이 남는다.
  2. mock gazetteer 밖의 scope id(예: 존재하지 않는 셀 id)로 쓰고 mock 실행은 `NOT_FOUND`를 정답 행동으로 본다 — 실행 검증이 약해진다(권하지 않음).
  3. 이 약점은 teacher(Partial MEASURE 규칙을 thinking에서 다룸)와 기존 5질문으로만 다룬다.

## 5. 남은 일

- J11(base 첫 응답)·J12(두 arm 표본 9개)를 넣어 검토 시트를 다시 만든다(`build_review.py`).
- 사람 검토(Claude 2차 검토 권고 → 사용자 결정). 승인되면 J12 정답 표본과 teacher(추가 teacher 대상)를 RC2에 넣는다.
