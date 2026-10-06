# -*- coding: utf-8 -*-
"""학습 모델(고른 SFT, 최종)의 Q4_K_M 변환본을 base 변환본과 같은 방식으로 새 이름에 등록한다(결정 20).

    python sft_dpo_inventory/pilot_001/ollama/register_model.py --model NAME --receipt GGUF_RECEIPT.json --out REGISTRATION.json

- ``pilot_prep_003/ollama/register_base.py``와 같다. 모델 이름, GGUF(변환 receipt의 Q4_K_M 경로·sha256), 결과 파일만 인자로 받는다.
  TEMPLATE·PARAMETER는 base와 같은 ``pilot_prep_003/ollama/Modelfile.base.thinking``에서 읽는다(FROM 줄은 쓰지 않는다).

- 컨테이너(`/root/.ollama`만 마운트)는 호스트 GGUF 경로를 볼 수 없다. 그래서 ``ollama create``와 같은 일을 Ollama API로 한다.
  1. ``POST /api/blobs/sha256:<digest>``로 GGUF를 올린다(sha256 f060d7cb… 대조).
  2. ``POST /api/create``에 ``files``(그 blob), ``template``, ``parameters``(``Modelfile.base.thinking``과 같은 값)를 보낸다.
- 새 이름 ``MODEL``이 이미 있으면 멈춘다. 기존 모델을 덮어쓰거나 지우지 않는다.
- 결과(``registration.json``): 이름, digest, 보낸 template·parameters의 sha256, Ollama 버전, ``/api/show``의 template과 보낸
  template이 같은지.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HERE = Path(__file__).resolve().parent
HOST = "http://localhost:11434"
MODELFILE = HERE.parents[1] / "pilot_prep_003/ollama/Modelfile.base.thinking"


def parse_modelfile(text):
    template = re.search(r'^TEMPLATE """(.*?)"""$', text, re.S | re.M).group(1)
    parameters = {"stop": []}
    for key, value in re.findall(r"^PARAMETER (\S+) (.+)$", text, re.M):
        value = value.strip()
        if key == "stop":
            parameters["stop"].append(json.loads(value))
        else:
            parameters[key] = float(value) if "." in value else int(value)
    return template, parameters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
    MODEL, GGUF, GGUF_SHA256 = args.model, Path(receipt["q4_k_m_gguf"]), receipt["q4_k_m_sha256"]
    names = {m["name"] for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
    if MODEL in names:
        raise SystemExit(f"{MODEL} already exists; not overwriting")
    digest = hashlib.sha256()
    with GGUF.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 24), b""):
            digest.update(chunk)
    if digest.hexdigest() != GGUF_SHA256:
        raise SystemExit("GGUF sha256 mismatch")
    blob = f"sha256:{GGUF_SHA256}"
    if httpx.head(f"{HOST}/api/blobs/{blob}", timeout=30).status_code != 200:
        with GGUF.open("rb") as stream:
            response = httpx.post(f"{HOST}/api/blobs/{blob}", content=stream, timeout=None)
        if response.status_code not in (200, 201):
            raise SystemExit(f"blob upload failed: {response.status_code} {response.text[:300]}")
    template, parameters = parse_modelfile(MODELFILE.read_text(encoding="utf-8"))
    payload = {"model": MODEL, "files": {GGUF.name: blob}, "template": template, "parameters": parameters,
               "stream": False}
    response = httpx.post(f"{HOST}/api/create", json=payload, timeout=None)
    if response.status_code != 200:
        raise SystemExit(f"create failed: {response.status_code} {response.text[:500]}")
    tags = {m["name"]: m for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
    show = httpx.post(f"{HOST}/api/show", json={"model": MODEL}, timeout=30).json()
    record = {
        "model": MODEL, "digest": tags[MODEL]["digest"], "details": tags[MODEL]["details"],
        "ollama_version": httpx.get(f"{HOST}/api/version", timeout=10).json()["version"],
        "gguf": str(GGUF), "gguf_sha256": GGUF_SHA256, "gguf_receipt": receipt, "modelfile": str(MODELFILE.relative_to(HERE.parents[2])),
        "modelfile_sha256": hashlib.sha256(MODELFILE.read_bytes()).hexdigest(),
        "template_sha256": hashlib.sha256(template.encode("utf-8")).hexdigest(), "parameters": parameters,
        "show_template_equals_sent": show.get("template") == template,
        "show_parameters": show.get("parameters"), "capabilities": show.get("capabilities"),
        "method": "POST /api/blobs + POST /api/create (equivalent of ollama create; container cannot read host path)",
        "existing_models_untouched": sorted(names),
        "registered_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(args.out).write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("model", "digest", "show_template_equals_sent", "capabilities")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
