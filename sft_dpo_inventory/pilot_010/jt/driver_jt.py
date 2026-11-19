# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271, PLAN_JT 3–4절) 2단계 순차 실행기. 커밋에 고정한 worktree에서 hf env python으로 돌린다. **교사 참고 측정(판정 아님)**.

    runtime/envs/hf/bin/python <WT>/sft_dpo_inventory/pilot_010/jt/driver_jt.py --main /home/hwkim/assistant_univ [--from STEP]

순서(PLAN_JT 3절, 하나가 끝나면 바로 다음):
  1 smoke   서버 A(GPU 0·1)만, H-dev 앞 100문항 × 1, S, 동시 16(본 측정 H-final의 서버당 동시 수). 잘림 호출 ≥ 5% → STOPPED, 멈춤.
            범위 규칙: 예상 시간 = smoke wall × 30 / 2(서버 2벌) ≤ 5시간 → H-final 3,000 전체, 넘으면 ``hfinal_subset1000_ids.txt``. ``scope.json``.
  2 서버 B(GPU 2·3) 기동. 실패하면 서버 A만으로 계속(범위는 다시 계산하지 않음, 기록).
  3 S: PF2 k=1–4(동시 8) → H-final(범위, k=1, 동시 32).  4 G1: 같은 두 셋, PF2 k=4·H-final k=1.
  5 선택(각 셀 시작 시각 < OPTIONAL_DEADLINE일 때만, S, k=1, 동시 8): refusal_dev v2 120 → valid98 → aux(개발 셋 149 = 98 + 51).
  6 지연: 서버 B 내림 → 27B(서버 A, 동시 1, 고정 30문항, S) → 서버 A 내림 → 8B(GPU 0 하나, serve_a11.sh, LoRA RR+NM4 o101) base → RR+NM4 o101(동시 1).
            측정 중 30초마다 쓰지 않는 GPU에 프로세스가 있는지 보고, 있으면 그 셀을 멈추고 기록(latency6와 같은 규칙).
- 잘림 다시 돌리기(학생 셀과 같음, ``completeness_B``): H-final·H-dev 밖 셀 > 1%, refusal_dev v2 잘림 ≥ 2 또는 서버 오류 ≥ 2 → 같은 seed로 한 번, 원본은 replaced/.
  PF2는 다시 돌리지 않는다. smoke는 다시 돌리지 않는다.
- 기록: ``pilot_010/gpu/JT/``(runs.log·gpu_check.txt·timeline.jsonl·gpu_mem.jsonl·scope.json·RERUNS_JT.json·DONE|STOPPED). 셀: H-dev·H-final·rdev·dev·지연은
  ``pilot_010/cells/JT``(원문 ``training/generated/pilot_010/cells_raw_JT``), PF2는 700 디렉터리(``pf2jt_<cond>_t27_s<k>``, 저장소 밖).
- PF2 내용은 읽지 않는다(이 실행기는 PF2 셀을 열지 않음).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
KST = ZoneInfo("Asia/Seoul")
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
EXPECT_UUID = {0: "GPU-2445b100-70d8-e384-3a24-0249eeefc64d", 1: "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555",
               2: "GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e", 3: "GPU-48f798cc-9437-50ac-d604-448bbad7b311"}
OLLAMA_UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"
PORT_A, PORT_B, PORT_8B = 8700, 8701, 8710
WORK27 = Path("/data/hwkim/sftdpo_work/pilot_010_jt/vllm")
WORK8 = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
PF_GOLD = "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"
PF_CELLS, PF_RAW = Path("/data/hwkim/sftdpo_work/protected_final_v2/cells"), Path("/data/hwkim/sftdpo_work/protected_final_v2/raw")
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
RDEV_GOLD = "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"
VALID98_GOLD = "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml"
AUX_GOLD = "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"
LAT_IDS_FILE = "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt"
V4_O101 = "/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984"
V4_O101_SHA = "6402ba63352e1f21591a1625c9bcf0635211d2ea0d3d2870c22d3e50343d9a1d"  # FREEZE_JP.json 기록(JG adapters_check_main.json에서 일치 확인)
OPTIONAL_DEADLINE = datetime(2026, 11, 20, 21, 0, tzinfo=KST)
SMOKE_N, SMOKE_STOP_PCT, SCOPE_HOURS = 100, 5.0, 5.0
STEPS = ("smoke", "serverB", "S", "G1", "optional", "latency")


def now():
    return datetime.now(KST)


class Ctx:
    def __init__(self, main):
        self.main = Path(main)
        self.G = self.main / "sft_dpo_inventory/pilot_010/gpu/JT"
        self.cells = self.main / "sft_dpo_inventory/pilot_010/cells/JT"
        self.raw = self.main / "training/generated/pilot_010/cells_raw_JT"
        for d in (self.G, self.cells, self.raw, self.cells / "smoke", self.cells / "latency"):
            d.mkdir(parents=True, exist_ok=True)
        self.env = {**os.environ, "OLLAMA_UUID": OLLAMA_UUID, "ALLOWED_UUIDS": " ".join(EXPECT_UUID.values()), "P3": str(self.G),
                    "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
        self.env.pop("LORAS", None)
        self.step = "init"
        self.attn_auto = False
        self.servers = {}

    def log(self, msg):
        line = f"== [jt] {msg} {now().isoformat(timespec='seconds')}"
        with open(self.G / "runs.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line, flush=True)

    def tl(self, **ev):
        with open(self.G / "timeline.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": now().isoformat(timespec="seconds"), "step": self.step, **ev}, ensure_ascii=False) + "\n")


def smi(query, kind="gpu"):
    q = "--query-gpu" if kind == "gpu" else "--query-compute-apps"
    out = subprocess.run(["nvidia-smi", f"{q}={query}", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    return [[x.strip() for x in l.split(",")] for l in out.strip().splitlines() if l.strip()]


def uuid_map():
    return {int(i): u for i, u in smi("index,uuid")}


def procs_on(indices):
    m = uuid_map()
    want = {m[i] for i in indices}
    return [p for p in smi("gpu_uuid,pid,used_memory,process_name", "apps") if p and p[0] in want]


def mem_sampler(ctx, stop):
    while not stop.is_set():
        try:
            rows = smi("index,memory.used,utilization.gpu")
            with open(ctx.G / "gpu_mem.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now().isoformat(timespec="seconds"), "step": ctx.step, "gpus": rows}) + "\n")
        except Exception:  # noqa: BLE001
            pass
        stop.wait(30)


# ---------------- 서버 ----------------
def start27(ctx, ga, gb, port):
    ctx.log(f"start server27 GPU {ga},{gb} port {port}")
    rc = subprocess.run(["bash", str(HERE / "serve27.sh"), str(ga), str(gb), str(port)], env=ctx.env, cwd=WT,
                        stdout=open(ctx.G / f"serve27_{port}.out", "a"), stderr=subprocess.STDOUT).returncode
    ctx.tl(event="server_start", port=port, gpus=[ga, gb], rc=rc)
    if rc != 0 and not ctx.attn_auto:
        ctx.log(f"server27 port {port} failed with FLASHINFER -> retry once with automatic attention backend (PLAN_JT 7절)")
        ctx.attn_auto = True
    if rc != 0 and ctx.attn_auto and ctx.env.get("ATTN") != "auto":
        ctx.env["ATTN"] = "auto"
        for _ in range(60):
            if not procs_on([ga, gb]):
                break
            time.sleep(2)
        rc = subprocess.run(["bash", str(HERE / "serve27.sh"), str(ga), str(gb), str(port)], env=ctx.env, cwd=WT,
                            stdout=open(ctx.G / f"serve27_{port}.out", "a"), stderr=subprocess.STDOUT).returncode
        ctx.tl(event="server_start", port=port, gpus=[ga, gb], rc=rc, attn="auto")
    if rc == 0:
        ctx.servers[port] = WORK27 / f"server_{port}.pid"
        shutil.copy(WORK27 / f"server_{port}.json", ctx.G / f"server_{port}.json")
    return rc == 0


def start8(ctx, g, port, loras):
    ctx.log(f"start server8 GPU {g} port {port} LORAS {loras}")
    env = dict(ctx.env, LORAS=loras, MAX_LORA_RANK="16")
    rc = subprocess.run(["bash", str(WT / "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh"), str(g), str(port), "bf16", "fi"], env=env, cwd=WT,
                        stdout=open(ctx.G / f"serve8_{port}.out", "a"), stderr=subprocess.STDOUT).returncode
    ctx.tl(event="server_start", port=port, gpus=[g], rc=rc, loras=loras)
    if rc == 0:
        ctx.servers[port] = WORK8 / f"server_{port}.pid"
        shutil.copy(WORK8 / f"server_{port}.json", ctx.G / f"server_{port}.json")
    return rc == 0


def stop_server(ctx, port, gpus):
    pidf = ctx.servers.pop(port, None)
    if pidf and pidf.exists():
        pid = int(pidf.read_text().strip())
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass
        for _ in range(120):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(2)
    for _ in range(90):
        if not procs_on(gpus):
            break
        time.sleep(2)
    ctx.tl(event="server_stop", port=port, gpus=gpus, left=procs_on(gpus))
    ctx.log(f"stop server port {port} GPUs {gpus} left={procs_on(gpus)}")


# ---------------- 셀 ----------------
def cell_cmd(ctx, *, label, k, cond, gold, conc, ports, out_dir, raw_dir, only=None, sealed=False, ref_date=None, all_items=False):
    c = [PY, str(HERE / "run_cell_jt.py"), "--ports", ",".join(map(str, ports)), "--cond", cond, "--model", "teacher27", "--label", label, "--k", str(k),
         "--concurrency", str(conc), "--out-dir", str(out_dir), "--raw-dir", str(raw_dir), "--seed-base", "20261100", "--gold", gold, "--work", str(WORK27)]
    if all_items:
        c.append("--all-items")
    if only:
        c += ["--only", only]
    if sealed:
        c.append("--sealed")
    if ref_date:
        c += ["--reference-date", ref_date]
    return c


def run(ctx, name, cmd, umask=None, watch=None):
    """watch: 측정 중 비어 있어야 할 GPU 번호(지연 셀). 위반이면 멈추고 False."""
    ctx.log(f"cell start {name}")
    ctx.tl(event="cell_start", cell=name)
    t0 = time.time()
    pre = (lambda: os.umask(umask)) if umask is not None else None
    proc = subprocess.Popen(cmd, cwd=WT, env=ctx.env, stdout=open(ctx.G / f"{name}.log", "w"), stderr=subprocess.STDOUT, preexec_fn=pre)
    violation = None
    while proc.poll() is None:
        time.sleep(30)
        if watch is not None and procs_on(watch):
            violation = procs_on(watch)
            proc.terminate()
            break
    rc = proc.wait()
    ctx.tl(event="cell_end", cell=name, rc=rc, seconds=round(time.time() - t0, 1), violation=violation)
    ctx.log(f"cell end {name} rc={rc} {round(time.time() - t0)}s" + (f" VIOLATION {violation}" if violation else ""))
    return rc == 0 and violation is None


def rerun_check(ctx, label, k, kind, cmd, umask=None):
    """학생 셀과 같은 다시 돌리기 규칙(scheduler20 ``rerun_needed``). 필요하면 원본을 replaced/로 옮기고 같은 명령으로 한 번."""
    sys.path.insert(0, str(WT / "sft_dpo_inventory/pilot_007/results"))
    import completeness_B as CB
    CB.CELLS = ctx.cells
    r = CB.cell(label, k)
    if not r.get("exists"):
        return
    need = ((r.get("truncated_calls") or 0) >= 2 or r.get("server_error_rows", 0) >= 2) if kind == "rdev" else bool(r["rerun"])
    rp = ctx.G / "RERUNS_JT.json"
    rec = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {"rule": "학생 셀과 같음: rdev 잘림 ≥ 2 또는 서버 오류 ≥ 2, 그 밖 > 1%; 같은 seed 한 번, 원본 replaced/, 결과와 무관하게 교체; PF2·smoke 없음", "reruns": {}}
    name = f"{label}_s{k}"
    if not need or name in rec["reruns"]:
        return
    (ctx.cells / "replaced").mkdir(exist_ok=True)
    (ctx.raw / "replaced").mkdir(exist_ok=True)
    for src, dst in ((ctx.cells / f"{name}.json", ctx.cells / "replaced"), (ctx.cells / f"{name}.log", ctx.cells / "replaced"), (ctx.raw / f"{name}_raw.jsonl", ctx.raw / "replaced")):
        if src.exists():
            shutil.move(str(src), str(dst / src.name))
    rec["reruns"][name] = {"truncated_calls": r.get("truncated_calls"), "raw_lines": r.get("raw_lines"), "truncated_pct": r.get("truncated_pct"),
                           "server_error_rows": r.get("server_error_rows"), "rule": "rdev ≥ 2" if kind == "rdev" else "> 1%", "original_sha256": r.get("sha256"),
                           "moved_to": "cells/JT/replaced/", "queued": now().isoformat(timespec="seconds")}
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ok = run(ctx, f"R-{name}", cmd, umask=umask)
    rec["reruns"][name]["rerun_ok"] = ok
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------- 단계 ----------------
def step_smoke(ctx):
    import yaml
    ids = [i["id"] for i in yaml.safe_load((WT / HDEV_GOLD).read_text(encoding="utf-8"))["items"]][:SMOKE_N]
    if not start27(ctx, 0, 1, PORT_A):
        raise SystemExit("server A failed")
    out = ctx.cells / "smoke"
    cmd = cell_cmd(ctx, label="hdev100jt_s_t27", k=1, cond="s", gold=HDEV_GOLD, conc=16, ports=[PORT_A], out_dir=out, raw_dir=ctx.raw, only=",".join(ids))
    if not run(ctx, "smoke_hdev100", cmd):
        raise SystemExit("smoke cell failed")
    d = json.loads((out / "hdev100jt_s_t27_s1.json").read_text(encoding="utf-8"))
    rows = d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    trunc = sum(c.get("finish_reason") == "length" for c in calls)
    pct = 100.0 * trunc / max(1, len(calls))
    wall = d["meta"]["vllm"]["wall_seconds"]
    est_h = wall * (3000 / SMOKE_N) / 2 / 3600
    gen = sum(c.get("generated_tokens") or 0 for c in calls)
    rec = {"decision": 271, "label": "교사 참고 측정 smoke(H-dev 개발 셋); 정답률은 기록만, 어떤 설정도 이 값으로 조정하지 않음",
           "items": len(rows), "calls": len(calls), "truncated_calls": trunc, "truncated_pct": round(pct, 4),
           "think_unclosed_calls": sum(c.get("think_closed") is False for c in calls),
           "echo_mismatch_calls": sum(c.get("prompt_ids_echo_equal") is False for c in calls),
           "error_rows": sum(1 for r in rows if r.get("error_code")), "error_codes": sorted({r.get("error_code") for r in rows if r.get("error_code")}),
           "wall_seconds": wall, "items_per_hour_server_A": round(len(rows) / wall * 3600, 1), "generated_tokens": gen,
           "output_tok_per_s_server_A": round(gen / wall, 1), "accuracy_pct_report_only": round(100 * sum(r.get("category") == "match" for r in rows) / len(rows), 2),
           "stop_rule": f"truncated_pct >= {SMOKE_STOP_PCT} -> stop", "scope_rule": f"est_hours = wall x 3000/{SMOKE_N} / 2 <= {SCOPE_HOURS} -> full 3000, else subset 1000",
           "est_hfinal_3000_hours_two_servers": round(est_h, 3)}
    rec["stopped"] = pct >= SMOKE_STOP_PCT
    rec["scope"] = None if rec["stopped"] else ("full3000" if est_h <= SCOPE_HOURS else "subset1000")
    (ctx.G / "scope.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ctx.log(f"smoke truncated {trunc}/{len(calls)} = {pct:.2f}% est {est_h:.2f} h scope {rec['scope']}")
    if rec["stopped"]:
        stop_server(ctx, PORT_A, [0, 1])
        (ctx.G / "STOPPED").write_text(json.dumps({"at": "smoke", "reason": f"truncation {pct:.2f}% >= 5%", "t": now().isoformat()}) + "\n")
        raise SystemExit(2)


def ports_up(ctx):
    return [p for p in (PORT_A, PORT_B) if p in ctx.servers]


def hfinal_only(ctx):
    scope = json.loads((ctx.G / "scope.json").read_text(encoding="utf-8"))["scope"]
    if scope == "full3000":
        return None
    return (HERE / "hfinal_subset1000_ids.txt").read_text(encoding="utf-8").strip()


def step_cond(ctx, cond):
    ports = ports_up(ctx)
    for k in range(1, 5):
        label = f"pf2jt_{cond}_t27"
        if (PF_CELLS / f"{label}_s{k}.json").exists():
            continue
        cmd = ["bash", "-c", "umask 077 && exec " + " ".join(cell_cmd(ctx, label=label, k=k, cond=cond, gold=PF_GOLD, conc=8, ports=ports, out_dir=PF_CELLS,
                                                                      raw_dir=PF_RAW, sealed=True, ref_date="2026-10-26", all_items=True))]
        run(ctx, f"{label}_s{k}", cmd)
    label = f"hfinaljt_{cond}_t27"
    only = hfinal_only(ctx)
    if not (ctx.cells / f"{label}_s1.json").exists():
        cmd = cell_cmd(ctx, label=label, k=1, cond=cond, gold=HF_GOLD, conc=32, ports=ports, out_dir=ctx.cells, raw_dir=ctx.raw, sealed=True,
                       only=only, all_items=only is None)
        if run(ctx, f"{label}_s1", cmd):
            rerun_check(ctx, label, 1, "hf", cmd)


def step_optional(ctx):
    ports = ports_up(ctx)
    for tag, gold, kind in (("rdevv2", RDEV_GOLD, "rdev"), ("valid98", VALID98_GOLD, "dev"), ("aux", AUX_GOLD, "dev")):
        label = f"jt_s_t27_{tag}"
        if (ctx.cells / f"{label}_s1.json").exists():
            continue
        if now() >= OPTIONAL_DEADLINE:
            ctx.log(f"optional {label} skipped (deadline {OPTIONAL_DEADLINE.isoformat()})")
            ctx.tl(event="skipped", cell=label)
            continue
        cmd = cell_cmd(ctx, label=label, k=1, cond="s", gold=gold, conc=8, ports=ports, out_dir=ctx.cells, raw_dir=ctx.raw, all_items=True)
        if run(ctx, f"{label}_s1", cmd):
            rerun_check(ctx, label, 1, kind, cmd)


def ensure_servers(ctx):
    """--from으로 중간부터 시작할 때: 서버가 없으면 A·B를 띄운다(B 실패면 A만)."""
    if PORT_A not in ctx.servers and not start27(ctx, 0, 1, PORT_A):
        raise SystemExit("server A failed")
    if PORT_B not in ctx.servers and not start27(ctx, 2, 3, PORT_B):
        ctx.log("server B failed -> continue with server A only (PLAN_JT 3절)")


def step_latency(ctx):
    import hashlib
    lat = (WT / LAT_IDS_FILE).read_text(encoding="utf-8").strip()
    obs = hashlib.sha256((Path(V4_O101) / "adapter_model.safetensors").read_bytes()).hexdigest()
    ctx.tl(event="adapter_check", adapter=V4_O101, recorded=V4_O101_SHA, observed=obs, ok=obs == V4_O101_SHA)
    if obs != V4_O101_SHA:
        raise SystemExit("RR+NM4 o101 adapter sha256 differs from record")
    out = ctx.cells / "latency"
    if PORT_B in ctx.servers:
        stop_server(ctx, PORT_B, [2, 3])
    if PORT_A not in ctx.servers and not start27(ctx, 0, 1, PORT_A):
        raise SystemExit("server A failed (latency)")
    if not (out / "latjt_t27_s1.json").exists():
        run(ctx, "latjt_t27", cell_cmd(ctx, label="latjt_t27", k=1, cond="s", gold="sft_dpo_inventory/conversion_diag/selection_gold.yaml", conc=1,
                                         ports=[PORT_A], out_dir=out, raw_dir=ctx.raw, only=lat), watch=[2, 3])
    stop_server(ctx, PORT_A, [0, 1])
    if not start8(ctx, 0, PORT_8B, f"V4_o101={V4_O101}"):
        raise SystemExit("8B server failed (latency)")
    for label, model in (("latjt_8b_base", "base"), ("latjt_8b_v4_o101", "V4_o101")):
        if (out / f"{label}_s1.json").exists():
            continue
        cmd = [PY, str(WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py"), "--port", str(PORT_8B), "--model", model, "--label", label, "--k", "1",
               "--concurrency", "1", "--only", lat, "--grounding-target", "full", "--out-dir", str(out), "--raw-dir", str(ctx.raw), "--work", str(WORK8)]
        run(ctx, label, cmd, watch=[1, 2, 3])
    stop_server(ctx, PORT_8B, [0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--from", dest="start", choices=STEPS, default="smoke")
    a = ap.parse_args()
    ctx = Ctx(a.main)
    m = uuid_map()
    if m != EXPECT_UUID:
        raise SystemExit(f"GPU index/UUID map differs: {m}")
    busy = procs_on([0, 1, 2, 3])
    if busy:
        raise SystemExit(f"GPU processes present: {busy}")
    stop = threading.Event()
    threading.Thread(target=mem_sampler, args=(ctx, stop), daemon=True).start()
    ctx.log(f"driver start from {a.start} worktree {WT}")
    try:
        for s in STEPS[STEPS.index(a.start):]:
            ctx.step = s
            ctx.tl(event="step_start")
            if s == "smoke":
                step_smoke(ctx)
            elif s == "serverB":
                if PORT_A not in ctx.servers and not start27(ctx, 0, 1, PORT_A):
                    raise SystemExit("server A failed")
                if not start27(ctx, 2, 3, PORT_B):
                    ctx.log("server B failed -> continue with server A only (PLAN_JT 3절)")
            elif s in ("S", "G1"):
                ensure_servers(ctx)
                step_cond(ctx, s.lower())
            elif s == "optional":
                ensure_servers(ctx)
                step_optional(ctx)
            elif s == "latency":
                step_latency(ctx)
            ctx.tl(event="step_end")
        (ctx.G / "DONE").write_text(json.dumps({"finished": now().isoformat(timespec="seconds")}) + "\n")
        ctx.log("driver done")
    finally:
        for port in list(ctx.servers):
            stop_server(ctx, port, [0, 1] if port == PORT_A else [2, 3] if port == PORT_B else [0])
        stop.set()


if __name__ == "__main__":
    main()
