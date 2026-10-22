# batch011 후보 — 거부 보강(pilot_008 P2, 결정 219)

작성: 2026-10-22. **승인이 아니다.** 초안 정답, 검증 사슬·겹침 검사 통과는 승인으로 다루지 않는다. 검토는 지금까지와 같이 Claude 2차 검토 → 사용자 결정.
보호 셋·개발 셋·n33 문장을 보지 않고 새로 썼다. 장소는 mock gazetteer 이름만. 학습·prompt·`SEMANTIC_CODE` 변경 없음(지문 `791c4a68`). 기준일 2026-09-25.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts11.py` → `candidates_draft.yaml` | Claude 초안 100건(r1 60, r2 40). 질문·정답(r1: `{"unsupported": true}`, r2: 업체 형식 호출)·근거를 손으로 적음 |
| `build_candidates11.py` → `candidates_checked.json`(남은 100), `excluded.json`(빠짐 0), `inputs_first_response.jsonl`, `inputs_self.jsonl` | batch010 검사 도구 사본 + RC5 실제 학습 레코드·batch010·corpus v3 대상, 거부 문항 검사 규칙(2절) |
| `excluded_r2_round1.json`, `excluded_r2_round2.json` | r2 1차(40 모두 보호 넷 family)·2차(9: 겹침·검증 사슬) 기록 |
| `base_first_response.jsonl`, `o11_first_response.jsonl` | J-b011(base greedy)·J-o11-b011(F-o11 greedy) 첫 응답 채점(원문 없이) |
| `build_review11.py` → `review/batch011_review_v1.xlsx`, `jb011_draft_judgement.json`, `review/summary.json` | 검토 시트와 J-b011 표본(greedy 1 + 8) 판정 |

## 2. 설계와 검사

- **r1 거부(60 = 6범주 × 10)**: 계약의 모델 거부 (M)(`pilot_008/refusal_contract.md` 1절) — 측정값·조건·대상을 계약 개념·factor로 적을 수 없는 질문. 정답 target `{"unsupported": true}`.
  범주: 없는 지표(승객 수·대기 시간·사고·연료·배출·주행 거리·배차 실패율·근무 시간·만족도·팁), 없는 묶음 단위(날짜·분기·반기·시간·하루·연도·15분·격주·30분),
  개인·차량 단위(차량번호·기사·승객·회사·연령대·경력), 예측(다음 주·내일·다음 달·내년·모레·연휴), 다른 교통수단(버스·지하철·자전거·KTX·화물차·렌터카·킥보드·오토바이·자가용·대리운전),
  도메인 밖(날씨·맛집·주차장·기본요금 규정·길안내·인구·호출 방법·집값·병원·리무진 시간표).
- **r2 근접 대조(40)**: 각 r1 범주와 겉모습이 비슷하지만 지원되는 질문(목록 안 측정값, week·month bucket·요일 dimension, 지역·셀·택시 유형 단위, 지난 기간, 택시 실차, 장소 분석).
  1차 단순 구조 40개는 모두 보호 넷(selection_v2·holdout·valid98·aux) family라 결정 120으로 빠져, batch010 빈 구조(`batch010/free_structures10.json`)로 다시 썼다(2차 31 남음),
  남은 9는 표현·장소·집계를 바꿨다(3차, 9 남음).
- **겹침 검사**: 결정 120 규칙 + 대상에 RC5 실제 학습 레코드(Full·Partial, `validate_v2.train_targets`)·batch010·승인 corpus v3. **거부 문항은 정답 grounding이 없어
  정규화 질문·문자 3-gram Jaccard ≥ 0.5만**(같은 grounding·template·family 검사 무의미). 거부 target이 T2PC 경로에서 `unsupported`로 끝나는지 확인(60/60).
- r2는 검증 사슬(Full·Partial 같은 판정·mock·execution 일치)·Full 경로 답함 40/40. 남은 100건의 대상 셋 최대 Jaccard 0.457.

| 묶음 | 작성 | 남김 | 빠짐(최종) |
|---|---:|---:|---|
| r1 거부(6범주 × 10) | 60 | **60** | 0 |
| r2 근접 대조(7·7·7·7·6·6) | 40(1차) + 40(2차) + 9(3차) | **40** | 0(1차 40·2차 9는 바꿔 씀) |

## 3. J-b011·J-o11-b011 요약

`review/summary.json`, `jb011_draft_judgement.json`. r1 "올바른 거부" = 모델 거부 출력(`{"unsupported": true}`) 또는 응답 grounding이 gold 파이프라인(mock)에서 거부로 끝남.

| | base 첫 응답 | base 표본(greedy 1 + 8) | F-o11 첫 응답 |
|---|---|---|---|
| r1 거부 60 | 올바른 거부 13문항(모델 거부 2) | 107/540 표본(모델 거부 38), **올바른 거부 표본이 있는 문항 28**(모델 거부 13) | 올바른 거부 9문항(모델 거부 0) |
| r2 대조 40 | 초안과 같음 21, 거부 4 | 같음 191/360, 같은 표본 있는 문항 29, 거부 29 | 같음 23, 거부 1 |

범주별 base 올바른 거부 표본이 있는 r1 문항: 없는 지표 6, 묶음 단위 5, 개인·차량 7, 예측 2, 다른 교통수단 1, 도메인 밖 7(각 10).

## 4. 남은 일

- 사람 검토(Claude 2차 검토 권고 → 사용자 결정). 승인분은 RC6에 들어간다(`pilot_008/RC6_PLAN.md`).
