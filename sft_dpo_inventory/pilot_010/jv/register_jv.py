# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 1절) Q4 GGUF를 JV 모델 디렉터리에 새 이름(``geoflow-jv-…``)으로 등록한다. GPU 없음, 생성 없음.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/register_jv.py [--only NAME,...]

- CPU 전용 Ollama 0.40.6 서버(JU 실행 파일, ``CUDA_VISIBLE_DEVICES=-1``, ``OLLAMA_VULKAN=false``, 포트 11460, ``OLLAMA_MODELS`` = ``pilot_010_jv/models``)를 잠깐 띄워
  ``conversion_diag/register_diag.py``(결정 61·75)와 같은 방법으로 ``POST /api/blobs`` + ``POST /api/create``(= ``ollama create``)를 하고 내린다. 기존 모델·컨테이너는 건드리지 않는다.
- Modelfile = 결정 75 hfthink: ``pilot_prep_003/ollama/Modelfile.base.thinking``의 TEMPLATE·PARAMETER(``pilot_001/ollama/register_model.parse_modelfile``) 그대로.
- 등록 조건: ``jv/receipts/<name>.json``의 ``types_equal_official`` true, Q4 sha256 = 영수증 값. 이미 있는 이름은 덮어쓰지 않는다.
- 기록 ``jv/registration/<name>.json``: digest, details, ``/api/show``의 template·parameters·capabilities·키 목록(renderer·parser 필드 유무), template = hfthink 여부,
  결정 75 base 공식 방식 Q4 등록(``quant_recipe/registration/base_official_q4.json``)의 template sha256(``a55ee1b1…``)과 같은지.
- manifest 확인(``manifest_check``): 0.40.6 ``/api/show``의 ``template`` 필드는 GGUF 안의 HF Jinja chat template을 보여 준다(결정 75 기록의 sha256 ``a55ee1b1…``도 그것).
  그래서 모델 디렉터리의 manifest를 직접 읽어 template 층 blob = 보낸 hfthink TEMPLATE, params 층, config(renderer·parser 키 없음), ``runner``를 기록한다.
  ``--verify``는 이미 등록한 이름의 기록에 manifest 확인만 더한다(등록하지 않음).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_001/ollama"))
import models_jv as M  # noqa: E402
from register_model import MODELFILE, parse_modelfile  # noqa: E402

BIN = "/data/hwkim/sftdpo_work/pilot_010_ju/ollama-0.40.6/bin/ollama"
PORT = 11460
HOST = f"http://127.0.0.1:{PORT}"
MODELS = M.JV / "models"
D75 = json.loads((ROOT / "sft_dpo_inventory/quant_recipe/registration/base_official_q4.json").read_text(encoding="utf-8"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def manifest_check(name, hf_template):
    repo, tag = name.split(":")
    mp = MODELS / "manifests-v2/ollama.com/library" / repo / tag
    man = json.loads(mp.read_text(encoding="utf-8"))
    blob = lambda d: MODELS / "blobs" / ("sha256-" + d.split(":", 1)[1])  # noqa: E731
    cfg = json.loads(blob(man["config"]["digest"]).read_text(encoding="utf-8"))
    lay = {l["mediaType"].rsplit(".", 1)[-1]: l for l in man["layers"]}
    tpl = blob(lay["template"]["digest"]).read_text(encoding="utf-8") if "template" in lay else None
    return {"manifest_path": str(mp), "manifest_sha256": hashlib.sha256(mp.read_bytes()).hexdigest(), "manifest": man, "config": cfg,
            "config_has_renderer_or_parser": any(k in cfg for k in ("renderer", "parser")), "runner": man.get("runner"),
            "template_layer_equals_sent_hfthink": tpl == hf_template, "template_layer_bytes": len(tpl.encode()) if tpl else None,
            "params_layer": json.loads(blob(lay["params"]["digest"]).read_text(encoding="utf-8")) if "params" in lay else None,
            "model_layer_digest": lay["model"]["digest"]}


def start():
    (M.JV / "home_reg").mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    log = open(M.JV / "logs/register_server.log", "a")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(M.JV / "home_reg"), "CUDA_VISIBLE_DEVICES": "-1", "OLLAMA_VULKAN": "false",
           "OLLAMA_HOST": f"127.0.0.1:{PORT}", "OLLAMA_MODELS": str(MODELS), "OLLAMA_NOPRUNE": "1"}
    p = subprocess.Popen([BIN, "serve"], env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            if httpx.get(f"{HOST}/api/version", timeout=2).status_code == 200:
                return p, env
        except httpx.HTTPError:
            pass
        time.sleep(1)
    p.kill()
    raise SystemExit("register server did not start")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    out = HERE / "registration"
    out.mkdir(exist_ok=True)
    hf_template, parameters = parse_modelfile(MODELFILE.read_text(encoding="utf-8"))
    if a.verify:
        for m in [m for m in M.all_models() if not a.only or m["name"] in a.only.split(",")]:
            rp = out / f"{m['name']}.json"
            if rp.exists():
                rec = json.loads(rp.read_text(encoding="utf-8"))
                rec["manifest_check"] = manifest_check(m["ollama"], hf_template)
                rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                print(json.dumps({"name": m["name"], **{k: rec["manifest_check"][k] for k in ("template_layer_equals_sent_hfthink", "config_has_renderer_or_parser", "runner")}}))
        return
    srv, env = start()
    try:
        version = httpx.get(f"{HOST}/api/version", timeout=10).json()["version"]
        if version != "0.40.6":
            raise SystemExit(f"version {version}")
        for m in [m for m in M.all_models() if not a.only or m["name"] in a.only.split(",")]:
            rp = HERE / "receipts" / f"{m['name']}.json"
            if not rp.exists():
                print(json.dumps({"name": m["name"], "skip": "no receipt"}), flush=True)
                continue
            r = json.loads(rp.read_text(encoding="utf-8"))
            names = {x["name"] for x in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
            if not r.get("types_equal_official") or m["ollama"] in names:
                print(json.dumps({"name": m["name"], "skip": "types differ" if not r.get("types_equal_official") else "exists"}), flush=True)
                continue
            q4 = r["q4"]["path"]
            d = sha(q4)
            if d != r["q4"]["sha256"]:
                raise SystemExit(f"{m['name']} q4 sha differs from receipt")
            blob = f"sha256:{d}"
            if httpx.head(f"{HOST}/api/blobs/{blob}", timeout=30).status_code != 200:
                with open(q4, "rb") as s:
                    resp = httpx.post(f"{HOST}/api/blobs/{blob}", content=s, timeout=None)
                if resp.status_code not in (200, 201):
                    raise SystemExit(f"blob upload failed {resp.status_code} {resp.text[:300]}")
            payload = {"model": m["ollama"], "files": {Path(q4).name: blob}, "template": hf_template, "parameters": parameters, "stream": False}
            resp = httpx.post(f"{HOST}/api/create", json=payload, timeout=None)
            if resp.status_code != 200:
                raise SystemExit(f"create failed {resp.status_code} {resp.text[:500]}")
            tags = {x["name"]: x for x in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
            show = httpx.post(f"{HOST}/api/show", json={"model": m["ollama"]}, timeout=30).json()
            tsha = hashlib.sha256((show.get("template") or "").encode()).hexdigest()
            rec = {"decision": 273, "model": m["ollama"], "name": m["name"], "digest": tags[m["ollama"]]["digest"], "details": tags[m["ollama"]]["details"],
                   "ollama_version": version, "models_dir": str(MODELS), "source_gguf": {"path": q4, "sha256": d, "bytes": Path(q4).stat().st_size},
                   "modelfile_source": str(MODELFILE.relative_to(ROOT)), "sent_template_sha256": hashlib.sha256(hf_template.encode()).hexdigest(),
                   "sent_parameters": parameters, "show_keys": sorted(show), "show_renderer": show.get("renderer"), "show_parser": show.get("parser"),
                   "show_template": show.get("template"), "show_template_sha256": tsha, "show_template_equals_sent": show.get("template") == hf_template,
                   "show_template_equals_decision75_base_official": tsha == D75["template_sha256"], "show_parameters": show.get("parameters"),
                   "show_capabilities": show.get("capabilities"), "show_details": show.get("details"),
                   "show_model_info_keys_sample": sorted((show.get("model_info") or {}))[:12],
                   "show_modelfile_head": "\n".join((show.get("modelfile") or "").splitlines()[:6]),
                   "method": "POST /api/blobs + POST /api/create (= ollama create, conversion_diag/register_diag.py와 같음)",
                   "existing_models_before": sorted(names), "manifest_check": manifest_check(m["ollama"], hf_template), "server_env": env, "registered_at": datetime.now().astimezone().isoformat(timespec="seconds")}
            (out / f"{m['name']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print(json.dumps({k: rec[k] for k in ("name", "digest", "show_renderer", "show_parser", "show_template_equals_sent",
                                                   "show_template_equals_decision75_base_official", "show_capabilities")}), flush=True)
    finally:
        srv.terminate()
        srv.wait(timeout=60)


if __name__ == "__main__":
    main()
