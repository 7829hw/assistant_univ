# pilot_004 보고

작성: 2026-10-15. 계획 `PLAN.md`(학습 시작 전 고정, `993ad97`), 절차 `../vendor100_protocol/PROTOCOL_v4.md`(확정 2026-10-14, sha256 `9e75c2a6…`), 결정 95–100.
숫자는 아래 기록 파일에서 옮겼다. 업체 100은 쓰지 않았다(중단 규칙에서 멈춤).

## 0. 요약

| 단계 | 결과 | 기록 |
|---|---|---|
| PROTOCOL_v4 확정 | BF16, flashinfer, 중단 규칙에 U 조건, 참고 셀 27b·vicinity 보고, GPU 3장 | `../vendor100_protocol/PROTOCOL_v4.md`(`8be4f31`) |
| 실차 8b 표본(결정 98) | 대상 16문항 × 32표본. 정답 나온 문항 5(plain 2, trip 1, vacant 2). **occupied 6문항은 192표본 중 정답 0** | `realtrip/realtrip_report.json` |
| 데이터 | SFT 467(131질문), DPO 385(58질문). 손실 token teacher 81.8%·8b 자체 18.2%. 상한으로 빠진 레코드 0 | `data/summary.json` |
| SFT 선택 | checkpoint-934(epoch 2). 84.18%(vLLM-base 75.00%), +9.18 [2.30, 16.08], U +2.04 [−1.79, 6.12] | `selection_sft.json` |
| DPO 선택 | checkpoint-385(100%). 81.12%, base 대비 +6.12 **[−0.77, 13.27]**, U +2.04 [−1.02, 5.36] | `selection_dpo.json` |
| **중단 규칙(결정 96)** | 조건 1(정답률 CI 하한 > 0) **불만족**, 조건 2(U CI 하한 ≤ 0) 만족 → **업체 100 평가하지 않음** | `selection_dpo.json` `stop_rule(decision 96)` |
| 업체 100, 참고 셀(E, 27b), aux_test_v1, valid98 | 재지 않음(작업 7은 중단 규칙을 통과할 때만) | — |
| 실차 통행량(selection_v2) | 오독 문항 3개 중 old44/g02·g04는 최종 모델에서 오독 0(thinking이 occupied로 추론). indepv2/n33은 그대로 | `selection/compare_pilot003.json`, `selection/real_trip_thinking.json` |

판정은 PROTOCOL_v4의 중단 규칙 결과만 쓴다. selection_v2 결과를 업체 100이나 다른 셋으로 넓혀 해석하지 않는다.

## 1. 실차 대조 묶음 8b 표본(결정 98, `realtrip/`)

- 대상(`realtrip/targets.json`): 승인된 batch006 실차 대조 묶음 24문항 가운데 pilot_003 HF trace(greedy 1 + 표본 8)에서 정답이 없던 16문항
  (occupied 6, plain 4, trip 3, vacant 3).
- 생성: vLLM 0.30.0 BF16 base, flashinfer, 문항당 32표본, 서버 3개(GPU 0·1·2) × 동시 요청 8. 요청 512개(서버별 171·171·170)가 모두 같은 sampling 값 한 종류였다
  (`realtrip/request_log.json`). 서버가 받은 입력 id열이 보낸 것과 모두 같았다(echo 불일치 0). 생성 상한 0.
- 첫 실행은 수집 스크립트 오류(공용 thread pool이 한 서버에 동시 요청을 8개 넘게 배정)로 결과 없이 멈췄다. 서버별 executor로 고쳐 처음부터 다시 했다(`runs.log`).
- 판정·필터: pilot_003 trace와 같은 기준(조건 계층 전 출력의 gold 비교, 결정 4 tokenize 왕복(vLLM 생성 id 기준), 결정 40-D 루프, 결정 18 길이, 계약, 결정 6 운영 경로 재판정).

| 변형 | 문항 | 정답 표본(32 중 합) | SFT 후보 | DPO 쌍(필터 뒤 → 결정 52 상한 뒤) |
|---|---:|---:|---:|---|
| occupied | 6 | **0** | 0 | 0 |
| plain | 4 | 3 | 3 | → 16 |
| trip | 3 | 2 | 2 | → 8 |
| vacant | 3 | 2 | 2 | → 13 |
| 합 | 16 | 7 | 7 | 153 → 37 |

- 정답 표본이 끝내 0인 문항 11개: b006-05, 08, 09, 13, 15, 17, 21, 22, 23, 24, 25(occupied 6개 모두 포함).
- 필터에서 빠진 것: 결정 4 tokenize 왕복 불일치 2쌍, 결정 6(운영 경로에서 맞음 14, 그 밖 44). 원문은 `training/generated/thinking_traces/realtrip_vllm/`(ignore).

## 2. 데이터(`data/summary.json`, `data/README` 대신 이 절)

- 판 `training/generated/thinking_pilot004_t2pc`. sha256 sft_train `7cf221e6…`, dpo_train `6c52d047…`, manifest `ac7e7a7a…`.
- pilot_003 레코드 SFT 460·DPO 348이 모두 그대로 들어 있다(SFT는 `metadata.loss_scope`만 더해짐, teacher 레코드의 trace 파일 경로 표기가 pilot_004로 바뀜). 더한 것: 실차 SFT 7, DPO 37.

| 항목 | 값 |
|---|---|
| SFT 출처 | HF v004 124, HF batch005 86, HF batch006 17, **vLLM 실차 7**, teacher17 68, teacher batch005 101, teacher batch006 64. 8b 자체 234 : teacher 233 |
| 손실 범위(결정 86) | teacher 233 `full_response` — 손실 token 227,454(**81.8%**). 8b 자체 234 `json_only` — 50,573(18.2%) |
| DPO 출처 | HF trace 쌍 348(v004 161·batch005 127·batch006 60) + vLLM 실차 37. 교차 DPO 없음 |
| 유형 TV(질문 / 레코드 / DPO) | 실차 대조 묶음 포함 **0.117 / 0.127 / 0.189**(0.09 초과, 결정 92대로 그대로). 제외 0.016 / 0.080 / 0.087 |
| 유형 상한(결정 88·92) | 예외 제외 부분이 이미 0.09 이하라 빠진 레코드·질문 0 |
| 실차 대조 SFT(출처별) | occupied: teacher 24. plain: HF 4·teacher 16·vLLM 3. trip: HF 9·teacher 12·vLLM 2. vacant: HF 4·teacher 12·vLLM 2 |
| 실차 대조 DPO(출처별) | occupied 0. plain: HF 16·vLLM 16. trip: HF 24·vLLM 8. vacant: HF 20·vLLM 13 |
| 빠진 레코드 | pilot_003과 같다(v004 SFT 계약 8, DPO 계약 37·결정 18 길이 5·결정 52 상한 155). 실차 DPO 결정 52 상한 116 |
| 검사 | dry-run·tokenizer-check 통과(SFT·DPO), 출처별 손실 token 검사 467/467(`data/loss_tokens.json`), 평가 셋 새 겹침 0 — valid98 template 4·family 7, 업체 100 template 3·family 17은 결정 54의 기존 겹침(`data/overlap.json`) |

- 결정 52 상한의 seed 순번은 pilot_003 질문은 그대로, 실차 쌍이 새로 생긴 5질문은 뒤에 붙였다(`decision52_cap.seed_index`). 그래서 pilot_003 DPO 348쌍이 바뀌지 않았다.

## 3. 학습(`train_logs/`)

설정은 PLAN 2절 그대로(pilot_003과 같고 SFT 손실 범위만 by_source). 학습은 GPU 0(`2445b100`) 1장.

| 단계 | 시간 | step | step당 | peak 메모리 | checkpoint(loss at step / 마지막 50 평균, adapter sha256) |
|---|---|---:|---:|---:|---|
| SFT | 5,557 s(20:52–22:25) | 934 | 5.91 s | 43,900 MiB | 467: 0.2163 / 0.1510, `de62d4d4…` · 934: 0.1676 / 0.1211, `ca66b017…` |
| DPO | 8,862 s(22:47–01:14) | 385 | 18.13 s | 45,130 MiB | 193: 0.0087 / 0.2646, `9c0316c6…` · 385: 0.3707 / 0.0345, `5414ddd7…` |

- SFT loss가 pilot_003(마지막 50 평균 0.005)보다 크다. teacher 레코드의 thinking까지 손실에 들어가서다(결정 86). 두 값은 손실 범위가 달라 비교하지 않는다.
- adapter는 저장소 밖 `/home/hwkim/sftdpo_work/pilot_004/checkpoints/`.

## 4. checkpoint 선택과 중단 규칙(selection_v2 98, vLLM BF16 flashinfer, LoRA, 동시 요청 8, k=4)

| 셀 | 평균 | 표본별 | U | 조용한 오답 | 안정 정답 | 생성 상한 | 루프 | 실차 오독(표본) | vicinity 빠짐 | base 대비 [CI] | U [CI] | 조용한 오답 [CI] |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|---|
| vLLM-base(기준값, pilot_prep_007) | 75.00 | 74 72 72 76 | 4.08 | 2.04 | 52 | 0 | 0 | 8 | 0/4 | – | – | – |
| SFT 467 | 84.18 | 82 84 82 82 | 6.63 | 0.77 | 65 | 0 | 0 | 2 | 0/4 | +9.18 [3.06, 15.56] | +2.55 [−1.53, 6.89] | −1.28 [−4.08, 0.77] |
| **SFT 934(선택)** | 84.18 | 82 78 82 88 | 6.12 | 0.51 | 67 | 0 | 0 | 3 | 0/4 | +9.18 [2.30, 16.08] | +2.04 [−1.79, 6.12] | −1.53 [−4.34, 0.77] |
| DPO 193 | 80.10 | 80 80 74 80 | 6.38 | 7.65 | 65 | 0 | 0 | 3 | 0/4 | +5.10 [−2.04, 12.24] | +2.30 [−1.28, 6.38] | **+5.61 [0.77, 10.97]** |
| **DPO 385(선택, 최종)** | 81.12 | 78 81 78 81 | 6.12 | 5.87 | 70 | 0 | 0 | 4 | 0/4 | +6.12 **[−0.77, 13.27]** | +2.04 [−1.02, 5.36] | +3.83 [−0.77, 8.67] |

오류 유형(%, base → SFT 934 → DPO 385): aggregation_added 10.46 → 1.53 → 0.00, dt_missing 2.81 → 3.32 → 6.38, role_error 3.83 → 1.28 → 2.04,
role_notation 0 → 1.02 → 1.02, occupied_misread 2.04 → 0.77 → 1.02.

- SFT 467과 934의 평균이 같아(84.18) U가 낮은 934를 골랐다(7절 4의 순서).
- 표본 장치: 각 셀의 4표본이 GPU 0·1·2 서버에 나뉘었다(셀 json의 `meta.vllm.server_meta.gpu_uuid`). 모든 표본이 동시 요청 8, attention FLASHINFER, 요청 로그의 sampling 값 1종.
- vicinity 빠짐: selection_v2의 gold vicinity 문항은 1개뿐이고 모든 셀에서 0/4다. 이 셋으로는 감시 지표의 크기를 볼 수 없다.
- **중단 규칙(결정 96)**: vLLM-base → DPO 385
  - 조건 1: grounding_ok 차이 +6.12, CI [−0.77, 13.27]. 하한 −0.77 ≤ 0 → **불만족**.
  - 조건 2: U 차이 +2.04, CI [−1.02, 5.36]. 하한 ≤ 0 → 만족.
  - **결과: 업체 100으로 가지 않는다.** 작업 7(업체 100·E·27b·aux_test_v1·valid98)은 하지 않았다(`run_vendor4.sh`는 실행하지 않음).

### 4.1 보조 비교(판정·선택에 쓰지 않음, `selection/compare_pilot003.json`)

같은 조건(vLLM BF16 flashinfer, 동시 요청 8, k=4, selection_v2)의 셀끼리만 비교했다. pilot_003 최종은 pilot_prep_007의 `vllm-bf16-final`이다.

| 비교 | 정답률 [CI] | U [CI] | 조용한 오답 [CI] |
|---|---|---|---|
| DPO 효과: SFT 934 → DPO 385 | −3.06 [−9.18, 2.81] | 0.00 [−3.57, 3.57] | **+5.36 [2.04, 9.44]** |
| pilot_003 최종 → pilot_004 최종(DPO 385) | +0.77 [−5.87, 7.40] | −0.51 [−3.57, 2.55] | +3.57 [−0.77, 8.42] |
| pilot_003 최종 → pilot_004 SFT 934 | +3.83 [−2.55, 9.95] | −0.51 [−4.59, 3.57] | −1.79 [−4.34, 0.51] |

- **확인됨:** pilot_004에서 DPO 단계가 조용한 오답을 늘렸다(SFT 934 대비 +5.36, CI 하한 > 0). 늘어난 것은 주로 dt_missing(dimension_target 빠짐, 3.32 → 6.38%)이다.
  원인은 미확인이다(DPO 데이터는 pilot_003 348쌍 + 실차 37쌍이고, 시작점 SFT가 다르다).
- 참고: SFT 934만 놓고 보면 base 대비 +9.18 [2.30, 16.08], U +2.04 [−1.79, 6.12]로 결정 96의 두 조건을 만족하는 값이지만, 중단 규칙은 고른 최종 checkpoint(DPO)에 적용한다(PROTOCOL_v4 8절).
- 모든 비교는 같은 표본으로 고른 checkpoint라 선택 편향이 있다.

## 5. 실차 통행량(결정 66·86·98)

| 문항(selection_v2) | 질문 형태 | vLLM-base 정답 / 오독 | pilot_003 최종 | pilot_004 SFT 934 | pilot_004 최종 |
|---|---|---|---|---|---|
| old44/g02 | "…동성로의 실차 통행량은?" | 2 / 2 | 0 / 4 | **4 / 0** | **4 / 0** |
| old44/g04 | "…시군구별 실차 택시 통행량…" | 2 / 2 | 2 / 2 | 2 / 0 | **4 / 0** |
| indepv2/n33 | "…손님을 태운 택시가 몇 번이나 지나갔어?"(실차라는 말 없음) | 0 / 4 | 1 / 3 | 0 / 3 | 0 / 4 |

(4표본 중 수. `selection/compare_pilot003.json` `real_trip_items`)

- thinking(첫 계획, `selection/real_trip_thinking.json`, pilot_003 후속 분석과 같은 정규식):
  - g02·g04: pilot_004 SFT 934·최종 모두 4/4 표본에서 thinking이 occupied를 언급한다. 첫 계획은 passage_count + taxi_status occupied다(g04 SFT 1표본 제외).
    vLLM-base와 pilot_003 최종은 occupied 언급 0–1, 첫 계획 occupied 0이었다.
  - n33: pilot_004도 첫 계획이 trip_count 3–4/4, occupied 0이다.
- **확인됨:** "실차"라는 말이 있는 문항에서는 추론이 바뀌었다(trip → occupied 통행). "손님을 태운 택시"처럼 말을 바꾼 문항에서는 바뀌지 않았다.
- **가능성 있음:** 결정 86(teacher thinking까지 학습)이 이 변화에 기여했다. occupied DPO 쌍은 여전히 0이라(실차 8b 표본 정답 0) SFT 쪽 변화다.
  다만 이번 판은 손실 범위·데이터가 함께 바뀌어 원인을 나누지 못한다.
- 보호 형태인 valid98 h30은 이번에 재지 않았다(작업 7이 중단 규칙에서 멈춤).

## 6. GPU 배정(결정 100)

- 실차 표본 수집: 서버 3개(GPU 0 `2445b100`, 1 `a5ce83d0`, 2 `48f798cc`), 서버마다 동시 요청 8.
- 학습: SFT·DPO 모두 GPU 0 한 장.
- checkpoint 선택: 단계마다 서버 3개(GPU 0·1·2, 두 checkpoint를 LoRA로)에 표본 8개를 나눔. 셀 하나의 4표본이 여러 GPU에 걸친다(결정 93·100: 장치 일치 대신 통계로 판단).
- 쓰기 전 GPU 확인 기록: `gpu_check.txt`, `runs.log`. Ollama는 이 작업 동안 부르지 않았다.

## 7. 계획과 다른 점

1. 실차 수집 첫 실행이 스크립트 오류로 결과 없이 멈췄다. 고쳐서 처음부터 다시 했다(1절).
2. vLLM 셀 meta의 장치 필드(`A.device`가 읽는 `hf.device_uuid`)가 비어 있다. 장치는 `meta.vllm.server_meta.gpu_uuid`에 있다(기록 누락이 아니라 위치 차이).
3. 업체 100 단계 도구(`run_vendor4.sh`, `vendor100/judge4.py`, `valid98/valid98_gold.yaml`, `vllm_eval_thinking4.py`, `run_cell4v.py`)는 만들어 두었지만 실행하지 않았다.
