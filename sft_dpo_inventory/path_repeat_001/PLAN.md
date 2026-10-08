# 새 장비 경로 반복 측정 계획 (path_repeat_001) — **확정(2026-10-08, 사용자)**

작성: 2026-10-08. 확정: 2026-10-08, 사용자(결정 56, `../DECISIONS.md`).
**확정한 뒤에는 고치지 않는다.** 이탈은 `PLAN_DEVIATIONS.md`에 따로 적는다.

## 0. 목적과 쓰임

- 질문 1: 장비가 바뀌어도 greedy 결과(HF Qwen3-8B (BF16) 84, Ollama qwen3:8b (Q4_K_M) 79, 판정이 갈린 17문항)가 재현되는가.
- 질문 2: 17문항의 차이가 경로의 체계적 차이인가, 경계 문항이 경로마다 다르게 뒤집힌 것인가. sampling 5회로 잰 문항별 정답 수(k)로 가린다.
- 이 측정은 경로 진단이다. 판정(PROTOCOL 7절, PROTOCOL_v2 2절), 기준값(84, 79) 교체, 학습, checkpoint 선택, trace 선택,
  annotation 후보에 쓰지 않는다(`CLAUDE.md` 8번, 결정 36). 근거 결정: 결정 56.

## 1. 장비와 실행 환경(2026-10-08 확인)

| 항목 | 값 |
|---|---|
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition 1장, UUID `GPU-d4308fbb-d17f-3609-676a-935c6072c831`, 97,887 MiB, compute 12.0 |
| 드라이버 / CUDA(드라이버) | 595.91.07 / 13.2 |
| 시작 전 GPU | 사용 4 MiB, compute 프로세스 없음 |
| OS / Python | Ubuntu 24.04.5 / 3.12.3 (venv `/data/hwkim/path_repeat_001/venv/py`) |
| HF | torch 2.11.0+cu128(CUDA 12.8, cuDNN 9.19.0, arch에 sm_120 포함), transformers 4.56.2, accelerate 1.15.0, peft 0.17.1 |
| HF 모델 | `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`, `HF_HOME=/data/hwkim/path_repeat_001/hf-cache`, 실행 시 `HF_HUB_OFFLINE=1` |
| Ollama | **0.40.1**, 사용자가 띄운 Docker 컨테이너 `ollama`(이미지 `ollama/ollama:latest`, image id `e4cbe962…`, repo digest `69f27594…`, runtime nvidia, 포트 11434, 모델 저장소 `/data/hwkim/ollama`). 사용자가 이 버전을 쓰도록 정했다(결정 56). 기존 기록의 0.35.1과 다르다 |
| Ollama 서버 설정 | 환경 변수 `OLLAMA_HOST=0.0.0.0:11434`만 지정, 그 밖 기본값(keep_alive 5m, num_parallel 1, flash attention 끔, KV cache 기본). 서버 로그: CUDA `cuda_v13`, compute 12.0, `default_num_ctx=262144`(VRAM 기반). 컨테이너 안 `nvidia-smi -L`에 같은 GPU UUID가 보인다 |
| Ollama 모델 | `qwen3:8b` 하나, digest `500a1f067a9f…` (기존과 같음). Modelfile 파라미터 문자열이 E.json `model_runtime`과 바이트 단위로 같음, capabilities 같음, template sha256 `ae370d88…`(`pilot_prep_001/template/template_compare.json`과 같음), 모델 context_length 40960 |
| 컨테이너 규칙 | 컨테이너를 재시작·재설정하지 않는다. 다른 Ollama 서버를 띄우지 않는다. 받는 모델은 `qwen3:8b` 하나뿐이다 |
| 저장소 | `/home/hwkim/assistant_univ`, 브랜치 `geoflow/sft-dpo-t2pc`, 시작 commit `b5f1423`. 실행 의미 코드 지문 `791c4a68…` (같음) |
| 테스트 | 전체 1,274개 통과(skip 8, expected failure 1). 업체 원본 xlsx(gitignore, sha256 `2f84f6b1…`, 사용자 제공)를 `evaluation/vendor100/`에 둔 상태 |

- `/`는 여유가 약 9 GB라 venv, HF cache, pip cache는 `/data/hwkim/path_repeat_001/` 아래에 둔다(Ollama 모델은 컨테이너 저장소 `/data/hwkim/ollama`). 커밋하지 않는다.
- 기존 장비와 다른 점(분리하지 않음): GPU 종류(Ada → Blackwell), 드라이버, **Ollama 버전(0.35.1 → 0.40.1)**, llama.cpp CUDA 라이브러리 판(기존은 기록 없음).
  - 따라서 Ollama 경로의 greedy 비교(6.1)는 장비 변경과 버전 변경이 섞인 비교다. HF 경로는 소프트웨어 판이 같아 장비 변경만 남는다.

## 2. 셀

| 순서 | 셀 | 모델 | 생성 설정 | 횟수 |
|---|---|---|---|---|
| 1 | Ollama greedy 기준 | qwen3:8b 500a1f06 | temperature 0, think 미지정, num_predict 미지정(기존 E와 같음) | 1 |
| 2 | HF greedy 기준 | Qwen/Qwen3-8B@b968826d, BF16·SDPA | greedy, `enable_thinking=True`, max_new_tokens 8192(기존 HF-E와 같음) | 1 |
| 3 | Ollama sampling | 같음 | temperature 0.6, top_p 0.95, top_k 20, seed(3절), think 미지정, num_predict 미지정 | 5 |
| 4 | HF sampling | 같음 | do_sample, temperature 0.6, top_p 0.95, top_k 20, seed(3절), max_new_tokens 8192 | 5 |

공통 조건:
- prompt `87048d0c…`, 기준일 2026-09-25, `--condition-check`, mock·legacy, gold `evaluation/vendor100/gold.yaml`(sha256 `f99bc5fd…`), 문항 순서 file.
- Ollama: 문항마다 모델 내림(`OllamaStateReset`, 기존과 같음). host `http://localhost:11434`.
- HF: 회차마다 새 프로세스. 프로세스 안에서는 모델을 올려 둔 채 대화 상태 없이 문항을 돈다(기존과 같음).
- 명시하지 않은 sampling 값은 양쪽 기본값이다. HF는 min_p 없음·repetition_penalty 1.0, Ollama는 Modelfile `repeat_penalty 1`과 서버 기본 min_p. 이 차이는 분리하지 않는다(8절 한계).

## 3. seed 규칙(실행 전에 고정)

- 회차 seed: `S_r = 20261009 + r`, r = 1…5 (20261010–20261014).
- 호출 seed: `seed(r, id, c) = int.from_bytes(sha256(f"{S_r}:{id}:{c}".encode()).digest()[:4], "big") & 0x7FFFFFFF`
  - `id`는 문항 id(예: `"008"`), `c`는 그 문항 안에서 모델을 부른 순번(0 = 첫 plan, 1부터 repair 등 이후 호출). 실패한 호출도 순번을 쓴다.
  - 두 경로에 같은 규칙을 쓴다. Ollama는 `options.seed`로, HF는 생성 직전 `torch.manual_seed`·`torch.cuda.manual_seed_all`로 넣는다.
- 같은 seed라도 HF와 llama.cpp의 난수열은 다르다. **회차끼리 짝짓지 않는다.** 비교 단위는 문항별 5회 중 정답 수 k다.

## 4. 셀 전환 절차(매 셀 시작 직전과 끝난 직후, `runs.log`에 기록)

- **HF 셀 시작 전**
  1. Ollama `/api/ps`가 비어 있다.
     - `OllamaStateReset`은 문항 *시작 전*에 모델을 내리므로, Ollama 셀의 마지막 문항 모델은 keep_alive(5분) 동안 남는다.
       서버 재시작·강제 종료·unload 호출 없이, keep_alive가 끝나 자연히 빌 때까지 기다린다.
  2. `nvidia-smi`에 compute 프로세스가 없다. 사용 중 메모리를 적는다(기준선: 4 MiB).
  3. HF 셀이 끝날 때까지 Ollama 호출을 하지 않는다.
- **Ollama 셀 시작 전**
  1. HF 프로세스가 끝났다(launch 때 잡은 PID로 `kill -0` 확인).
  2. GPU 메모리가 HF 이전 수준(기준선 ±200 MiB 안)으로 돌아왔다. 값을 적는다.
  3. `/api/ps`가 비어 있고, 서버 버전 0.40.1, digest `500a1f06…`, `docker exec ollama nvidia-smi -L`에 UUID `GPU-d4308fbb…`.
- **Ollama 셀 중**(guard, 결정 55와 같은 방식)
  - 첫 문항 동안 `/api/ps`에서 `size_vram == size`(100% GPU)를 확인한다. 아니면 즉시 멈춘다.
  - 같은 때 `/api/ps`의 `context_length`가 기존 기록(E.json `model_runtime`)과 같은 **40960**인지 확인한다. 다르면 즉시 멈추고 보고한다(0.40.1의 VRAM 기반 기본 context가 기존과 다를 수 있다).
  - 문항별 생성 속도 = 그 문항의 성공 호출 `Σ eval_count / Σ (duration_ms − load_duration_ms)`.
  - 셀 1(greedy 기준)은 기준이 아직 없으므로 기존 기준 **30 tok/s**(`pilot_002/PLAN_DEVIATIONS.md`, Ada 기록)를 잠정 하한으로 쓴다.
  - 셀 1이 끝나면 그 분포에서 **기준 = 문항별 속도 중앙값의 0.5배**로 정해 `PLAN_DEVIATIONS.md`에 적는다. 셀 3은 이 기준을 쓴다.
  - 기준 미만인 문항이 나오면 셀을 즉시 멈추고 출력을 `ABORTED_*`로 남긴다. 서버는 건드리지 않고 보고한다.
- 위 조건 중 하나라도 맞지 않으면 셀을 시작하지 않고 원인을 적은 뒤 보고한다.
- 두 측정은 절대 동시에 돌리지 않는다.

## 5. 실행 규칙

- 2단계 harness 준비가 끝나고 커밋·push된 뒤에 2절 순서대로 한 셀씩 잰다.
- 긴 작업은 `CLAUDE.md` 대기 규칙대로 백그라운드에서 돌리고 완료 알림을 기다린다(별도 polling 없음, `pgrep -f` 자기 매치 금지).
- greedy 기준 두 셀 뒤 장비 변경 비교(6.1)를 사용자에게 짧게 보고하고 이어 간다. 다음이면 멈추고 보고한다.
  - 한 경로라도 첫 응답 바이트 일치 < 50/100.
  - grounding_ok가 기존 값과 10 이상 차이.
- 기반 장애(crash, OOM, GPU 오류, 전원)가 아니면 회차를 다시 돌리지 않는다. 결과가 이상해도 다시 돌리지 않는다.
  - 기반 장애면 원인을 적고, 완료 문항은 유지하고 남은 문항부터 같은 명세로 이어 잰다. 이탈로 적는다.
- 셀마다 시작·끝 시각과 소요 시간을 적는다.
- smoke(분석에 쓰지 않음): 001–003의 3문항으로 두 경로 각각 sampling을 r=1 seed로 두 번 돌려 같은 출력인지 적는다.
  Ollama가 같지 않아도 사실만 적는다. 출력은 `smoke/`. smoke 사이에도 4절을 지킨다.

## 6. 분석 규칙(실행 전에 고정)

채점은 `baseline_conditions_001/compare_cells.py`의 `load_cell()`(기존과 같음). 산출물 `analysis.py`, `analysis.json`, `REPORT.md`.

### 6.1 장비 변경 비교(greedy, 경로별)

| 경로 | 기존 기록 | 비교 |
|---|---|---|
| HF | `thinking_prep_001/hf_e/HF-E_run1.json`, 원문 `training/generated/thinking_prep_001/HF-E_run1_raw.jsonl` | 첫 호출 원문(`raw_text`, thinking 포함) 바이트 일치 수, 모든 호출 일치 수 |
| Ollama | `pilot_prep_003/ollama/E.json` | 첫 plan 호출 `content` 바이트 일치 수와 `thinking_chars` 일치 수(결정 37 `device_check/compare.py`와 같은 기준), 모든 호출 일치 수 |

- 두 경로 모두 grounding_ok, 문항별 grounding_ok 일치 수(와 b·c)를 적는다.
- 새 장비 HF greedy 대 Ollama greedy의 갈린 문항 목록을 구하고, 기존 17문항과의 교집합·차집합을 적는다.

### 6.2 지표

- 주 지표: grounding_ok.
- 보조 지표: 정상 답변, U(U1–U4), 조용한 오답(U 아님), 실행 실패(v4), 생성 상한 도달 호출 수(`done_reason == "length"`),
  첫 plan 호출 thinking 길이(문자 수) 중앙값, 문항 지연 중앙값. 지연은 장비가 달라 기존 기록과 비교하지 않는다.

### 6.3 문항 분류

문항마다 k_HF, k_Ollama(0–5, sampling 5회 중 grounding_ok 수):

| 분류 | 조건(위에서부터 먼저 맞는 것) |
|---|---|
| 둘 다 안정 정답 | k_HF = 5 그리고 k_Ollama = 5 |
| 둘 다 안정 오답 | k_HF = 0 그리고 k_Ollama = 0 |
| 체계적 차이 | \|k_HF − k_Ollama\| ≥ 4 |
| 경계 | 그 밖 |

- 기존 17문항과 새 장비 greedy에서 갈린 문항 각각이 어느 분류에 드는지 표로 적는다.

### 6.4 전체 비교

- 회차별 grounding_ok의 평균과 범위(경로별).
- 문항별 정답률 차이 d_i = (k_HF,i − k_Ollama,i)/5. 평균과 95% 신뢰구간: 문항 단위 bootstrap 10,000회(복원추출, numpy `default_rng(20261009)`, percentile 2.5·97.5).
- paired permutation 검정: 문항마다 d_i의 부호를 1/2 확률로 바꾸는 10,000회(`default_rng(20261009)`의 별도 stream), 양측 p = (#{|평균*| ≥ |평균_obs|} + 1)/(10,000 + 1).
- 기존 greedy(84, 79)와 새 장비 greedy가 각 경로의 회차별 sampling 값(5개)의 최소·최대 안에 있는지, 몇 번째인지 적는다(기술 통계만).
- 결론 문구: 신뢰구간이 0을 포함하면 "경로 간 차이를 확인하지 못함"으로 쓴다.

### 6.5 오류 유형(문항×회차 빈도, 경로별)

grounding_ok가 거짓인 문항×회차마다 최종 grounding의 `grounding_diffs`(형식 `[키, 정답, 모델]`)와 `error_code`로 판별한다. 하나에 여러 유형이 붙을 수 있다.

| 유형 | 판별 규칙 |
|---|---|
| 없는 `sum` 집계 추가 | `factor:aggregation_spec` 차이에서 정답의 집계가 없음(null)이고 모델 집계가 `sum` |
| "실차 통행량"을 실차 구간 건수로 해석 | `measure` 차이가 정답 `[AMOUNT, passage_count]` → 모델 `[AMOUNT, trip_count]` |
| 장소를 scope 개념으로 표기 | `error_code == UNGROUNDED_SCOPE`, 또는 `places` 차이에서 정답 장소 이름이 모델 장소에 없고 같은 문항의 `scopes` 차이에서 모델에만 있는 scope가 있음 |
| 출발/도착 역할을 `dimension_target`으로 옮김 | `factor:dimension_target` 차이에서 정답 null → 모델 `pickup`·`dropoff`·`both` |
| 차원 오류(읍면동↔시군구) | `factor:dimension` 차이에서 정답과 모델이 모두 값이 있고 서로 다름 |
| 그 밖 | 위 다섯에 하나도 맞지 않음. 하위 표: grounding 없음(`error_code`별), 그 밖 차이 키별 |

- 문항별 표의 "대표 오류"는 그 경로에서 가장 자주 나온 유형(동률이면 표의 위 순서).

## 7. 산출물(`sft_dpo_inventory/path_repeat_001/`)

- `PLAN.md`(이 문서), `PLAN_DEVIATIONS.md`, `runs.log`(셀 전환 확인·시각), `env/`(nvidia-smi, `/api/show`, 해시, pip freeze).
- `runs/`: `ollama_greedy.{json,jsonl,spec.json,log}`, `hf_greedy.{json,log}`, `ollama_sample_r{1..5}.*`, `hf_sample_r{1..5}.*`, `smoke/`.
- HF 원문: `training/generated/path_repeat_001/*_raw.jsonl`(결정 33에 따라 커밋).
- `analysis.py`, `analysis.json`, `REPORT.md`. REPORT에서는 셀 이름 대신 모델명("HF Qwen3-8B (BF16)", "Ollama qwen3:8b (Q4_K_M)")을 쓴다.
- 모델 파일, cache, venv는 커밋하지 않는다.

## 8. 한계(REPORT에 적는다)

- sampling 결과는 greedy 운영 조건과 다르다.
- 양자화, chat template(Ollama 입력이 2 token 더 김), 추론 엔진, 가중치 출처, sampler 구현(min_p 기본값 포함)은 분리되지 않는다.
- Ollama 경로의 장비 변경 비교에는 버전 변경(0.35.1 → 0.40.1)이 섞여 있다. 둘을 나누지 않는다.
- 새 장비 결과를 기존 장비 기록과 직접 섞어 해석하지 않는다.
- 문항 100개 × 5회라 k의 해상도가 낮다(0–5).
