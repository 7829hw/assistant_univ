# pilot_002 보고서

작성: 2026-10-09. 브랜치 `geoflow/sft-dpo-t2pc`.

- 계획: `PLAN.md`(학습 전 고정, `2ab373e`). 계획 밖 실행 조건: `PLAN_DEVIATIONS.md`.
- 판정 기준: `../vendor100_protocol/PROTOCOL_v2.md`(확정 2026-10-08). 보조 분석: `../vendor100_protocol/ADDENDUM_three_way.md`. 결정: `../DECISIONS.md` 1–55.
- 하지 않은 것: prompt 변경, SEMANTIC_CODE 변경, 학습 설정 탐색, 재학습·재평가·재실행.
  업체 100은 4절 평가에서만 썼다(선택·설정에 쓰지 않음).
- 실행 의미 코드 지문은 모든 측정 meta(HF 결과 meta, Ollama `*.spec.json`)에서 `791c4a68`이다.

> **이 결과의 범위.**
> - 학습 데이터는 107질문(SFT 379 레코드, DPO 288쌍)이고, 판정 셋은 업체 100문항 하나다.
> - 아래 판정은 이 셋에서의 결과이며, 업체 100 밖으로 일반화하지 않는다.
> - 각 셀은 한 번씩만 쟀다. 판정 문구는 PROTOCOL_v2 규칙의 결과만 적는다. 보조 분석(5–7절)으로 판정을 바꾸지 않는다.

## 0. 요약

| 항목 | 결과 |
|---|---|
| 데이터 | SFT 379 레코드(107질문; HF 210, teacher 169), DPO 288쌍(45질문, HF base trace 쌍만) |
| 선택(selection_v1) | SFT step 380(75/100; 570과 동점, 이른 step), 최종 DPO step 144(80/100). base HF-E는 82 |
| **PROTOCOL_v2 판정** | **HF 주 비교(HF-E → 최종): 차이 없음.** **운영 주 비교(E → Ollama-최종): 악화(U 순증 6).** 참고 비교: HF-SFT 차이 없음, Ollama-SFT 악화(U 순증 4) |
| grounding_ok(업체 100) | HF-E 84 → SFT 85 / 최종 88(p 1.0 / 0.42). E 79 → SFT 77 / 최종 86(p 0.80 / 0.14) |
| U(업체 100) | HF 2 → SFT 1 / 최종 1. 운영 3 → SFT 7 / 최종 9 |
| 등록 | 두 모델을 새 이름으로 등록. 렌더링 확인 10/10(결정 31), 모든 Ollama 셀이 결정 55 GPU 확인 통과 |

## 1. 데이터(`data/README.md`, `data/summary.json`, `data/overlap.json`)

- 판: `training/generated/thinking_pilot002_t2pc`(sft_train `398d1991…`, dpo_train `4047769f…`). gold `reviewed_gold_v005_t2pc`.
- **SFT 379 레코드, 107질문.**
  - HF v004 124(32.7%), HF batch005 86(22.7%), teacher(qwen3.8:27b) 17질문 68(17.9%, 결정 48·49), teacher batch005 27질문 101(26.6%, 결정 50).
  - 정지 target 레코드(결정 14) 31. SFT 레코드가 없는 gold 질문 4개(b004-19, b004-35, b005-11, b005-60).
- **DPO 288쌍, 45질문**(constraint 194, semantic 94). HF base trace 쌍만이다(결정 52 cap 8).
- 유형 분포 TV(개발 셋 454질문 대비): SFT 질문 0.016, SFT 레코드 0.080, DPO 쌍 0.087.
- **결정 54의 겹침**(학습 질문과 평가 셋의 gold 비교):
  - selection_v1, aux_test_v1: 질문·id·template·family 겹침 없음.
  - 업체 100: template 겹침 3문항(012, 076, 093), family 겹침 10문항(012, 016, 037, 046, 060, 068, 070, 076, 080, 093).
    결정 54에 따라 평가에 그대로 두고 family 분리로 따로 적는다(5절).
  - valid98: template 겹침 4문항(heldout_v8/t11, t22, t25, heldout_v9/h14), family 겹침 6문항. valid98은 보조 기록이다.
- pilot_001(34질문, SFT 124, DPO 212)보다 질문 수는 약 3배다. 여전히 작은 데이터다.

## 2. 학습과 checkpoint 선택(`train_logs/`, `selection/SUMMARY.md`, `selection_*.json`)

GPU 3에 다른 사용자(jmbae) 프로세스가 있어 PLAN 4절대로 Ollama 모델이 없는 GPU 2에서 학습했다(`runs.log`, `gpu_check.txt`).
학습 동안 Ollama 측정은 없었다.

| 단계 | step | step당 | 총 시간 | torch max allocated / reserved | nvidia-smi peak |
|---|---:|---:|---:|---|---:|
| SFT(2 epoch) | 758 | 6.1초 | 77.9분 | 38.3 / 42.3 GiB | 43,882 MiB |
| DPO(1 epoch, reference 미리 계산 포함) | 288 | 18.6초 | 113.8분 | 42.6 / 43.6 GiB | 45,130 MiB |

**selection_v1**(100문항, HF-E 조건, base 82; 선택 규칙: grounding_ok 최고, 동점이면 이른 step)

| checkpoint | loss(그 step / 구간 평균) | grounding_ok | 첫 응답 일치 | 생성 상한 호출 | 루프 호출(문항) | 문항 초 중앙 | 평가 GPU |
|---|---|---:|---:|---:|---:|---:|---|
| SFT 190 | 0.0015 / 0.0155 | 74 | 48 | 4 | 4(2) | 30.0 | GPU 2 |
| **SFT 380(선택)** | 0.0033 / 0.0085 | **75** | 58 | 2 | 2(1) | 28.1 | GPU 2 |
| SFT 570 | 0.0111 / 0.0058 | 75 | 58 | 0 | 0(0) | 26.7 | GPU 2 |
| SFT 758 | 0.0034 / 0.0047 | 73 | 55 | 4 | 4(2) | 27.8 | GPU 2 |
| DPO 72 | 0.305 / 0.614 | 72 | 56 | 4 | 4(2) | 28.0 | GPU 2 |
| **DPO 144(선택)** | 1.132 / 0.539 | **80** | 59 | 4 | 4(2) | 25.5 | GPU 3 |
| DPO 216 | 0.330 / 0.320 | 78 | 57 | 2 | 2(1) | 27.1 | GPU 2 |
| DPO 288 | 0.0001 / 0.333 | 78 | 57 | 10 | 10(5) | 27.5 | GPU 3 |

- 모든 checkpoint가 selection_v1에서 base(82)보다 낮다. PLAN에는 이 경우의 중단 규칙이 없어 계획대로 진행했다.
- DPO 구간 평균 reward accuracy 0.63 → 0.75 → 0.92 → 0.88, margin 0.34 → 0.72 → 1.47 → 1.73.
- 루프는 결정 40-D `is_loop`를 모든 호출의 thinking 원문에 적용한 수다. 루프 호출은 모두 생성 상한 호출과 같은 호출이다.
- **valid98**(보조, 고른 두 모델만): SFT 380 **54/98**, 최종 DPO 144 **65/98**(base 55/98, pilot_001 SFT 61 / 최종 65).
  - 생성 상한 호출 SFT 8, 최종 4. 루프 호출 같은 수(`analysis/loops_latency.json`).
- adapter(저장소 밖 `/home/hwkim/sftdpo_work/pilot_002/checkpoints/`): SFT checkpoint-380 `416dd303…`, DPO checkpoint-144/policy `60cf9ffe…`.
  전체 sha256은 `selection_sft.json`, `selection_dpo.json`.

## 3. 등록(결정 20·31·55, `ollama/`)

| 모델 | adapter | Ollama 이름(digest) | 렌더링 확인 | GPU 확인 |
|---|---|---|---|---|
| SFT | sft/checkpoint-380 | `geoflow-qwen3-8b-pilot002-sft:q4km-hfthink`(1a813e0a) | 10/10(token 수·thinking 켬·분리) | 100% GPU |
| 최종 | dpo/checkpoint-144/policy | `geoflow-qwen3-8b-pilot002-final:q4km-hfthink`(c2d10cb2) | 10/10 | 100% GPU |

- merge(bfloat16, CPU) → `gguf_convert.sh`(llama.cpp b11434, Q4_K_M) → API 등록(base와 같은 TEMPLATE·PARAMETER). 기존 모델은 건드리지 않았다.
- merge·GGUF는 루트 디스크 여유 때문에 `/data/hwkim/sftdpo_work/`(저장소 밖)에 두었다(`PLAN_DEVIATIONS.md` 3번). sha256은 `ollama/*.receipt.json`.

## 4. PROTOCOL_v2 판정(업체 100, `vendor100/judgment.json`)

평가 직전 Ollama 버전은 0.35.1로 E·B-conv와 같아 기준 셀을 다시 재지 않았다(`vendor100/ollama_version_check.json`).
HF 셀은 GPU 3, Ollama 셀은 GPU 2에서 순서대로 쟀고 동시에 돌리지 않았다(`runs.log`).

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 안전한 실패 | 지연 중앙값(초) |
|---|---:|---:|---:|---:|---:|---:|
| HF-E | 84 | 91 | 2 | 0 | 7 | 22.0 |
| HF-SFT | 85 | 91 | 1 | 0 | 8 | 27.0 |
| HF-최종 | 88 | 87 | 1 | 0 | 12 | 25.1 |
| E | 79 | 84 | 3 | 1 | 12 | 10.9 |
| B-conv | 77 | 79 | 6 | 0 | 15 | 10.4 |
| Ollama-SFT | 77 | 80 | 7 | 2 | 11 | 11.2 |
| Ollama-최종 | 86 | 86 | 9 | 1 | 4 | 11.2 |

| 비교 | grounding_ok | b / c | McNemar p | U(전→후, 새로 생긴 / 사라진) | 조용한 오답(전→후) | 지연 비율 | **판정** |
|---|---|---|---:|---|---|---:|---|
| HF 주: HF-E → HF-최종 | 84 → 88 | 9 / 5 | 0.42 | 2 → 1(없음 / 074) | 0 → 0 | 1.14 | **차이 없음** |
| HF 참고: HF-E → HF-SFT | 84 → 85 | 7 / 6 | 1.00 | 2 → 1(054 / 007, 074) | 0 → 0 | 1.23 | 차이 없음 |
| 운영 주: E → Ollama-최종 | 79 → 86 | 12 / 5 | 0.14 | 3 → 9(016, 026, 037, 040, 041, 074, 093 / 047) | 1 → 1(100 / 080) | 1.03 | **악화(U 순증 6)** |
| 운영 참고: E → Ollama-SFT | 79 → 77 | 7 / 9 | 0.80 | 3 → 7(026, 037, 040, 041, 044, 085 / 047, 054) | 1 → 2(030, 100 / 080) | 1.03 | 악화(U 순증 4) |

- **grounding_ok 차이는 네 비교 모두 유의하지 않다(p 0.14–1.00).** 개선 조건 1(p < 0.05)을 만족한 비교는 없다.
- **운영 경로의 "악화"는 U 순증 규칙(≥ 3) 때문이다.** grounding_ok가 줄어서가 아니다.
- 업체 100에는 정책·모호 라벨 문항이 없어, 뺀 값은 전체 값과 같다.

## 5. 보조: family 분리, U 문항, 삼자 비교(판정에 쓰지 않음)

**family 분리(결정 15·54).** 학습 질문 family와 겹치는 업체 100 문항은 10개다.

| 비교 | family 안(10) grounding_ok, b / c | family 밖(90) grounding_ok, b / c |
|---|---|---|
| HF-E → HF-최종 | 7 → 7, 1 / 1 | 77 → 81, 8 / 4 |
| E → Ollama-최종 | 5 → 7, 3 / 1 | 74 → 79, 9 / 4 |
| E → Ollama-SFT | 5 → 4, 1 / 2 | 74 → 73, 6 / 7 |

- Ollama-최종에서 새로 생긴 U 7문항 가운데 3문항(016, 037, 093)이 family 안이다. 093은 template도 겹친다.
  family 밖만 세어도 U는 3 → 6(순증 3)이다.

**Ollama-최종의 U 9문항**(`u_flags`, E와 HF-최종의 같은 문항 분류):

| 문항 | U 종류 | E | HF-최종 |
|---|---|---|---|
| 013 | U1 taxi_status, U2 scope, U3 tool | U | 정상 |
| 016(family) | U2 dimension_target | 정상 | 정상 |
| 026 | U2 dimension_target | 정상 | 정상 |
| 037(family) | U1, U2 scope, U3 | 안전한 실패(MISSING_RELATION_QUALIFIER) | 안전한 실패 |
| 040 | U2 dimension_target | 정상 | 정상 |
| 041 | U2 scope_dropoff·pickup | 정상 | 정상 |
| 054 | U1, U2 scope, U3 | U | 안전한 실패 |
| 074 | U1, U2 scope, U3 | 정상 | 안전한 실패 |
| 093(family, template) | U2 scope_dropoff | 안전한 실패(MISSING_RELATION_QUALIFIER) | 안전한 실패 |

- 운영 경로에서 안전한 실패가 12 → 4로 줄고 U가 3 → 9로 늘었다. 같은 adapter의 HF 경로에서는 U가 1이다.
- 이 차이가 Q4_K_M 변환·Ollama 경로 때문인지는 이 기록으로 가를 수 없다(아래 삼자 비교 참고).

**삼자 비교(ADDENDUM, 운영 경로).**

| 쌍 | grounding_ok | b / c | p | U(전→후) | 조용한 오답 |
|---|---|---|---:|---|---|
| E → B-conv(변환 효과) | 79 → 77 | 10 / 12 | 0.83 | 3 → 6 | 1 → 0 |
| B-conv → Ollama-최종(학습 효과) | 77 → 86 | 15 / 6 | 0.078 | 6 → 9 | 0 → 1 |
| B-conv → Ollama-SFT(학습 효과) | 77 → 77 | 11 / 11 | 1.00 | 6 → 7 | 0 → 2 |

- U 조합(E, B-conv, 최종): U U U 1(013), U N U 1(054), U N N 1(047), N U U 3(040, 074, 093), N U N 2(031, 084), N N U 4(016, 026, 037, 041).
- 최종의 U 9개 중 4개(040, 074, 093, 013)는 직접 변환한 base(B-conv)에서도 U다.

## 6. 보조 시험 셋 aux_test_v1(51문항, 보고만, `aux_test/comparison.json`)

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 생성 상한 호출 |
|---|---:|---:|---:|---:|---:|---:|
| HF-E | 27 | – | – | – | 21.9 | 2 |
| HF-SFT | 33 | – | – | – | 30.8 | 2 |
| HF-최종 | 30 | – | – | – | 29.3 | 6 |
| E | 29 | 32 | 3 | 5 | 13.5 | 0 |
| B-conv | 24 | 27 | 3 | 8 | 11.6 | 0 |
| Ollama-SFT | 32 | 32 | 6 | 3 | 12.0 | 0 |
| Ollama-최종 | 29 | 31 | 4 | 5 | 11.0 | 0 |

| 비교 | grounding_ok | b / c | p | U(전→후) | 조용한 오답 | 지연 비율 |
|---|---|---|---:|---|---|---:|
| HF-E → HF-최종 | 27 → 30 | 7 / 4 | 0.55 | – | – | 1.34 |
| HF-E → HF-SFT | 27 → 33 | 10 / 4 | 0.18 | – | – | 1.41 |
| E → Ollama-최종 | 29 → 29 | 9 / 9 | 1.00 | 3 → 4(f31) | 5 → 5 | 0.82 |
| E → Ollama-SFT | 29 → 32 | 10 / 7 | 0.63 | 3 → 6 | 5 → 3 | 0.89 |
| E → B-conv | 29 → 24 | 5 / 10 | 0.30 | 3 → 3 | 5 → 8 | 0.86 |
| B-conv → Ollama-최종 | 24 → 29 | 10 / 5 | 0.30 | 3 → 4 | 8 → 5 | 0.96 |

- HF 셀은 base 기준값과 같은 `eval_set.py`로 쟀다. 이 출력에는 호출·최종 답 기록이 없어 정상·U·조용한 오답을 셀 수 없다(`–`).
- 판정은 업체 100으로만 한다(PROTOCOL_v2 2.2절).

## 7. 루프·생성 상한·지연(`analysis/loops_latency.json`)

| 셋 | 셀 | 호출 | 생성 상한 호출 | 루프 호출(문항) |
|---|---|---:|---:|---|
| 업체 100 | HF-E | 118 | 2 | 2(095) |
| 업체 100 | pilot_002 HF-SFT | 117 | 2 | 2(026) |
| 업체 100 | pilot_002 HF-최종 | 119 | 2 | 2(067) |
| aux_test_v1 | HF-E | 61 | 2 | 2(f02) |
| aux_test_v1 | pilot_002 HF-SFT | 62 | 2 | 2(f24) |
| aux_test_v1 | pilot_002 HF-최종 | 62 | 6 | 6(f21, f24, f27) |

- Ollama 셀은 평가 기록에 thinking 원문이 없어 루프를 셀 수 없다. 생성 상한 호출은 모든 Ollama 셀에서 0이다.
  첫 plan thinking 글자 수 최대: 업체 100 E 8,987, Ollama-SFT 9,002, Ollama-최종 58,603.
- 지연(운영): E 대비 1.03배(SFT·최종 모두). 악화 기준 1.5배 아래다. HF 지연은 HF-E(GPU 2)와 학습 모델(GPU 3)의 장치가 다르다.

## 8. pilot_001과의 비교(같은 지표·같은 조건만)

같은 업체 100, 같은 기준 셀(HF-E, E), 같은 코드 지문(791c4a68), 같은 Ollama 버전(0.35.1)이다.
pilot_001의 판정은 PROTOCOL(v1)이고 pilot_002는 PROTOCOL_v2라 **판정 문구는 서로 비교하지 않는다.** 숫자만 나란히 적는다.

| 셀 | pilot_001 grounding_ok / 정상 / U / 조용한 오답 / 지연 | pilot_002 grounding_ok / 정상 / U / 조용한 오답 / 지연 |
|---|---|---|
| HF-SFT | 82 / 87 / 2 / 1 / 34.2 | 85 / 91 / 1 / 0 / 27.0 |
| HF-최종 | 86 / 90 / 4 / 0 / 28.4 | 88 / 87 / 1 / 0 / 25.1 |
| Ollama-SFT | 80 / 82 / 6 / 3 / 12.6 | 77 / 80 / 7 / 2 / 11.2 |
| Ollama-최종 | 77 / 81 / 2 / 2 / 12.2 | 86 / 86 / 9 / 1 / 11.2 |

- valid98: pilot_001 SFT 61 / 최종 65, pilot_002 SFT 54 / 최종 65.
- 다른 조건:
  - 선택 셋이 다르다(pilot_001 valid98, pilot_002 selection_v1).
  - HF 셀 장치가 다르다(pilot_001 GPU 2, pilot_002 GPU 3). HF 경로의 GPU 2·3 출력 일치는 확인되지 않았다(`../pilot_001_analysis/REPORT.md` e절).
  - 데이터 크기·구성이 다르다(1절).

## 9. Ollama 장애와 감사(결정 55, `ollama_gpu_audit.md`, `PLAN_DEVIATIONS.md` 1·2번)

- 2026-10-08 10:33 aux_test E 시도는 컨테이너 CUDA 장애로 CPU에서 돌아(4.3–7.2 tok/s) 6문항 뒤 멈췄다. 출력은 `aux_test/ABORTED_cpu_E.*`로 남기고 쓰지 않았다.
- 사용자가 컨테이너를 복구한 뒤 결정 55의 확인(precheck, 첫 문항 100% GPU, 호출 30 tok/s 이상)을 붙여 E·B-conv를 처음부터 쟀다(첫 측정, 재실행 아님).
- **감사:** 판정에 쓴 기존 Ollama 기록(업체 100 E·B-conv, pilot_001 Ollama 셀, valid98 Ollama 셀, teacher 수집)은 기록된 속도로 보아 모두 GPU였다. 의심 셀은 없다.
- 이번 Ollama 셀 6개(렌더링 확인 2, 업체 100 2, aux 2)는 모두 100% GPU였다. 호출 속도 최소값: 업체 100 SFT 46.3, 최종 65.1, aux SFT 89.3, 최종 91.0 tok/s.

## 10. 실행 기록에 남길 것

- **push 거부.** 2026-10-09 03:3x KST부터 `geoflow/sft-dpo-t2pc` push가 거부됐다(fetch first).
  - 원인: 다른 장비(RTX PRO 6000 Blackwell)의 다른 세션이 같은 브랜치에 path_repeat_001 커밋 5개(`274c75e`–`7630af8`, 결정 56)를 먼저 push했다.
  - CLAUDE.md대로 merge·rebase로 우회하지 않았다. `b5f1423`(SFT) 뒤의 커밋은 로컬에만 있다.
  - `run_eval.sh`는 push 실패를 기록만 하고 측정을 이어가게 바꿨다(`426cc8c`). 측정 내용에는 영향이 없다.
  - 원격의 커밋은 `thinking_prep_001/hf_eval_thinking.py`·`hf_thinking.py`를 바꿨다. pilot_002 HF 셀은 로컬(바뀌기 전) 판으로 쟀다. HF-E 기준값과 같은 판이다.
- **선택 평가 장치.** selection_v1 평가는 GPU 3이 비면 GPU 3, 아니면 GPU 2에서 했다. SFT 4개는 GPU 2, DPO 144·288은 GPU 3, DPO 72·216은 GPU 2다.
  HF 경로의 GPU 2·3 출력 일치는 확인되지 않았으므로, DPO 선택(144)에 장치 차이가 섞였을 수 있다.
