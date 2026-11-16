"""x12_score.py와 같은 값(Δ, logp_loc_given_cont)을 tree attention으로 계산한다(PREREGISTRATION 3.1의 정의·PRUNE −40 그대로).

x12_score.py는 토큰화 경로 하나마다 token 하나짜리 forward를 차례로 부른다(문항당 약 111회). 여기서는 같은 경로 나무를 깊이별로 펼쳐,
한 깊이의 새 마디 전부를 forward 한 번에 넣는다. 각 새 token은 4D 마스크로 (문항 접두 전체 + 자기 조상 마디)만 보고, 위치 id는
접두 길이 + 깊이 − 1이다. 그래서 각 마디의 다음 token 분포는 순차 계산과 수학적으로 같다(bf16 커널 차이만 남는다).
가지치기 규칙도 같다: 부모까지 누적 로그 확률 + 그 token 로그 확률 < PRUNE이면 그 자식을 만들지 않는다.
세 목표 문자열(tail+",", tail+"]", tail+',{"concept":"LOCATION"')이 공유하는 마디는 한 번만 계산한다.

    CUDA_VISIBLE_DEVICES=N python x12_tree.py --readers R.json --writers writer_prefixes.jsonl --prompt-ids prompt_ids_147.jsonl \
        --pairs all|self|same_run --out OUT.jsonl [--limit N] [--only-writers-from X1.jsonl]
출력 행은 x12_score.py와 같은 키 + "method": "tree", "tree_nodes", "tree_depths".
"""
import argparse
import contextlib
import hashlib
import json
import math
import time
from pathlib import Path

from x12_score import CLOSE_SUFFIX, CONT_SUFFIX, LOC_SUFFIX, PRUNE, Candidates, logaddexp, token_bytes_table


def tree_logprobs(root_logp, targets, cands, eval_batch):
    """targets: 바이트열 목록. eval_batch(list of (parent_seq, token)) → 각 자식 마디의 다음 token 로그 확률 목록.
    돌려주는 것: (각 target의 log P(이어지는 글이 target으로 시작), stats)."""
    logp = {(): root_logp}
    acc = {(): 0.0}
    rem = {(): set(targets)}
    frontier = [()]
    stats = {"tree_nodes": 0, "tree_depths": 0, "pruned": 0}
    while frontier:
        new = {}
        for seq in frontier:
            lpv = logp[seq]
            for s in rem[seq]:
                cont, _ = cands(s)
                for i, b in cont:
                    lp = float(lpv[i])
                    if acc[seq] + lp < PRUNE:
                        stats["pruned"] += 1
                        continue
                    child = seq + (i,)
                    if child not in new:
                        new[child] = (acc[seq] + lp, set())
                    new[child][1].add(s[len(b):])
        if not new:
            break
        kids = list(new)
        outs = eval_batch([(k[:-1], k[-1]) for k in kids])
        for k, o in zip(kids, outs):
            logp[k] = o
            acc[k] = new[k][0]
            rem[k] = new[k][1]
        stats["tree_nodes"] += len(kids)
        stats["tree_depths"] += 1
        frontier = kids

    memo = {}

    def value(seq, s):
        key = (seq, s)
        if key in memo:
            return memo[key]
        lpv = logp[seq]
        cont, end = cands(s)
        total = -math.inf
        for i in end:
            total = logaddexp(total, float(lpv[i]))
        for i, b in cont:
            child = seq + (i,)
            if child in logp and s[len(b):] in rem[child]:
                total = logaddexp(total, float(lpv[i]) + value(child, s[len(b):]))
        memo[key] = total
        return total
    return [value((), t) for t in targets], stats


class TreeModel:
    def __init__(self, model, device):
        import torch
        self.torch = torch
        self.model = model
        self.device = device
        self.cache = None
        self.pos = {}      # 마디 seq → cache 위치
        self.base_len = 0

    def length(self):
        return 0 if self.cache is None else self.cache.get_seq_length()

    def crop(self, n):
        self.cache.crop(n)

    def forward(self, ids):
        torch = self.torch
        from transformers import DynamicCache
        if self.cache is None:
            self.cache = DynamicCache()
        x = torch.tensor([ids], device=self.device)
        with torch.no_grad():
            out = self.model(input_ids=x, past_key_values=self.cache, use_cache=True)
        self.cache = out.past_key_values
        return torch.log_softmax(out.logits[0, -1].float(), dim=-1).cpu()

    def start_item(self):
        self.base_len = self.length()
        self.pos = {}

    def eval_batch(self, items):
        torch = self.torch
        L = self.length()
        n = len(items)
        mask = torch.zeros((1, 1, n, L + n), dtype=torch.bool, device=self.device)
        mask[0, 0, :, :self.base_len] = True
        pos_ids = []
        for j, (parent, tok) in enumerate(items):
            for k in range(1, len(parent) + 1):
                mask[0, 0, j, self.pos[parent[:k]]] = True
            mask[0, 0, j, L + j] = True
            pos_ids.append(self.base_len + len(parent))
        x = torch.tensor([[t for _, t in items]], device=self.device)
        with torch.no_grad():
            out = self.model(input_ids=x, attention_mask=mask, position_ids=torch.tensor([pos_ids], device=self.device),
                             cache_position=torch.arange(L, L + n, device=self.device), past_key_values=self.cache, use_cache=True)
        self.cache = out.past_key_values
        for j, (parent, tok) in enumerate(items):
            self.pos[parent + (tok,)] = L + j
        lp = torch.log_softmax(out.logits[0].float(), dim=-1).cpu()
        return [lp[j] for j in range(n)]


def score_item_tree(m, cands, prompt_tail_ids, prefix_ids, tail):
    lp = m.forward(prompt_tail_ids + prefix_ids)
    m.start_item()
    t = tail.encode("utf-8")
    (cont, close, loc), stats = tree_logprobs(lp, [t + CONT_SUFFIX.encode(), t + CLOSE_SUFFIX.encode(), t + LOC_SUFFIX.encode()],
                                              cands, m.eval_batch)
    return cont, close, loc, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readers", required=True)
    ap.add_argument("--writers", required=True)
    ap.add_argument("--prompt-ids", required=True)
    ap.add_argument("--pairs", choices=("all", "self", "same_run"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="smoke용: reader마다 앞 N개만")
    args = ap.parse_args()

    import sys
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "sft_dpo_inventory/thinking_prep_001"))
    import hf_thinking as H

    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cands = Candidates(token_bytes_table(tok))
    prompts = {}
    for line in open(args.prompt_ids, encoding="utf-8"):
        d = json.loads(line)
        prompts[d["id"]] = d["prompt_ids"]
    first = next(iter(prompts.values()))
    common = len(first)
    for p in prompts.values():
        k = 0
        while k < min(common, len(p)) and p[k] == first[k]:
            k += 1
        common = k
    writers = [json.loads(line) for line in open(args.writers, encoding="utf-8")]
    readers = json.loads(Path(args.readers).read_text(encoding="utf-8"))

    device = "cuda:0"
    base = AutoModelForCausalLM.from_pretrained(H.MODEL, revision=H.REVISION, torch_dtype=torch.bfloat16,
                                                attn_implementation="sdpa").to(device).eval()
    peft_model = None
    done = set()
    if Path(args.out).exists():
        for line in open(args.out, encoding="utf-8"):
            d = json.loads(line)
            done.add((d["reader"], d["writer"], d["id"]))
    out = open(args.out, "a", encoding="utf-8")
    prefix_cache = {}
    for r in readers:
        if r["path"]:
            from peft import PeftModel
            if peft_model is None:
                peft_model = PeftModel.from_pretrained(base, r["path"], adapter_name=r["name"]).eval()
            else:
                peft_model.load_adapter(r["path"], adapter_name=r["name"])
            peft_model.set_adapter(r["name"])
            net = peft_model
            sha = hashlib.sha256(Path(r["path"], "adapter_model.safetensors").read_bytes()).hexdigest()
        else:
            net = base if peft_model is None else peft_model
            sha = None
        ctx = peft_model.disable_adapter() if (r["path"] is None and peft_model is not None) else contextlib.nullcontext()
        rows = [w for w in writers if args.pairs == "all" or w["writer"] == r["run"]]
        if args.limit:
            rows = rows[:args.limit]
        with ctx:
            m = TreeModel(net, device)
            m.forward(first[:common])
            t0 = time.time()
            n = 0
            for w in rows:
                key = (r["name"], w["writer"], w["id"])
                if key in done:
                    continue
                if w["prefix_text"] not in prefix_cache:
                    prefix_cache[w["prefix_text"]] = tok(w["prefix_text"], add_special_tokens=False)["input_ids"]
                pids = prefix_cache[w["prefix_text"]]
                cont, close, loc, stats = score_item_tree(m, cands, prompts[w["id"]][common:], pids, w["tail"])
                m.crop(common)
                out.write(json.dumps({"reader": r["name"], "reader_adapter_sha256": sha, "writer": w["writer"], "id": w["id"],
                                      "emitted": w["emitted"], "logp_cont": cont, "logp_close": close, "delta": cont - close,
                                      "logp_loc_given_cont": loc - cont, "method": "tree", **stats, "prefix_tokens": len(pids)}) + "\n")
                n += 1
                if n % 200 == 0:
                    out.flush()
                    print(f"{r['name']} {n}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
            out.flush()
            print(f"{r['name']} done {n} rows {time.time() - t0:.0f}s", flush=True)
        if r["path"] and peft_model is not None and len(peft_model.peft_config) > 1:
            peft_model.delete_adapter(r["name"])
        torch.cuda.empty_cache()
    print(json.dumps({"done": True, "readers": len(readers), "prune_threshold": PRUNE, "method": "tree"}), flush=True)


if __name__ == "__main__":
    main()
