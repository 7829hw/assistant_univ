# A·D 준비 결과 (결정 40-A·40-D, 작업 지시 5)

작성: 2026-10-07. 이번에는 규모만 셌다. pilot_002 데이터는 batch005 승인 뒤에 만든다. 모델·GPU를 쓰지 않았다.

## A. teacher trace를 `source=teacher`로 받기

**builder 변경**

- 바꾼 파일: `training/data/thinking.py`, `training/data/build_thinking.py`. 둘 다 SEMANTIC_CODE 밖이라 실행 의미 코드 지문은 그대로다.
- `normalize_trace`: teacher 행(`source: teacher`, thinking·content만 있음)을 HF trace와 같은 응답 모양 `<think>\n{thinking}\n</think>\n\n{content}`으로 바꾼다.
  - 행에 이미 `raw_text`가 있으면 그 값이 이 모양과 같은지만 확인한다.
  - batch004 teacher 파일은 `raw_text`를 갖고 있었고, 모두 같았다.
- `sft_record`·`dpo_pair`: teacher trace로 만든 레코드의 metadata를 다음과 같이 둔다.
  - `source: "teacher"`, `source_path`(trace 파일), `teacher_model`, `teacher_model_digest`.
  - DPO는 `chosen_source: "teacher"`도 붙인다.
- teacher trace를 DPO rejected로 쓰면 오류로 멈춘다. HF trace의 레코드는 바뀌지 않는다.
- 시험: `tests/test_training_thinking.py`의 `TeacherTraceTest`. 관련 시험 51개가 통과했다(기존 expected failure 1개는 그대로).

**규모**

- 스크립트: `count_teacher.py`. 결과: `teacher_scale.json`.
- 대상: 17질문(known7 7, batch004 6, v003_valid 4)의 teacher trace 136개.

| 단계 | 수 |
|---|---:|
| 정답 표본(조건 계층 전 원응답 `raw_match`) | 121 |
| 같은 응답 중복 | 0 |
| tokenize 일치(재tokenize 왕복, `json_only`·`full_response` 렌더링 token 경계) 실패 | 0 |
| 계약 필터(`target_ok`) 실패 | 0 |
| 길이 한도(결정 18, SFT total ≤ 12,887) 초과 | 0 (최대 9,718) |
| 결정 27 기준(사람 검토의 "우연히 정답") | 0 — 아직 검토하지 않음 |
| 루프(D) | 0 |
| **남는 SFT 레코드** | **121 (17질문 모두)** |

- 질문별 SFT 레코드: 8개 10질문, 7개 3질문, 6개 1질문, 5개 2질문, 4개 1질문.
- r1 SFT는 124 레코드·34질문이다. teacher를 그대로 넣으면 245 레코드 중 121개(49%)가 teacher가 된다.
  - 질문당 레코드 수에 상한을 둘지는 pilot_002 데이터 구성 때 정할 일이다.
- **tokenize 일치의 한계:** teacher는 Ollama 출력이라 생성 token id가 없다. 결정 4의 비교(생성 id 대 재tokenize)를 그대로 할 수 없어 위의 두 검사로 대신했다.
- **DPO(참고):** teacher 정답을 chosen, 같은 질문의 HF base 오답을 rejected로 하면 다음과 같다.
  - 결정 6의 운영 경로 재판정을 통과한 쌍(운영에서도 틀림): 463개(rejected 153개 판정).
  - chosen은 27b, rejected는 8b로 모델이 다르다. DPO에 넣을지는 사람이 정한다.

## D. 루프 trace 제외

- 기준: `../loop_filter/CRITERIA.md`. 적용 전 커밋 db1dab6으로 고정했다.
  - L1 끝부분 반복 ≥ 3, L2 압축률 ≤ 0.086, L3 같은 줄 반복 ≥ 21.
- 적용 결과(`../loop_filter/applied.json`):

| 묶음 | trace | 루프 |
|---|---:|---:|
| v004 HF trace(`combined_traces.jsonl`) | 477 | 0 |
| teacher trace | 136 | 0 |
| r1 SFT 레코드 / DPO 쌍 | 124 / 212 | 0 / 0 |

- 지금 pool에는 기준에 걸리는 trace가 없다. 생성 상한에 걸린 trace는 수집 단계에서 이미 후보가 아니었다(모두 `done_reason: stop`).
- pilot_001의 루프는 학습 trace를 따라 한 것으로 보기 어렵다. 이 해석은 "가능성 있음" 수준이다.
- D는 batch005 승인 뒤 수집할 trace에 같은 기준으로 적용한다.
