"""X1·X2 teacher forcing 채점(PREREGISTRATION 3.1·3.3·3.4). GPU 작업 하나 = GPU 하나.

답안 모델(reader) 목록과 풀이 작성자 접두(prep_writers.py 출력)를 받아, (reader, writer, 문항)마다
    Δ = log P(이어지는 글이 tail+"," 로 시작) − log P(tail+"]" 로 시작)
와 log P(tail+',{"concept":"LOCATION"') − log P(tail+",")(이어 쓰는 분기에서 다음 concept가 LOCATION일 로그 확률)을 쓴다.
문자열 접두 확률은 모든 토큰화 경로의 합이다(string_logprob). 접두 = 평가와 같은 prompt id열(render_check.py로 해시 검증) +
풀이 원문 접두의 재토큰화. 문항 공통 prompt 접두의 KV는 reader마다 한 번 계산해 재사용한다(DynamicCache.crop).

    CUDA_VISIBLE_DEVICES=N python x12_score.py --readers READERS.json --writers writer_prefixes.jsonl \
        --prompt-ids prompt_ids_147.jsonl --pairs all|self|same_run --out OUT.jsonl
READERS.json: [{"name": "A-o1102-r1", "path": "/…/checkpoint-1984" 또는 null(base), "run": "A-o1102-r1"}, …]
--pairs all: 모든 writer, self: reader.run과 같은 writer만(자기 풀이), same_run: self와 같음(중간 체크포인트용 이름).
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

PRUNE = -40.0   # 경로 누적 로그 확률이 이보다 작으면 그 경로를 버린다(무시할 수 있는 크기, 결과에 기록)
CONT_SUFFIX, CLOSE_SUFFIX, LOC_SUFFIX = ",", "]", ',{"concept":"LOCATION"'


def token_bytes_table(tok):
    """id → 그 token이 디코딩되는 바이트열(byte-level BPE). 추가·특수 token은 None."""
    from transformers.models.gpt2.tokenization_gpt2 import bytes_to_unicode
    dec = {v: k for k, v in bytes_to_unicode().items()}
    special = set(tok.all_special_ids) | set(getattr(tok, "added_tokens_decoder", {}).keys())
    table = [None] * len(tok)
    for i in range(len(tok)):
        if i in special:
            continue
        t = tok.convert_ids_to_tokens(i)
        if t is None:
            continue
        try:
            table[i] = bytes(dec[ch] for ch in t)
        except KeyError:
            table[i] = None
    return table


class Candidates:
    """문자열 S(바이트)와 맞는 token: S의 접두인 token(계속 내려감)과 S를 접두로 갖는 token(거기서 끝)."""

    def __init__(self, table):
        self.by_first = {}
        for i, b in enumerate(table):
            if b:
                self.by_first.setdefault(b[0], []).append((i, b))

    def __call__(self, s):
        out_cont, out_end = [], []
        for i, b in self.by_first.get(s[0], ()):
            if len(b) >= len(s):
                if b.startswith(s):
                    out_end.append(i)
            elif s.startswith(b):
                out_cont.append((i, b))
        return out_cont, out_end


def logaddexp(a, b):
    if a == -math.inf:
        return b
    if b == -math.inf:
        return a
    m = max(a, b)
    return m + math.log(math.exp(a - m) + math.exp(b - m))


def string_logprob(s, logp, step, cands, acc=0.0, stats=None):
    """log P(다음에 이어지는 글이 바이트열 s로 시작). logp: 현재 위치의 다음 token 로그 확률(list/tensor 인덱싱 가능).
    step(token_id) → 그 token을 붙인 뒤의 logp를 돌려주는 함수(호출 뒤 원래 상태로 되돌리는 것은 step의 책임: 아래 Model.branch)."""
    cont, end = cands(s)
    total = -math.inf
    for i in end:
        total = logaddexp(total, float(logp[i]))
    for i, b in cont:
        lp = float(logp[i])
        if acc + lp < PRUNE:
            if stats is not None:
                stats["pruned"] = stats.get("pruned", 0) + 1
            continue
        with step(i) as logp2:
            if stats is not None:
                stats["forwards"] = stats.get("forwards", 0) + 1
            total = logaddexp(total, lp + string_logprob(s[len(b):], logp2, step, cands, acc + lp, stats))
    return total


class Model:
    """HF causal LM + KV cache. branch(token)은 token 하나를 붙여 logp를 주고, 끝나면 cache를 원래 길이로 자른다."""

    def __init__(self, model, device):
        import torch
        self.torch = torch
        self.model = model
        self.device = device
        self.cache = None

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

    def length(self):
        return 0 if self.cache is None else self.cache.get_seq_length()

    def crop(self, n):
        self.cache.crop(n)

    def branch(self, token_id):
        outer = self

        class _B:
            def __enter__(self_inner):
                self_inner.n = outer.length()
                return outer.forward([token_id])

            def __exit__(self_inner, *exc):
                outer.crop(self_inner.n)
                return False
        return _B()


def score_item(m, cands, prompt_tail_ids, prefix_ids, tail, stats):
    lp = m.forward(prompt_tail_ids + prefix_ids)
    t = tail.encode("utf-8")
    cont = string_logprob(t + CONT_SUFFIX.encode(), lp, m.branch, cands, 0.0, stats)
    close = string_logprob(t + CLOSE_SUFFIX.encode(), lp, m.branch, cands, 0.0, stats)
    loc = string_logprob(t + LOC_SUFFIX.encode(), lp, m.branch, cands, 0.0, stats)
    return cont, close, loc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--readers", required=True)
    ap.add_argument("--writers", required=True)
    ap.add_argument("--prompt-ids", required=True)
    ap.add_argument("--pairs", choices=("all", "self", "same_run"), required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="smoke용: reader마다 앞 N개만")
    args = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "sft_dpo_inventory/thinking_prep_001"))
    import hf_thinking as H

    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    table = token_bytes_table(tok)
    cands = Candidates(table)
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
    out = open(args.out, "a", encoding="utf-8")
    done = set()
    if Path(args.out).exists():
        for line in open(args.out, encoding="utf-8"):
            d = json.loads(line)
            done.add((d["reader"], d["writer"], d["id"]))
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
        ctx = peft_model.disable_adapter() if (r["path"] is None and peft_model is not None) else _null()
        rows = [w for w in writers if args.pairs == "all" or w["writer"] == r["run"]]
        if args.limit:
            rows = rows[:args.limit]
        with ctx:
            m = Model(net, device)
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
                stats = {}
                cont, close, loc = score_item(m, cands, prompts[w["id"]][common:], pids, w["tail"], stats)
                m.crop(common)
                out.write(json.dumps({"reader": r["name"], "reader_adapter_sha256": sha, "writer": w["writer"], "id": w["id"],
                                      "emitted": w["emitted"], "logp_cont": cont, "logp_close": close, "delta": cont - close,
                                      "logp_loc_given_cont": loc - cont, "forwards": stats.get("forwards", 0),
                                      "pruned": stats.get("pruned", 0), "prefix_tokens": len(pids)}) + "\n")
                n += 1
                if n % 200 == 0:
                    out.flush()
                    print(f"{r['name']} {n}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
            out.flush()
            print(f"{r['name']} done {n} rows {time.time() - t0:.0f}s", flush=True)
        if r["path"] and peft_model is not None:
            peft_model.delete_adapter(r["name"]) if len(peft_model.peft_config) > 1 else None
        torch.cuda.empty_cache()
    print(json.dumps({"done": True, "readers": len(readers), "prune_threshold": PRUNE}), flush=True)


class _null:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


if __name__ == "__main__":
    main()
