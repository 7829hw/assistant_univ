# "실차 통행량" 오독: 개발 셋 확인(결정 63 E-3)

- 이 문서는 기록만 쓴다. 모델 호출은 없고, 업체 100과 aux_test_v1은 근거로 쓰지 않았다.
- 스크립트는 `passage_status.py`, 결과는 `passage_status.json`이다.
- 대상 문항은 gold 측정값이 passage_count이고 taxi_status가 있는 문항이다.
  - selection_v1: 7문항. 그중 실차(occupied)는 g02, g04, n33의 3문항이다.
  - valid98: 4문항. 그중 실차는 h30 1문항이다.
- gold 판단: 실차 통행량 = passage_count + taxi_status occupied(결정 62에서 확인).

## 1. 실차 문항을 trip_count로 읽은 수

| 셋 | 셀 | 실차 → trip_count | 그중 답을 냄 | 상태 있는 통행량 전체 grounding_ok |
|---|---|---|---:|---:|
| selection_v1 | HF-base | 2/3(g04, n33) | 1 | 4/7 |
| selection_v1 | HF SFT 190 / 380 / 570 / 758 | 2/3, 2/3, 1/3, 3/3 | 1, 0, 0, 0 | 3, 2, 4, 3 |
| selection_v1 | HF DPO 72 / 144 / 216 / 288 | 2/3, 2/3, 2/3, 1/3 | 1, 1, 2, 1 | 2, 3, 3, 3 |
| selection_v1 | E(공식 Q4_K_M) | 3/3 | 2 | 2/7 |
| selection_v1 | c(공식 + HF TEMPLATE) | 2/3 | 1 | 3/7 |
| selection_v1 | B-conv(직접 변환 base Q4_K_M) | 3/3 | 3 | 1/7 |
| selection_v1 | d(직접 변환 base Q8_0) | 3/3 | 2 | 2/7 |
| selection_v1 | Ollama-final(Q4_K_M) | 2/3 | 2 | 3/7 |
| selection_v1 | e(최종 Q8_0) | 2/3 | 1 | 3/7 |
| valid98 | HF-base | 1/1(h30) | 1 | 3/4 |
| valid98 | pilot_001 SFT 124 / DPO 212 | 1/1, 1/1 | 0, 1 | 3, 3 |
| valid98 | pilot_002 SFT 380 / DPO 144 | 1/1, 1/1 | 0, 0 | 2, 3 |
| valid98 | B-conv | 0/1(상태 누락) | 0 | 3/4 |
| valid98 | pilot_001 Ollama-final | 1/1 | 1 | 2/4 |

- "답을 냄"은 trip_count로 읽고 멈추지 않은 경우다. 이것이 조용한 오답이나 U 후보가 된다. 나머지는 대부분 MISSING_RELATION_QUALIFIER로 멈췄다.
- 실차가 아닌 상태(공차·대기, selection_v1 4문항과 valid98 3문항)를 trip_count로 읽은 경우는 22셀 가운데 1건뿐이다. Ollama-final이 공차 m27을 trip_count로 읽었다.
- 나머지 오독은 모두 "실차" 문항에서 나왔다.

## 2. 학습 데이터(`reviewed_gold_v005_t2pc`)

| 유형 | SFT | DPO |
|---|---:|---:|
| passage_count + taxi_status occupied | 0 | 0 |
| passage_count + taxi_status vacant | 1 | 0 |
| passage_count + 상태 없음 | 5 | 4 |
| trip_count 정답인데 질문에 "실차"가 있음 | 50 | 28 |

## 3. 결론

- **확인됨: 개발 셋에도 오독이 있다.** 학습하지 않은 base(HF-base, E, c, B-conv, d)에서 이미 실차 문항을 trip_count로 읽는다.
  - selection_v1에서는 셀마다 2–3/3이다.
  - valid98 h30에서도 HF-base가 trip_count로 읽었다.
  - 따라서 오독은 학습이 만든 것이 아니다.
- **확인됨: 학습 후에도 줄지 않았다.** 학습한 checkpoint와 모델 모두 1–3/3이다.
- **확인됨: 학습 데이터에는 "실차 통행량" 정답이 하나도 없다.** 반면 "실차"가 들어간 질문의 정답이 trip_count인 기록은 SFT에 50개, DPO에 28개 있다.
- 위 세 가지가 개발 셋에서 확인되었으므로, **데이터 보강 근거 있음**으로 적는다.
  - 보강했을 때 오독이 얼마나 줄지는 추정하지 않았다.
  - 대상 문항 수가 적어서(실차 4문항) 셀 사이 차이(1/3 대 3/3)도 해석하지 않는다.
