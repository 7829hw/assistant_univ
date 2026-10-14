# -*- coding: utf-8 -*-
"""vLLM 경로의 token 확률(결정 90·91, serving_vllm_fp8). serving_vllm/score_vllm.py의 사본에 정밀도·커널 인자를 더했다. 생성 없음.

    CUDA_VISIBLE_DEVICES=G vllmvenv/bin/python score_vllm2.py {base|final} {bf16|fp8} {fi|torch} OUT.bin
  (fi: attention FLASHINFER + VLLM_USE_FLASHINFER_SAMPLER=1, 환경 변수는 run_scores2.sh가 둔다. fp8: --quantization fp8과 같은 온라인 FP8)

- 엔진: vLLM 오프라인 ``LLM``(서버와 같은 dtype·max_model_len·LoRA 설정). ``final``은 pilot_003 최종 adapter를 LoRA로 붙인다.
- prefix cache는 끈다(같은 prompt를 여러 번 넣지 않지만, 채점값이 캐시 상태에 따라 달라지지 않게).
- 위치 t의 응답 token을 prompt_logprobs[t](위치 t−1까지 보고 낸 분포, logprobs_mode raw, 온도 1)로 채점하고,
  top-64는 rank 순으로 정리해 logprob_diag와 같은 이진 형식(target lp, top1, top-K id, top-K lp)으로 쓴다.
"""
import json
import struct
import sys
from pathlib import Path

WORK = Path("/data/hwkim/sftdpo_work/logprob_diag")
ADAPTER = "/home/hwkim/sftdpo_work/pilot_003/checkpoints/dpo/checkpoint-174/policy"
K = 64


def main():
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from vllm.lora.request import LoRARequest
    name, prec, ker, out_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    extra = {}
    if prec == "fp8":
        extra["quantization"] = "fp8"
    if ker == "fi":
        extra["attention_backend"] = "FLASHINFER"
    llm = LLM(model="Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218", dtype="bfloat16",
              max_model_len=16384, enable_lora=True, max_lora_rank=16, max_loras=1, max_logprobs=K,
              gpu_memory_utilization=0.85, enable_prefix_caching=False, seed=0, generation_config="vllm", **extra)
    lora = LoRARequest("final", 1, ADAPTER) if name == "final" else None
    params = SamplingParams(max_tokens=1, temperature=1.0, prompt_logprobs=K)
    seqs = [json.loads(line) for line in (WORK / "sequences.jsonl").read_text(encoding="utf-8").splitlines()]
    with open(out_path, "wb") as out:
        for s in seqs:
            ids, start = s["ids"], s["resp_start"]
            res = llm.generate(TokensPrompt(prompt_token_ids=ids), params, lora_request=lora, use_tqdm=False)[0]
            plp = res.prompt_logprobs
            count = len(ids) - start
            out.write(struct.pack("<ii", s["index"], count))
            for t in range(start, len(ids)):
                d = plp[t]
                ranked = sorted(((v.rank, k, v.logprob) for k, v in d.items() if v.rank is not None and v.rank <= K))[:K]
                top_ids = [k for _, k, _ in ranked]
                top_lps = [lp for _, _, lp in ranked]
                while len(top_ids) < K:   # 동률 등으로 모자라면 마지막 값으로 채운다(기록에 표시)
                    top_ids.append(top_ids[-1]); top_lps.append(top_lps[-1])
                out.write(struct.pack("<fi", float(d[ids[t]].logprob), int(top_ids[0])))
                out.write(struct.pack(f"<{K}i", *top_ids))
                out.write(struct.pack(f"<{K}f", *top_lps))
            print("seq", s["index"], "n", len(ids), "scored", count, flush=True)
    import torch
    print("device", torch.cuda.get_device_properties(0).name, "GPU-" + str(torch.cuda.get_device_properties(0).uuid))


if __name__ == "__main__":
    main()
