# -*- coding: utf-8 -*-
"""HF 경로의 token 확률(결정 75, 작업 2). 고정 token id열만 넣는다(문자열을 다시 tokenize하지 않음). 생성 없음.

    CUDA_VISIBLE_DEVICES=3 HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python score_hf.py PATH_NAME OUT.bin

PATH_NAME:
- ``hf_base``: Qwen/Qwen3-8B@b968826d, BF16.
- ``hf_final_peft``: base + pilot_002 최종 adapter(DPO checkpoint-144 policy, PEFT, 병합하지 않음).
- ``hf_final_merged``: 병합본(``/data/hwkim/sftdpo_work/pilot_002/merged/final``, BF16).

평가와 같이 BF16·SDPA다. 위치 t(응답 구간)의 token을 위치 t−1의 logits(float32 log_softmax, 온도 1)로 채점하고,
token_logprobs.cpp와 같은 이진 형식(target lp, top1, top-K id, top-K lp)으로 쓴다.
"""
import json
import struct
import sys
from pathlib import Path

import torch

WORK = Path("/data/hwkim/sftdpo_work/logprob_diag")
BASE = "Qwen/Qwen3-8B"
REVISION = "b968826d9c46dd6066d109eabc6255188de91218"
ADAPTER = "/home/hwkim/sftdpo_work/pilot_002/checkpoints/dpo/checkpoint-144/policy"
MERGED = "/data/hwkim/sftdpo_work/pilot_002/merged/final"
K = 64


def load(name):
    from transformers import AutoModelForCausalLM
    kwargs = dict(torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    if name == "hf_final_merged":
        model = AutoModelForCausalLM.from_pretrained(MERGED, **kwargs)
    else:
        model = AutoModelForCausalLM.from_pretrained(BASE, revision=REVISION, **kwargs)
        if name == "hf_final_peft":
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, ADAPTER)
    return model.to("cuda").eval()


def main():
    name, out_path = sys.argv[1], sys.argv[2]
    model = load(name)
    seqs = [json.loads(line) for line in (WORK / "sequences.jsonl").read_text(encoding="utf-8").splitlines()]
    with open(out_path, "wb") as out, torch.inference_mode():
        for s in seqs:
            ids, start = s["ids"], s["resp_start"]
            count = len(ids) - start
            x = torch.tensor([ids[:-1]], device="cuda")
            logits = model(input_ids=x, logits_to_keep=count).logits[0].float()   # 위치 start-1 .. n-2
            lp = torch.log_softmax(logits, dim=-1)
            target = lp.gather(1, torch.tensor(ids[start:], device="cuda")[:, None])[:, 0]
            top_lp, top_id = lp.topk(K, dim=-1)
            out.write(struct.pack("<ii", s["index"], count))
            t, i1, ti, tl = (target.cpu().numpy(), top_id[:, 0].int().cpu().numpy(), top_id.int().cpu().numpy(),
                             top_lp.cpu().numpy())
            for p in range(count):
                out.write(struct.pack("<fi", float(t[p]), int(i1[p])))
                out.write(ti[p].astype("<i4").tobytes())
                out.write(tl[p].astype("<f4").tobytes())
            print("seq", s["index"], "n", len(ids), "scored", count, flush=True)
    print("device", torch.cuda.get_device_properties(0).name, "GPU-" + str(torch.cuda.get_device_properties(0).uuid))


if __name__ == "__main__":
    main()
