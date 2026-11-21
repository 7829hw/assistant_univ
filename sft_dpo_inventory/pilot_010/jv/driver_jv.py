# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 3절) 측정 드라이버. commit-pinned worktree에서 돌리고 기록은 ``--main``(저장소)에 쓴다. **참고 측정(판정 아님)**.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/driver_jv.py --main /home/hwkim/assistant_univ

순서: (2단계 ``gpu/JV/render_check.json``·``render_split.json``이 ok인지 확인) → smoke(base Q4, GPU 0, H-dev 앞 100 × 1) → 범위(필수 예상 ≤ 14시간이면 11개, 넘으면 SFT·RR+NM4 앞 3 seed)
→ 작업 대기열(필수 PF2 → 필수 H-final → 선택 PF2 → 선택 H-final)을 GPU 4장이 빈 대로 가져감 → 지연(GPU 0, 다른 작업 없이 교사 Q4 → base → RR+NM4 o101, context 17,408) → 서버 내림 → DONE.
- 작업 = 모델 하나·서버 하나(작업마다 새로 띄우고 끝나면 내림). PF2 작업 = k=1–4 네 셀(한 세션), H-final 작업 = 층화 1,000 × k=1.
- 선택 작업: 대기 중인 필수 작업이 없을 때만, 2026-11-22 12:00 KST 전에만 시작(PLAN_JV 6절 1).
- guard: ``run_cell_jv.py`` exit 3(느린 decode·100% GPU 아님)·6(다른 프로세스) → 서버를 한 번 다시 띄워 끝나지 않은 셀을 처음부터, 두 번째면 그 작업만 멈춤(보고).
  exit 4(첫 호출 렌더링 차이)·서버 로그 입력 잘림 줄 → 모든 작업을 멈추고(STOPPED) 보고. exit 5(그 밖의 실패) → 그 작업만 멈춤.
- H-final 잘림 다시 돌리기(JU와 같음): 잘림 호출 > 1% 또는 서버 오류 행 > 1% → 같은 seed 한 번(새 세션), 원본 ``replaced/``, 결과와 무관하게 교체(``RERUNS_JV.json``).
- 같은 명령을 다시 실행하면 끝난 셀은 건너뛴다(smoke 포함).
"""
import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
import common_jv as C  # noqa: E402
import models_jv as M  # noqa: E402

SMOKE_N, SMOKE_STOP_PCT, SCOPE_HOURS = 100, 5.0, 14.0
SMOKE_MIN_TOK_S = 30.0           # pilot_002 8B Q4 GPU 기준(PLAN_DEVIATIONS.md)
MAIN_GUARD_FRACTION = 0.5
TEACHER_MIN_TOK_S = 48.85        # JU 본 측정 기준(gpu/JU/scope.json)
OPT_DEADLINE = datetime(2026, 11, 22, 12, 0, tzinfo=C.KST)
LAT_CTX = 17408
ARMK = M.ARM_KEY


def reg(m):
    return json.loads((HERE / "registration" / f"{m['name']}.json").read_text(encoding="utf-8"))


def label(m, phase):
    tag = "base" if m["arm"] == "base" else f"{ARMK[m['arm']]}_{m['seed']}"
    return f"{'pf2jv' if phase == 'pf2' else 'hfinaljv'}_{tag}_q4"


class Driver:
    def __init__(self, main):
        self.ctx = C.Ctx(main)
        self.stopping = None
        self.qlock = threading.Lock()
        self.jobs_req, self.jobs_opt = [], []
        self.results = {}
        self.subset = (C.WT / C.SUBSET_FILE).read_text(encoding="utf-8").strip()

    # ---------- 셀 ----------
    def cell_cmd(self, g, m, digest, work, lab, k, kind, min_tok_s, render="hf8b"):
        port = C.PORTS[g]
        c = [C.PY, str(HERE / "run_cell_jv.py"), "--port", str(port), "--gpu", str(g), "--model", m["ollama"], "--digest", digest, "--render", render,
             "--label", lab, "--k", str(k), "--min-tok-s", str(min_tok_s), "--server-meta", str(work / f"server_{port}.json"), "--model-meta", json.dumps(m)]
        if kind == "pf2":
            c += ["--gold", C.PF_GOLD, "--all-items", "--sealed", "--reference-date", "2026-10-26", "--out-dir", str(C.PF_CELLS), "--raw-dir", str(C.PF_RAW)]
        elif kind == "hfinal":
            c += ["--gold", C.HF_GOLD, "--only", self.subset, "--out-dir", str(self.ctx.cells), "--raw-dir", str(self.ctx.raw)]
        elif kind == "smoke":
            import evaluate_vendor100 as EV
            ids = [i["id"] for i in EV.load_gold(C.WT / C.HDEV_GOLD)["items"]][:SMOKE_N]
            c += ["--gold", C.HDEV_GOLD, "--only", ",".join(ids), "--out-dir", str(self.ctx.cells / "smoke"), "--raw-dir", str(self.ctx.raw)]
        elif kind == "latency":
            ids = (C.WT / C.LAT_IDS_FILE).read_text(encoding="utf-8").strip()
            c += ["--gold", C.LAT_GOLD, "--only", ids, "--out-dir", str(self.ctx.cells / "latency"), "--raw-dir", str(self.ctx.raw)]
        return c

    def out_path(self, kind, lab, k):
        d = {"pf2": C.PF_CELLS, "hfinal": self.ctx.cells, "smoke": self.ctx.cells / "smoke", "latency": self.ctx.cells / "latency"}[kind]
        return d / f"{lab}_s{k}.json"

    def run_cell(self, g, job, cmd, name, kind):
        ctx = self.ctx
        ctx.tl(event="cell_start", job=job, cell=name, gpu=g)
        ctx.log(f"cell start {name} GPU {g}")
        t0 = datetime.now(C.KST)
        pre = (lambda: os.umask(0o077)) if kind == "pf2" else None
        r = subprocess.run(cmd, cwd=C.WT, env=ctx.env, capture_output=True, text=True, preexec_fn=pre)
        sec = round((datetime.now(C.KST) - t0).total_seconds())
        (ctx.G / f"{name}.log").write_text((r.stdout.strip().splitlines() or [""])[-1] + "\n", encoding="utf-8")
        ctx.tl(event="cell_end", job=job, cell=name, gpu=g, rc=r.returncode, seconds=sec)
        ctx.log(f"cell end {name} rc={r.returncode} {sec}s GPU {g}")
        return r.returncode

    # ---------- 작업 ----------
    def run_job(self, g, job, m, cells, kind, min_tok_s, models_dir=C.JV_MODELS, ctx_len=None, render="hf8b", digest=None):
        """cells: [(label, k)]. → 'ok' | 'failed:…' | 'stop:…'"""
        ctx = self.ctx
        digest = digest or reg(m)["digest"]
        rec = {"job": job, "gpu": g, "model": m, "digest": digest, "kind": kind, "sessions": [], "started": C.now().isoformat(timespec="seconds")}
        ctx.tl(event="job_start", job=job, gpu=g)
        status, attempt = "ok", 0
        while True:
            todo = [(lab, k) for lab, k in cells if not self.out_path(kind, lab, k).exists()]
            if not todo:
                break
            sess = job if attempt == 0 else f"{job}_r{attempt}"
            ok, sj, work = C.start_server(ctx, g, sess, m["ollama"], digest, models_dir, ctx_len=ctx_len)
            ses = {"session": sess, "server_ready": ok, "server": {k: (sj or {}).get(k) for k in ("pid", "started_at", "gpu_uuid", "context_length", "gpu_100", "backend_cuda",
                                                                                             "only_own_gpu", "nvidia_smi_after_load", "api_ps_after_load", "llama_server_cmd")},
                   "cells": []}
            rec["sessions"].append(ses)
            if not ok:
                C.stop_server(ctx, g, sess)
                status = "failed:server not ready"
                break
            ctx.running[g] = job
            bad = None
            for lab, k in todo:
                if self.stopping:
                    bad = "stop:driver stopping"
                    break
                rc = self.run_cell(g, job, self.cell_cmd(g, m, digest, work, lab, k, kind, min_tok_s, render), f"{lab}_s{k}", kind)
                ses["cells"].append({"cell": f"{lab}_s{k}", "rc": rc})
                if rc == 0:
                    continue
                bad = {3: "guard", 6: "guard", 4: "stop:render mismatch", 5: "failed:cell error"}.get(rc, "failed:cell error")
                break
            ses["server_log"] = C.server_log_summary(sess, g)
            if ses["server_log"] and ses["server_log"]["truncation_lines"]:
                bad = "stop:server log input truncation"
            ctx.running.pop(g, None)
            C.stop_server(ctx, g, sess)
            if bad is None:
                break
            if bad == "guard" and attempt == 0:
                attempt += 1
                ctx.log(f"job {job} guard abort -> restart server once, rerun unfinished cells from start")
                continue
            status = bad if bad != "guard" else "failed:guard twice"
            break
        rec["status"], rec["finished"] = status, C.now().isoformat(timespec="seconds")
        (ctx.G / "jobs" / f"{job}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        ctx.tl(event="job_end", job=job, gpu=g, status=status)
        if status.startswith("stop:"):
            self.stopping = status
        return status

    def hfinal_rerun(self, g, job, m, lab, min_tok_s):
        ctx = self.ctx
        p = self.out_path("hfinal", lab, 1)
        if not p.exists():
            return
        rows = json.loads(p.read_text(encoding="utf-8"))["rows"]
        calls = [c for r in rows for c in r["hf_calls"]]
        trunc = sum(c["done_reason"] == "length" for c in calls)
        srv = sum(1 for r in rows if r.get("error_code") == "UNHANDLED_EXCEPTION")
        tpct, spct = round(100 * trunc / max(len(calls), 1), 2), round(100 * srv / max(len(rows), 1), 2)
        rp = ctx.G / "RERUNS_JV.json"
        with self.qlock:
            rr = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {"rule": "JU와 같음: H-final 잘림 호출 > 1% 또는 서버 오류 행 > 1% → 같은 seed 한 번(새 세션), 원본 replaced/, 결과와 무관하게 교체; PF2·smoke 없음", "reruns": {}}
        ctx.tl(event="rerun_check", cell=p.stem, truncated_calls=trunc, calls=len(calls), truncated_pct=tpct, server_error_rows=srv)
        if not (tpct > 1.0 or spct > 1.0) or p.stem in rr["reruns"]:
            return
        rdir, rrdir = ctx.cells / "replaced", ctx.raw / "replaced"
        rdir.mkdir(exist_ok=True)
        rrdir.mkdir(exist_ok=True)
        for f in (p, p.with_suffix(".log")):
            if f.exists():
                shutil.move(str(f), rdir / f.name)
        rawf = ctx.raw / f"{p.stem}_raw.jsonl"
        if rawf.exists():
            shutil.move(str(rawf), rrdir / rawf.name)
        ent = {"truncated_calls": trunc, "calls": len(calls), "truncated_pct": tpct, "server_error_rows": srv, "server_error_pct": spct, "at": C.now().isoformat(timespec="seconds")}
        st = self.run_job(g, f"{job}_rerun", m, [(lab, 1)], "hfinal", min_tok_s)
        ent["rerun_status"] = st
        with self.qlock:
            rr = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else rr
            rr["reruns"][p.stem] = ent
            rp.write_text(json.dumps(rr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---------- 단계 ----------
    def check_stage2(self):
        a = json.loads((self.ctx.G / "render_check.json").read_text(encoding="utf-8"))
        b = json.loads((self.ctx.G / "render_split.json").read_text(encoding="utf-8"))
        if not (a.get("ok") and b.get("ok")):
            raise SystemExit("stage 2 checks not ok")
        self.ctx.log("stage 2 render/split checks ok")

    def smoke(self):
        ctx = self.ctx
        sc = ctx.G / "scope.json"
        if sc.exists():
            return json.loads(sc.read_text(encoding="utf-8"))
        base = M.model("base", "base")
        lab = "hdev100jv_base_q4"
        st = self.run_job(0, "smoke_base", base, [(lab, 1)], "smoke", SMOKE_MIN_TOK_S)
        p = self.out_path("smoke", lab, 1)
        if st != "ok" or not p.exists():
            (ctx.G / "STOPPED").write_text(json.dumps({"at": C.now().isoformat(), "reason": f"smoke {st}"}) + "\n")
            raise SystemExit(f"smoke {st}")
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = d["rows"]
        calls = [c for r in rows for c in r["hf_calls"]]
        trunc = sum(c["done_reason"] == "length" for c in calls)
        rates = [c["decode_tok_s"] for c in calls if (c.get("generated_tokens") or 0) >= 64 and c.get("decode_tok_s")]
        wall = d["meta"]["jv"]["wall_seconds"]
        est = wall * (600 + 1000) / 100 * 11 / 4 / 3600
        rec = {"decision": 273, "smoke_cell": str(p.relative_to(ctx.main)), "items": len(rows), "calls": len(calls), "truncated_calls": trunc,
               "truncated_pct": round(100 * trunc / len(calls), 2), "error_rows": sum(1 for r in rows if r.get("error_code")),
               "error_codes": sorted({r.get("error_code") for r in rows if r.get("error_code")}), "wall_seconds": wall,
               "items_per_hour": round(len(rows) / wall * 3600, 1), "generated_tokens": sum(c.get("generated_tokens") or 0 for c in calls),
               "decode_tok_s_median": statistics.median(rates), "decode_tok_s_min": min(rates),
               "accuracy_pct_report_only": round(100 * sum(r.get("category") == "match" for r in rows) / len(rows), 2),
               "stop_rule": f"truncated_pct >= {SMOKE_STOP_PCT} -> stop", "smoke_guard_min_tok_s": SMOKE_MIN_TOK_S,
               "est_rule": "smoke wall x (600 + 1000)/100 x 11 models / 4 GPUs", "est_required_hours": round(est, 2), "scope_hours_limit": SCOPE_HOURS,
               "reduced": est > SCOPE_HOURS, "main_guard_min_tok_s": round(MAIN_GUARD_FRACTION * statistics.median(rates), 2),
               "render_all_equal": d["meta"]["ollama"]["render_all_equal"]}
        sc.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        ctx.log(f"smoke truncated {trunc}/{len(calls)} = {rec['truncated_pct']}% est {rec['est_required_hours']} h reduced={rec['reduced']} main guard {rec['main_guard_min_tok_s']} tok/s")
        if rec["truncated_pct"] >= SMOKE_STOP_PCT:
            (ctx.G / "STOPPED").write_text(json.dumps({"at": C.now().isoformat(), "reason": "smoke truncation >= 5%"}) + "\n")
            raise SystemExit("smoke truncation >= 5%")
        return rec

    def next_job(self):
        with self.qlock:
            if self.stopping:
                return None
            if self.jobs_req:
                return self.jobs_req.pop(0)
            if self.jobs_opt and C.now() < OPT_DEADLINE:
                return self.jobs_opt.pop(0)
            return None

    def worker(self, g, guard):
        while True:
            j = self.next_job()
            if j is None:
                return
            m, kind = j["model"], j["kind"]
            cells = [(label(m, "pf2"), k) for k in range(1, 5)] if kind == "pf2" else [(label(m, "hfinal"), 1)]
            st = self.run_job(g, j["job"], m, cells, kind, guard)
            self.results[j["job"]] = st
            if kind == "hfinal" and st == "ok":
                self.hfinal_rerun(g, j["job"], m, label(m, "hfinal"), guard)
            if st.startswith("failed:server"):
                self.ctx.log(f"GPU {g} worker stops after server failure ({j['job']})")
                return

    def latency(self, guard):
        ctx = self.ctx
        stop = threading.Event()
        th = threading.Thread(target=C.mem_sampler, args=(ctx, stop, ctx.G / "latency_mem.jsonl", 5), daemon=True)
        th.start()
        try:
            t = C.TEACHER
            tm = {"arm": "teacher_q4", "seed": "-", "name": t["name"], "adapter": None, "adapter_sha256": None, "ollama": t["ollama"]}
            for m, lab, models, render, digest, mt in ((tm, "latjv_t27q4", t["models"], "qwen38", t["digest"], TEACHER_MIN_TOK_S),
                                                         (M.model("base", "base"), "latjv_base_q4", C.JV_MODELS, "hf8b", None, guard),
                                                         (M.model("V4", "o101"), "latjv_v4_o101_q4", C.JV_MODELS, "hf8b", None, guard)):
                if self.stopping:
                    break
                st = self.run_job(0, f"latency_{m['name']}", m, [(lab, 1)], "latency", mt, models_dir=models, ctx_len=LAT_CTX, render=render, digest=digest)
                self.results[f"latency_{m['name']}"] = st
        finally:
            stop.set()

    def run(self):
        ctx = self.ctx
        ctx.log(f"driver start worktree {C.WT}")
        self.check_stage2()
        stop = threading.Event()
        threading.Thread(target=C.mem_sampler, args=(ctx, stop), daemon=True).start()
        sc = self.smoke()
        guard = sc["main_guard_min_tok_s"]
        req = M.required(reduced=sc["reduced"])
        self.jobs_req = [{"job": f"pf2_{m['name']}", "model": m, "kind": "pf2"} for m in req] + [{"job": f"hfinal_{m['name']}", "model": m, "kind": "hfinal"} for m in req]
        opt = M.optional()
        self.jobs_opt = [{"job": f"pf2_{m['name']}", "model": m, "kind": "pf2"} for m in opt] + [{"job": f"hfinal_{m['name']}", "model": m, "kind": "hfinal"} for m in opt]
        ctx.log(f"jobs required {len(self.jobs_req)} optional {len(self.jobs_opt)} (reduced={sc['reduced']}) guard {guard} tok/s")
        ws = [threading.Thread(target=self.worker, args=(g, guard)) for g in sorted(C.PORTS)]
        for w in ws:
            w.start()
        for w in ws:
            w.join()
        if not self.stopping:
            self.latency(guard)
        stop.set()
        left = C.procs_on(sorted(C.PORTS))
        res = {"finished": C.now().isoformat(timespec="seconds"), "results": self.results, "stopping": self.stopping, "gpu_procs_left": left}
        (ctx.G / ("STOPPED" if self.stopping else "DONE")).write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
        ctx.log(f"driver {'STOPPED ' + self.stopping if self.stopping else 'done'} left={left}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    a = ap.parse_args()
    Driver(a.main).run()


if __name__ == "__main__":
    main()
