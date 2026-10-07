# batch005 annotation 후보 (결정 40-C·45, 작업 지시 4)

작성: 2026-10-07. **승인이 아니다.** 초안 gold와 validator PASS는 승인으로 다루지 않는다. 승인된 corpus에는 아무것도 넣지 않았다.
학습 trace 수집과 import는 하지 않았다(승인 뒤에 한다).

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts.py` → `candidates_draft.yaml` | Claude 초안 60건(질문, 초안 gold, 근거, 유형 칸, family, intent). 스크립트에 손으로 적었다 |
| `build_candidates.py` → `candidates_checked.json`, `excluded.json` | 현재 코드 결과와 겹침 검사. 뺀 후보와 이유는 `excluded.json` |
| `hf_collect.py`, `run_hf.sh` → `hf_outputs.json`, `hf_collect.log`, `runs.log`, `gpu_check.txt` | base 모델 첫 응답(thinking 켬) |
| `build_review.py` → `review/review_queue.jsonl`, `review/manifest.json`, `review/batch005_review.xlsx`(커밋하지 않음) | 검토 시트 |
| `review/README.md` | 한국어 검토 안내 |

## 2. 설계

**배분**

- 칸별 배분은 `../pilot_prep_004/type_target/TARGET.md`를 그대로 따랐다.
  - 집계 없음·묶음 없음 30, dimension+dimension_target 15, 집계만 7, dimension만 5, 집계+dimension 3.
- 칸 안 세부는 보호 셋의 semantic family와 겹치지 않는 범위에서 골랐다. 이유는 작업 지시 4가 확장 겹침까지 빼라고 했기 때문이다.

**family 가능 범위 확인**

- 보호 셋 정답의 라벨 조합만 썼다(측정값, od_role, 집계·묶음 구조). 문항 문장은 보지 않았다.
- 보호 family 218개: thor `Protection` 75, vendor 형식 확장 178, 겹치는 것 포함.
  - "집계 없음·묶음 없음" 칸은 vendor 형식 확장 기준으로 보호 family가 15개다. thor 기준으로는 rpm 단독 같은 조합이 더 막힌다. 이것만으로 자연스러운 조합 대부분이 막힌다.
  - 예: 장소 없음의 통행량·속도·요금·수입, `trip_count`의 pickup·dropoff·pickup+dropoff.
- 계약상 쓸 수 없는 조합도 확인했다(작은 확인, `assess_t2pc`).
  - `fare`는 장소 od_role을 받지 않는다(`UNUSED_CONCEPT`).
  - 장소 두 개에 vicinity를 붙이면 `AMBIGUOUS_LOCATION_RELATION`.
  - 장소 없는 `trip_count`(묶음 없음)는 `UNCONSUMED_CONDITION`.
  - 집계 없는 `speed` + dimension은 `UNCONSUMED_CONDITION`.

**칸 안 세부: 목표와 실제**

| 칸 | 목표(`TARGET.md`) | 실제 초안 | 차이의 이유 |
|---|---|---|---|
| 집계 없음·묶음 없음 30 | od_role 없음 12, pickup+dropoff 9, pickup 6, dropoff 3 | od_role both 14(`trip_count`), od_role 없음 10(rpm 5, 공차율 5, vicinity), dropoff 6(`trip_count`, vicinity) | pickup·pickup+dropoff `trip_count`는 vicinity 유무와 관계없이 보호 family이거나 계약상 안 된다. 그래서 한 장소 안 이동(both)으로 바꿨다 |
| dimension+dimension_target 15 | emd 위주, od pickup·dropoff·pickup+dropoff | emd 10, sigungu 5. dt: dropoff 5, pickup 6, both 4. od: both 5, 장소 없음 4, dropoff 3, pickup 2, pickup+dropoff 1 | 목표 조합 중 보호 family인 것은 od를 both로 바꾸거나 장소를 뺐다 |
| 집계만 7 | 장소 있음 6, 장소 없음 1 | 공차율 avg·max(vicinity) 3, rpm avg(vicinity) 2, 가동률 min 1, 가동률 med(장소 없음) 1 | 수입 med는 보호 family였다 |
| dimension만 5 | sigungu 2, emd 1, h3 1, sido 1 | 통행량 sigungu 2, h3 3 | 통행량 emd와 sido 단위는 보호 family이거나 계약상 안 된다 |
| 집계+dimension 3 | sido 2, dayofweek 1 | 수입 med sido top, 가동률 min sido bottom, 가동률 max dayofweek top | 같음 |

- 측정값: `trip_count` 35, `vacant_ratio` 8, `rpm` 7, `passage_count` 5, `active_taxi_ratio` 4, `revenue` 1.
  - 개발 셋의 측정값 비율(`trip_count` 45%)과 다르다. 측정값은 배분 기준이 아니었다.
- D1–D4는 피했다.
  - 수입의 요일 순위, 운행일 지표, 기간 활성 택시 수는 쓰지 않았다.
  - 중구는 "대구 중구"처럼 지역을 붙였다.
- 장소는 대부분 mock이 아는 장소다(대구·부산의 구·동·역·거리). mock 실행까지 갈 수 있다.
- 기준일은 2026-09-25(평가 harness와 같음)다.

## 3. 현재 코드 결과와 겹침 검사(`candidates_checked.json`)

**겹침 검사**

| 검사 | 대상 | 걸린 후보 |
|---|---|---:|
| thor leakage | `Protection.current(reviewed_gold_v004_t2pc)`: 보호 원본 54개. 정규화 질문, id, semantic template, semantic family | 0 |
| 확장 겹침 | vendor 형식 보호 셋(업체 100 포함)의 정답 역산 template·family | 0 |
| 새 선택용·보조 시험 셋 | 아직 없다(`../pilot_prep_004/sets/SURVEY.md`). 후보 문항이 모두 vendor 형식 보호 셋 안에 있으므로 확장 겹침이 그 범위를 덮는다 | 0 |
| batch005 안 중복 질문 | – | 0 |

- 뺀 후보는 0개다. `excluded.json`은 빈 목록이다.
- 결정 15("보호 범위는 넓히지 않는다")는 batch004의 업체 100 family 겹침을 학습에 쓰기로 한 결정이다. batch005는 작업 지시 4대로 확장 겹침도 빼는 기준을 썼다. 결과적으로 걸린 것이 없어 두 기준의 차이는 생기지 않았다.

**현재 코드 결과**

검사 항목: thor `assess`(normalize 끔·켬), `assess_t2pc`(조건 계층 켬, compose, validate, compile).

- **답 52.** 계약 통과, compile 통과. 조건 계층이 뜻을 바꾼 후보는 0이다.
- **정지 8**(`UNCONSUMED_CONDITION`): b005-05, 06, 07, 18, 19, 20, 25, 44.
  - 모두 택시 유형(개인·법인)이 붙은 `trip_count`·`rpm` 질문이다. 이 측정값의 Tool이 `taxi_type`을 받지 않는다.
  - 공차율의 `taxi_type`은 통과한다(b005-28·30).
  - 결정 14의 T2PC식 정지 target(조건을 적고 코드가 멈춤)으로 검토 시트에 표시했다.
  - 초안을 쓸 때는 답할 수 있는 질문으로 의도했다. 정지 target으로 둘지, 질문에서 조건을 뺄지는 검토자가 정한다.
- 학습 데이터(v004)와 질문·family·template 겹침: 0.

## 4. HF base 출력(`hf_outputs.json`)

**실행**

- 2026-10-07 23:22–23:47, base Qwen3-8B@b968826d, thinking 켬, greedy, max_new_tokens 8192, prompt 87048d0c, 지문 791c4a68. 후보마다 첫 응답 하나다.
- **장치: GPU 2**(UUID `GPU-a644de12…`). 작업 지시의 GPU 3은 다른 사용자(jmbae)의 프로세스 2개(6,411 MiB)가 있어 쓰지 않았다(`runs.log`, `gpu_check.txt`).
  - GPU 2는 Ollama 모델이 올라가 있지 않고, Ollama 측정(결정 43)이 끝난 뒤에 썼다(`CLAUDE.md` 5번의 예외).
  - HF 경로는 GPU 2와 GPU 3에서 바이트 단위로 같은 출력을 냈다(결정 43, `../pilot_001_analysis/REPORT.md` 6절 a).
- 채점: `thinking_prep_001/collect_traces.judge`(조건 계층 전 원출력과 초안 비교).

**결과**

| 항목 | 값 |
|---|---:|
| 후보 | 60 |
| 초안과 같음 | 15 |
| 초안과 다름(DPO rejected 후보, 검토 시트 `hf_outputs`) | 45 |
| 그중 조건 계층 뒤에는 같아짐 | 4 |
| 생성 상한(8192) 도달 | 0 |
| JSON 파싱 실패, thinking 안 닫힘 | 0, 0 |
| 생성 token 중앙값(최대) | 822(2,241) |

칸별 초안과 같음: 집계 없음·묶음 없음 8/30, dimension+dimension_target 3/15, 집계만 1/7, dimension만 2/5, 집계+dimension 1/3.

차이의 종류(한 후보에 여러 개일 수 있음):

| 차이 | 건수 | 내용 |
|---|---:|---|
| vicinity | 18 | 모두 초안 있음 → 모델 없음. 질문의 "근처·주변·부근"을 모델이 뺐다 |
| 집계 | 13 | 모두 초안 없음 → 모델 `sum`. 집계어가 없는 질문에 합계를 붙였다 |
| 날짜 표기 | 11 | 10건은 한 달 전체를 초안은 범위(`20260801-20260831`), 모델은 월(`202608`)로 적었다. 기존 승인 corpus(v004)에 두 표기가 모두 있다. 1건은 "이번 달"을 모델이 `202605`로 적었다 |
| 장소 od_role | 15 | 한 장소 `both`(초안)를 모델이 pickup+dropoff 두 항목, 한쪽, 또는 od 없음으로 적었다 |
| dimension, dimension_target | 6 | 묶음을 더하거나 뺐다 |
| 시간, scope, order·limit | 4 | 각 1건 |

- 정지 후보 8건(택시 유형): 3건(b005-07, 18, 44)은 모델 출력이 초안과 같다. 5건은 다르다(집계 `sum` 추가 2, vicinity 누락 2, 묶음 추가와 vicinity 누락 1).
- **사람 검토가 필요한 점("초안과 모델 중 어느 쪽이 맞는가").** 위 차이 가운데 다음은 초안이 틀렸을 수 있다.
  - 날짜 표기 10건은 뜻이 같을 수 있다. 같다고 보면 DPO 쌍으로 쓰지 않는다(뜻이 같은 두 출력을 chosen·rejected로 두지 않는다).
  - 한 장소 `both` 대 pickup+dropoff 두 항목은 뜻이 다를 수 있다(검토 안내 4번). 질문 문장이 어느 쪽인지 사람이 정한다.
- 출력 원문(thinking 포함)은 `hf_outputs.json`과 `review/review_queue.jsonl`에 있다. 학습 trace로 쓰지 않는다(trace는 승인 뒤 따로 모은다).

**검토 시트**

- `build_review.py` 결과: queue 105행 = SFT gold 60(그중 정지 target 8) + DPO 쌍 45, `model_output_note` 0.
- `review/batch005_review.xlsx`는 커밋하지 않는다. `python sft_dpo_inventory/batch005/build_review.py --xlsx-only`로 다시 만든다.
