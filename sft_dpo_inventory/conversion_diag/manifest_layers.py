# -*- coding: utf-8 -*-
"""Ollama 모델의 manifest 층(가중치·adapter·TEMPLATE·PARAMETER blob digest)을 읽는다(모델 호출 없음).

    python sft_dpo_inventory/conversion_diag/manifest_layers.py --out OUT.json MODEL...

- Ollama 0.35.1의 ``/api/show`` ``template``은 저장된 TEMPLATE 층이 아니라 GGUF의 ``tokenizer.chat_template``을 보여 줄 때가 있다
  (B-conv 등록 때부터 ``show_template_equals_sent: false``). 그래서 실제로 쓰이는 TEMPLATE은 manifest의 template 층으로 확인한다.
- 저장소는 컨테이너의 ``/root/.ollama``가 마운트된 호스트 경로 ``/data/hwkim/ollama/models``다(읽기만 함).
"""
import argparse
import hashlib
import json
from pathlib import Path

STORE = Path("/data/hwkim/ollama/models")


def layers(model):
    name, tag = model.split(":")
    manifest = json.loads((STORE / "manifests/registry.ollama.ai/library" / name / tag).read_text())
    out = {"manifest_sha256": hashlib.sha256((STORE / "manifests/registry.ollama.ai/library" / name / tag).read_bytes()).hexdigest(),
           "layers": {}}
    for layer in manifest["layers"]:
        kind = layer["mediaType"].rsplit(".", 1)[1]
        entry = {"digest": layer["digest"], "size": layer["size"]}
        if kind in ("template", "params"):
            entry["content"] = (STORE / "blobs" / layer["digest"].replace(":", "-")).read_text()
        out["layers"].setdefault(kind, []).append(entry)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("models", nargs="+")
    args = ap.parse_args()
    res = {m: layers(m) for m in args.models}
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m, r in res.items():
        print(m, {k: [e["digest"][7:19] for e in v] for k, v in r["layers"].items() if k != "license"})


if __name__ == "__main__":
    main()
