# Thor validation — 2026-10-04

실제 `hpclab-thor2`에서 수행한 결과다. Fake benchmark, x86 서버 측정값 또는 모델 크기만으로
추정한 메모리가 아니다. 긴 full training은 실행하지 않았다. Production의 question →
grounding JSON 경계와 deterministic downstream, 기존 generic QLoRA config는 유지했다.
실행 절차/CLI/제약은 [THOR.md](THOR.md), 전체 pipeline은 [README.md](README.md)에 있다.

## 실제 환경

| 항목 | 조회 결과 |
|---|---|
| Host OS / architecture / Python | Ubuntu 24.04.5 LTS / aarch64 / 3.12.3 |
| Kernel | 6.8.12-tegra, tegra264 |
| JetPack / Jetson Linux | 7.1-b112 / L4T 38.4.0-20251230160601 |
| Host CUDA / nvcc | 13.0 / 13.0.48 |
| nvidia-smi driver | 580.00 |
| GPU / compute capability | NVIDIA Thor / (11, 0) |
| Shared system memory | 131881115648 bytes = 122.82 GiB |
| Initial available memory before training | 약118 GiB; 다음 실행은 이전 CUDA allocation/cache 상태에 따라 달라짐 |
| NVMe | 937 GiB filesystem, 모델 캐시 다운로드 후 약556 GiB free |
| Power mode | `nvpmodel -q`: 120W, mode 1 (조회만 수행) |
| jetson_clocks | `--show`에 root 필요; 조회 실패 기록, sudo/설정 변경 없음 |
| tegrastats / thermal | Host bounded query 성공, thermal sysfs를 학습 단계별 조회 |

기본 host Python에 PyTorch가 없어 기존 로컬 `vllm/vllm-openai:v0.28.0` ARM64 이미지를
격리해 재사용했다. Image digest:
`sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f`.
Container Ubuntu24.04.3, nvcc13.0.88, working torch **2.13.0+cu130**(CUDA runtime13.0)를
교체하지 않았다. 별도 system-site-packages venv에서 transformers4.56.2, TRL0.23.1,
PEFT0.17.1, accelerate1.14.0, datasets4.8.5를 사용했다. 상속된 vLLM/lmcache dependency
충돌 경고는 이 venv에서 해당 서버를 실행하지 않는 training 전용 격리로 처리했다.
이미지나 host PyTorch/CUDA/JetPack/power 설정은 수정하지 않았다.

Repository base SHA: `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`, branch `geoflow/dev-v2`.
학습 코드 변경은 working tree에 있다. Config seed42, model revision
`Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`을 사용했다.

## 호환성

| 항목 | 결과 / 근거 |
|---|---|
| CUDA GPU recognition | PASS, device Thor/capability11.0 |
| BF16 | PASS, matmul + backward + finite check |
| SDPA | PASS, causal attention + backward + finite check |
| BF16 LoRA training | PASS, 실제8B SFT/DPO backward/optimizer/evaluation/save |
| bitsandbytes | NOT INSTALLED; optional operation attempt는 ModuleNotFoundError로 FAIL 보고 |
| QLoRA | 실제 quantized 학습 NOT TESTED; optional Linear4bit operation은 dependency 부재로 FAIL |
| flash-attn | NOT INSTALLED |

실제 설치된 TRL API signature에 precompute_ref_log_probs, precompute_ref_batch_size,
use_logits_to_keep, model_adapter_name, ref_adapter_name, force_use_ref_model,
SFT completion_only_loss가 존재하는 것을 확인했다. Import만으로 CUDA extension 호환성을
판단하지 않았다. QLoRA/FlashAttention을 설치하거나 CUDA를 바꾸지 않았다.

## 실제 token distribution

Production prompt hash:
`522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
전체 train+valid, 실제 Qwen non-thinking chat generation prefix + JSON + EOS 기준.
Total에는 truncation guard용 1 token margin이 포함된다.

| 입력 | n | p50 | p90 | p95 | p99 | max |
|---|---:|---:|---:|---:|---:|---:|
| SFT prompt | 15 | 6741 | 6747 | 6748 | 6748 | 6748 |
| SFT JSON+EOS | 15 | 123 | 137 | 138 | 138 | 138 |
| SFT total+margin | 15 | 6863 | 6883 | 6884 | 6884 | 6884 |
| DPO prompt | 106 | 6741 | 6747 | 6748 | 6748 | 6748 |
| DPO chosen+EOS | 106 | 124 | 137 | 138 | 138 | 138 |
| DPO rejected+EOS | 106 | 120 | 137 | 137 | 138 | 140 |
| DPO max pair total+margin | 106 | 6864 | 6883 | 6884 | 6884 | 6886 |

선택: SFT/DPO total6912, DPO prompt6784/completion256. 2048/4096은 prompt만으로 초과한다.
Production prompt를 줄이거나 completion을 truncate하지 않았다.

## 실제 SFT/DPO smoke

BF16 LoRA rank16/alpha32, target252 modules, gradient checkpointing(non-reentrant), SDPA,
unfused AdamW, batch1/accumulation1, worker0, pin_memory=false, compile=false.
각 optimizer2 step, validation1 sample, 최종 adapter1회 저장. Pilot config의 accumulation8은
별도이며 이번 throughput 측정은 accumulation1이다. 초기 테스트에서 잠깐 겹친 GPU 실행의
처리량은 제외하고 아래는 수정 후 단독 실행 결과다.

| 단계 | SFT CUDA allocated GiB | DPO CUDA allocated GiB |
|---|---:|---:|
| initial | 0 | 0 |
| CPU model_load | 0 | 0 |
| GPU trainer_ready | 15.42 | 15.58 |
| first policy forward 종료 | 25.19 | 27.42 |
| first backward 종료 | 15.60 | 15.76 |
| first optimizer 종료 | 15.92 | 16.09 |
| peak allocated(train+eval) | **29.18** | **32.03** |
| peak reserved(train+eval) | **40.79** | **40.51** |
| system minimum available(1초 polling) | **62.66** | **62.13** |

Backward 종료 숫자가 forward보다 작은 것은 activation 해제 후 snapshot이기 때문이다.
CPU model_load는 GPU placement 이전이고 GPU weight memory는 trainer_ready에서 본다.
CUDA allocation은 전체 unified-memory 사용량과 같지 않으므로 system MemAvailable도 기록했다.
Reserve 약24.57GiB보다 충분히 남았지만 긴 실행에 동일한 minimum이 보장되는 것은 아니다.

| 지표 | SFT | DPO |
|---|---:|---:|
| 모델 로드 준비(tokenizer/data 포함) | 5.70s | 5.99s |
| optimizer steps | 2 | 2 |
| sec/step(eval/save 제외) | **13.90** | **42.26** |
| nonpadding policy input tokens/sec | **489.33** | **323.14** |
| mean logged loss | 2.9754 | 0.6931 |
| 관측된 최대 thermal reading | 57.16°C | 56.44°C |

DPO tokens는 chosen/rejected 두 sequence를 세고 reference token은 제외한다. SFT loss는
JSON completion에만 적용했다. 첫 step warmup LR0, 둘째 step에서 policy 실제 변경을 확인했다.
SFT loss0.8802→5.0706은 서로 다른 질문의 값이며 수렴/단조 감소를 주장하지 않는다.
단기 validation loss도 품질 향상 근거가 아니다. DPO loss0.6931은 초기 policy/reference의
일치와 짧은 학습에 부합하며 downstream benchmark 향상을 입증하지 않는다.

실제 reference 검증 중 PEFT 두 번째 adapter load에서 FP32→BF16→FP32 반올림을 발견했다
(최대 절대 차이4.77e-7). 로드 후 초기 FP32 policy state를 reference에 다시 복사하는 방식으로
보정했다. 초기/최종 reference hash 동일 검사가 통과했다. Policy만 학습됐으며 production
reference-free objective로 바꾸지 않았다. Tiny Qwen regression에서도 이 보정을 검증했다.

## DPO reference A/B/C 실측 비교

동일 seed42/SFT adapter/rank16, 같은 train2 pairs + valid1, batch1/accumulation1,
각 optimizer1 step. 전체82 pairs precompute 성능 결과로 해석하지 않는다. 첫 step은 warmup
LR0이므로 이 비교 자체는 품질 향상 실험이 아니다. 기본 smoke2 step에서는 policy가 실제
업데이트됐고 reference가 원본 SFT tensor와 정확히 동일함을 별도 확인했다.

| 전략 | CUDA peak allocated GiB | peak reserved GiB | system min available GiB | optimizer sec/step | total seconds | initial DPO loss |
|---|---:|---:|---:|---:|---:|---:|
| A: full reference | 46.90 | 52.59 | 60.82 | 29.49 | 84.35 | 0.6931 |
| B: shared adapter | 31.48 | 37.03 | 62.65 | 29.47 | 73.44 | 0.6931 |
| C: reference precompute | 27.85 | 33.99 | 61.08 | 22.31 | 87.90 | 0.6931 |

B는 A보다 별도 base weight 약15.42GiB를 절약했다. C는 optimizer 구간 reference forward를
줄였지만 사전 계산 때문에 이 짧은 실험의 전체 시간은 B보다 길었다. 기본값은 B다.
Reference-free로 objective를 바꾸지 않았다. CUDA peak는 train_begin 이후 train+eval,
system minimum과 total seconds는 model 준비/ref precompute까지 포함한다.

TRL0.23.1에서 precompute가 Accelerator policy wrapping보다 먼저 실행되는 것을 확인했다.
BF16 base + FP32 LoRA reference를 autocast 없이 사전 계산하면 initial loss0.7238로 live
reference0.6931과 달랐다. 동일 Accelerator autocast context를 적용한 후 initial loss는
세 전략 모두0.6931로 일치했고 reference hash 보존 검사도 통과했다. Upstream log-prob/DPO
loss 계산을 재사용하며 새 preference objective를 구현하지 않았다. 이 precision 경로는
unit regression과 실제8B 1-step 재측정으로 검증했다.

## Tests / 재현 산출물

- 최종 전체1106개: **1103 PASS**, 2 GPU opt-in skip, 1 expected failure; error/failure 없음.
  Localhost 테스트는 socket 허용 환경에서 통과.
- Training 관련48개: **46 PASS + 2 opt-in skip**. 기존34개 포함.
- Thor14개는 실제 container에서 `GEOFLOW_RUN_GPU_TESTS=1`로 **14 PASS**.
- Strict SFT/DPO builder: 12/3 samples, 82/24 pairs; clarification1개 명시 제외, critical issues 없음.
- Thor4 profile dry-run, frozen tokenizer preflight, token analyzer, CLI help, compileall 확인.

초기에는 vendor source XLSX 누락으로1 error가 있었다. 사용자가 제공한
`질문 결과 및 정답 설명_100문항.xlsx`의 SHA256
`2f84f6b1e7e1dae7071e94578bd0c1c88b7746b7b12705d53b25c95a04bf17a6`이
기존 gold.yaml 기록과 정확히 일치해 `evaluation/vendor100/`에 복원했다. 해당3개 테스트와
전체 suite가 통과했다. 원본은 git-ignore를 유지하며 evaluation 전용으로 사용하고
training 데이터에 편입하지 않았다.

Ignored 산출물: `training/generated/thor_*environment.json`, `thor_*tokens.json`,
`training/checkpoints/thor_smoke_{sft,dpo}/memory_profile.json`, adapter/토크나이저/
training_provenance.json. Weight와 generated 데이터를 git에 추가하지 않는다.

## 이번 변경 파일

- 추가: `training/check_thor_env.py`, `training/data/analyze_tokens.py`,
  `training/profiling.py`, `training/benchmark_thor.py`, `training/requirements-thor.txt`.
- 추가 profile: `qwen3_8b_thor_sft.yaml`, `qwen3_8b_thor_dpo.yaml`,
  `qwen3_8b_thor_smoke_sft.yaml`, `qwen3_8b_thor_smoke_dpo.yaml` (`training/configs/`).
- 수정: `training/trainer_common.py`, `training/train_sft.py`, `training/train_dpo.py`.
- 테스트: `tests/test_training_thor.py` 추가.
- 문서: `training/README.md`, `training/VALIDATION.md` 수정;
  `training/THOR.md`, `training/THOR_VALIDATION.md` 추가.

Production/runtime 파일에 이번 Thor 작업의 변경을 추가하지 않았다. 시작 시 이미 있던
`.gitignore`, evaluator, aggregation 및 training 구현 변경은 보존했다. Temporary 검증
container는 종료/제거했고 cache/checkpoint/diagnostic/freeze는 유지했다.
종료 후 host 조회에서 GPU compute process가 없고 utilization0%, MemAvailable 약118.54GiB로
복귀한 것을 확인했다. 측정 중의 system minimum과 종료 후 회수 상태를 구분했다.

## Full pilot와 남은 검증

검증된 CUDA 환경/container 안에서:

```bash
python -m training.check_thor_env
python -m training.train_sft --config training/configs/qwen3_8b_thor_sft.yaml
python -m training.train_dpo --config training/configs/qwen3_8b_thor_dpo.yaml
```

위1 epoch pilot은 이 작업에서 실행하지 않았다. DPO는 pilot SFT 출력 `thor_sft`를 참조한다.
학습 시간을 임의로 추정하지 않는다. Pilot과 동일한 accumulation8 profile을 짧게 benchmark한
후 `ceil(train_count/(batch*accumulation)) × epochs × measured_sec_per_step`으로 optimizer
시간을 계산하고 load/precompute/eval/save 시간을 추가한다. Accumulation1 smoke sec/step을
accumulation8 optimizer step 시간으로 그대로 대입하면 안 된다.

남은 위험: 작은/검토중인 corpus, OD gold 부재, overfit, long-run thermal/throttling/메모리,
GPU resume, multi-GPU, QLoRA/FlashAttention/compile/fused optimizer 미검증. Pin/worker 성능
차이와 reference precompute 전체82 pairs 비용은 후속 benchmark가 필요하다. Profile의
rank/LR/epoch/effective batch/beta는 최종 품질용 hyperparameter로 검증되지 않았다.
