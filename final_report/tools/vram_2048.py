# -*- coding: utf-8 -*-
"""최종 결과보고서 자체시험: 2,048-token 장문 질의 10건의 VRAM 할당·실사용 측정(새 파일, 기존 코드 수정 없음).

    python vram_2048.py build --out final_report/data/vram_inputs_2048.jsonl          # CPU, 실제 Qwen3-8B 토크나이저
    CUDA_VISIBLE_DEVICES=2 python vram_2048.py hf   --inputs ... --out ... [--adapter DIR]
    CUDA_VISIBLE_DEVICES=2 VLLM_ENABLE_V1_MULTIPROCESSING=0 python vram_2048.py vllm --inputs ... --out ... [--fp8] [--lora NAME=DIR]

입력(build): ``selection_gold.yaml``(평가 개발 셋, 보호 셋 아님)의 실제 교통 질의를 질의별로 다른 순서로 이어 붙인 사용자 메시지를
Qwen3 chat template(enable_thinking=True)으로 렌더링한 뒤, 템플릿 앞뒤를 보존하고 본문 token만 잘라 **prompt = 정확히 2,048 token**으로 만든다.
두 경로(HF·vLLM)에 같은 token id열을 그대로 넣는다. 생성은 greedy, 정확히 256 token(min=max, EOS 무시)이라 질의마다 처리 token = 2,304로 같다.

측정 정의(같은 시점·같은 범위):
- hf: 범위 = 이 프로세스의 PyTorch caching allocator. 질의마다 ``empty_cache``·``reset_peak_memory_stats`` 뒤 생성하고,
  같은 구간(그 질의 처리 전체)의 ``max_memory_reserved``(할당) 대 ``max_memory_allocated``(실사용 tensor)를 쓴다.
  (a) 프로세스 전체(가중치 포함), (b) 질의 증분(질의 직전 값을 뺀 값) 두 가지를 남긴다.
  decode step마다 같은 순간의 (allocated, reserved) 쌍도 표본으로 남긴다.
- vllm: 범위 = 그 질의에 배정된 KV cache(PagedAttention block). engine step마다 같은 순간에
  배정 block 수 × block_size × token당 KV 바이트(할당) 대 KV가 실제로 채워진 token 수(num_computed_tokens) × token당 KV 바이트(실사용).
  질의별 값은 배정 block이 가장 많은 순간(처리 끝 직전). 미리 잡아 둔 KV pool 전체(gpu_memory_utilization)는 할당으로 보지 않고 참고로만 남긴다.
  prefix caching은 꺼서 질의 사이 block 공유가 없게 한다.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "Qwen/Qwen3-8B"
REV = "b968826d9c46dd6066d109eabc6255188de91218"
PROMPT_TOKENS = 2048
GEN_TOKENS = 256
N = 10
KST = ZoneInfo("Asia/Seoul")
MIB = 1024 ** 2


def now():
    return datetime.now(KST).isoformat()


def build(args):
    import random
    import yaml
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    gold = yaml.safe_load((ROOT / "sft_dpo_inventory/conversion_diag/selection_gold.yaml").read_text(encoding="utf-8"))["items"]
    header = "다음은 택시 운행 데이터 분석 시스템에 들어온 교통 질의 목록이다. 각 질의의 장소·기간·측정값·집계 단위를 정리하라.\n\n"
    # 템플릿 앞뒤(본문을 비운 렌더링)를 구해 두고 본문 token만 자른다.
    marker = "\u0000MARK\u0000"
    tmpl = tok.apply_chat_template([{"role": "user", "content": marker}], tokenize=False, add_generation_prompt=True, enable_thinking=True)
    pre_text, post_text = tmpl.split(marker)
    pre = tok(pre_text, add_special_tokens=False)["input_ids"]
    post = tok(post_text, add_special_tokens=False)["input_ids"]
    budget = PROMPT_TOKENS - len(pre) - len(post)
    out = []
    for q in range(N):
        order = list(range(len(gold)))
        random.Random(20261124 + q).shuffle(order)
        lines, used = [], []
        body_ids = []
        for k, idx in enumerate(order):
            lines.append(f"{k + 1}. {gold[idx]['question']}")
            used.append(gold[idx]["id"])
            body_ids = tok(header + "\n".join(lines), add_special_tokens=False)["input_ids"]
            if len(body_ids) >= budget:
                break
        ids = pre + body_ids[:budget] + post
        assert len(ids) == PROMPT_TOKENS, len(ids)
        out.append({"qid": f"L{q + 1:02d}", "prompt_tokens": len(ids), "source_question_ids": used,
                    "body_text_untruncated_chars": len(header + "\n".join(lines)), "prompt_token_ids": ids,
                    "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
                    "decoded_prompt": tok.decode(ids)})
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"inputs": len(out), "prompt_tokens": [r["prompt_tokens"] for r in out], "template_tokens": len(pre) + len(post),
                      "tokenizer": f"{MODEL}@{REV}"}, ensure_ascii=False))


def load_inputs(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def run_hf(args):
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, StoppingCriteria, StoppingCriteriaList
    t = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REV, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to("cuda")
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    load_s = time.perf_counter() - t
    after_load = {"allocated_mib": torch.cuda.memory_allocated() / MIB, "reserved_mib": torch.cuda.memory_reserved() / MIB}
    inputs = load_inputs(args.inputs)

    class Sampler(StoppingCriteria):
        def __init__(self):
            self.samples = []

        def __call__(self, input_ids, scores, **kw):
            self.samples.append((torch.cuda.memory_allocated(), torch.cuda.memory_reserved()))
            return torch.zeros(input_ids.shape[0], dtype=torch.bool, device=input_ids.device)

    def one(r, phase):
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        a0, r0 = torch.cuda.memory_allocated(), torch.cuda.memory_reserved()
        ids = torch.tensor([r["prompt_token_ids"]], device="cuda")
        s = Sampler()
        t0 = time.perf_counter()
        with torch.no_grad():
            out = model.generate(ids, attention_mask=torch.ones_like(ids), do_sample=False, max_new_tokens=GEN_TOKENS,
                                 min_new_tokens=GEN_TOKENS, use_cache=True, stopping_criteria=StoppingCriteriaList([s]),
                                 pad_token_id=151643)
        torch.cuda.synchronize()
        sec = time.perf_counter() - t0
        pa, pr = torch.cuda.max_memory_allocated(), torch.cuda.max_memory_reserved()
        gen = out.shape[1] - ids.shape[1]
        step_waste = [(rr - aa) / rr * 100 for aa, rr in s.samples if rr]
        row = {"phase": phase, "qid": r["qid"], "prompt_tokens": ids.shape[1], "generated_tokens": int(gen), "seconds": round(sec, 3),
               "before_allocated_mib": round(a0 / MIB, 1), "before_reserved_mib": round(r0 / MIB, 1),
               "peak_allocated_mib": round(pa / MIB, 1), "peak_reserved_mib": round(pr / MIB, 1),
               "process_waste_pct": round((pr - pa) / pr * 100, 3),
               "query_alloc_mib": round((pa - a0) / MIB, 1), "query_reserved_mib": round((pr - r0) / MIB, 1),
               "query_waste_pct": round(((pr - r0) - (pa - a0)) / (pr - r0) * 100, 3) if pr > r0 else None,
               "decode_step_samples": len(s.samples),
               "decode_step_waste_pct_min_mean_max": [round(min(step_waste), 3), round(sum(step_waste) / len(step_waste), 3), round(max(step_waste), 3)] if step_waste else None,
               "output_sha256": hashlib.sha256(json.dumps(out[0, ids.shape[1]:].tolist()).encode()).hexdigest()}
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return row

    warm = one(inputs[0], "warmup")
    rows = [one(r, "measure") for r in inputs]
    p = torch.cuda.get_device_properties(0)
    meta = {"backend": "hf", "label": args.label, "model": f"{MODEL}@{REV}", "adapter": args.adapter, "dtype": "bfloat16", "attention": "sdpa",
            "torch": torch.__version__, "transformers": transformers.__version__, "gpu": p.name, "gpu_uuid": "GPU-" + str(p.uuid),
            "gpu_total_mib": round(p.total_memory / MIB), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "PYTORCH_CUDA_ALLOC_CONF": os.environ.get("PYTORCH_CUDA_ALLOC_CONF"), "load_seconds": round(load_s, 2), "after_load": after_load,
            "gen_tokens": GEN_TOKENS, "decoding": "greedy, min_new_tokens=max_new_tokens", "inputs": args.inputs, "finished_at": now(), "argv": sys.argv}
    Path(args.out).write_text(json.dumps({"meta": meta, "warmup": [warm], "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


def run_vllm(args):
    assert os.environ.get("VLLM_ENABLE_V1_MULTIPROCESSING") == "0", "in-process engine needed to read the scheduler"
    import torch
    import vllm
    from vllm import LLM, SamplingParams
    kw = dict(model=MODEL, revision=REV, dtype="bfloat16", max_model_len=17408, gpu_memory_utilization=0.85, seed=0,
              enable_prefix_caching=False, attention_backend="FLASHINFER", generation_config="vllm")
    lora = None
    if args.fp8:
        kw["quantization"] = "fp8"
    if args.lora:
        from vllm.lora.request import LoRARequest
        name, path = args.lora.split("=", 1)
        kw.update(enable_lora=True, max_lora_rank=16, max_loras=1)
        lora = LoRARequest(name, 1, path)
    t = time.perf_counter()
    llm = LLM(**kw)
    load_s = time.perf_counter() - t
    engine = llm.llm_engine
    sched = engine.engine_core.engine_core.scheduler
    kvm = sched.kv_cache_manager
    cfg = kvm.kv_cache_config
    groups = []
    for g in cfg.kv_cache_groups:
        spec = g.kv_cache_spec
        groups.append({"layers": len(g.layer_names), "block_size": spec.block_size, "page_size_bytes": spec.page_size_bytes,
                       "spec": type(spec).__name__, "dtype": str(getattr(spec, "dtype", ""))})
    block_size = groups[0]["block_size"]
    bytes_per_block_all_layers = sum(g["layers"] * g["page_size_bytes"] for g in groups)
    bytes_per_token = bytes_per_block_all_layers / block_size
    pool_bytes = sum(t.size for t in cfg.kv_cache_tensors)
    inputs = load_inputs(args.inputs)
    sp = SamplingParams(temperature=0.0, max_tokens=GEN_TOKENS, min_tokens=GEN_TOKENS, ignore_eos=True)

    def one(r, n, phase):
        rid = f"{phase}-{r['qid']}-{n}"
        t0 = time.perf_counter()
        engine.add_request(rid, {"prompt_token_ids": r["prompt_token_ids"]}, sp, lora_request=lora)
        snaps, outs = [], None
        while engine.has_unfinished_requests():
            o = engine.step()
            for out in o:
                if out.finished:
                    outs = out
            for key, req in sched.requests.items():
                blocks = sum(len(b) for b in kvm.get_block_ids(key))
                snaps.append({"blocks": blocks, "computed_tokens": req.num_computed_tokens, "num_tokens": req.num_tokens,
                              "pool_free_blocks": kvm.block_pool.get_num_free_blocks(),
                              "torch_allocated_mib": torch.cuda.memory_allocated() / MIB, "torch_reserved_mib": torch.cuda.memory_reserved() / MIB})
        sec = time.perf_counter() - t0
        peak = max(snaps, key=lambda s: (s["blocks"], s["computed_tokens"]))
        alloc_b = peak["blocks"] * block_size * bytes_per_token
        used_b = peak["computed_tokens"] * bytes_per_token
        step_waste = [(s["blocks"] * block_size - s["computed_tokens"]) / (s["blocks"] * block_size) * 100 for s in snaps if s["blocks"]]
        gen_ids = list(outs.outputs[0].token_ids) if outs else []
        row = {"phase": phase, "qid": r["qid"], "prompt_tokens": len(r["prompt_token_ids"]), "generated_tokens": len(gen_ids), "seconds": round(sec, 3),
               "engine_steps": len(snaps), "peak_blocks": peak["blocks"], "block_size": block_size, "peak_computed_tokens": peak["computed_tokens"],
               "kv_allocated_mib": round(alloc_b / MIB, 3), "kv_used_mib": round(used_b / MIB, 3),
               "kv_waste_pct": round((alloc_b - used_b) / alloc_b * 100, 3),
               "step_waste_pct_min_mean_max": [round(min(step_waste), 3), round(sum(step_waste) / len(step_waste), 3), round(max(step_waste), 3)],
               "pool_blocks_used_at_peak": cfg.num_blocks - peak["pool_free_blocks"],
               "torch_allocated_mib_at_peak": round(peak["torch_allocated_mib"], 1), "torch_reserved_mib_at_peak": round(peak["torch_reserved_mib"], 1),
               "output_sha256": hashlib.sha256(json.dumps(gen_ids).encode()).hexdigest()}
        print(json.dumps(row, ensure_ascii=False), flush=True)
        return row

    warm = one(inputs[0], 0, "warmup")
    rows = [one(r, 1, "measure") for r in inputs]
    p = torch.cuda.get_device_properties(0)
    meta = {"backend": "vllm", "label": args.label, "vllm": vllm.__version__, "torch": torch.__version__, "engine_kwargs": kw,
            "lora": args.lora, "gpu": p.name, "gpu_uuid": "GPU-" + str(p.uuid), "gpu_total_mib": round(p.total_memory / MIB),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "load_seconds": round(load_s, 2),
            "kv_cache_groups": groups, "kv_bytes_per_token": bytes_per_token, "kv_pool_blocks": cfg.num_blocks,
            "kv_pool_mib(reference only, not counted as allocation)": round(pool_bytes / MIB, 1),
            "gen_tokens": GEN_TOKENS, "decoding": "greedy, min_tokens=max_tokens, ignore_eos", "inputs": args.inputs, "finished_at": now(), "argv": sys.argv}
    Path(args.out).write_text(json.dumps({"meta": meta, "warmup": [warm], "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("build", "hf", "vllm"))
    ap.add_argument("--inputs", default=str(ROOT / "final_report/data/vram_inputs_2048.jsonl"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--fp8", action="store_true")
    ap.add_argument("--lora", default=None)
    args = ap.parse_args()
    if args.mode != "build" and Path(args.out).exists():
        raise SystemExit(f"output exists: {args.out}")
    {"build": build, "hf": run_hf, "vllm": run_vllm}[args.mode](args)


if __name__ == "__main__":
    main()
