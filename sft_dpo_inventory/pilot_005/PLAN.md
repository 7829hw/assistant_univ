# pilot_005 계획

고정: 2026-10-15, 학습 시작 전 고정. 학습을 시작한 뒤에는 고치지 않는다(이탈은 REPORT에 따로 적는다).

따르는 문서:
- `CLAUDE.md`(SFT/DPO 규칙, 15번 실행 중 스크립트 수정 금지, 결정 100·105의 GPU 3장)
- `../DECISIONS.md`(결정 1–105)
- `../vendor100_protocol/PROTOCOL_v5.md`(확정 2026-10-15, sha256 `2de1264161a6171a42083a4d6f748ed346ecf77d5259d0c4a38dd8887c215e0f`)

하지 않는 것:
- prompt 변경, `SEMANTIC_CODE` 변경(실행 의미 코드 지문 `791c4a68`).
- 결정 101의 세 변형 말고 학습 설정 변경, 결과를 맞추기 위한 재학습·재평가. 장치 장애나 guard로 멈춘 실행만 원인이 풀린 뒤 처음부터 다시 할 수 있고(결정 105), 그 사실과 이유를 기록한다.
- 업체 100은 중단 규칙을 통과했을 때 업체 100 평가 단계에서만 쓴다. 데이터·후보 선택·설정에 쓰지 않는다.
- Ollama 모델 등록·삭제, 컨테이너 조작. batch007 import.

## 1. 데이터(pilot_004와 같음)

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_pilot004_t2pc`(pilot_004 `data/summary.json`) |
| sha256 | sft_train `7cf221e6061d09ca78ffe6ba4936ae8a2bbff2b7090ddeae794baf08ea34f5db`, dpo_train `6c52d0477d0a0aa4199bf57cfc27f544602e3abf1a5c6b6b87a896ca0099a96b`, manifest `ac7e7a7a03366f71184be8512dadb1dda223b76961db04b5db6ad71246789e1b`(valid 둘은 빈 파일) |
| 규모 | SFT 467(131질문), DPO 385쌍(58질문). 손실 범위 by_source(teacher `full_response`, 8b 자체 `json_only`, 결정 86) |
| 검사 | 세 config 모두 dry-run·tokenizer-check 통과(2026-10-15) |

## 2. 변형별 설정(결정 101, PROTOCOL_v5 2절)

모든 변형: base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing, LoRA r16/α32/dropout 0.05(7개 projection), AdamW, warmup 1 step, batch 1, accum 1,
`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17). 아래 표에 적은 것 말고는 pilot_004 config와 같다(config의 `diff`는 출력 위치와 표의 값뿐).

| 변형 | config(sha256 앞 16자) | pilot_004와 다른 것 | seed | 예상 step | 저장(후보) |
|---|---|---|---|---|---|
| V1 | `training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml`(`190bdb66776d4825`) | seed 42 → **43** | 43 | 934(467/epoch × 2) | `save_steps 0.5` → **step 467(epoch 1), 934(epoch 2)** |
| V2 | `training/configs/qwen3_8b_t2pc_thinking_pilot005_v2_sft.yaml`(`a7deb845a504dc19`) | **3 epoch**, `save_steps 934` | 42 | 1,401 | **step 934(epoch 2), 1,401(epoch 3, 마지막 step 저장)** |
| V3 | `training/configs/qwen3_8b_t2pc_thinking_pilot005_v3_dpo.yaml`(`e1ce438a0b4bd35b`) | 출발 adapter pilot_004 SFT checkpoint-934(sha256 `ca66b017…`), **lr 1e-5 → 5e-6**, **1 → 0.5 epoch** | 42 | 193(ceil(0.5 × 385)) | `save_steps 0.5` → **step 97(50%), 193(100%)** |

- V1·V2는 SFT lr 5e-5, max_seq_length 11,392. 학습률 스케줄은 자기 길이로 선형 감소(V2는 1,401 step).
- V3은 DPO β 0.1, `full_response`(결정 26), reference는 출발 SFT 미리 계산(결정 9, 385쌍 전체), 한도 11,392 / prompt 7,424 / completion 4,096.
- adapter·checkpoint는 `/home/hwkim/sftdpo_work/pilot_005/checkpoints/<variant>/`(저장소 밖). 경로와 sha256만 `train_logs/<variant>_summary.json`에 남긴다.
- 변형마다 기록: loss(log history), step당 시간(profile), peak 메모리(nvidia-smi 0.5초 간격), checkpoint 경로·sha256.

## 3. 후보 7개(결정 102)

| # | 후보 label | 출처 | 누적 학습 step(동점 기준) |
|---|---|---|---|
| 1 | `v1_step467` | V1 epoch 1 | 467 |
| 2 | `v1_step934` | V1 epoch 2 | 934 |
| 3 | `v2_step934` | V2 epoch 2 | 934 |
| 4 | `v2_step1401` | V2 epoch 3 | 1,401 |
| 5 | `v3_step97` | V3 50% | 934 + 97 = 1,031 |
| 6 | `v3_step193` | V3 100% | 934 + 193 = 1,127 |
| 7 | `p4_sft_step934` | pilot_004 SFT checkpoint-934(새로 학습·측정하지 않음, PROTOCOL_v5 3절) | 934 |

학습이 실패한 변형이 있어도 m = 7이다.

## 4. GPU 배정(결정 105)

| GPU(UUID) | 학습 | 그 뒤 |
|---|---|---|
| `GPU-2445b100-70d8-e384-3a24-0249eeefc64d`(2026-10-15 번호 0) | V1 | 평가 서버(포트 8500 + 번호) |
| `GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555`(번호 1) | V2 | 평가 서버 |
| `GPU-48f798cc-9437-50ac-d604-448bbad7b311`(번호 2, Ollama GPU) | V3 | 평가 서버 |

- 번호는 실행 때 host `nvidia-smi`에서 UUID로 다시 찾는다. 학습·서버 시작 전마다 `gpu_ok`(UUID, 상태, 메모리 < 100 MiB, 다른 프로세스 없음, Ollama GPU면 Ollama 모델 적재 0, torch UUID 일치).
  기록 `gpu_check.txt`, `runs.log`.
- 학습 중인 GPU에서는 평가하지 않는다. 이 단계 동안 Ollama는 부르지 않는다.
- 학습 중 메모리 부족 등 외부 요인으로 멈춘 변형은 출력 폴더를 `ABORTED_<variant>_<시각>`으로 옮기고, 원인을 확인한 뒤 그 변형만 처음부터 다시 돌린다(`run_pilot005.py --variants <v>`).

## 5. 후보 평가와 선택(PROTOCOL_v5 3·4절, 결정 103)

- 경로: **vLLM 0.30.0 BF16, flashinfer attention·sampler, adapter는 LoRA(병합하지 않음)**, 서버 인자는 PROTOCOL_v4 3절(`serve5.sh`, sha256 `5e7288827eaa425e`).
  한 서버에 그때까지 끝난 adapter를 모두 올리고(`--max-loras` = 올린 수), 필요한 adapter가 없으면 서버를 다시 띄운다.
- 셋: selection_v2(98문항), **k=4**, PROTOCOL_v4 3절 sampling(temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1, presence·frequency 0, max_tokens 8192,
  호출 seed `EV.call_seed(20261100+k, id, 호출)`), **동시 요청 8**(`run_cell5.py`, sha256 `bcc449c54ce640c2`). 서버마다 한 번에 셀 하나.
- 새로 재는 셀: 후보 1–6 × k=4 = **24셀**. 학습이 끝나 비는 GPU부터 자기 변형 셀 → 다른 끝난 변형 셀 순서로 맡는다.
- 기준값: pilot_prep_007 `serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json`. 후보 7은 `pilot_004/selection/runs/sft_step934_s1–4.json`(둘 다 다시 씀).
- 분석 `analyze_selection5.py`(sha256 `715d90c4e84c527a`). 후보마다: 평균 정답률, base 대비 차이의 95% CI(10,000회)와 **99.29% CI(20,000회, `default_rng(20261109)`)**,
  U·조용한 오답 비율, U 차이와 조용한 오답 차이의 95% CI, 오류 유형, 생성 상한·루프 수, 실차 통행량 오독 수(“실차” 표현 g02·g04와 n33 따로), vicinity 빠짐,
  학습 기록. 비교표 `selection_table.md`, 전체 `selection.json`.
- **고르는 방법**: U 차이 95% CI 하한 ≤ 0인 후보 가운데 평균 정답률 최대 → U 비율 낮은 것 → 누적 학습 step 적은 것. 해당 후보가 없으면 선택 없음(중단).
- **중단 규칙**: 고른 후보의 정답률 차이 **99.29% CI 하한 > 0** 그리고 **U 차이 95% CI 하한 ≤ 0**일 때만 업체 100으로 간다. 아니면 업체 100을 평가하지 않고 보고한다.
- 실행: `run_pilot005.py`(sha256 `c940ff76e625baa3`): 사전 확인(이 PLAN의 고정 표시, 지문, 데이터·출발 adapter·PROTOCOL_v5 sha256) → 세 변형 동시 학습(변형마다 커밋·push)
  → 셀 24개 → 커밋 → 선택·중단 규칙 → 커밋·push. 학습 기록 요약 `train_summary5.py`(sha256 `95790cc876afffb8`).

## 6. 업체 100 평가(중단 규칙 통과 때만)

PROTOCOL_v5 5절(= PROTOCOL_v4 5·6절, 보정 없음): 주 비교 vLLM-base → vLLM-고른 후보(업체 100, k=8, 동시 요청 8), 지연은 고정 30문항 순차(base 대비 1.5배),
참고 셀 E(Ollama 0.40.3, k=8)와 27b(Ollama `qwen3.8:27b`, k=4), aux_test_v1(base·고른 후보·E, k=4), valid98(base·고른 후보, k=4, 보조), vicinity 빠짐(모든 셋).
Ollama 셀은 측정 전에 버전과 digest를 확인하고 결정 55 guard를 켜며, 그동안 Ollama GPU에서 다른 작업을 하지 않는다.
pilot_004의 업체 100 단계 도구를 쓰면 먼저 PROTOCOL_v5와 맞는지 확인하고, 고칠 것은 새 파일(pilot_005 아래)로 만든다. 실행 스크립트는 그때 새로 만들고 sha256을 REPORT에 적는다.

## 7. batch007 준비(결정 104, 학습과 병행)

학습과 같은 때 CPU로 질문·gold 초안, 겹침 검사, 현재 코드 결과를 만든다. 8b base 출력은 후보 평가가 끝나 GPU가 빌 때 vLLM BF16으로 모은다(이 PLAN의 비교에 들어가지 않는다).
import와 학습용 trace 수집은 하지 않는다.
