# -*- coding: utf-8 -*-
"""진단용 Ollama 모델을 새 이름(``geoflow-diag-…``)으로 등록한다(결정 61). 기존 모델은 덮어쓰거나 지우지 않는다.

    python sft_dpo_inventory/conversion_diag/register_diag.py --model NAME --template {official,hf} --out REG.json
        (--gguf PATH | --from qwen3:8b) [--adapter LORA_GGUF]

- 방법은 ``pilot_001/ollama/register_model.py``와 같다(컨테이너가 호스트 경로를 못 보므로 ``ollama create``와 같은 일을 API로 한다).
  - ``--gguf``: GGUF를 ``/api/blobs``로 올리고 ``files``로 만든다.
  - ``--from qwen3:8b``: 공식 모델을 바탕으로 만든다(가중치 blob은 공식 모델의 것 그대로).
  - ``--adapter``: LoRA GGUF를 blob으로 올리고 ``adapters``로 얹는다(Modelfile ``ADAPTER``와 같음).
- TEMPLATE: ``hf``는 B-conv와 같은 ``pilot_prep_003/ollama/Modelfile.base.thinking``의 TEMPLATE.
  ``official``은 template을 보내지 않아 공식 qwen3:8b의 TEMPLATE을 이어받는다(``--from qwen3:8b``일 때만).
- PARAMETER: E(공식 qwen3:8b)와 같은 값(``Modelfile.base.thinking``의 PARAMETER = 공식 Modelfile 값)을 명시해서 보낸다.
- 기록: 이름, digest, 원천 파일 sha256, 보낸 Modelfile에 해당하는 내용, ``/api/show``의 template·parameters와 E의 것의 일치 여부.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_001/ollama"))
from register_model import MODELFILE, parse_modelfile  # noqa: E402

HOST = "http://localhost:11434"
OFFICIAL = "qwen3:8b"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 24), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upload(path):
    digest = sha256_file(path)
    blob = f"sha256:{digest}"
    if httpx.head(f"{HOST}/api/blobs/{blob}", timeout=30).status_code != 200:
        with Path(path).open("rb") as stream:
            response = httpx.post(f"{HOST}/api/blobs/{blob}", content=stream, timeout=None)
        if response.status_code not in (200, 201):
            raise SystemExit(f"blob upload failed: {response.status_code} {response.text[:300]}")
    return digest, blob


def modelfile_text(source, adapter, template, parameters):
    lines = [f"FROM {source}"]
    if adapter:
        lines.append(f"ADAPTER {adapter}")
    if template is not None:
        lines.append(f'TEMPLATE """{template}"""')
    for key, value in parameters.items():
        for v in (value if isinstance(value, list) else [value]):
            lines.append(f"PARAMETER {key} {json.dumps(v) if isinstance(v, str) else v}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--template", choices=["official", "hf"], required=True)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--gguf")
    src.add_argument("--from", dest="from_model", choices=[OFFICIAL])
    ap.add_argument("--adapter")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not args.model.startswith("geoflow-diag-"):
        raise SystemExit("진단 모델 이름은 geoflow-diag-로 시작해야 한다(결정 61)")
    if args.template == "official" and not args.from_model:
        raise SystemExit("official TEMPLATE은 --from qwen3:8b일 때만")
    names = {m["name"] for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
    if args.model in names:
        raise SystemExit(f"{args.model} already exists; not overwriting")
    hf_template, parameters = parse_modelfile(MODELFILE.read_text(encoding="utf-8"))
    template = hf_template if args.template == "hf" else None
    payload = {"model": args.model, "parameters": parameters, "stream": False}
    sources = {}
    if args.gguf:
        digest, blob = upload(args.gguf)
        payload["files"] = {Path(args.gguf).name: blob}
        sources["gguf"] = {"path": args.gguf, "sha256": digest}
        source_label = Path(args.gguf).name
    else:
        payload["from"] = OFFICIAL
        source_label = OFFICIAL
        show_official = httpx.post(f"{HOST}/api/show", json={"model": OFFICIAL}, timeout=30).json()
        tags = {m["name"]: m for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
        sources["from"] = {"model": OFFICIAL, "digest": tags[OFFICIAL]["digest"]}
    if args.adapter:
        digest, blob = upload(args.adapter)
        payload["adapters"] = {Path(args.adapter).name: blob}
        sources["adapter"] = {"path": args.adapter, "sha256": digest}
    if template is not None:
        payload["template"] = template
    response = httpx.post(f"{HOST}/api/create", json=payload, timeout=None)
    if response.status_code != 200:
        raise SystemExit(f"create failed: {response.status_code} {response.text[:500]}")
    tags = {m["name"]: m for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
    show = httpx.post(f"{HOST}/api/show", json={"model": args.model}, timeout=30).json()
    show_e = httpx.post(f"{HOST}/api/show", json={"model": OFFICIAL}, timeout=30).json()
    record = {
        "model": args.model, "digest": tags[args.model]["digest"], "details": tags[args.model]["details"],
        "ollama_version": httpx.get(f"{HOST}/api/version", timeout=10).json()["version"],
        "template_kind": args.template, "sources": sources,
        "modelfile": modelfile_text(source_label, Path(args.adapter).name if args.adapter else None,
                                    template, parameters),
        "template_sha256": hashlib.sha256(show.get("template", "").encode()).hexdigest(),
        "show_template_equals_official": show.get("template") == show_e.get("template"),
        "show_template_equals_hf": show.get("template") == hf_template,
        "show_parameters": show.get("parameters"),
        "show_parameters_equal_E": sorted((show.get("parameters") or "").split("\n")) ==
                                   sorted((show_e.get("parameters") or "").split("\n")),
        "capabilities": show.get("capabilities"),
        "method": "POST /api/blobs + POST /api/create (equivalent of ollama create)",
        "existing_models_untouched": sorted(names),
        "registered_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(args.out).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("model", "digest", "show_template_equals_official", "show_template_equals_hf",
                                             "show_parameters_equal_E", "capabilities")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
