# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272, PLAN_JU 2–3절) 순차 실행기. 커밋에 고정한 worktree에서 hf env python으로 돌린다. **교사 4비트 빌드 참고 측정(판정 아님)**.

    runtime/envs/hf/bin/python <WT>/sft_dpo_inventory/pilot_010/ju/driver_ju.py --main /home/hwkim/assistant_univ [--from STEP]

순서(PLAN_JU 3절):
  servers  GPU 0–3에 Ollama 0.40.6 서버 4벌(포트 11441–11444, GPU i → 포트 11441 + i), 모델 올림, 100% GPU 확인(``serve_ju.sh``).
  smoke    H-dev 앞 100문항 × 1, S, 서버 4벌, 속도 guard = 기존 기록의 33.71 tok/s, ``--check-input``. 잘림 호출 ≥ 5% → STOPPED, 멈춤.
           범위: 예상 시간 = smoke wall × 3000/100 ≤ 8시간 → H-final 3,000 전체, 넘으면 ``jt/hfinal_subset1000_ids.txt``. 본 측정 속도 guard =
           smoke 호출(eval_count ≥ 64)의 decode tok/s 중앙값 × 0.5. ``scope.json``.
  S        PF2 150 × k=1–4(``--sealed``, 기준일 2026-10-26, 700 디렉터리) → H-final(범위) × k=1(회차 seed 20261101).
  G1       각 셀 시작 시각 < G1_DEADLINE일 때만 PF2 × k=1–4.
  stop     서버 4벌 내림(SIGTERM), GPU에 프로세스가 남지 않았는지 확인.
- 조각이 멈추면(실행기 exit 3): 그 서버를 한 번 내렸다 다시 띄우고(새 세션) 같은 셀 명령을 다시 실행한다(끝나지 않은 조각만 처음부터). 또 멈추면 STOPPED.
  입력 잘림(exit 4)은 바로 STOPPED(한도를 바꾸지 않음).
- 잘림 다시 돌리기(JT와 같음): H-final 잘림 호출 > 1% 또는 서버 오류 행 > 1% → 같은 seed로 한 번, 원본은 replaced/, 결과와 무관하게 교체. PF2·smoke 없음.
- 기록: ``pilot_010/gpu/JU/``(runs.log·gpu_check.txt·timeline.jsonl·gpu_mem.jsonl·server_*.json·scope.json·RERUNS_JU.json·DONE|STOPPED).
  셀: smoke·H-final은 ``pilot_010/cells/JU``(원문 ``training/generated/pilot_010/cells_raw_JU``), PF2는 700 디렉터리(``pf2ju_<cond>_q4_s<k>``).
- PF2 내용은 읽지 않는다(이 실행기는 PF2 셀을 열지 않음). 기존 Ollama 컨테이너·포트 11434·/data/hwkim/ollama는 건드리지 않는다.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
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
OLLAMA_UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"   # 결정 191 기존 컨테이너 GPU(gpu_ok가 그 컨테이너 상태를 읽기만 함)
PORTS = {0: 11441, 1: 11442, 2: 11443, 3: 11444}
WORK = Path("/data/hwkim/sftdpo_work/pilot_010_ju/servers")
PF_GOLD = "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"
PF_CELLS, PF_RAW = Path("/data/hwkim/sftdpo_work/protected_final_v2/cells"), Path("/data/hwkim/sftdpo_work/protected_final_v2/raw")
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
SMOKE_N, SMOKE_STOP_PCT, SCOPE_HOURS = 100, 5.0, 8.0
SMOKE_MIN_TOK_S = 33.71        # pilot_006/post/o1_speed.json(결정 163 O1) — qwen3.8:27b 교사 수집 guard 기준(pilot_009·010 teacher)
MAIN_GUARD_FRACTION = 0.5
G1_DEADLINE = datetime(2026, 11, 21, 20, 0, tzinfo=KST)
STEPS = ("servers", "smoke", "S", "G1", "stop")


def now():
    return datetime.now(KST)


class Ctx:
    def __init__(self, main):
        self.main = Path(main)
        self.G = self.main / "sft_dpo_inventory/pilot_010/gpu/JU"
        self.cells = self.main / "sft_dpo_inventory/pilot_010/cells/JU"
        self.raw = self.main / "training/generated/pilot_010/cells_raw_JU"
        for d in (self.G, self.cells, self.raw, self.cells / "smoke"):
            d.mkdir(parents=True, exist_ok=True)
        self.env = {**os.environ, "OLLAMA_UUID": OLLAMA_UUID, "ALLOWED_UUIDS": " ".join(EXPECT_UUID.values()), "P3": str(self.G),
                    "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
                    "PYTHONDONTWRITEBYTECODE": "1"}
        self.env.pop("OLLAMA_HOST", None)
        self.step = "init"
        self.up = set()

    def log(self, msg):
        line = f"== [ju] {msg} {now().isoformat(timespec='seconds')}"
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
            procs = smi("gpu_uuid,pid,used_memory", "apps")
            with open(ctx.G / "gpu_mem.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now().isoformat(timespec="seconds"), "step": ctx.step, "gpus": rows, "procs": procs}) + "\n")
        except Exception:  # noqa: BLE001
            pass
        stop.wait(30)


# ---------------- 서버 ----------------
def start(ctx, g):
    port = PORTS[g]
    ctx.log(f"start ollama server GPU {g} port {port}")
    rc = subprocess.run(["bash", str(HERE / "serve_ju.sh"), str(g), str(port)], env=ctx.env, cwd=WT,
                        stdout=open(ctx.G / f"serve_{port}.out", "a"), stderr=subprocess.STDOUT).returncode
    ctx.tl(event="server_start", port=port, gpu=g, rc=rc)
    if rc == 0:
        ctx.up.add(g)
        shutil.copy(WORK / f"server_{port}.json", ctx.G / f"server_{port}.json")
        with open(ctx.G / "server_starts.jsonl", "a", encoding="utf-8") as f:
            f.write((WORK / f"server_{port}.json").read_text(encoding="utf-8").replace("\n", " ") + "\n")
    return rc == 0


def stop_server(ctx, g):
    port = PORTS[g]
    pidf = WORK / f"server_{port}.pid"
    if pidf.exists():
        pid = int(pidf.read_text().strip())
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass
        for _ in range(60):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(2)
    for _ in range(60):
        if not procs_on([g]):
            break
        time.sleep(2)
    ctx.up.discard(g)
    left = procs_on([g])
    ctx.tl(event="server_stop", port=port, gpu=g, left=left)
    ctx.log(f"stop server GPU {g} port {port} left={left}")


def ports(ctx):
    return ",".join(str(PORTS[g]) for g in sorted(ctx.up))


# ---------------- 셀 ----------------
def cell_cmd(ctx, *, label, k, cond, gold, out_dir, raw_dir, min_tok_s, only=None, all_items=False, sealed=False, ref_date=None, check_input=False):
    c = [PY, str(HERE / "run_cell_ju.py"), "--ports", ports(ctx), "--cond", cond, "--label", label, "--k", str(k), "--gold", gold,
         "--out-dir", str(out_dir), "--raw-dir", str(raw_dir), "--seed-base", "20261100", "--min-tok-s", str(min_tok_s)]
    c += ["--all-items"] if all_items else ["--only", only]
    if sealed:
        c.append("--sealed")
    if ref_date:
        c += ["--reference-date", ref_date]
    if check_input:
        c.append("--check-input")
    return c


TRUNC_RE = re.compile(r"(?i)truncat")


def trunc_lines():
    """서버 로그의 입력 잘림 경고 줄 수(Ollama: 'truncating input prompt' 등). 포트별."""
    out = {}
    for port in PORTS.values():
        f = WORK / f"server_{port}.log"
        out[port] = sum(1 for l in f.read_text(errors="replace").splitlines() if TRUNC_RE.search(l)) if f.exists() else 0
    return out


def run(ctx, name, cmd, umask=None):
    ctx.log(f"cell start {name}")
    ctx.tl(event="cell_start", cell=name)
    t0 = time.time()
    before = trunc_lines()
    pre = (lambda: os.umask(umask)) if umask is not None else None
    rc = subprocess.run(cmd, cwd=WT, env=ctx.env, stdout=open(ctx.G / f"{name}.log", "a"), stderr=subprocess.STDOUT, preexec_fn=pre).returncode
    new = {p: n - before.get(p, 0) for p, n in trunc_lines().items() if n - before.get(p, 0) > 0}
    ctx.tl(event="cell_end", cell=name, rc=rc, seconds=round(time.time() - t0, 1), server_log_truncation_lines=new)
    ctx.log(f"cell end {name} rc={rc} {round(time.time() - t0)}s" + (f" SERVER LOG TRUNCATION {new}" if new else ""))
    if new:
        stop_all(ctx, f"{name}: server log reports input truncation {new} (한도를 바꾸지 않고 멈춤)")
    return rc


def guarded(ctx, name, cmd, umask=None):
    """조각 멈춤(exit 3)이면 멈춘 조각의 서버를 한 번 다시 띄우고 같은 명령(끝나지 않은 조각만)을 다시 실행. 입력 잘림(4)·두 번째 멈춤 → STOPPED."""
    rc = run(ctx, name, cmd, umask)
    if rc == 0:
        return True
    if rc == 3:
        tail = (ctx.G / f"{name}.log").read_text(encoding="utf-8", errors="replace").splitlines()[-1:]
        try:
            bad = sorted(int(x) for x in json.loads(tail[0])["codes"])
        except Exception:  # noqa: BLE001
            bad = []
        gpus = sorted(ctx.up) if not bad else [sorted(ctx.up)[j] for j in bad if j < len(ctx.up)]
        ctx.log(f"{name} shard aborted (shards {bad}) -> restart server(s) on GPU {gpus} once and rerun unfinished shards from start")
        ctx.tl(event="shard_abort", cell=name, shards=bad, gpus=gpus)
        for g in gpus:
            stop_server(ctx, g)
            if not start(ctx, g):
                ctx.log(f"server GPU {g} restart failed")
                stop_all(ctx, f"{name}: server GPU {g} restart failed after shard abort")
        rc = run(ctx, f"{name}_retry", cmd, umask)
        if rc == 0:
            return True
    stop_all(ctx, f"{name}: rc={rc} (3 = shard aborted twice, 4 = input truncation)")


def stop_all(ctx, reason):
    (ctx.G / "STOPPED").write_text(json.dumps({"reason": reason, "t": now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
    ctx.log(f"STOPPED: {reason}")
    raise SystemExit(2)


def cell_stats(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    rows = d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    return d, rows, calls


def rerun_check(ctx, label, cmd):
    """JT·학생 셀과 같은 규칙: 잘림 호출 > 1%(반올림 둘째 자리) 또는 서버 오류 행 > 1% → 같은 seed 한 번, 원본은 replaced/."""
    name = f"{label}_s1"
    p = ctx.cells / f"{name}.json"
    d, rows, calls = cell_stats(p)
    raw = Path(d["meta"]["hf"]["raw_out"])
    recs = [json.loads(x) for x in raw.read_text(encoding="utf-8").splitlines()]
    trunc = sum(x.get("finish_reason") == "length" for x in recs)
    tpct = round(100 * trunc / max(1, len(recs)), 2)
    srv_re = re.compile(r"^(URLError|HTTPError|ConnectionError|ConnectionResetError|ConnectionRefusedError|RemoteDisconnected|TimeoutError|socket\.timeout|"
                        r"IncompleteRead|ReadTimeout|ConnectTimeout|ConnectError|RemoteProtocolError|ReadError|OllamaRequestError)\b")
    srv = sum(1 for r in rows if r.get("error_code") == "UNHANDLED_EXCEPTION" and srv_re.match(((r.get("planner_trace") or {}).get("exception") or "")))
    spct = round(100 * srv / max(1, len(rows)), 2)
    rp = ctx.G / "RERUNS_JU.json"
    rec = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {"rule": "JT와 같음: H-final 잘림 호출 > 1% 또는 서버 오류 행 > 1% → 같은 seed 한 번, 원본 replaced/, 결과와 무관하게 교체; PF2·smoke 없음", "reruns": {}}
    ctx.tl(event="rerun_check", cell=name, truncated_calls=trunc, raw_lines=len(recs), truncated_pct=tpct, server_error_rows=srv)
    if not (tpct > 1.0 or spct > 1.0) or name in rec["reruns"]:
        return
    import hashlib
    (ctx.cells / "replaced").mkdir(exist_ok=True)
    (ctx.raw / "replaced").mkdir(exist_ok=True)
    rec["reruns"][name] = {"truncated_calls": trunc, "raw_lines": len(recs), "truncated_pct": tpct, "server_error_rows": srv,
                           "original_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "moved_to": "cells/JU/replaced/", "queued": now().isoformat(timespec="seconds")}
    for src, dst in ((p, ctx.cells / "replaced"), (ctx.cells / f"{name}.log", ctx.cells / "replaced"), (raw, ctx.raw / "replaced")):
        if src.exists():
            shutil.move(str(src), str(dst / src.name))
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    rec["reruns"][name]["rerun_ok"] = bool(guarded(ctx, f"R-{name}", cmd))
    rp.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ---------------- 단계 ----------------
def step_servers(ctx):
    for g in (0, 1, 2, 3):
        if g in ctx.up:
            continue
        if not start(ctx, g):
            stop_all(ctx, f"server GPU {g} failed to start (100% GPU·digest·version 확인 포함)")


def step_smoke(ctx):
    import yaml
    ids = [i["id"] for i in yaml.safe_load((WT / HDEV_GOLD).read_text(encoding="utf-8"))["items"]][:SMOKE_N]
    out = ctx.cells / "smoke"
    cmd = cell_cmd(ctx, label="hdev100ju_s_q4", k=1, cond="s", gold=HDEV_GOLD, out_dir=out, raw_dir=ctx.raw, min_tok_s=SMOKE_MIN_TOK_S,
                   only=",".join(ids), check_input=True)
    guarded(ctx, "smoke_hdev100", cmd)
    d, rows, calls = cell_stats(out / "hdev100ju_s_q4_s1.json")
    trunc = sum(c.get("finish_reason") == "length" for c in calls)
    pct = 100.0 * trunc / max(1, len(calls))
    wall = d["meta"]["ju"]["wall_seconds"]
    est_h = wall * (3000 / SMOKE_N) / 3600
    rates = [c["decode_tok_s"] for c in calls if c.get("decode_tok_s") and (c.get("generated_tokens") or 0) >= 64]
    med = statistics.median(rates)
    gen = sum(c.get("generated_tokens") or 0 for c in calls)
    rec = {"decision": 272, "label": "교사 4비트 빌드 참고 측정 smoke(H-dev 개발 셋); 정답률은 기록만, 어떤 설정도 이 값으로 조정하지 않음",
           "items": len(rows), "calls": len(calls), "truncated_calls": trunc, "truncated_pct": round(pct, 4),
           "think_unclosed_calls(추정: content 빔)": sum(c.get("think_closed") is False for c in calls),
           "error_rows": sum(1 for r in rows if r.get("error_code")), "error_codes": sorted({r.get("error_code") for r in rows if r.get("error_code")}),
           "wall_seconds": wall, "items_per_hour_4_servers": round(len(rows) / wall * 3600, 1), "generated_tokens": gen,
           "output_tok_per_s_4_servers": round(gen / wall, 1), "decode_tok_s_median_per_call": round(med, 2),
           "decode_tok_s_min_per_call": round(min(rates), 2), "first_input_checks": {p: s.get("first_input_check") for p, s in d["meta"]["ju"]["sessions"].items()},
           "accuracy_pct_report_only": round(100 * sum(r.get("category") == "match" for r in rows) / len(rows), 2),
           "stop_rule": f"truncated_pct >= {SMOKE_STOP_PCT} -> stop", "scope_rule": f"est_hours = wall x 3000/{SMOKE_N} <= {SCOPE_HOURS} -> full 3000, else subset 1000",
           "est_hfinal_3000_hours_4_servers": round(est_h, 3), "smoke_guard_min_tok_s": SMOKE_MIN_TOK_S,
           "main_guard_rule": f"min_tok_s = {MAIN_GUARD_FRACTION} x median decode tok/s of smoke calls with eval_count >= 64",
           "main_guard_min_tok_s": round(MAIN_GUARD_FRACTION * med, 2)}
    rec["stopped"] = pct >= SMOKE_STOP_PCT
    rec["scope"] = None if rec["stopped"] else ("full3000" if est_h <= SCOPE_HOURS else "subset1000")
    (ctx.G / "scope.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    ctx.log(f"smoke truncated {trunc}/{len(calls)} = {pct:.2f}% est {est_h:.2f} h scope {rec['scope']} main guard {rec['main_guard_min_tok_s']} tok/s")
    if rec["stopped"]:
        stop_all(ctx, f"smoke truncation {pct:.2f}% >= 5%")


def scope(ctx):
    return json.loads((ctx.G / "scope.json").read_text(encoding="utf-8"))


def step_pf2(ctx, cond, guard):
    for k in range(1, 5):
        label = f"pf2ju_{cond}_q4"
        if (PF_CELLS / f"{label}_s{k}.json").exists():
            continue
        if cond == "g1" and now() >= G1_DEADLINE:
            ctx.log(f"G1 {label}_s{k} skipped (deadline {G1_DEADLINE.isoformat()})")
            ctx.tl(event="skipped", cell=f"{label}_s{k}")
            continue
        cmd = ["bash", "-c", "umask 077 && exec " + " ".join(cell_cmd(ctx, label=label, k=k, cond=cond, gold=PF_GOLD, out_dir=PF_CELLS, raw_dir=PF_RAW,
                                                                      min_tok_s=guard, all_items=True, sealed=True, ref_date="2026-10-26"))]
        guarded(ctx, f"{label}_s{k}", cmd)


def step_hfinal(ctx, guard):
    label = "hfinalju_s_q4"
    if (ctx.cells / f"{label}_s1.json").exists():
        return
    sc = scope(ctx)["scope"]
    only = None if sc == "full3000" else (HERE.parent / "jt/hfinal_subset1000_ids.txt").read_text(encoding="utf-8").strip()
    cmd = cell_cmd(ctx, label=label, k=1, cond="s", gold=HF_GOLD, out_dir=ctx.cells, raw_dir=ctx.raw, min_tok_s=guard, sealed=True,
                   only=only, all_items=only is None)
    guarded(ctx, f"{label}_s1", cmd)
    rerun_check(ctx, label, cmd)


def stop_all_servers(ctx):
    for g in sorted(ctx.up):
        stop_server(ctx, g)
    left = procs_on([0, 1, 2, 3])
    ctx.tl(event="all_servers_stopped", left=left)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--from", dest="start", choices=STEPS, default="servers")
    a = ap.parse_args()
    ctx = Ctx(a.main)
    m = uuid_map()
    if m != EXPECT_UUID:
        raise SystemExit(f"GPU index/UUID map differs: {m}")
    busy = procs_on([0, 1, 2, 3])
    if busy and a.start == "servers":
        raise SystemExit(f"GPU processes present: {busy}")
    if a.start != "servers":   # 중간부터: 떠 있는 JU 서버를 인정(포트가 응답하고 server json이 있을 때)
        for g, port in PORTS.items():
            if subprocess.run(["curl", "-sf", f"http://127.0.0.1:{port}/api/version"], capture_output=True).returncode == 0:
                ctx.up.add(g)
    stop = threading.Event()
    threading.Thread(target=mem_sampler, args=(ctx, stop), daemon=True).start()
    ctx.log(f"driver start from {a.start} worktree {WT}")
    try:
        for s in STEPS[STEPS.index(a.start):]:
            ctx.step = s
            ctx.tl(event="step_start")
            if s == "servers":
                step_servers(ctx)
            elif s == "smoke":
                step_smoke(ctx)
            elif s in ("S", "G1"):
                step_servers(ctx)
                guard = scope(ctx)["main_guard_min_tok_s"]
                step_pf2(ctx, s.lower(), guard)
                if s == "S":
                    step_hfinal(ctx, guard)
            elif s == "stop":
                stop_all_servers(ctx)
            ctx.tl(event="step_end")
        (ctx.G / "DONE").write_text(json.dumps({"finished": now().isoformat(timespec="seconds")}) + "\n")
        ctx.log("driver done")
    finally:
        stop_all_servers(ctx)
        stop.set()


if __name__ == "__main__":
    main()
