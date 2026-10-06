# 진짜 pilot 데이터·기준선 준비 (pilot_prep_003)

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`. 결정 13–22와 16-1은 `../DECISIONS.md`에 있다.

- 하지 않은 것: pilot 학습(4번의 반복 측정만 예외), prompt 변경, SEMANTIC_CODE 변경.
- 업체 100은 E와 B-conv 측정에만 썼다. 학습 모델로는 재지 않았다.
- Ollama 등록은 base 변환본 하나뿐이고, 기존 모델은 그대로다.
- 실행 의미 코드 지문은 작업 시작, 모든 측정 meta, 작업 끝 모두 `791c4a68`이다.

## 0. 요약

| 항목 | 결과 |
|---|---|
| 결정 기록 | 결정 13–22를 `DECISIONS.md`에, Ollama 해제·`expandable_segments` 기본값·`ollama create` 범위를 `CLAUDE.md`(5·11·12번)에 반영했다. PROTOCOL은 확정(2026-10-06, 사용자). `a1df5b5` |
| batch004 import | thor `decide`로 queue A 33개 + 정지 후보 queue B 8개 결정 기록 → `reviewed_gold_v004_t2pc` 53문항(전부 학습). **thor 보호가 v003 valid 16문항을 막아 멈추고 물었고, 사용자가 이 16개만 명시 해제했다(결정 16-1).** `de82d79` |
| thinking trace | 새 34문항 수집(batch004 18: pass@8 11, v003 valid 16: pass@8 12). 정답 표본 없는 질문은 7 → **17** |
| teacher trace | qwen3.8:27b로 17문항 모두 정답 표본 4–8/8. 첫 pilot 데이터에는 넣지 않았다 |
| pilot 데이터 v004 | SFT 126(34문항), DPO 215(26문항). 길이 한도 SFT 11,392, DPO 11,392/7,424/4,096. 넘는 레코드 0. dry-run·tokenizer 검사 통과 |
| 반복 측정 | 같은 설정 반복의 loss 차이 최대 0.0021(SFT). expandable 측정의 차이(0.0031)도 같은 크기다 |
| Ollama 기준선 | E(791c4a68) 79, 첫 응답 100/100이 이전 E와 같다. B-conv 77(E 대비 b 10, c 12, p = 0.83, U +3) |
| base 등록 | `geoflow-qwen3-8b-b968826d-base:q4km-hfthink`. 렌더링 확인 10/10 통과. 다만 Ollama는 보낸 Go TEMPLATE 대신 GGUF 내장 HF Jinja template을 쓴다(5.3) |
| valid 기준선 | valid100(stage_v7 15 + heldout_v8 40 + heldout_v9 45) base grounding_ok **55**(gold를 넣었을 때의 상한 99). 65분 |

## 1. batch004 결정 import

- **결정 기록**(`import/record_decisions.py`, reviewer hwkim, 근거 "Claude 검토 의견을 사용자가 확인·승인").
  - **queue A**(`batch004/review`, 사용자가 검토한 33행), decisions는 `import/decisions_004.jsonl`.
    - 결정: accepted 29(gold 18 + 쌍 11), rejected 4(b004-24/31/40/41-hf).
    - 기록 위치: thor `decide`는 queue 폴더 안의 다른 이름 파일을 거부한다. 그래서 README에 적은 경로(queue 폴더 안) 대신 `pilot_prep_003/import/`에 두었다. 처음 시도에서 생긴 1행짜리 파일은 지웠다.
  - **queue B**(`import/stop_queue`): queue A의 정지 후보 8행.
    - 바꾼 것: `expected_outcome`을 `t2pc_stop_grounding`으로, 형식 미정 blocker를 뺐다(결정 14). README의 "형식이 정해지면 새 queue" 절차다.
    - 초안·질문·rejected는 그대로다. 결정: accepted 6, rejected 2.
- **결정 14를 받도록 학습 도구를 고쳤다**(`training/`, SEMANTIC_CODE 밖, `de82d79`의 앞 커밋).
  - 사람이 정지 target으로 승인한 gold(tag `t2pc_stop_grounding`)는 parse되고 계약 오류로 멈춰야 한다. 그 정지(오류 코드·검증 코드)를 metadata에 기록한다.
  - 이후 판정 `target_ok`는 기존 `chosen_ok`이거나 같은 정지로 멈출 때만 통과한다. 표시 없는 gold의 판정은 그대로다.
  - 테스트 3개를 추가했다. 전체 1,272 통과.
- **import:** queue A에서 gold 14·쌍 9, queue B에서 gold 4·쌍 2.
- **합치기**(`import/merge_v004.py`).
  - 구성: v003_t2pc 35(train 19 + valid 16) + batch004 18 = **SFT 53**.
  - DPO: v003 32 − 표시 4쌍(결정 13) + batch004 11 = **39**.
  - 전부 train이고 valid는 비어 있다(결정 16). 질문 중복 0, 모든 레코드 target 판정 통과.
- **보호 검사 결과**
  - 첫 실행에서 thor `Protection.current`가 v003 valid 16문항만 막았다. 규칙은 "이전 판의 validation family는 판이 바뀌어도 풀지 않는다"이다.
  - 지시대로 우회하지 않고 멈춰 물었고, 사용자가 이 16개만 명시 해제했다(결정 16-1).
  - 해제 조건: 이전 validation 출처를 뺀 보호(평가 셋 질문·id·template·family)로 다시 대조해 걸리지 않는 경우만 푼다(16/16 통과).
  - 그 밖의 37문항은 thor 보호를 그대로 통과했다.
- 기록: `training/records/corpora/reviewed_gold_v004_t2pc/`(manifest. 학습 레코드는 ignored 경로).

## 2. thinking trace(GPU 2)

- 설정은 `thinking_prep_001`과 같다: greedy 1 + 표본 8(temperature 0.6, top_p 0.95, top_k 20), seed 20261006 + 묶음 안 순번, max_new_tokens 8192.
- 판정은 조건 계층 전 원 출력의 grounding_check다. 원문은 `training/generated/thinking_traces/`(ignored)에 있다.

| 묶음 | 문항 | greedy 정답 | pass@8 | 정답 표본 없음 | 잘림 | 시간 |
|---|---:|---:|---:|---|---:|---|
| v003 train(기존) | 19 | 3 | 12 | 7 | 0 | 37분 |
| batch004 | 18 | 6 | 11 | b004-06, 15, 22, 24, 30, 31 | 0 | 52분 |
| v003 valid였던 16 | 16 | 6 | 12 | 0e4edbda, 0d51b49a, 2d254560, dd838f31 | 0 | 37분 |

- **정답 표본 없는 질문**: 17개(기존 7 + 새로 10). `data/summary.json`의 `no_correct_sample_questions`에 있다.
- 0d51b49a·2d254560은 pilot valid에서 11셀 모두 O였다(조건 계층 뒤 최종 grounding 기준). 원 출력 기준으로는 표본 9개가 모두 틀렸다. 판정 기준이 다르기 때문이다.
- mock·reference 모두 장소를 모르는 batch004 문항 중 학습 데이터에 남은 것은 b004-05, 23, 27, 28이다(metadata에 표시하지 않고 요약에 목록으로 둔다).

## 3. teacher trace(결정 21, Ollama qwen3.8:27b aaee06c3)

- 설정: think true, temperature 0.6, 표본 8, seed = 20261006 + 1000 × 순번 + 표본 번호. 그 밖은 Modelfile 기본값.
- 판정은 2번과 같다. 원문(thinking·content 분리)은 `training/generated/thinking_traces/teacher_qwen3.8_27b/`에 두고 `source: teacher`로 표시했다.

| 묶음 | 질문별 정답 표본(8개 중) | 시간 |
|---|---|---|
| 기존 7 | 77e9dacb 8, e645cbc1 6, 9b222bf8 7, a27c5965 8, 914c48da 7, 8b23b657 4, 51491e86 7 | 14분 |
| batch004 6 | b004-06 5, 15 8, 22 8, 24 8, 30 8, 31 8 | 8분 |
| v003 valid 4 | 0e4edbda 8, 0d51b49a 8, 2d254560 8, dd838f31 5 | 7분 |

- 모든 표본이 `</think>` 뒤 JSON까지 끝났고(done_reason stop), parse 실패는 0이다.
- 첫 pilot 데이터에는 넣지 않았다.

## 4. pilot 데이터와 반복 측정

**데이터**(`data/build_v004_thinking.py`, `data/summary.json`, 출력 `training/generated/thinking_v004_t2pc`)

| 단계 | SFT | DPO |
|---|---:|---:|
| 후보(세 묶음) | 143 | 550 |
| 결정 4: tokenization 불일치(19 trace: v003 train 10 = 기존 기록과 같음, batch004 7, v003 valid 2) | −9 | −44 |
| 결정 6: 운영 경로 재판정(506쌍, provider mock 478·reference 28) | — | 남김 252 / 조건 계층이 고침 −198 / 기타 −56 |
| 결정 18: 길이 한도 초과 | 0 | 0 |
| 계약 필터(`target_ok`) | −8 | −37 |
| **최종** | **126(34문항)** | **215(26문항)** |

- DPO 재판정에서 남긴 252쌍의 이유:
  - 계약 재질의 103.
  - 최종 grounding이 gold와 다름 78.
  - 최종 grounding 없음 71.
- **출처.** SFT: v003 train 40, batch004 24, v003 valid 62. DPO: 48, 81, 86.
- **범주.** SFT의 출처 태그: review_batch_003 77, targeted_gold(batch004) 24, gold_re_review 20, review_batch_002 5.
  - 결정 14 정지 target의 SFT 레코드는 7개다.
  - DPO: constraint 166, semantic 49.
- **남은 표시:** `compile_stop:UNVERIFIED_TIMS_CONTRACT`가 SFT 73, DPO 92(결정 7로 포함).
- **길이**(`data/token_lengths_*.json`):

  | | prompt 최대 | 응답 p50 / p95 / 최대 | total p50 / p95 / 최대 |
  |---|---:|---|---|
  | SFT | 7,327 | 948 / 1,897 / 4,050 | 8,252 / 9,180 / 11,326 |
  | DPO | 7,327 | chosen 1,065 / 2,996 / 4,050, rejected 1,026 / 2,164 / 2,711 | 8,495 / 10,282 / 11,326 |

- **config**(`training/configs/qwen3_8b_t2pc_thinking_v004_{sft,dpo}.yaml`).
  - 길이 한도: SFT 11,392, DPO 11,392 / 7,424 / 4,096. pilot_prep_002 보수 추정 한도(SFT 12,887, DPO 문장당 13,833) 아래다.
  - 확인: dry-run과 tokenizer 검사(결정 14 정지 target 포함) 통과.
  - **`max_steps`·`save_steps`는 pilot 001의 자리값이다(미확정, 6절).**
- **메모리**(추정, 측정하지 않음). pilot_prep_002의 선형식(A)으로 계산하면, 가장 긴 DPO 쌍(문장당 11,326)에서 nvidia-smi 약 42,300MiB다(전체 49,140, expandable 켬).

**반복 측정**(결정 17, `repeat/`, GPU 2, 기존 할당 설정, pilot SFT 12 step)

| step | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 본 학습 | 0.1191 | 0.1478 | 0.1000 | 0.1512 | 0.1123 | 0.0900 | 0.1382 | 0.1216 | 0.1177 | 0.1292 | 0.1026 | 0.1426 |
| 반복(같은 설정) | 0.1191 | 0.1478 | 0.0991 | 0.1500 | 0.1103 | 0.0919 | 0.1376 | 0.1196 | 0.1167 | 0.1271 | 0.1020 | 0.1414 |
| expandable(pilot_prep_002) | 0.1191 | 0.1478 | 0.0995 | 0.1507 | 0.1137 | 0.0911 | 0.1365 | 0.1185 | 0.1169 | 0.1276 | 0.1024 | 0.1423 |

- **같은 설정을 다시 돌려도** step 3부터 달라진다(최대 0.0021). 최종 adapter sha256도 다르다(a0d378d8 대 5ca8e111).
- expandable 측정의 SFT 차이(최대 0.0031)는 이 비결정성 범위와 같은 크기다.
- **DPO의 차이(최대 0.10)는 이번 반복이 다루지 않았다**(SFT만 반복). 그래서 비결정성 범위인지 판정할 수 없다. batch 1 DPO는 margin이 작아 작은 수치 차이에도 loss가 크게 움직인다는 점만 적는다.
- 반복의 메모리는 nvidia-smi peak 47,882MiB, reserved 46.24GiB, step 6.13초로 본 학습과 같다. checkpoint는 지웠다.

## 5. Ollama 기준선과 base 등록(GPU 3)

### 5.1 실행

- 순서: E → base 등록 → 렌더링 확인 → B-conv. 사이에 다른 Ollama 측정은 없었다.
- 격리: 문항마다 모델 내림(PROTOCOL 4절). 시작 전에 앞선 teacher 실행의 27b가 스스로 내려갈 때까지 기다렸다.
- 측정 중 GPU 2에서는 HF trace 생성(측정이 아님)이 돌았다. E와 B-conv 모두 같은 조건이다.
- **Ollama 버전이 0.35.1로 바뀌어 있었다.** 이전 E는 0.34.4다.

### 5.2 E와 B-conv(업체 100, `ollama/comparison.json`)

| 셀 | 모델 | grounding_ok | 정상 | U | 조용한 오답 | 첫 응답 raw/정규화/보존 일치 | 지연 중앙값 | 재질의 |
|---|---|---:|---:|---|---:|---|---:|---:|
| 이전 E | qwen3:8b 500a1f06, 0.34.4, 코드 97efa866 | 79 | 84 | 3(U1 2, U2 3, U3 2) | 1 | 59 / 64 / 73 | 11.9초 | 17 |
| **E(기준)** | 같은 모델, 0.35.1, 코드 791c4a68 | **79** | 84 | 3(같음) | 1 | 59 / 64 / 73 | 10.9초 | 17 |
| **B-conv** | 변환본 ab29de19(Q4_K_M) | **77** | 79 | 6(U1 2, U2 6, U3 2) | 0 | 56 / 65 / 68 | 10.4초 | 20 |
| HF-E(참고) | HF BF16 | 84 | 91 | 2 | 0 | 64 / 74 / 79 | 22.0초 | 18 |

- **E 재현.** 첫 응답 본문이 이전 E와 100/100 같고, 문항별 판정도 모두 같다(코드·Ollama 버전이 달라도). 운영 비교의 기준은 이 E(79)다.
- **E → B-conv.**
  - grounding_ok 전이: O→O 67, O→X 12, X→O 10, X→X 11.
  - b 10, c 12, McNemar p = 0.83. 지연 비율 0.95.
  - U 순증 +3. 새 U 문항: 031, 040, 074, 084, 093. 조용한 오답 순증 −1.
  - B-conv의 thinking 최대 길이는 29,136자다(E 최대 8,987자). num_predict를 지정하지 않는 조건이다.
- **해석의 범위.** 둘 다 Q4_K_M이므로 이 차이는 양자화 형식의 차이가 아니다. 다음 경로 차이의 효과다.
  - 렌더링: 라이브러리 Go template(` /think`, system 앞 줄바꿈) 대 HF 형식.
  - 변환: Ollama 라이브러리 GGUF 대 같은 base revision을 llama.cpp b11434로 변환한 GGUF.
  - 한 번씩만 쟀으므로 b와 c의 크기는 우연과 구분되지 않는다(p = 0.83).
- **결정 15의 family 분리.** 업체 100 중 v004 학습 family(thor `family_key`)에 속한 문항은 10개다.
  - 이전 E·E: 5/10, B-conv 5/10, HF-E 7/10.
  - 나머지 90문항: 74, 74, 72, 77.

### 5.3 base 등록과 렌더링 확인

- **등록**(`ollama/register_base.py`, `registration.json`).
  - 컨테이너가 호스트 GGUF 경로를 볼 수 없다. 그래서 `ollama create`와 같은 일을 API로 했다: blob 업로드(sha256 f060d7cb… 대조) + `/api/create`.
  - 새 이름: `geoflow-qwen3-8b-b968826d-base:q4km-hfthink`(digest ab29de19). 기존 5개 모델은 그대로다.
- **관찰: Ollama 0.35.1의 `/api/show`는 보낸 Go TEMPLATE이 아니라 GGUF에 내장된 Qwen3 HF Jinja chat template을 보고한다.**
  - 보낸 TEMPLATE이 실제로 쓰이지 않았을 수 있다.
  - 다만 아래 렌더링 확인은 실제 token 수로 했다. 그 결과는 HF와 같다. HF Jinja template 그대로라면 `enable_thinking` 미지정 = thinking 켬이다.
  - 학습 모델 등록 때도 같은 동작을 가정할 수 없다. 등록마다 같은 확인을 한다.
- **렌더링 확인**(`render_check.json`, v004 학습 질문 10개: v003 train 4, v003 valid 3, batch004 3, 요청마다 keep_alive 0).
  - prompt_eval_count = HF `apply_chat_template(enable_thinking=True)` token 수: 10/10.
  - think 미지정 시 thinking 생성: 10/10.
  - thinking과 본문 분리(본문에 `<think>` 없음): 10/10.
  - 그래서 B-conv를 쟀다.

## 6. valid 기준선(결정 16, GPU 2)

- **셋**(`valid100/valid100_items.json`, 질문 문장 없이 id·원본 sha256만).
  - 구성: stage_v7 15 + heldout_v8 40 + heldout_v9 45 = 100. 앞 셋과 중복 1, gold를 만들 수 없는 3은 뺐다. 정책·모호 제외는 0이다(감사 대상이 아니었다).
  - provider: mock. 장소는 모두 mock으로 풀리거나(82) 조회가 없다(18).
  - 기대 결과: 답 95, 확인 요청 3, 지원 불가 2.
- **gold 상한.** gold grounding을 넣으면 99/100이다. heldout_v8/t10은 gold도 조건 계층에서 DATE_AMBIGUOUS로 멈춰 grounding이 없다. 라벨은 바꾸지 않았다.
- **base 기준값**(HF-E 조건, `valid100/runs/base.json`).
  - **grounding_ok 55/100**: stage_v7 10/15, heldout_v8 21/40, heldout_v9 24/45.
  - 첫 응답 raw 일치 40. 생성 상한 도달 4회.
  - 소요: 65분(39초/문항). peak allocated 17.4GiB.
  - 업체 100 방식 호출 채점(참고): match 64.
- **grounding_ok와 호출 채점이 다른 문항.** 호출은 맞지만 grounding_ok가 X인 문항이 10개다.
  - 9개(t08, t18, t20, h04, h17, h21, h22, h25, h28): 질문에 없는 `aggregation: sum`을 지어냈다. 실행 호출은 결과적으로 같다. grounding_ok가 잡는 것이 맞는 오류다.
  - h03: "출발·도착 둘 다 수성구"를 `od_role: both` 하나로 적었다. gold는 장소 두 개(pickup, dropoff)다. 같은 뜻인지 사람 판단이 필요하다(6.1).
  - 반대 방향(호출은 다르지만 grounding_ok가 O)은 1개(s03b, 기대한 정지)다.
- **v004와 다시 대조.**
  - 정규화 질문 겹침 0.
  - 거친 의미 family 겹침 6: heldout_v8 t11, t16, t22, t25 / heldout_v9 h14, h27. base는 이 중 1개만 맞았다.
  - thor template 겹침 4.
  - 겹침이 남는 이유: vendor 형식 셋은 thor 보호에서 질문·id만 보호되고 template·family 지문이 없다. 결정 15로 보호 범위는 넓히지 않았다.

### 6.1 해석상 주의

- 선택 지표는 grounding_ok다. 지어낸 집계(9개)를 오류로 잡는 것은 프로젝트 기준과 맞다.
- h03처럼 표현이 다르고 뜻이 같을 수 있는 문항이 있으면 checkpoint 사이 차이에 섞인다. 학습 전에 h03 라벨의 뜻을 정하는 것이 좋다(라벨은 바꾸지 않았다).

## 7. 진짜 pilot의 예상 소요 시간(측정값에서 계산, 추정)

| 단계 | 근거 | 예상 |
|---|---|---|
| SFT 학습 | step 6.1–6.2초(≤9.1k token). 가장 긴 11.3k에서는 길이 비례로 약 7.7초 | 1 epoch(126 step) 약 13–16분. pilot 001 자리값(12 step)이면 약 1.5분 |
| DPO reference 미리 계산 | 쌍당 4.6–4.7초(≤9.1k) | 215쌍 약 17–21분 |
| DPO 학습 | step 17.6초(≤9.1k), 11.3k에서 약 22초 | 1 epoch(215 step) 약 63–79분. 자리값(8 step)이면 약 2.5분 |
| checkpoint 평가(valid100) | base 65분 | 단계마다 4개 이하 → 최대 8개 × 약 65분 = **약 8.7시간** |
| 업체 100 HF 셀 | HF-E 52분 | SFT·최종 2셀 약 1.7시간 |
| 업체 100 Ollama 셀 | merge·변환(GGUF bf16 → Q4_K_M) 셀당 약 15분 추정 + B-conv 29분 | 2셀 약 1.5–2시간(등록·렌더링 확인 포함) |

합계는 학습 설정에 따라 약 12–14시간이고, 대부분이 checkpoint 평가다.

## 8. 학습 전에 남은 일

**사용자**

1. 추론 표본 10개 검토.
   - 결정 3(full_response, 추론까지 학습) 유지 여부를 판단하는 자료다.
   - 문서: `training/generated/thinking_traces/v003_t2pc_train/human_review_10.md`(ignored, sha256 7dd14274…).
2. 학습 checkpoint 저장 시점과 step 수 확정.
   - 단계마다 4개 이하다(결정 16). 예: epoch 기준 1 epoch에서 25·50·75·100%.
   - config의 `max_steps`·`save_steps`는 지금 자리값이다.
3. valid100 h03 라벨의 뜻 확인(6.1). 선택 지표에 들어가는 문항이다.
4. B-conv의 U 증가(+3: 031, 040, 074, 084, 093)와 template 관찰(5.3)을 운영 비교 해석에 어떻게 반영할지.
   - PROTOCOL은 운영 비교 기준을 E로 정했다. B-conv는 변환 경로 효과를 나누는 참고값이다.

**Claude Code**(결정 뒤)

1. config에 확정된 step·저장 시점을 넣고 PLAN.md를 고정한 뒤 학습한다(expandable 켬, GPU 2).
2. checkpoint마다 valid100을 재고(`eval_valid100.py --adapter`), 선택 규칙에 따라 SFT·최종을 고정·커밋한다.
3. PROTOCOL대로 업체 100을 한 번 잰다.
   - HF: 최종(주 비교) 대 HF-E, SFT(참고).
   - Ollama: SFT·최종을 merge → GGUF Q4_K_M → 새 이름 등록 → 렌더링 확인 → 측정. 기준은 E(79).
4. teacher trace(17문항)를 다음 데이터 판에 쓸지는 첫 pilot 뒤에 정한다(결정 21).

## 9. 산출물

| 경로 | 내용 |
|---|---|
| `import/` | 결정 기록 스크립트, queue A·B decisions, queue B, v004 합치기 |
| `../../training/records/corpora/reviewed_gold_v004_t2pc/` | v004 manifest(보호 대조·해제 기록) |
| `traces/batch004`, `traces/v003_valid` | trace 요약·후보 목록·로그 |
| `teacher/` | teacher 수집 스크립트, 대상, 요약(원문 없음) |
| `data/` | v004 thinking 데이터 생성, 요약, 재판정, 길이 |
| `repeat/` | 반복 측정 스크립트·로그·profile·trainer_state·sha256 |
| `ollama/` | E·B-conv 결과·로그, Modelfile, 등록·렌더링 확인, 비교 |
| `valid100/` | valid 고정, 평가 스크립트, base 결과 |
| `gpu_check.txt`, `gpu_runs.log` | GPU 확인, 실행 순서 |

저장소 밖·ignored(커밋하지 않음):

- trace·teacher·평가 원문.
- `training/generated/{reviewed_gold_v004_t2pc, thinking_v004_t2pc, corpora/batch004_import_*}`.
- GGUF(`/home/hwkim/sftdpo_work/gguf`).
- 반복 측정 checkpoint(지움).
