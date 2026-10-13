# P0 SFT 2차 — Thinking Loss Mechanism

2026-10-13. 결정 69. 사전 등록 `PLAN.md`(커밋 `b9ba5b7`), checkpoint 진단 계획 `CHECKPOINT_DIAGNOSTIC_PLAN.md`(커밋 `cda6cac`). p0_sft_001의 결과·REPORT는 고치지 않았다.

## 1. 결론

- **질문 1(json_only 때문에 thinking이 사라졌는가): 아니다. json_only 단독은 thinking을 없애지 않았다.**
  - 같은 70개 reasoning 데이터로 json_only(R70-json)와 full_response(R70-full)를 학습했다. 두 arm 모두 `<think>` 56/56을 유지했다.
  - p0_sft_001에서 thinking이 사라진 직접 원인은 **답만 있는 레코드(direct JSON)가 assistant 첫 token `{"`를 학습시킨 것**이다.
    - Gold-only는 154/154, Clean-Hybrid는 84/154 레코드가 이 위치에 `{"` 손실을 받았다.
    - json_only reasoning 레코드는 그 위치가 MASK라 반대 신호가 없었다.
  - R70-json에는 답만 있는 레코드가 없다. 첫 위치에 손실이 전혀 없어 base 행동(thinking)이 남았다.
- **사전 등록 gate 판정은 FAIL이다**(R70-full − R70-json emission 차이 0 < 50%p). 그래서 403문항 진단 평가는 하지 않았다.
  - FAIL은 "full_response도 thinking을 못 살림"이 아니라 "대조군이 억제하지 않음" 때문이다.
  - R70-full 자체는 thinking 100%, 중앙값 2,674자다.
- **질문 2(과적합 기여): 제한적이다.**
  - checkpoint 진단에서 두 arm 모두 0.5 epoch(checkpoint-77)부터 `<think>` 0/56이었다.
  - semantic correctness는 0.5 epoch에 이미 Base보다 낮았고, 이후 계속 떨어지지 않았다.
  - 하락의 대부분은 thinking 소실과 함께 초기에 생겼다. bucket·scope 역조회는 1 epoch에서 더 떨어진 부분이 있다.
- full_response가 mechanism을 "고쳤는가": full_response는 `<think>`를 직접 학습시킨다(첫 위치 LOSS `<think>` 70/70). 다만 이번에는 json_only도 thinking을 유지했으므로, 두 손실의 차이로 thinking 차이를 보이지는 못했다.

## 2. Git / 실행 무결성

- 시작: branch `geoflow/partial-grounding`, local HEAD = remote HEAD = `69fa8ea`, 작업 트리 깨끗함.
- 작업 단위마다 commit → push → `git fetch` 후 HEAD와 `origin/geoflow/partial-grounding` 일치를 확인했다.

| 단위 | commit | push |
|---|---|---|
| checkpoint 진단 계획·panel | `cda6cac` | 성공, 일치 |
| R70 데이터 + loss mask 검증 | `658feb6` | 성공, 일치 |
| checkpoint 진단 결과 | `7834ed6` | 성공, 일치 |
| R70 사전 등록(결정 69) | `b9ba5b7` | 성공, 일치 |
| R70-json 학습 | `9b516ad` | 성공, 일치 |
| R70-full 학습 | `8f544b4` | 성공, 일치 |
| mechanism probe·first token 감사 | `dad02e2` | 성공, 일치 |
| REPORT | (이 커밋) | |

- 모든 GPU 단계 앞에 `cell_guard precheck --path hf`가 통과했다(Ollama 모델 없음, GPU 프로세스 없음). Ollama 호출은 없었다.
- NaN, OOM, 재시작, 이탈 없음.

## 3. 기존 checkpoint trajectory(`CHECKPOINT_DIAGNOSTIC.md`, 56문항 panel, 사후 진단)

| run | epoch | train loss | 정답 | `<think>` | structural |
|---|---:|---:|---:|---:|---:|
| Base | – | – | 38 | 56/56 | 5 |
| Gold-only checkpoint-77 / checkpoint-154 / checkpoint-231 / checkpoint-308 | 0.5 / 1 / 1.5 / 2 | 0.198 / 0.035 / 0.014 / 0.009 | 29 / 25 / 29 / 30 | 0 / 0 / 0 / 0 | 11 / 11 / 8 / 10 |
| Clean-Hybrid checkpoint-77 / checkpoint-154 / checkpoint-231 / checkpoint-308 | 0.5 / 1 / 1.5 / 2 | 0.202 / 0.041 / 0.014 / 0.012 | 28 / 27 / 33 / 34 | 0 / 0 / 0 / 0 | 9 / 3 / 5 / 2 |

- bucket(10문항): Gold-only 7 → 2 → 2 → 4, Clean-Hybrid 4 → 4 → 3 → 5, Base 10.
- dimension_target(10): 두 arm 모두 처음부터 6–7(Base 7).
- od_ne_dt(10): 두 arm 모두 4–7(Base 6).
- checkpoint-308 재측정은 p0_sft_001 결과와 56/56 같은 category였다(greedy 재현).
- 이 결과로 어떤 checkpoint도 선택하지 않는다.

## 4. thinking collapse 시점

- **Case A.** 첫 저장 시점인 checkpoint-77(0.5 epoch, 77 step)에서 이미 두 arm 모두 `<think>` 0/56, 첫 token `{` 56/56이다.
- 학습 아주 초기에 생겼다. 그보다 이른 step은 저장되지 않아 정확한 시점은 0–77 step 사이로만 말할 수 있다.

## 5. loss mask 검증(`LOSS_MASK_AUDIT.md`)

실제 TRL collator label tensor, 70개 레코드 합이다.

| 영역 | R70-json | R70-full |
|---|---|---|
| system·user | MASK | MASK |
| `<think>` | MASK 70 | LOSS 70 |
| thinking 본문 | MASK 64,245 | LOSS 64,245 |
| `</think>` + `\n\n` | MASK 140 | LOSS 140 |
| JSON | LOSS 6,265 | LOSS 6,265 |
| EOS | LOSS 70 | LOSS 70 |

- 두 arm의 input_ids는 70/70 같다. 차이는 label뿐이다.
- 70/70 레코드가 기대와 일치했다. trainer는 고치지 않았다.

## 6. R70 데이터(`r70_dataset_manifest.json`)

- p0_sft_001 Clean-Hybrid의 승인 reasoning 레코드 70, 원래 순서다(v005 54, Gap A 5, Gap B 11).
- `sft_train.jsonl` sha256 `fa073a3f…`. 두 arm이 같은 파일을 쓴다.
- item ID, thinking 원문, 최종 P0 JSON이 승인 trace·canonical target과 일치함을 hash로 확인했다.
- 새 trace, STRUCTURALLY_REPAIRABLE, 답만 있는 레코드는 없다.

## 7. R70-json 학습

| 항목 | 값 |
|---|---|
| 손실 | json_only |
| step | 1 epoch = 70 |
| 시각 | 15:34:57–15:38:19 UTC(202초) |
| loss | 앞 35 step 평균 0.222, 뒤 35 step 0.050, 마지막 0.015 |
| 최종 adapter | checkpoint-70, sha256 `3f091ee3…` |
| 이상 | NaN·OOM 없음 |

## 8. R70-full 학습

| 항목 | 값 |
|---|---|
| 손실 | full_response |
| step | 70 |
| 시각 | 15:38:46–15:42:18 UTC(212초) |
| loss | 앞 35 step 평균 0.161, 뒤 35 step 0.127, 마지막 0.066 |
| 최종 adapter | checkpoint-70, sha256 `59361e96…` |
| 이상 | NaN·OOM 없음 |

- loss 대상 token이 thinking까지 포함해 약 11배 많아서 평균 loss가 덜 내려간다.

## 9. mechanism probe(`mechanism_probe/README.md`, 56문항)

| 지표 | Base | R70-json | R70-full |
|---|---:|---:|---:|
| `<think>` emission | 100% | **100%** | **100%** |
| 첫 token `{` | 0% | 0% | 0% |
| thinking 글자 중앙값 | 3,006 | 2,357 | 2,674 |
| 생성 token 중앙값 | 855 | 661 | 758 |
| 생성 상한 도달 | 2 | 10 | 4 |
| 정답 | 38 | 28 | 34 |
| malformed(첫 응답) | 2 | 5 | 2 |
| structural | 5 | 13 | 10 |

- **gate: FAIL**(차이 0). 사전 등록대로 403문항 평가로 넘어가지 않았다.

첫 assistant token 감사(`first_token_audit.json`, 결과 뒤 추가한 보조 검증):

| 학습 | assistant 첫 위치 손실 |
|---|---|
| p0_sft_001 Gold-only | `{"` 154/154 |
| p0_sft_001 Clean-Hybrid | `{"` 84, MASK 70 |
| R70-json | MASK 70(손실 없음) |
| R70-full | `<think>` 70/70 |

## 10. semantic trade-off(56문항, 기술 통계)

- 두 R70 arm 모두 Base보다 낮다(38 대 28·34). R70-full이 R70-json보다 6문항 많다(정답, malformed·생성 상한 도달·structural 모두 적음).
- bucket: Base 10, R70-json 8, R70-full 10. p0_sft_001(2–5/10)과 달리 R70-full에서는 떨어지지 않았다.
- dimension_target: Base 7, R70-json 5, R70-full 4.
- od_ne_dt: Base 6, 두 arm 4.
- p0_sft_001에서 얻은 dimension_target 개선은 R70에서 나타나지 않았다. R70 데이터는 teacher가 맞힌 70문항이고, Gap A·B 예제가 16개뿐이다.
- 403문항 평가를 하지 않았으므로 전체 semantic correctness 비교는 없다.

## 11. 과적합 분석

- p0_sft_001에서 train loss는 1 epoch에 0.035–0.041, 2 epoch에 0.009–0.012로 거의 외웠다.
- 그러나 semantic correctness는 0.5 epoch(29·28)에서 2 epoch(30·34)까지 떨어지지 않았다. 0.5 epoch에 이미 Base(38)보다 낮았다.
- 전체 하락의 주원인은 학습 기간이 아니라 초기 thinking 소실(형식 변화)로 본다.
- 예외: Gold-only의 bucket(7 → 2)·scope 역조회(2 → 0)는 0.5 → 1 epoch에서 더 나빠졌다. 학습 기간이 일부 유형 하락에 기여했을 가능성이 있다.
- 56문항 panel이라 2–4문항 차이는 노이즈 범위다.

## 12. 다음 단계(제안, 시작하지 않음)

- 사용자 결정 규칙 30절에 대응시키면 이렇다.
  - R70-full이 thinking을 유지·학습했으므로 Case C(구현 문제)가 아니다.
  - 과적합이 주원인이 아니므로 Case D도 아니다.
  - thinking은 유지되지만 R70 두 arm의 semantic은 Base보다 낮으므로, Case A와 Case B의 경계다.
- 핵심 설계 결론: **full-data SFT에서 답만 있는 레코드를 섞으면 thinking이 사라진다.** 다음 full-data 실험은 모든 학습 레코드가 reasoning을 갖거나, 답만 있는 레코드를 쓰지 않아야 한다.
- 그러려면 정답 trace가 없는 84문항의 reasoning coverage가 필요하다. 이때 처음으로 27B teacher 보충(또는 다른 승인 teacher)을 검토할 수 있다.
  - 반입은 별도 승인 사항이다.
  - 그 전에 R70의 semantic 하락(Base 38 대 34)이 trace 품질·분포 문제인지 확인하는 것이 좋다(Case B 쪽 점검).
- 선택적 결정:
  - gate가 정의상 FAIL이라 R70 두 arm의 403문항 진단 평가는 하지 않았다.
  - 대조군이 억제하지 않았다는 것이 확인된 지금, 403문항 평가를 사용자 결정으로 진행할 수 있다(약 4–5시간, 두 arm 모두 thinking).
- 손실 선택: 두 손실 모두 thinking을 유지했다. 56문항에서 full_response가 malformed·생성 상한 도달·structural이 적고 정답이 많았다. full-data에서 비교할 가치가 있다.
- 하지 않은 것: 27B 반입, 새 trace, STRUCTURALLY_REPAIRABLE, Gap C, 새 prompt, P0.4, DPO, pruning, quantization.
