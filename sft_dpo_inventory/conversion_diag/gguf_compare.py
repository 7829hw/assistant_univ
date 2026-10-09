"""공식 qwen3:8b(E)와 직접 변환한 B-conv의 GGUF 비교(모델 호출 없음, CPU).

- 메타데이터: 이름·출처, file_type, imatrix 키, tokenizer 배열(sha256), chat_template(sha256).
- 텐서: 이름·모양·타입 전체 목록과 차이.
- 원본 가중치: 고른 텐서를 역양자화해 HF Qwen/Qwen3-8B@b968826d(BF16 safetensors)와 상대 오차·상관을 잰다.
  같은 측정을 B-conv(같은 HF 원본에서 만든 Q4_K_M)에도 해서 오차 수준을 비교한다.

실행: llamacpp_venv python(gguf-py, torch cpu, safetensors).
"""
import argparse
import hashlib
import json
from collections import Counter

import numpy as np
from gguf import GGUFReader
from gguf.quants import dequantize
from safetensors import safe_open

HF = "/home/hwkim/sftdpo_work/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218"
BLOBS = "/data/hwkim/ollama/models/blobs/sha256-"
MODELS = {
    "E": BLOBS + "a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f",
    "B-conv": BLOBS + "f060d7cbb5a2d45470b29af3df3d60662036f0fa97f851b63f7a55bb25935154",
}
LAYERS = [0, 1, 17, 18, 34, 35]
PARTS = {
    "attn_q": "self_attn.q_proj", "attn_k": "self_attn.k_proj", "attn_v": "self_attn.v_proj",
    "attn_output": "self_attn.o_proj", "ffn_gate": "mlp.gate_proj", "ffn_up": "mlp.up_proj",
    "ffn_down": "mlp.down_proj", "attn_norm": "input_layernorm", "attn_q_norm": "self_attn.q_norm",
}
SAMPLE = {"token_embd.weight": "model.embed_tokens.weight", "output.weight": "lm_head.weight",
          "output_norm.weight": "model.norm.weight"}
for i in LAYERS:
    for g, h in PARTS.items():
        SAMPLE[f"blk.{i}.{g}.weight"] = f"model.layers.{i}.{h}.weight"


def sha(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False).encode()).hexdigest()


def meta(reader):
    out = {}
    for k, f in reader.fields.items():
        if k.startswith("GGUF."):
            continue
        v = f.contents()
        if isinstance(v, list) and len(v) > 8:
            out[k] = {"len": len(v), "sha256": sha(v)}
        elif isinstance(v, str) and len(v) > 200:
            out[k] = {"len": len(v), "sha256": hashlib.sha256(v.encode()).hexdigest()}
        else:
            out[k] = v
    return out


def hf_tensor(index, name):
    shard = index["weight_map"][name]
    with safe_open(f"{HF}/{shard}", framework="pt") as f:
        return f.get_tensor(name).float().numpy()


def stats(a, b):
    a = a.astype(np.float64).ravel()
    b = b.astype(np.float64).ravel()
    d = a - b
    return {"rel_err": float(np.linalg.norm(d) / np.linalg.norm(b)),
            "corr": float(np.corrcoef(a, b)[0, 1]),
            "max_abs": float(np.abs(d).max())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    readers = {m: GGUFReader(p) for m, p in MODELS.items()}
    res = {"files": {m: {"path": p, "sha256": p.rsplit("-", 1)[1]} for m, p in MODELS.items()},
           "hf_snapshot": HF, "meta": {}, "tensors": {}}
    tens = {}
    for m, r in readers.items():
        res["meta"][m] = meta(r)
        tens[m] = {t.name: t for t in r.tensors}
        res["tensors"][m] = {"count": len(r.tensors),
                             "types": dict(Counter(t.tensor_type.name for t in r.tensors)),
                             "n_elements": int(sum(int(t.n_elements) for t in r.tensors))}
    keys = sorted(set(res["meta"]["E"]) | set(res["meta"]["B-conv"]))
    res["meta_diff"] = {k: {"E": res["meta"]["E"].get(k), "B-conv": res["meta"]["B-conv"].get(k)}
                        for k in keys if res["meta"]["E"].get(k) != res["meta"]["B-conv"].get(k)}
    res["imatrix_keys"] = {m: [k for k in res["meta"][m] if "imatrix" in k] for m in readers}
    names_e, names_b = set(tens["E"]), set(tens["B-conv"])
    res["names_only_E"] = sorted(names_e - names_b)
    res["names_only_B"] = sorted(names_b - names_e)
    shape_diff, type_diff = [], []
    for n in sorted(names_e & names_b):
        te, tb = tens["E"][n], tens["B-conv"][n]
        if list(te.shape) != list(tb.shape):
            shape_diff.append({"name": n, "E": list(map(int, te.shape)), "B-conv": list(map(int, tb.shape))})
        if te.tensor_type != tb.tensor_type:
            type_diff.append({"name": n, "E": te.tensor_type.name, "B-conv": tb.tensor_type.name})
    res["shape_diff"] = shape_diff
    res["type_diff"] = type_diff
    res["type_diff_patterns"] = dict(Counter(
        (".".join(d["name"].split(".")[2:3]) if d["name"].startswith("blk.") else d["name"]) + f": {d['E']} vs {d['B-conv']}"
        for d in type_diff))
    index = json.load(open(f"{HF}/model.safetensors.index.json"))
    rows = []
    for g, h in SAMPLE.items():
        ref = hf_tensor(index, h)
        row = {"gguf": g, "hf": h, "shape_hf": list(ref.shape)}
        deq = {}
        for m in readers:
            t = tens[m][g]
            w = dequantize(t.data, t.tensor_type).reshape(ref.shape)
            deq[m] = w
            row[m] = {"type": t.tensor_type.name, **stats(w, ref)}
        row["E_vs_B-conv"] = stats(deq["E"], deq["B-conv"])
        rows.append(row)
        print(g, row["E"]["type"], round(row["E"]["rel_err"], 5), row["B-conv"]["type"], round(row["B-conv"]["rel_err"], 5), flush=True)
    res["dequant_vs_hf"] = rows
    json.dump(res, open(args.out, "w"), ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
