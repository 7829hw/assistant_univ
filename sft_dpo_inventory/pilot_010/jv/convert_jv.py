# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273) 1단계 변환(CPU만, GPU·모델 호출 없음): adapter 병합 → BF16 GGUF → 공식 방식 Q4_K_M → 텐서 타입 대조 → 영수증.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/convert_jv.py [--only NAME,...] [--jobs 3]

- 절차는 기존 그대로(지시·PLAN_JV 1절): ``training.merge_adapter``(bfloat16, CPU; pilot_002 PLAN 78행과 같음) →
  ``pilot_prep_001/gguf_convert.sh``(바꾸지 않음; ``QUANT_RECIPE=official`` = ``llama-quantize --tensor-type attn_v=f16 … Q4_K_M``, imatrix 없음).
  llama.cpp는 결정 258의 rebuilt runtime ``runtime/native/llama.cpp-b11434``(commit 5e03bdd8, 결정 75와 같은 tag)와 ``runtime/envs/llamacpp``를 환경 변수
  (``LLAMA_CPP_DIR``·``VENV``)로 넘긴다(스크립트 기본 경로 /home/hwkim/sftdpo_work는 결정 258로 없어짐).
- base: 병합 없이 pilot_prep_001의 BF16 GGUF(sha256 ``4bed31be…``, 읽기만)에서 ``FROM_BF16``으로 양자화하고, 결정 75 base 공식 방식 Q4(``c55752ae…``)와 sha256이 같은지 적는다.
- adapter sha256을 학생 BF16 셀 기록(JG adapters_check_main)과 대조하고 다르면 그 모델을 멈춘다.
- 텐서 타입: ``compare_types_jv.types``로 공식 qwen3:8b blob(``a3de86cd…``, 읽기만)과 텐서 399개 이름·모양·타입 대조. 하나라도 다르면 ``types_equal_official`` false → 등록하지 않는다.
- Q4 확인(타입 같음) 뒤 병합본·BF16 GGUF(이 작업이 만든 것만)를 지운다. 영수증 ``jv/receipts/<name>.json``(저장소)과 gguf_convert 영수증 사본.
- 모든 가중치는 저장소 밖 ``/data/hwkim/sftdpo_work/pilot_010_jv/{merged,gguf}``.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import models_jv as M  # noqa: E402
import compare_types_jv as CT  # noqa: E402

ROOT = HERE.parents[2]
RT = Path("/data/hwkim/sftdpo_work/runtime")
HF_PY = RT / "envs/hf/bin/python"
LLAMA_DIR = RT / "native/llama.cpp-b11434"
LLAMA_VENV = RT / "envs/llamacpp"
OUT = M.JV / "gguf"
MERGED = M.JV / "merged"
LOGS = M.JV / "logs"
REC = HERE / "receipts"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def run(cmd, log, env=None):
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n== {now()} $ {' '.join(map(str, cmd))}\n")
        f.flush()
        t0 = time.time()
        rc = subprocess.run([str(c) for c in cmd], stdout=f, stderr=subprocess.STDOUT, env=env, cwd=ROOT).returncode
        f.write(f"== {now()} rc={rc} {round(time.time() - t0)}s\n")
    return rc, round(time.time() - t0, 1)


def convert(m):
    name = m["name"]
    log = LOGS / f"convert_{name}.log"
    rec = {"decision": 273, "model": m, "started_at": now(), "steps": {}}
    q4 = OUT / f"{name}-Q4_K_M-official.gguf"
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "QUANT_RECIPE": "official", "LLAMA_CPP_DIR": str(LLAMA_DIR), "VENV": str(LLAMA_VENV),
           "HF_HUB_OFFLINE": "1", "PYTHONPATH": str(ROOT)}
    made = []
    if m["adapter"]:
        got = sha(m["adapter"])
        rec["adapter_sha256_observed"], rec["adapter_sha256_ok"] = got, got == m["adapter_sha256"]
        if not rec["adapter_sha256_ok"]:
            rec["error"] = "adapter sha256 differs"
            return rec
        mdir = MERGED / name
        if mdir.exists():
            shutil.rmtree(mdir)
        cmd = [HF_PY, "-m", "training.merge_adapter", "--base", M.BASE_SNAPSHOT, "--adapter", Path(m["adapter"]).parent, "--output", mdir, "--dtype", "bfloat16"]
        rc, s = run(cmd, log, env)
        rec["steps"]["merge"] = {"command": " ".join(map(str, cmd)), "rc": rc, "seconds": s}
        if rc:
            rec["error"] = "merge failed"
            return rec
        made.append(mdir)
        src, extra = mdir, {}
        made.append(OUT / f"{name}-bf16.gguf")
    else:
        rec["base_bf16_gguf"] = {"path": str(M.BASE_BF16_GGUF), "sha256": sha(M.BASE_BF16_GGUF)}
        rec["base_bf16_gguf"]["prefix_ok"] = rec["base_bf16_gguf"]["sha256"].startswith(M.BASE_BF16_SHA)
        src, extra = M.BASE_SNAPSHOT, {"FROM_BF16": str(M.BASE_BF16_GGUF)}
    cmd = ["bash", ROOT / "sft_dpo_inventory/pilot_prep_001/gguf_convert.sh", src, OUT, name]
    rc, s = run(cmd, log, {**env, **extra})
    rec["steps"]["gguf_convert"] = {"command": " ".join(map(str, cmd)), "env": {k: env.get(k) or extra.get(k) for k in ("QUANT_RECIPE", "LLAMA_CPP_DIR", "VENV", "FROM_BF16") if (env.get(k) or extra.get(k))},
                                    "rc": rc, "seconds": s}
    if rc:
        rec["error"] = "gguf_convert failed"
        return rec
    rp = OUT / f"{name}.official.receipt.json"
    rec["gguf_receipt"] = json.loads(rp.read_text(encoding="utf-8"))
    rec["q4"] = {"path": str(q4), "sha256": sha(q4), "bytes": q4.stat().st_size}
    rec["q4"]["receipt_sha_matches"] = rec["q4"]["sha256"] == rec["gguf_receipt"]["q4_k_m_sha256"]
    if not m["adapter"]:
        rec["q4"]["equals_decision75_base_official"] = rec["q4"]["sha256"] == M.BASE_OFFICIAL_Q4_SHA
    t = CT.compare(str(q4))
    rec["types"] = t
    rec["types_equal_official"] = t["same_type"] == t["tensors"] == t["official_tensors"] and t["shape_diff"] == 0
    if rec["types_equal_official"] and rec["q4"]["receipt_sha_matches"]:
        rec["deleted_intermediates"] = []
        for p in made:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            rec["deleted_intermediates"].append(str(p))
    rec["finished_at"] = now()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    for d in (OUT, MERGED, LOGS, REC):
        d.mkdir(parents=True, exist_ok=True)
    ms = [m for m in M.all_models() if not a.only or m["name"] in a.only.split(",")]
    free = shutil.disk_usage(M.JV).free
    need = 40e9 * min(a.jobs, len(ms))
    print(json.dumps({"models": [m["name"] for m in ms], "disk_free_gb": round(free / 1e9, 1), "need_gb_at_once": round(need / 1e9, 1)}), flush=True)
    if free < need + 50e9:
        raise SystemExit("not enough disk")

    def one(m):
        r = convert(m)
        (REC / f"{m['name']}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"name": m["name"], "error": r.get("error"), "types_equal_official": r.get("types_equal_official"),
                          "q4_sha256": (r.get("q4") or {}).get("sha256", "")[:12], "deleted": len(r.get("deleted_intermediates") or [])}), flush=True)
        return r
    with ThreadPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, ms))
    bad = [r["model"]["name"] for r in res if r.get("error") or not r.get("types_equal_official")]
    print(json.dumps({"done": len(res), "bad": bad}), flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
