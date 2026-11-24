# 실행 명령 기록 (2026-11-24, 자체시험)

모든 GPU 작업은 커밋 `f82e7cef`에 고정한 worktree `/data/hwkim/sftdpo_work/worktrees/wt_f82e7cef_final`에서 실행했다(결정 114 방식).
각 셀의 실제 인자는 결과 JSON의 `meta.argv`와 서버 기록(`server_*.json`의 `args`)에 남아 있다.

## 0. 사전 확인

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu --format=csv
nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv   # 다른 프로세스 없음
docker ps -a        # 빈 목록(Ollama 컨테이너 없음) → Ollama 신규 측정 없음, 기존 기록만 인용
```

GPU별 확인 결과(UUID·메모리·프로세스·torch UUID 대조)는 `latency/gpu_check.txt`, `vram/gpu_check.txt`.

## 1. 입력 구성(CPU)

```bash
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
CUDA_VISIBLE_DEVICES= /data/hwkim/sftdpo_work/runtime/envs/hf/bin/python final_report/tools/vram_2048.py build \
  --out final_report/data/vram_inputs_2048.jsonl
# → {"inputs": 10, "prompt_tokens": [2048 × 10], "template_tokens": 8, "tokenizer": "Qwen/Qwen3-8B@b968826d…"}
```

## 2. 지연시간 자체시험(GPU index 3, UUID GPU-48f798cc-9437-50ac-d604-448bbad7b311)

```bash
cd /data/hwkim/sftdpo_work/worktrees/wt_f82e7cef_final
bash final_report/tools/run_latency.sh 3 > /home/hwkim/assistant_univ/final_report/logs/run_latency.stdout 2>&1
```

`run_latency.sh` 내부(요약):

```bash
# A: HF transformers BF16 (프로세스 안 적재)
CUDA_VISIBLE_DEVICES=3 python final_report/tools/latency_e2e.py --backend hf --label A_hf_bf16_base \
  --warmup-ids old44/g02,old44/g03,old44/g04 --out .../A_hf_bf16_base.json --raw-out .../raw/A_hf_bf16_base_raw.jsonl
# vLLM 서버(기존 스크립트 그대로 사용): BF16 → 셀 B(base)·D(LoRA V4_o101), FP8 → 셀 C(base)·E(LoRA V4_o101)
LORAS="V4_o101=/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984" MAX_LORA_RANK=16 \
  bash sft_dpo_inventory/ablation_011/gpu/serve_a11.sh 3 8810 {bf16|fp8} fi
python final_report/tools/latency_e2e.py --backend vllm --base-url http://127.0.0.1:8810 --served-model {base|V4_o101} \
  --label <셀> --warmup-ids old44/g02,old44/g03,old44/g04 --server-meta .../server_{bf16|fp8}.json --out ... --raw-out ...
```

- 고정 30문항: `sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt`(기존 지연 시험 문항, 결정 93·113), 질문 원본 `sft_dpo_inventory/conversion_diag/selection_gold.yaml`.
- sampling: temperature 0.6, top-p 0.95, top-k 20, min-p 0, repetition 1, 회차 seed 20261101(호출 seed = `EV.call_seed`), max_new_tokens 8,192, thinking 켬, 동시 1.
- 실행 순서와 시각: `latency/runs.log`. 서버 로그 원문: `latency/server_{bf16,fp8}_fi.log`.

## 3. VRAM 자체시험(GPU index 2, UUID GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e)

```bash
cd /data/hwkim/sftdpo_work/worktrees/wt_f82e7cef_final
bash final_report/tools/run_vram.sh 2 > /home/hwkim/assistant_univ/final_report/logs/run_vram.stdout 2>&1
```

`run_vram.sh` 내부(요약):

```bash
CUDA_VISIBLE_DEVICES=2 hf/bin/python vram_2048.py hf --label M1_hf_bf16_default ...                                   # allocator 기본
CUDA_VISIBLE_DEVICES=2 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True hf/bin/python vram_2048.py hf --label M2_... # 결정 17 설정
VLLM_ENABLE_V1_MULTIPROCESSING=0 VLLM_USE_FLASHINFER_SAMPLER=1 CUDA_VISIBLE_DEVICES=2 vllm/bin/python vram_2048.py vllm --label M3_vllm_bf16_fi_base ...
VLLM_ENABLE_V1_MULTIPROCESSING=0 VLLM_USE_FLASHINFER_SAMPLER=1 CUDA_VISIBLE_DEVICES=2 vllm/bin/python vram_2048.py vllm --fp8 \
  --lora V4_o101=/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984 --label M4_vllm_fp8_fi_v4 ...
```

## 4. 집계(CPU)

```bash
python3 final_report/tools/collect_env.py      # environment.json
python3 final_report/tools/aggregate.py        # latency_results.csv, vram_results.csv, summary.json, figures/*.svg
cd final_report/figures && for f in *.svg; do convert -density 144 $f ${f%.svg}.png; done
```
