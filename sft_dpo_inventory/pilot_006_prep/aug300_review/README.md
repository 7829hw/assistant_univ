# 300문항 v2 semantics 초안 검토(W7a)

작성: 2026-10-15(pilot_006 준비 세션 1). **초안이고 승인이 아니다.** 검증 사슬 통과(validator PASS)도 승인이 아니다. 승인된 corpus에는 아무것도 넣지 않았다.

## 무엇을 했나

- 대상: 결정 106을 적용한 train 220 + holdout 53 = 273문항(제외 5·축소 22는 뺐다).
- 뜻(측정값, 장소·scope 값, od_role, dimension, dimension_target, bucket/rollup, aggregation, order/limit, vicinity, 날짜·시간·택시 유형·운행 상태)은
  xlsx 정답 Tool 호출에서 역산했다(`evaluate_vendor100.derive_grounding`, 질문을 읽지 않음). 질문 span(장소명, scope id, 측정 표현)만 규칙으로 붙였다(`draft_semantics.py`).
- 검증 사슬(`grounding.validation`): train 218/220, holdout 53/53 통과. 실패 2건(aug300-134·135)은 현재 코드가 정답 호출을 실행하지 못하는 문항이다
  (주변 장소 + 읍면동 묶음, UNSUPPORTED_COMBINATION; W6 제안에도 있음).
- span을 못 찾은 측정 표현 23건(train 18, holdout 5)은 빈 칸으로 두고 표시했다.

## 파일

| 파일 | 내용 |
|---|---|
| `draft_semantics.py` → `semantics_draft.jsonl`, `semantics_draft_summary.json` | canonical 레코드 초안 273(status draft) |
| `build_review.py` → `review/review_queue.jsonl`, `review/manifest.json`, `review/aug300_review.xlsx` | batch007과 같은 형식의 queue와 검토 시트(결정 115로 XLSX도 커밋) |

## 검토 시트(`review/aug300_review.xlsx`)

| 시트 | 행 | 내용 |
|---|---:|---|
| 안내 | – | 한국어 안내(승인 아님, 판단 기준, holdout 규칙, 결정 칸) |
| aug300 | 273 | 문항별 정답 호출, semantics 요약, 초안 Full·Partial grounding, span 표시, 검증 사슬, 겹침 |
| vllm_outputs | 69 | train 문항에서 base 첫 응답(J3, vLLM BF16 greedy)이 초안과 다른 경우(220 중 69). 초안과 모델 중 어느 쪽이 맞는지 |
| status_proposals | 15 | W6 재검사에서 새로 걸린 13문항과 현재 코드 실패 2문항. 상태는 바꾸지 않았다 |

- holdout 53문항은 모델 출력 열이 없다(J2 셀 봉인). holdout은 평가 전용이고, 이 검토는 정답·span 확인만 한다.
- 결정 칸: 승인 / 수정 / 보류 / 제외, 수정 grounding(JSON), 메모, 검토자, 검토일. XLSX 편집은 자동으로 가져오지 않는다(`workflow decide`로 기록).
