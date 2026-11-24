# -*- coding: utf-8 -*-
"""environment.json 수집(새 파일). 실제 조회 결과만 넣는다. Thor 항목은 기존 기록(training/THOR_*.md)에서 옮긴 것이며 이번에 재조회하지 않았다."""
import json, platform, subprocess
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def sh(c):
    return subprocess.run(c, shell=True, capture_output=True, text=True).stdout.strip()
def py(env, code):
    return sh(f"/data/hwkim/sftdpo_work/runtime/envs/{env}/bin/python -c \"{code}\" 2>/dev/null | tail -1")
gpus = [dict(zip(["index", "name", "uuid", "memory_total_mib", "driver", "pcie_gen_max"], [x.strip() for x in l.split(",")]))
        for l in sh("nvidia-smi --query-gpu=index,name,uuid,memory.total,driver_version,pcie.link.gen.max --format=csv,noheader,nounits").splitlines()]
lscpu = {l.split(":", 1)[0].strip(): l.split(":", 1)[1].strip() for l in sh("lscpu").splitlines() if ":" in l}
env = {
 "collected_at": datetime.now().astimezone().isoformat(),
 "test_server(자체시험 수행 장비)": {
  "hostname": platform.node(), "os": sh("grep PRETTY_NAME /etc/os-release | cut -d= -f2").strip('"'), "kernel": platform.release(),
  "cpu": {"model": lscpu.get("Model name"), "sockets": lscpu.get("Socket(s)"), "logical_cpus": lscpu.get("CPU(s)"), "numa_nodes": lscpu.get("NUMA node(s)")},
  "memory_total_gib": round(int(sh("grep MemTotal /proc/meminfo | awk '{print $2}'")) / 1024 ** 2, 1),
  "gpus": gpus, "cuda_driver_max": sh("nvidia-smi | grep -o 'CUDA Version: [0-9.]*'"),
  "gpu_used_in_self_tests": {"latency": "index 3, GPU-48f798cc-9437-50ac-d604-448bbad7b311", "vram": "index 2, GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e"},
 },
 "software": {
  "hf_env(/data/hwkim/sftdpo_work/runtime/envs/hf)": py("hf", "import sys,torch,transformers,peft,trl,accelerate;print(sys.version.split()[0],torch.__version__,torch.version.cuda,transformers.__version__,peft.__version__,trl.__version__,accelerate.__version__)"),
  "hf_env_fields": "python torch torch_cuda transformers peft trl accelerate",
  "vllm_env(/data/hwkim/sftdpo_work/runtime/envs/vllm)": py("vllm", "import sys,vllm,torch,flashinfer,transformers;print(sys.version.split()[0],vllm.__version__,torch.__version__,torch.version.cuda,flashinfer.__version__,transformers.__version__)"),
  "vllm_env_fields": "python vllm torch torch_cuda flashinfer transformers",
  "llama_cpp": "b11434 (commit 5e03bdd8700948b9c41c54dd1b00f28a2aebc03f), CPU 빌드 llama-quantize — sft_dpo_inventory/quant_recipe/RECIPE.md",
  "ollama(기존 기록)": "Docker 컨테이너 0.40.3(serving_vllm_fp8 E 셀, 2026-10-14), 사용자 권한 서버 0.40.6(pilot_010 JU/JV, 2026-11-21~22). 2026-11-24 현재 컨테이너 없음(docker ps -a 빈 목록), 이번 자체시험에서 사용하지 않음",
 },
 "model": {"base": "Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218",
           "trained_adapter": {"name": "V4(RR+NM4) o101, pilot_010 판정 단계", "path": "/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984",
                               "adapter_model_sha256": "6402ba63352e1f21591a1625c9bcf0635211d2ea0d3d2870c22d3e50343d9a1d", "lora": "r16, alpha 32, q/k/v/o/gate/up/down"},
           "planner_prompt_sha256": "87048d0c554c365e0e7994d09a4515c1cc646785708ce6dc9d1f120b4b5e8c2c", "thinking": "on (enable_thinking=True)"},
 "jetson_agx_thor(기존 기록, 재조회 안 함)": {"source": ["training/THOR_VALIDATION.md", "training/THOR_V003_TOKEN_VALIDATION.md"],
   "host": "hpclab-thor2", "os": "Ubuntu 24.04.5 LTS aarch64", "kernel": "6.8.12-tegra", "jetpack": "7.1-b112 / L4T 38.4.0", "cuda": "13.0 (nvcc 13.0.48)",
   "driver": "580.00", "gpu": "NVIDIA Thor, compute capability 11.0", "unified_memory_gib": 122.82, "power_mode": "120W mode 1",
   "container": "vllm/vllm-openai:v0.28.0 ARM64 sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f",
   "training_stack": "torch 2.13.0+cu130, transformers 4.56.2, TRL 0.23.1, PEFT 0.17.1, accelerate 1.14.0"},
}
(ROOT / "final_report/environment.json").write_text(json.dumps(env, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(env["software"], ensure_ascii=False, indent=1))
