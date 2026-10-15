# batch007 annotation 후보 — "실차"라는 말 없는 운행 상태 통행량과 대조(결정 104)

작성: 2026-10-15(pilot_005 학습과 병행). **승인이 아니다.** 초안 gold와 validator PASS는 승인으로 다루지 않는다. 승인된 corpus에는 아무것도 넣지 않았다.
학습 trace 수집과 import는 하지 않았다. 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`. 업체 100·보호 셋은 겹침 검사에만 썼다.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts.py` → `candidates_draft.yaml` | Claude 초안 28건(질문, 초안 gold, 근거, family=의도, variant). 스크립트에 손으로 적었다 |
| `build_candidates.py` → `candidates_checked.json`, `excluded.json` | 현재 코드 결과와 겹침 검사(batch006과 같은 방법 + n33 유사도). 뺀 후보 1건 |
| `serve_b7.sh`, `run_vllm.sh`, `vllm_collect.py` → `vllm_outputs.json`, `vllm_collect.log`, `runs.log`, `gpu_check.txt` | base 모델 첫 응답(vLLM BF16). 원문은 ignore 경로 `training/generated/batch007/raw/vllm_outputs_raw.jsonl`(sha256 `1e1011ce…`) |
| `build_review.py` → `review/review_queue.jsonl`, `review/manifest.json`, `review/batch007_review.xlsx`(커밋하지 않음) | 검토 시트(batch006과 같은 형식, 모델 출력 시트 이름은 vllm_outputs) |
| `review/README.md` | 한국어 검토 안내 |

## 2. 설계

- **근거**: pilot_004에서 "실차"가 있는 selection_v2 g02·g04의 오독은 사라졌지만, "실차" 없이 표현한 indepv2/n33은 그대로 틀렸다
  (`../pilot_004/REPORT.md`, `../pilot_004/selection/real_trip_thinking.json`). 학습 데이터(`reviewed_gold_v006_t2pc`)의 occupied 통행량 문장은 batch006의
  "실차 통행량"과 b006-05 "손님을 태운 택시의 통행량"뿐이다. 질문은 n33이나 보호 셋의 문장을 보거나 바꿔 쓰지 않고 새로 썼고, batch006과 같은 표현은 피했다.
- **묶음**: 의도 7개 × 4 = 28건(occupied 10, vacant 7, plain 3, trip_pickup 5, trip_dropoff 3). 같은 의도 안에서 장소·날짜·시간·묶음 기준이 같다.

  | 의도 | 장소 | 날짜·시간 | 묶음 | 대조 |
  |---|---|---|---|---|
  | i1 | 대구 | 2026년 8월 | 시군구 | occupied 2, vacant, trip_pickup |
  | i2 | 부산 | 지난주 21–23시 | 시군구 | occupied, vacant, plain, trip_dropoff(b007-08, 뺌) |
  | i3 | 광안리 근처 | 2026-09-19 21–23시 | H3 + 근처 | occupied 2, vacant, trip_pickup |
  | i4 | 대구 동성로 | 2026-09-20 14–17시 | H3 | occupied, vacant, trip_pickup, trip_dropoff |
  | i5 | 부산 어린이대공원 주변 | 이번 달 | H3 + 근처 | occupied, vacant, plain, trip_pickup |
  | i6 | 대구 달서구 | 2026-09-01–07 | H3 | occupied 2, vacant, trip_dropoff |
  | i7 | 부산 수영구 | 2026-09-24 07–09시 | H3 | occupied, vacant, trip_pickup, plain |

- occupied 표현(의도마다 다름): 손님이 타고 있던 택시, 승객이 탄 택시가 지나간 양, 승객을 싣고 다닌 택시, 손님 태운 택시들이 얼마나 지나갔는지, 승객 탑승 택시,
  손님을 태우고 지나간 택시, 승객이 타고 있는 택시, 손님을 모시고 달린 택시, 손님 있는 택시, 승객을 태운 택시가 지나간 양.
- 장소는 mock gazetteer에 있는 이름만 썼다. 기준일 2026-09-25.

## 3. 현재 코드 결과와 겹침 검사

| 검사 | 대상 | 걸린 후보 |
|---|---|---:|
| thor leakage | `Protection.current(reviewed_gold_v006_t2pc)`: 보호 원본 54개. 정규화 질문, id, template, family | 0 |
| 확장 겹침 | vendor 형식 보호 셋(업체 100 포함)의 정답 역산 template·family | **1(b007-08, family: grounding_v8 heldout)** |
| 셋별 겹침 | selection_v1(100), selection_v2(98), aux_test_v1(51), valid98(98), 업체 100(100): 정규화 질문, template, family | **1(b007-08, valid98 family)** |
| 업체 100 문자 3-gram Jaccard | 0.5 이상이면 뺌(결과 전에 정함) | 0(최댓값 0.264) |
| selection_v2 n33 문자 3-gram Jaccard(보고만, 0.5 이상이면 검토 표시) | – | 0(최댓값 0.163 b007-20, 평균 0.037) |
| batch007 안 중복 질문 | – | 0 |

- b007-08("부산에서 손님을 내려준 건수를 하차 시군구별로")은 보호 family와 겹쳐 뺐다. **남은 후보 27건.**
- 현재 코드(thor `assess` normalize 끔·켬, `assess_t2pc` 조건 계층·compose·validate·compile): **27건 모두 답, 계약·compile 통과**, 조건 계층이 뜻을 바꾼 후보 0.
- 학습 데이터(v006)와의 겹침(정보): 질문 0, family 26, template 21(batch005·batch006의 시군구·H3 통행량·건수 family가 v006에 있기 때문).

## 4. vLLM base 출력(`vllm_outputs.json`)

- 2026-10-15 12:50–12:54, GPU `2445b100…`(다른 프로세스 없음), vLLM 0.30.0 BF16, flashinfer attention·sampler, base Qwen3-8B@b968826d, thinking 켬,
  **greedy**, max_tokens 8192, 동시 요청 8, prompt 87048d0c, 지문 791c4a68. 후보마다 첫 응답 하나. pilot_005 후보 평가가 끝나 GPU가 빈 뒤에 쟀다.
- 생성 token 694–8,192, 잘림 1(b007-09, JSON 없음), 초안과 같음 **2/27**(b007-15, b007-24).

| 대조 | 초안과 같음 | 주요 차이 |
|---|---:|---|
| occupied | **0/10** | taxi_status 빠짐 5(b007-01·02·05·10·21), **trip_count로 읽음 4**(b007-02·13·22·25), 잘림 1(b007-09), `sum` 추가 3, 근처(vicinity) 차이 2 |
| vacant | 0/7 | vacant 빠짐 3(b007-06·11·26), `sum` 추가 4, 근처(vicinity) 차이 2, 날짜 표기 1, 묶음 단위 1, H3 셀을 장소로 적음 1(b007-23) |
| plain | 0/3 | `sum` 추가 3, 근처 1 |
| trip_pickup | 1/5 | 장소 od_role 빠짐 4(b007-04·12·20·27), 근처(vicinity) 차이 2 |
| trip_dropoff | 1/2 | `sum` 추가, 시간 1(b007-16) |

- 초안과 다른 25건 중 24건이 DPO rejected 후보, 1건(b007-09)은 JSON이 없어 model_output_note다. 조건 계층 뒤 초안과 같아지는 쌍(결정 6) 0.
- **사람 검토가 필요한 점("초안과 모델 중 어느 쪽이 맞는가")**:
  - "승객을 태운 택시가 지나간 양"(b007-25), "손님을 태우고 지나간 택시의 양"(b007-13) 등을 trip_count로 읽은 4건은 결정 62·66·104의 판단(손님이 탄 택시의 통행량 =
    passage_count + occupied)대로면 모델이 틀렸다.
  - 근처·주변 차이(7건, 확인한 것은 factors가 아니라 장소 `attributes.vicinity`로 적은 형태): prompt(“factors에 "vicinity": true를 넣습니다”)대로면 초안이 맞다.
  - 집계어 없는 질문의 `sum`(12건)은 결정 65대로면 모델이 틀렸다.
  - 날짜 표기(2026년 8월 → 범위 대 월)는 뜻이 같을 수 있다(batch005·006과 같은 쟁점).

## 5. 검토 시트

- queue 52행 = SFT gold 27 + DPO 쌍 24 + model_output_note 1(b007-09).
- `review/batch007_review.xlsx`는 커밋하지 않는다. `python sft_dpo_inventory/batch007/build_review.py --xlsx-only`로 다시 만든다(원문이 있으면 모델 응답 본문을 채운다).
- 다음 판에서 이 데이터로 학습하면 selection_v2 결과를 n33을 넣은 것과 뺀 것 둘 다로 보고한다(결정 104).
