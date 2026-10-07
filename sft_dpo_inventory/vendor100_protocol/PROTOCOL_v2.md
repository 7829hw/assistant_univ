# 업체 100 평가 절차 v2 (pilot_002) — **확정(2026-10-08, 사용자)**

작성: 2026-10-07(결정 44). 확정: 2026-10-08, 사용자(결정 46으로 셋 선택지 1을 고름).

- 2026-10-07 초안은 결정 42의 보조 시험 셋이 없어 확정을 보류했다(`../pilot_prep_004/sets/SURVEY.md`).
- 결정 46으로 두 셋을 고정하고(`../pilot_prep_005/sets/`), base HF-E 기준값을 두 셋에서 한 번씩 잰 뒤 3절과 7절을 채웠다.
- **확정한 뒤에는 이 문서를 고치지 않는다.**
- pilot_001의 `PROTOCOL.md`와 `ADDENDUM_three_way.md`는 고치지 않는다.

## 1. 이어받는 문서

아래 두 문서의 모든 절을 그대로 이어받는다. 2절의 두 변경과 7절의 추가만 다르다.

| 문서 | 결정 | sha256 | 커밋 |
|---|---|---|---|
| `PROTOCOL.md`(확정 2026-10-06) | 22 | `ca9cd3aa44ddca6c8fdaae0eb46bf810a865569e0e8248c6a69cfd714e92a818` | a1df5b5 |
| `ADDENDUM_three_way.md`(고정 2026-10-06) | 30 | `bae0c0cad6a7f9984153f283d7ba383103b86d67032126642b68718657008d47` | 8c21633 |

이어받는 것의 요약(원문이 우선한다):

- **평가 원칙.**
  - 업체 100은 평가 전용이고 한 번만 잰다. 결과를 보고 checkpoint, 설정, prompt, 코드를 바꾸지 않는다(1절).
  - 학습 모델 두 개(SFT, 최종)를 잰다. 주 비교는 최종 대 기준이다. 학습 효과(HF)와 운영 판단(Ollama)은 따로 판정한다(3절).
- **실행 조건(4절).**
  - 기준일 2026-09-25, 조건 계층 켬, mock·legacy.
  - HF: greedy, thinking 켬, 8192.
  - Ollama: temperature 0, think 미지정, num_predict 미지정, Q4_K_M, 문항마다 모델 내림.
- **재실행 금지와 기반 장애 예외(5절).**
- **문항별 비교(6절).** grounding_ok의 b·c와 McNemar 정확 검정(양측). U(U1–U4)와 조용한 오답(v4 "오답" 중 U 아님)은 따로 센다.
- **보조 보고.** 결정 15의 family 분리(7절)와 삼자 비교(ADDENDUM, 판정에 쓰지 않음).

## 2. 바뀌는 것(결정 44)

### 2.1 U와 조용한 오답의 악화 기준

PROTOCOL 7절의 개선 조건 2·3과 악화 조건 2·3을 다음으로 바꾼다. 나머지 조건(McNemar, 지연 1.5배)과 "차이 없음"의 뜻은 그대로다.

- **개선**(모두 만족):
  1. 주 비교에서 grounding_ok가 늘고(b > c), McNemar 양측 p < 0.05. *(그대로)*
  2. **U 순증 ≤ 2.**
  3. **조용한 오답(U 아님) 순증 ≤ 2.**
- **악화**(하나라도 해당):
  1. grounding_ok가 줄고(c > b), McNemar 양측 p < 0.05. *(그대로)*
  2. **U 순증 ≥ 3.**
  3. **조용한 오답(U 아님) 순증 ≥ 3.**
  4. 운영 셀에서 지연 중앙값이 기준 셀의 1.5배를 넘음. *(그대로)*
- 순증 = (비교 셀의 개수) − (기준 셀의 개수). 새로 생긴 문항과 사라진 문항 목록은 계속 함께 적는다.
- U와 조용한 오답은 각각 따로 센다. 둘을 더해 한 기준으로 보지 않는다.

### 2.2 보조 시험 셋 보고(결정 42)

- 판정은 업체 100으로만 한다. 보조 시험 셋의 결과로 판정을 바꾸지 않는다.
- 보조 시험 셋은 업체 100과 같은 셀(3절)을 같은 실행 조건(4절)으로 한 번씩 재고, 같은 지표(6절)로 함께 보고한다.
  - 지표: grounding_ok, b·c·p, 보고 분류, U·조용한 오답 순증과 문항 목록, 지연.
- 보조 시험 셋도 평가 전용이다. 학습, checkpoint 선택, trace 선택, annotation 후보에 쓰지 않는다.
- 보조 시험 셋의 기준 셀은 업체 100과 같은 기준 모델이다.
  - HF-E: base, HF 경로.
  - E: `qwen3:8b`, Ollama 경로.
  - 셋이 정해진 뒤 학습 전에 같은 명세로 한 번 잰다. 이것은 재측정이 아니라 그 셋의 첫 측정이다.

## 3. pilot_002의 셀과 기준값(이어받은 규칙을 적용한 값)

| 경로 | 기준 셀 | 기록 | 재사용 조건(PROTOCOL 3절) |
|---|---|---|---|
| HF | HF-E | 84(`thinking_prep_001/hf_e/HF-E_run1.json`, 지문 791c4a68) | 지문·prompt·명세가 같으면 재사용. 다르면 새 명세로 첫 측정 |
| Ollama | E | 79(`pilot_prep_003/ollama/E.json`, Ollama 0.35.1, GPU 3). 같은 값이 GPU 2에서도 첫 응답 100/100 바이트 일치로 재현됐다(결정 37, `pilot_001_analysis/device_check/`) | 결정 31: 버전이 0.35.1과 다르면 같은 버전에서 다시 잰다 |
| Ollama(삼자) | B-conv | 77(`pilot_prep_003/ollama/B-conv.json`). GPU 2에서도 같음 | 같음 |

**새 두 셋의 base 기준값(첫 측정, 2026-10-08)**

명세: base Qwen3-8B@b968826d, HF 경로, thinking 켬(`enable_thinking=True`), greedy, max_new_tokens 8192, 기준일 2026-09-25, 조건 계층 켬, mock·legacy, prompt 87048d0c, 지문 791c4a68. 장치는 GPU 2(UUID `GPU-a644de12…`, Ollama 모델 없음, Ollama 측정 없음)다.

| 셋 | 셀 | grounding_ok | 첫 응답 일치 | 생성 상한 호출 | 기록 |
|---|---|---:|---:|---:|---|
| 선택용 셋 `selection_v1`(100) | HF-E | 82 | 61 | 0 | `../pilot_prep_005/sets/runs/selection_base.json`(원문 sha256 `9d4ab1f3…`) |
| 보조 시험 셋 `aux_test_v1`(51) | HF-E | 27 | 21 | 2 | `../pilot_prep_005/sets/runs/aux_test_base.json`(원문 sha256 `2d05117b…`) |

- 셋 안 출처별: 선택용 old44 26/29, contrast 10/14, indepv2 12/18, indepv3 18/21, indepv4 16/18. 보조 at 10/14, final_v12 17/37.
- 보조 시험 셋의 Ollama 셀(E, B-conv)은 이 확정 시점에 재지 않았다. 2.2절대로 학습 전에 같은 명세로 한 번 잰다(그 셋의 첫 측정).
- 선택용 셋은 HF 경로로만 쓴다(checkpoint 선택). Ollama 셀은 재지 않는다.

- 비교 셀은 pilot_002에서 고른 SFT와 최종(SFT+DPO)이다. 각각 HF와 등록 모델(Ollama)로 잰다.
- checkpoint 선택은 결정 41의 새 선택용 셋으로 한다. valid98은 보조 기록으로만 잰다. 업체 100과 보조 시험 셋은 선택에 쓰지 않는다.

## 4. 판정에 쓰지 않는 실행 환경 메모

이것은 결정 44의 변경이 아니라 다른 결정에서 온 실행 환경이다. 판정 규칙을 바꾸지 않는다.

- **GPU 배치.** PROTOCOL 4절의 "HF = GPU 2, Ollama = GPU 3"은 결정 32·38로 바뀌었다.
  - 지금은 Ollama가 GPU 2(UUID `GPU-a644de12…`), HF는 GPU 3(`GPU-48f798cc…`)이 기본이다.
  - HF를 GPU 2에서 돌리는 것은 Ollama 모델이 올라가 있지 않을 때만 한다(`CLAUDE.md` 4–6번).
- **장치.** 실행 장치는 셀마다 결과 meta에 남긴다.
  - Ollama 경로는 GPU 2와 GPU 3에서 업체 100 첫 응답이 100/100 바이트 일치했다(결정 37).
  - HF 경로의 장치 일치는 결정 43의 실험 결과(`pilot_001_analysis/REPORT.md` 추가 절)를 따른다.
- **원문 보관.** 원문(평가 raw)은 결정 33에 따라 커밋한다. weights·adapter·GGUF·cache는 커밋하지 않는다.

## 5. 재실행 금지

PROTOCOL 5절을 그대로 따른다. 보조 시험 셋에도 같은 규칙을 적용한다. 셀마다 한 번만 재고, 기반 장애에서만 이어서 잰다.

## 6. 산출물

`sft_dpo_inventory/pilot_002/vendor100/`(업체 100)과 `sft_dpo_inventory/pilot_002/aux_test/`(보조 시험 셋):

- 셀별 결과와 원문.
- 비교 표와 판정(업체 100만).
- 삼자 비교(보조).
- 이 문서의 확정판 sha256.

## 7. 셋

| 셋 | 용도 | 이름·경로 | 문항 | sha256 |
|---|---|---|---:|---|
| 업체 100 | 판정 | `evaluation/vendor100/gold.yaml` | 100 | `f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0` |
| 보조 시험 셋(결정 42·46) | 함께 보고, 판정에 쓰지 않음 | `aux_test_v1` — `sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json` | 51 | `692b792fdfd1a95f9bd46c27262ed347d816076d15744070c1ca35ac25779aa0` |
| 선택용 셋(결정 41·46, 참고) | checkpoint 선택 | `selection_v1` — `sft_dpo_inventory/pilot_prep_005/sets/selection_items.json` | 100 | `405af9c879ff2989374f6285195467793ee38a4b61fe867919e6eae8893cad25` |

- 만든 방법: `../pilot_prep_005/sets/build_sets.py`(seed 20261008). 결정 46의 선택지 1(문항 family 단위 제외).
  - 선택용: old44·contrast·indepv2–4의 후보 154에서 유형 칸 × 정지 기대로 층을 나눠 100을 뽑았다(최대 잔여 배분).
  - 보조: at·final_v12의 51 전부.
- 조건: mock이 아는 장소, 정책·모호 문항 제외, gold가 현재 파이프라인을 통과. 학습 데이터(`reviewed_gold_v005_t2pc`)와 family 겹침을 다시 확인했고 빠진 문항은 0이다.
- 두 셋 사이: 문항 id 겹침 0, family 겹침 0. 거친 의미 family는 결정 46대로 나누지 않았다(겹침 16, 참고).
- 두 셋 모두 평가 전용이다. 학습, trace 선택, annotation 후보에 쓰지 않는다. 보조 시험 셋은 checkpoint 선택에도 쓰지 않는다.
