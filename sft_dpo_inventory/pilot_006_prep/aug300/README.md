# 300문항 v2 준비(W6)

작성: 2026-10-15(pilot_006 준비 세션 1). **승인이 아니다.** 상태 제안은 사람 검토 대상이고, 이 디렉터리의 어떤 파일도 승인된 corpus가 아니다. 모델 호출 없음.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `xlsx_read.py` | 표준 라이브러리만 쓰는 xlsx 리더(셀 값, 셀 메모). openpyxl이 설치된 venv가 없어서 만들었다 |
| `build_aug300.py` → `augmentation_300.jsonl`, `aug300_gold.yaml` | xlsx `증강_300` 시트 → 문항 300(execution 층 `gold`·`gold_text` + v2 열 전부 + 셀 메모). ID `aug300-<번호>`. 상태 `status_v2`(xlsx 그대로)와 `status`(결정 106 적용) |
| `check_aug300.py` → `check_results.json`, `status_proposals.json` | W6 2(현재 코드)와 W6 3(겹침 재검사). 기준은 스크립트 머리 주석 3에 결과 전에 적었다 |
| `freeze_holdout.py` → `holdout_v1.json`, `augmentation_holdout_v1_gold.yaml` | W6 5 holdout 고정 |

## 2. 결과

- **상태(결정 106 적용)**: train 220 / holdout 53 / 제외 5 / 축소 22. 지시의 기대값과 같다. `보류_vendor100` 58 → train, holdout은 그대로.
- **현재 코드(W6 2)**: 300문항 모두 schema 통과. 정답 호출 역산 grounding → compose → validate → compile → mock execute → 업체 100 채점에서
  **298 match**, 2 실패(`aug300-134`·`aug300-135`, 둘 다 train, `UNSUPPORTED_COMBINATION`: 주변 장소 scope에 읍면동 dimension).
  - 수정 4가지: 130·305·306 질문·정답 **3/3 match**, SCOPE_NAME 난이도 수정 **30/30 match**.
- **겹침 재검사(W6 3)**: 대상 11개 셋(selection_v1 100, selection_v2 98, aux_test_v1 51, valid98 98, 업체 100, batch007 27, `reviewed_gold_v006_t2pc` 135행,
  `thinking_pilot004_t2pc` 467행, pg_batch006 43, pg reviewed_reasoning_v001 154, pg reviewed_gold_v006_p0 154). thor 보호 원본 54개.
  - 새 강한 겹침 13문항(train 11, 제외 2). **holdout 0.** 코드 실패 2와 합쳐 제안 15건(`status_proposals.json`). 상태는 바꾸지 않았다.
    - train: 102(업체 100 018과 같은 grounding), 120·233(업체 100 Jaccard 0.519·0.529), 360·364·371·372·381(SCOPE_NAME, 보호 셋과 같은 scope id 역조회),
      134·135(코드 실패).
    - 보류_vendor100 → train 복귀분: 243(valid98 h34 Jaccard 0.524·같은 grounding), 286(selection c03d 같은 grounding), 350(valid98 s03a 같은 grounding).
    - 제외(이미 제외): 324(thor 보호 질문), 394(aux f17·valid98 h36 같은 grounding).
  - 약한 겹침(template·family)은 기록만 했다. holdout 53 중 48문항이 어떤 셋과 family가 겹친다(업체 100 42, selection_v1·v2 30, valid98 22, aux 16).
    학습 데이터와의 holdout family 겹침은 4문항(v006·pilot004·pg 모두 같은 4)이다.
- **pg 데이터**: partial-grounding `ab9d215`에서 `git show`로 꺼내 W3 이식 전에 미리 검사했다(W6 3 마지막 문단). 원본 sha256:
  `batch006/approved.jsonl` `8540c321…`, `reviewed_reasoning_v001/dataset.jsonl` `071ccdbe…`, `reviewed_gold_v006_p0/sft_train.jsonl` `e792ee5e…`.
  W3 뒤 `pg_imports/`에서 다시 검사한다.

## 3. augmentation_holdout_v1(고정)

- 53문항. 정렬된 질문 ID sha256 `69d3af197dd591d73fba097e1b7be9ffadfb9ba71e153338f274b29ac9457d17`,
  질문 텍스트 sha256 `23ee1bc8eab8e6a9420775fb48a87b77a6c2a13fa0217fa8fde6dbb77aadb73b`, gold 파일 sha256 `b5914744…`(`holdout_v1.json`에 전체 값).
- 이 커밋 전에 모델 출력을 만들거나 보지 않았다. 고정 뒤 학습, prompt 예시, 오류 기반 보강 설계에 쓰지 않는다.
- base 셀(J2) 결과는 학습 데이터가 고정된 뒤에 집계한다. 이번 세션에는 파일 존재, 줄 수, sha256만 확인한다.
