"""gguf_compare.py 보강(모델 호출 없음, CPU).
- E의 F16 텐서(attn_v 36개 층 전체)를 HF BF16과 원소 단위로 비교한다(bf16 → f16 변환이 무손실인지 포함).
- 같은 타입인 텐서마다 E와 B-conv의 양자화 바이트가 같은지 센다.
"""
import json
import sys

import numpy as np
from gguf import GGUFReader
from safetensors import safe_open

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from gguf_compare import HF, MODELS  # noqa: E402

out = sys.argv[1]
r = {m: {t.name: t for t in GGUFReader(p).tensors} for m, p in MODELS.items()}
index = json.load(open(f"{HF}/model.safetensors.index.json"))
f16 = []
for i in range(36):
    t = r["E"][f"blk.{i}.attn_v.weight"]
    name = f"model.layers.{i}.self_attn.v_proj.weight"
    with safe_open(f"{HF}/{index['weight_map'][name]}", framework="pt") as f:
        ref = f.get_tensor(name).float().numpy()
    e = np.asarray(t.data).astype(np.float32).reshape(ref.shape)
    f16.append({"layer": i, "type": t.tensor_type.name, "elements": int(ref.size),
                "equal_elements": int((e == ref).sum()), "max_abs_diff": float(np.abs(e - ref).max())})
same = {"same_type": 0, "byte_identical": 0, "by_type": {}}
for n, te in r["E"].items():
    tb = r["B-conv"][n]
    if te.tensor_type != tb.tensor_type:
        continue
    same["same_type"] += 1
    ident = bytes(np.asarray(te.data).tobytes()) == bytes(np.asarray(tb.data).tobytes())
    same["byte_identical"] += ident
    k = same["by_type"].setdefault(te.tensor_type.name, {"tensors": 0, "byte_identical": 0})
    k["tensors"] += 1
    k["byte_identical"] += ident
res = {"E_attn_v_f16_vs_hf_bf16": f16,
       "E_attn_v_all_equal": all(x["equal_elements"] == x["elements"] for x in f16),
       "E_vs_Bconv_same_type_tensors": same}
json.dump(res, open(out, "w"), indent=1)
print(res["E_attn_v_all_equal"], same)
