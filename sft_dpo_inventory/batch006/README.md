# batch006 annotation 후보 — "실차 통행량" 대조 묶음(결정 66·77)

작성: 2026-10-12–13. **승인이 아니다.** 초안 gold와 validator PASS는 승인으로 다루지 않는다. 승인된 corpus에는 아무것도 넣지 않았다.
학습 trace 수집과 import는 하지 않았다. 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`. 업체 100·aux_test_v1은 겹침 검사에만 썼다.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts.py` → `candidates_draft.yaml` | Claude 초안 28건(질문, 초안 gold, 근거, family=의도, variant). 스크립트에 손으로 적었다 |
| `build_candidates.py` → `candidates_checked.json`, `excluded.json` | 현재 코드 결과와 겹침 검사. 뺀 후보는 `excluded.json`(이번에는 빈 목록) |
| `hf_collect.py`, `run_hf.sh` → `hf_outputs.json`, `hf_collect.log`, `runs.log`, `gpu_check.txt` | base 모델 첫 응답. 원문은 ignore 경로 `training/generated/batch006/raw/hf_outputs_raw.jsonl`(sha256 `390b5d1d…`) |
| `build_review.py` → `review/review_queue.jsonl`, `review/manifest.json`, `review/batch006_review.xlsx`(커밋하지 않음) | 검토 시트 |
| `review/README.md` | 한국어 검토 안내 |

## 2. 설계

- **근거**: 학습 데이터(`reviewed_gold_v005_t2pc`)에 passage_count + occupied 정답이 0개이고, "실차"가 든 질문의 정답은 trip_count뿐이다.
  valid98 h30에서 HF-base가 실차 통행량을 trip_count로 읽었다(`../selection_decline/PASSAGE_STATUS.md`). 업체 100·selection 셋의 문장에서 파생하지 않았다.
- **묶음**: 의도 7개 × 네 대조 = 28건. 같은 의도 안에서 장소·날짜·시간·묶음 기준이 같다.

  | 의도 | 장소 | 날짜·시간 | 묶음 | 실차 건수(trip)의 끝 |
  |---|---|---|---|---|
  | i1 | 대구 | 2026-09-03 | 시군구 | 대구에서 출발(pickup), 출발 시군구별 |
  | i2 | 부산 | 이번 달 | 시군구 | 부산 안(both), 도착 시군구별 |
  | i3 | 대구 동성로 | 지난주 18–20시 | H3 | 출발(pickup), 출발 H3 |
  | i4 | 부산 광안리 주변 | 2026-08-15 20–22시 | H3 + 근처 | 도착(dropoff), 출발 H3 |
  | i5 | 동대구역 근처 | 2026-09-21 | H3 + 근처 | 승차(pickup), 승차 H3 |
  | i6 | 부산 부산진구 | 2026년 7월 | H3 | 안에서만(both), 도착 H3 |
  | i7 | 대구 수성구 | 2026-09-12–14 07–09시 | H3 | 도착(dropoff), 도착 H3 |

- **보호 family를 피한 범위**(라벨 조합만 확인, 문장은 보지 않음): 묶음 없는 통행량(h30과 같은 형태), 읍면동별 통행량, 순위가 붙은 통행량은 보호 family다.
  `family_key`는 taxi_status를 보지 않으므로 실차·공차·상태 없는 통행량이 같은 family다. 그래서 묶음 없는 "실차 통행량"은 만들 수 없었다.
  요일별 통행량·집계 통행량은 현재 계약에서 멈춘다(`INVALID_PARAM_VALUE`, `UNCONSUMED_CONDITION`).
- D1–D4에 걸리는 질문은 없다. 장소는 mock이 아는 대구·부산의 시도·구·거리·역이고, 구 이름에는 지역을 붙였다. 기준일 2026-09-25.

## 3. 현재 코드 결과와 겹침 검사

| 검사 | 대상 | 걸린 후보 |
|---|---|---:|
| thor leakage | `Protection.current(reviewed_gold_v005_t2pc)`: 보호 원본 54개. 정규화 질문, id, template, family | 0 |
| 확장 겹침 | vendor 형식 보호 셋(업체 100 포함)의 정답 역산 template·family | 0 |
| 셋별 겹침 | selection_v1(100), selection_v2(98), aux_test_v1(51), valid98(98), 업체 100(100): 정규화 질문, template, family | 0 |
| 업체 100 문자 3-gram Jaccard | 0.5 이상이면 뺌(결과 전에 정함) | 0(최댓값 0.40, b006-03) |
| batch006 안 중복 질문 | – | 0 |

- 현재 코드(thor `assess` normalize 끔·켬, `assess_t2pc` 조건 계층·compose·validate·compile): **28건 모두 답, 계약·compile 통과**, 조건 계층이 뜻을 바꾼 후보 0.
- 학습 데이터(v005)와의 겹침(정보): 질문 0, family 22, template 8. batch005의 시군구·H3 통행량 family가 v005에 있기 때문이다.

## 4. HF base 출력(`hf_outputs.json`)

- 2026-10-12 23:52–10-13 00:08, GPU 3(`GPU-48f798cc…`, 다른 프로세스 없음, Ollama 모델 없음), base Qwen3-8B@b968826d, thinking 켬, greedy,
  max_new_tokens 8192, prompt 87048d0c, 지문 791c4a68. 후보마다 첫 응답 하나.
- 잘림 0, JSON 파싱 실패 0. 생성 token 637–2,540.

| 대조 | 초안과 같음 | 주요 차이 |
|---|---:|---|
| occupied(실차 통행량) | **0/7** | 7건 모두 occupied가 빠짐: trip_count로 읽음 3(b006-09·13·25), passage_count인데 상태 없음 4. `sum` 추가 5 |
| vacant(공차 통행량) | 1/7 | vacant가 빠짐 2(b006-14 근처, 26 "빈 차"), 근처 누락 2, `sum` 추가 1, 날짜 표기 1, 장소 1 |
| plain(상태 없는 통행량) | 1/7 | `sum` 추가 4, 날짜 표기 2, 근처 누락 1 |
| trip(실차 건수) | 2/7 | `sum` 추가 3, 장소 od_role 2(both를 pickup+dropoff 두 항목으로, 근처 승차를 od 없음으로), 날짜 표기 1 |

- 초안과 다른 24건이 DPO rejected 후보다. 그중 4건(b006-22·23·24·26)은 조건 계층 뒤 초안과 같아진다(결정 6 표시, DPO 쌍으로 쓰지 않음).
  22·23·24는 "2026년 7월"을 모델이 `202607`(월)로 적은 날짜 표기 차이다. 26은 "빈 차"를 조건 계층이 vacant로 채운다.
- **사람 검토가 필요한 점("초안과 모델 중 어느 쪽이 맞는가")**:
  - 실차 통행량을 trip_count로 읽은 3건은 결정 62·66의 판단(실차 통행량 = passage_count + occupied)대로면 모델이 틀렸다.
  - 집계어 없는 질문의 `sum`(13건)은 결정 65대로면 모델이 틀렸다.
  - 날짜 표기(월 대 범위)는 뜻이 같을 수 있다(batch005와 같은 쟁점).
  - b006-08의 "부산 안에서 출발해 부산 안에서 도착"을 모델은 장소 두 항목(pickup·dropoff)으로 적었다. 초안은 한 장소 both다(결정 29의 h03과 같은 쟁점).

## 5. 검토 시트

- queue 52행 = SFT gold 28 + DPO 쌍 24(그중 결정 6 표시 4), `model_output_note` 0.
- `review/batch006_review.xlsx`는 커밋하지 않는다. `python sft_dpo_inventory/batch006/build_review.py --xlsx-only`로 다시 만든다(원문이 있으면 모델 응답 본문을 채운다).
