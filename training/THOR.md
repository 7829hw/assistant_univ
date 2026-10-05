# Jetson AGX Thor: grounding SFT → DPO

LLM은 question → grounding JSON만 학습한다. Production planner/prompt, parser,
MacroComposer, G1–G7 Validator, compiler/operator mapping, executor를 변경하지 않는다.
기존 builder, canonicalization, parent-group split, manifest, evaluator를 그대로 사용한다.

## 기본 전략

Qwen3-8B + BF16 LoRA(r=16) + gradient checkpointing + PyTorch SDPA + `adamw_torch`.
Batch=1, accumulation=8, worker=0, pin_memory=false, torch_compile=false.
이는 작은 데이터에서 **안정성/pipeline pilot**을 위한 초기값이며 품질이 입증된 recipe가 아니다.
SFT train12/valid3, DPO train82/valid24는 최종 성능/일반화 결론을 내리기에 작다.
Full fine-tuning, FP8/FP4, fused optimizer, FlashAttention, compile은 baseline에 없다.
LoRA rank 8/16/32는 YAML `lora.r`/`alpha`를 별도 실험에서 변경한다. DPO adapter continuation의
rank/targets는 SFT adapter에 저장된 값을 사용하므로 SFT부터 같은 설정으로 학습해야 한다.
실제 `named_modules()`에서 q/k/v/o_proj, gate/up/down_proj 각각 36개, 총 252개 매칭을 확인했다.
0개/누락 target이면 즉시 실패한다.

Thor의 128GB는 CPU/GPU 공유 메모리다. Profile은 실제 `/proc/meminfo` total의 20%와 16GiB
중 큰 값을 reserve한다(이 장비에서는 약 24.6GiB). 시작 전, 모델 로드 후, optimizer step
전후에 MemAvailable/disk를 확인한다. Output filesystem free disk 최소 20GiB; 모델 cache를
다른 filesystem에 두면 별도로 공간을 확인한다. Guard는 batch 자동 확대나 OOM 복구 장치가
아니다. CUDA/system OOM은 오류로 기록하고 종료하며, CPU swap/QLoRA로 자동 전환하지 않는다.

## 환경과 설치

ARM64에서 x86 CUDA wheel을 설치하지 않는다. 동작하는 PyTorch를 먼저 확인한다.
[NVIDIA Thor CUDA 안내](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_cuda.html)
의 환경과 실제 JetPack/CUDA에 맞는 ARM64 PyTorch를 사용한다. 기존 설치가 CUDA BF16 연산을
통과하면 교체하지 않는다. NVIDIA 지원 wheel/container 선택은 장비의 JetPack에 따라 확인한다.

이미 검증된 CUDA PyTorch가 있는 환경에서:

```bash
python -m venv --system-site-packages training/runs/thor-env
source training/runs/thor-env/bin/activate
pip install -r requirements.txt -r training/requirements-thor.txt
python -m training.check_thor_env --output training/generated/thor_environment.json
```

`requirements-thor.txt`에는 torch/bitsandbytes/flash-attn 설치 지시가 없다. Generic training
requirements와 분리해 기존 NVIDIA torch를 유지한다. Shared site packages는 기존 서비스
환경과 함께 사용하지 말고 격리된 training container/venv로 사용한다. TRL 0.23.1,
transformers 4.56.x, PEFT 0.17.x API를 사용한다. 실제 실행 버전/image digest는 validation 문서에
기록했다. `pip freeze`와 profile environment를 함께 보관한다.

이번 장비의 기본 host Python에는 torch가 없어 **이미 존재하는 로컬 CUDA 13 ARM64 이미지**를
재사용했다. 동일 이미지가 있는 이 호스트에서의 재현 예시(다른 장비는 검증된 이미지를 선택):

```bash
docker run -d --name geoflow-thor-training --runtime nvidia --gpus all --shm-size 2g \
  -v "$PWD":/workspace -v /tmp/geoflow-hf-cache:/hf-cache -w /workspace \
  --entrypoint /bin/sh \
  sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f \
  -c 'sleep infinity'
docker exec geoflow-thor-training python3 -m venv --system-site-packages training/runs/thor-env
docker exec geoflow-thor-training training/runs/thor-env/bin/pip install \
  -r requirements.txt -r training/requirements-thor.txt
docker exec -it -e HF_HOME=/hf-cache geoflow-thor-training /bin/bash
source training/runs/thor-env/bin/activate
```

이 이미지는 기존 vLLM image다. venv 내 transformers pin은 training 전용이며 상속된 vLLM/
lmcache 요구 버전과 충돌할 수 있다. 이 venv에서 vLLM 서버를 실행하지 않는다. 이미지 자체,
호스트 패키지, 기존 서비스에는 변경하지 않았다. 새 장비에 이 image tag를 무조건 설치하는
것은 권장하지 않는다. 검증한 immutable digest와 working torch가 재현 기준이다.

## Diagnostic

```bash
python -m training.check_thor_env
python -m training.check_thor_env --test-optional --output training/generated/thor_optional.json
```

기본 검사에는 실제 BF16 matmul backward, SDPA backward가 있다. Dependency는 버전뿐 아니라
import도 검사한다. Optional 검사는 NF4 quantize/dequantize와 Linear4bit backward,
flash_attn forward/backward까지 실행한다. CUDA 없는 환경에서도 JSON을 출력하며 graceful하게
종료한다. PASS는 최소 연산 성공이지 장시간 training 보증이 아니다. Extension import/ABI
실패는 diagnostic JSON에 남긴다. `nvpmodel -q`, `jetson_clocks --show`, bounded tegrastats,
thermal sysfs, nvidia-smi를 **조회만** 한다. Container에는 JetPack/power query 도구가 없을 수
있으므로 host에서도 실행한다. Root 필요한 조회는 권한 오류로 보고하고 sudo를 실행하지 않는다.
최대 성능 mode를 원하면 사용자가 전력/냉각 조건을 확인해 직접 설정해야 한다.

QLoRA는 기본값이 아니다. 8B BF16 LoRA smoke가 메모리 reserve 안에서 실제 성공했고 optional
ARM64 CUDA extension 의존성을 피할 수 있다. bitsandbytes는 generic aarch64 지원만으로
Jetson에서의 연산 성공을 보장하지 않는다.
[설치/소스 빌드 문서](https://huggingface.co/docs/bitsandbytes/main/en/installation)를 참고해
격리 환경에서 ARM64/CUDA/Thor compute capability 지원을 확인한다. 설치 시 CUDA/JetPack을
임의로 downgrade하지 않는다. 필요하면 해당 source release의 CMake CUDA toolkit 및
architecture 설정으로 빌드하고 `--test-optional`을 다시 실행한다. Quantization + backward가
통과한 뒤 별도 profile로 `load_in_4bit`를 켠다. BF16 baseline의 unified-memory guard를 우회해
같은 실험처럼 취급하지 않는다. `model_for`도 4-bit CUDA operation 실패 시 actionable 오류를
내고 BF16 profile 선택을 안내하며 기존 모델을 자동으로 바꾸지 않는다.

## 데이터와 tokenizer 길이

```bash
python -m training.data.build_sft --input geoflow_examples/question_graph_examples.yaml \
  --output training/generated --strict
python -m training.data.build_dpo --gold training/generated --output training/generated --strict
python -m training.data.analyze_tokens --config training/configs/qwen3_8b_thor_sft.yaml \
  --output training/generated/thor_sft_tokens.json
python -m training.data.analyze_tokens --config training/configs/qwen3_8b_thor_dpo.yaml \
  --output training/generated/thor_dpo_tokens.json
python -m training.train_sft --config training/configs/qwen3_8b_thor_sft.yaml --tokenizer-check
python -m training.train_dpo --config training/configs/qwen3_8b_thor_dpo.yaml --dry-run
```

Full production system prompt와 non-thinking generation prefix를 사용하며 JSON/EOS까지 센다.
SFT prompt/completion/total, DPO prompt/chosen/rejected/total의 nearest-rank p50/p90/p95/p99/max를
출력한다. Max를 128 단위로 올림해 권장 길이를 제시한다. Prompt hash와 model revision도 남긴다.
현재 prompt만 최대6748 tokens라 2048/4096은 사용할 수 없다. 실측으로 SFT/DPO max_length=6912,
DPO prompt=6784/completion=256을 선택했다. Prompt를 줄이면 production 변경 실험이 되므로
이 작업에서 바꾸지 않았다. 데이터/prompt/tokenizer가 바뀌면 다시 분석한다. Overlength는
학습 전 실패하며 question/JSON을 잘라서 학습하지 않는다.

## Smoke와 실제 pilot 학습

```bash
python -m training.train_sft --config training/configs/qwen3_8b_thor_smoke_sft.yaml
python -m training.train_dpo --config training/configs/qwen3_8b_thor_smoke_dpo.yaml
# 결과 확인 후 사용자가 실행할 1 epoch pilot:
python -m training.train_sft --config training/configs/qwen3_8b_thor_sft.yaml
python -m training.train_dpo --config training/configs/qwen3_8b_thor_dpo.yaml
```

Smoke는 accumulation1, optimizer2 step, validation1 sample, intermediate save 없음,
최종 adapter1개를 저장한다. 전체 manifest/split은 먼저 검증하고 `data.max_valid_samples`를
적용한다. Dataset 형식/holdout 정책은 유지한다. SFT smoke adapter는 `thor_smoke_sft`,
pilot은 `thor_sft`; DPO profile은 각 경로를 명시적으로 참조한다. Smoke는 품질 개선/수렴
판정용이 아니다. Warmup 때문에 첫 step LR=0일 수 있으며 서로 다른 질문의 loss가 단조
감소할 필요는 없다. BF16 단독 연산 성공 후 실제 backward/optimizer/checkpoint 저장까지
확인하고, 장시간 실행은 별도로 결정한다.

`--dry-run`, `--tokenizer-check`, `--max-steps N`, `--resume-from-checkpoint PATH`는 기존
trainer에서 지원한다. Save/eval/logging interval과 checkpoint limit은 YAML training 필드로
지정한다. LoRA adapter 중심으로 저장하며 smoke의 optimizer checkpoint는 남기지 않는다.
중단 시 profile에 error/status가 기록된다. Resume 및 장시간 안정성은 별도 검증이 필요하다.

## DPO reference: objective 유지

[TRL 0.23.1 구현](https://github.com/huggingface/trl/blob/v0.23.1/trl/trainer/dpo_trainer.py)
및 실제 설치된 API signature를 확인했다. Default `reference.strategy: shared_adapter`는
동일 BF16 base 위에 trainable SFT policy와 frozen SFT reference adapter를 각각 로드한다.
`model_adapter_name=policy`, `ref_adapter_name=reference`, `ref_model=None`이며 reference에서
`torch.no_grad()`를 사용한다. Base 전체를 두 번 올리지 않는다. DPO-only의 fresh LoRA에서는
adapter를 disable해 초기 base reference를 사용한다(기존 동작 유지).

PEFT 0.17.1의 두 번째 `load_adapter`는 FP32 SFT adapter를 BF16으로 복사한 뒤 upcast하므로
미세한 반올림이 생긴다. Reference 로드/upcast 후 초기 policy state를 다시 복사하고 hash가
정확히 같은지 확인한다. 학습 후 reference hash도 검사해 고정 reference를 보장한다.
Tiny Qwen regression과 실제 8B checkpoint에서 이 보존 동작을 검증했다.

`reference.strategy: precompute`는 같은 fixed reference의 chosen/rejected log-prob를
TRL `precompute_ref_log_probs=true`, batch1로 먼저 계산한다. 학습과 평가 각각 캐시하며
objective는 동일하다. Reference adapter를 유지하므로 추가 절감은 reference 계산/activation에
있다. Default shared mode에서 이미 base duplication을 피하므로 precompute가 모델 weight
메모리를 더 크게 줄인다고 주장하지 않는다. 82 pairs 전체 precompute 시간도 측정해야 한다.
TRL0.23.1의 사전 계산은 Accelerator policy wrapping 이전에 실행된다. BF16 base/FP32 LoRA의
cached reference와 live reference가 같은 precision을 쓰도록 같은 Accelerator autocast를
적용한다. Upstream log-prob/loss 계산을 재사용하며 세 전략의 초기 loss 일치를 실측했다.

`reference.strategy: full`은 별도 전체 BF16 base + SFT adapter를 frozen reference로 올리는
비교용이다. `force_use_ref_model=true`를 사용한다. 비용이 크므로 기본으로 쓰지 않는다.
Explicit full reference checkpoint 모드와 generic full-tuning auto-reference도 유지했다.
Thor baseline은 reference_free/sync_ref_model을 거부해 objective를 몰래 바꾸지 않는다.
DPO의 `use_logits_to_keep=true`는 completion에 필요한 logits만 만들어 긴 prompt의 vocabulary
logit 메모리를 줄인다. 실제 Qwen/TRL smoke에서 확인했으며 preference objective는 유지한다.

## 메모리/throughput benchmark

```bash
python -m training.benchmark_thor --stage sft \
  --config training/configs/qwen3_8b_thor_smoke_sft.yaml --steps 3
python -m training.benchmark_thor --stage dpo \
  --config training/configs/qwen3_8b_thor_smoke_dpo.yaml --steps 3
# SFT 생성 후 동일 config/seed/data에서 reference 전략만 비교:
python -m training.benchmark_thor --stage dpo \
  --config training/configs/qwen3_8b_thor_smoke_dpo.yaml --steps 1 --reference-strategy precompute
python -m training.benchmark_thor --stage dpo \
  --config training/configs/qwen3_8b_thor_smoke_dpo.yaml --steps 1 --reference-strategy full
```

Benchmark는 optimizer step override, logging1, 마지막에 validation1개, 중간 checkpoint 없음,
최종 adapter1회 저장이다. Stage/strategy/step별 runs 폴더를 사용한다. 동시에 GPU 학습을
실행하지 않는다. 비교하려는 batch/accumulation/data가 같아야 하며 cold start와 evaluation
시간을 구분한다. Precompute는 지정한 전체 train split을 먼저 통과하므로 시간이 추가된다.

`memory_profile.json`: initial, CPU model_load, GPU trainer_ready, 첫 policy forward/backward,
첫 optimizer step, end, CUDA allocated/reserved/peaks, system available(1초 polling minimum),
thermal readings, optimizer step 시간, logged mean loss, model load 준비 시간, package 버전.
CUDA peak는 train_begin 이후 evaluation까지 포함한다. Model load 값에는 tokenizer/data 준비도
포함되므로 pure I/O benchmark로 해석하지 않는다. Sec/step은 eval/save를 제외하고 reference
계산은 포함한다. Tokens/sec는 nonpadding policy input tokens(질문/prompt 포함); DPO는 chosen+
rejected 두 sequence를 세고 reference/precompute 토큰은 세지 않는다. `total_seconds`는 준비,
precompute, eval/save를 포함한다. 첫/짧은 step 평균은 장시간 처리량 예측 근거가 약하다.

OOM 대응: batch1 확인 → 데이터가 손상되지 않는 범위에서 길이 제한 재분석 → checkpointing
확인 → LoRA rank/targets 축소 → DPO reference 최적화 → 별도 QLoRA 검증 → 더 작은 모델.
현재 데이터는 약6.9k라 그 아래로 길이만 줄일 수 없다. Prompt/schema를 바꾸는 실험은 분리한다.
Memory guard가 메모리를 확보하거나 OOM을 완전히 예방하지는 않는다. Swap을 GPU memory처럼
사용하는 해법은 기본으로 제공하지 않는다. Thermal throttling/worker/pin/fused/compile 등의
추가 최적화는 baseline 안정화 이후 실제 측정으로 판단한다.

평가/adapter merge/HF 저장/Ollama 연결은 기존 README의 CLI를 재사용한다. 평가 corpus는
training에 편입하지 않는다. 전체 결과와 task/intent별 regression을 모두 비교한다.
