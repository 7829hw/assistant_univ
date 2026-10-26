# batch012 후보 — 학습용 거부·근접 대조 초안(pilot_009 준비 P2, 결정 229)

작성: 2026-10-26. **승인이 아니다.** 초안 정답, 검증 사슬·겹침 검사 통과는 승인으로 다루지 않는다. 검토는 Claude 2차 검토 → 사용자 결정.
보호 셋·개발 셋·protected_final 문장을 보지 않고 새로 썼다. 장소는 mock gazetteer 이름만. 학습·prompt·`SEMANTIC_CODE` 변경 없음(지문 `791c4a68`). 기준일 2026-10-26.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts12.py` → `candidates_draft.yaml` | Claude 초안 100건(r1 60, r2 40). 2차에서 바꾼 문항은 줄 끝 주석에 1차 문장 |
| `build_candidates12.py` → `candidates_checked.json`(남은 100), `excluded.json`(빠짐 0), `inputs_first_response.jsonl`, `inputs_self.jsonl` | batch011 검사 도구 사본 + 대상 RC6·batch011·refusal_dev v1·refusal_dev 확장 초안·승인 corpus v4 |
| `excluded_round1.json` | 1차 검사에서 빠진 19(r1 3, r2 16) 기록 |
| `base_first_response.jsonl`, `o11_first_response.jsonl`, `p8_first_response.jsonl` | J-b012(base greedy)·J-o11-b012(B2-F-o11 greedy)·J-p8-b012(P8-o43 greedy) 첫 응답 채점 |
| `build_review12.py` → `review/batch012_review_v1.xlsx`, `jb012_draft_judgement.json`, `review/summary.json` | 검토 시트와 J-b012 표본(greedy 1 + 8) 판정 |

## 2. 설계와 검사

- **r1 거부(60)**: 계약 모델 거부 (M). 정답 target `{"unsupported": true}`.
  - 개별 단위 25(`r1_entity`): 기사·차량 번호·운수회사·사업자·조합·손님 한 사람·손님 속성(직업·나이대)·번호판 목록.
  - 묶음 단위 20(`r1_bucket`): 하루·날짜·매시간·2시간·분기·3개월·반기·반년·연 단위.
  - 다른 교통수단 15(`r1_mode`): 경전철·순환버스·시외·고속버스·SRT·오토바이·관광버스·화물 트럭·전기 자전거·공항철도·카셰어링·시내버스·자가용·여객선·퍼스널 모빌리티.
- **r2 근접 대조(40)**: batch010 빈 구조(`batch010/free_structures10.json`)만.
  - 개별 단위 대조 16: 택시 유형(개인·법인) + 월·주 bucket·시도·요일 묶음, 한 끝 실차의 시도·시군구·읍면동·H3 묶음.
  - 묶음 단위 대조 14: 주·월 bucket + rollup, 요일·시도 묶음.
  - 교통수단 대조 10: "택시"라고 밝힌 같은 구조.
  - 기간은 bucket에 맞췄다(월별 ≥ 2개월: 작년·올해·2026-01–06; 주별 ≥ 2주: 지난달·이번 달·2026-08–09; 요일별 ≥ 1주).
- **겹침 검사**(결정 120 규칙, `build_candidates12.py`):
  - 대상: RC5·**RC6** 실제 학습 레코드(`validate_v2.train_targets`, corpus v4), batch011 초안 전체, refusal_dev v1(승인본·초안), refusal_dev 확장 초안 60, 승인 corpus v4, 기존 대상 전부.
  - 거부 문항은 정규화 질문·문자 3-gram Jaccard ≥ 0.5만 본다. 거부 target이 T2PC 경로에서 `unsupported`로 끝나는지도 확인했다(60/60).
  - r2는 검증 사슬과 Full 경로 답함을 확인했다(40/40).
  - 남은 100건의 최대 Jaccard는 0.483이다.
- **1차 → 2차**:
  - r1 3은 refusal_dev v1 문장과 같아서 빠졌다(내가 같은 문장을 다시 씀).
  - r2 16의 사유: 빈 구조 목록 밖 집계 조합 10(보호 넷·확장 family), Jaccard 3(batch011 r2·refusal_dev v1 대조), mock 장소 조합 3(부산 동구 NOT_FOUND, 광안리 emd 짝, 시군구 billing).
  - 이 19를 바꿨다. 검사는 통과했지만 refusal_dev v1 거부 문항과 뜻·문형이 거의 같은 r1 3(성별 비율, 수입 적은 기사 세 명, 최근 5년 해마다)도 개발 셋 오염을 막으려고 바꿨다.

| 묶음 | 작성 | 남김 | 빠짐(최종) |
|---|---:|---:|---|
| r1 개별 단위·묶음 단위·교통수단 | 25 · 20 · 15 | **60** | 0(1차 3 바꿔 씀, 비슷한 3 더 바꿈) |
| r2 개별·묶음·교통수단 대조 | 16 · 14 · 10 | **40** | 0(1차 16 바꿔 씀) |

## 3. J-b012·J-o11-b012·J-p8-b012 요약(진단, 판정 아님)

`review/summary.json`, `jb012_draft_judgement.json`. r1 "올바른 거부" = 모델 거부 출력(`{"unsupported": true}`) 또는 응답 grounding이 gold 파이프라인(mock)에서 거부로 끝남.

| | base 첫 응답 | base 표본(greedy 1 + 8) | F-o11 첫 응답 | P8-o43 첫 응답 |
|---|---|---|---|---|
| r1 거부 60 | 올바른 거부 13(모델 거부 0) | 113/540(모델 거부 7), 올바른 거부 표본이 있는 문항 33(모델 거부 4) | 10(모델 0) | 14(모델 1) |
| r2 대조 40 | 초안과 같음 24, 거부 4 | 같음 186/360, 같은 표본 있는 문항 29, 거부 33 | 같음 25, 거부 0 | 같음 25, 거부 0 |

- r1 범주별 base 올바른 거부 표본: 개별 단위 52/225(문항 15/25), 묶음 단위 54/180(15/20), 교통수단 7/135(3/15).
- 범주별 첫 응답 올바른 거부(base / F-o11 / P8-o43):
  - 개별 단위 6 / 5 / 5(25 중)
  - 묶음 단위 7 / 1 / 3(20 중)
  - 교통수단 0 / 4 / 6(15 중)
- r2에서 base 정답 표본이 없는 11문항: b012-065·066·067·068·070·072·081·083·096·097·098(개별 대조 6, 교통수단 대조 3, 묶음 대조 2). 승인되면 teacher 대상 후보다(PLAN_DRAFT).
- 검토 우선순위 "높음" 42(판정 아님): r1에서 base 표본 올바른 거부 0, 또는 r2에서 base 일치 ≤ 3/9.

## 4. 남은 일

- 사람 검토(Claude 2차 검토 권고 → 사용자 결정). 승인분의 RC7 사용은 `pilot_009/PLAN_DRAFT.md`.
- r1 초안 60의 teacher 거부 trace는 TEACH-R에서 승인 전에 모았다(결정 228). 거르기와 사용은 승인 뒤에 한다.
