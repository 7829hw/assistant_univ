# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 3절) 셀 실행기: 서버 한 벌(GPU 한 장)에서 한 셀을 처음부터 끝까지 잰다. ``ju/run_cell_ju.py``(그대로 둠)의 구조를 따르되 조각 나누기가 없다.
**참고 측정(판정 아님)**.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/run_cell_jv.py --port P --gpu G --model M --digest D --render hf8b --label L --k K \
        --gold G (--only IDS | --all-items) --out-dir D --raw-dir R --min-tok-s X --server-meta S [--sealed] [--reference-date 2026-10-26] [--model-meta JSON]

- 회차 seed = 20261100 + k, 호출 seed = ``EV.call_seed``, S = T 0.6·top-p 0.95·top-k 20(+ min_p 0·presence_penalty 0·repeat_penalty 1, client가 보냄).
- guard: client가 느린 decode(exit 3)·첫 호출 렌더링 차이(exit 4)로 멈추거나, 이 실행기가 60초마다 보는 ``/api/ps``에서 100% GPU가 아니거나(exit 3),
  30초마다 보는 그 GPU의 compute 프로세스 중 서버(와 자식)가 아닌 것이 있으면(exit 6) 셀을 멈춘다. 멈춘 셀의 출력·원문·로그는 ``ABORTED_<이름>_<시각>``으로 남긴다.
- 끝나면 ``<out>/<label>_s<k>.json``(meta ``jv``: 세션·감시 기록)·``<raw>/<label>_s<k>_raw.jsonl``·``<out>/<label>_s<k>.log``(sealed면 집계 줄에 grounding 수 없음).
"""
import argparse
import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
from common_jv import KST, PY, now, smi  # noqa: E402

EVAL = HERE / "ollama_eval_jv.py"


def api_ps(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ps", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def kids(pid):
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    return {int(x) for x in out}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for a in ("--model", "--digest", "--label", "--gold", "--out-dir", "--raw-dir", "--server-meta"):
        p.add_argument(a, required=True)
    p.add_argument("--port", type=int, required=True)
    p.add_argument("--gpu", type=int, required=True)
    p.add_argument("--render", choices=("hf8b", "qwen38"), required=True)
    p.add_argument("--k", type=int, required=True)
    p.add_argument("--seed-base", type=int, default=20261100)
    p.add_argument("--only", default=None)
    p.add_argument("--all-items", action="store_true")
    p.add_argument("--min-tok-s", type=float, required=True)
    p.add_argument("--sealed", action="store_true")
    p.add_argument("--reference-date", default=None)
    p.add_argument("--model-meta", default="{}")
    p.add_argument("--save-first-messages", default=None)
    args = p.parse_args()
    out_dir, RAW = Path(args.out_dir), Path(args.raw_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    name = f"{args.label}_s{args.k}"
    final, final_raw, log = out_dir / f"{name}.json", RAW / f"{name}_raw.jsonl", out_dir / f"{name}.log"
    if final.exists() or final_raw.exists():
        raise SystemExit(f"{final} exists")
    import evaluate_vendor100 as EV
    if args.all_items:
        g = Path(args.gold) if Path(args.gold).is_absolute() else ROOT / args.gold
        ids = [i["id"] for i in EV.load_gold(g)["items"]]
    else:
        ids = args.only.split(",")
    sm = json.loads(Path(args.server_meta).read_text(encoding="utf-8"))
    spid, uuid = int(sm["pid"]), sm["gpu_uuid"]
    tmp, tmp_raw = out_dir / f".{name}.json", RAW / f".{name}_raw.jsonl"
    for f in (tmp, tmp_raw, Path(f"{tmp}.abort.json")):
        f.unlink(missing_ok=True)
    cmd = [PY, str(EVAL), "--host", f"http://127.0.0.1:{args.port}", "--model", args.model, "--digest", args.digest, "--render", args.render,
           "--model-meta", args.model_meta, "--gold", args.gold, "--only", ",".join(ids), "--condition-check",
           "--do-sample", "--temperature", "0.6", "--top-p", "0.95", "--top-k", "20", "--seed", str(args.seed_base + args.k),
           "--min-tok-s", str(args.min_tok_s), "--server-meta", args.server_meta, "--out", str(tmp), "--raw-out", str(tmp_raw),
           *(["--reference-date", args.reference_date] if args.reference_date else []),
           *(["--save-first-messages", args.save_first_messages] if args.save_first_messages else [])]
    start = now()
    t0 = time.perf_counter()
    plog = open(out_dir / f".{name}.log", "w")
    pr = subprocess.Popen(cmd, cwd=ROOT, stdout=plog, stderr=subprocess.STDOUT)
    ps_log, proc_log, killed, stop = [], [], {}, threading.Event()

    def watch():
        n = 0
        while not stop.wait(30):
            if pr.poll() is not None:
                return
            n += 1
            try:
                allowed = {spid} | kids(spid)
                apps = [a for a in smi("gpu_uuid,pid,used_memory,process_name", "apps") if a and a[0] == uuid]
                other = [a for a in apps if not (a[1].isdigit() and int(a[1]) in allowed)]
                proc_log.append({"t": now().isoformat(timespec="seconds"), "apps": len(apps), "other": other})
                if other:
                    killed["reason"], killed["code"] = f"other process on GPU {args.gpu}: {other}", 6
                    pr.terminate()
                    return
            except Exception as error:  # noqa: BLE001
                proc_log.append({"t": now().isoformat(timespec="seconds"), "error": str(error)[:200]})
            if n % 2:
                continue
            try:
                ms = [m for m in api_ps(args.port).get("models", []) if m.get("name") == args.model]
                ok = bool(ms) and ms[0].get("size_vram") == ms[0].get("size")
                ps_log.append({"t": now().isoformat(timespec="seconds"), "ok_100_gpu": ok, "size": ms[0].get("size") if ms else None,
                               "size_vram": ms[0].get("size_vram") if ms else None, "context_length": ms[0].get("context_length") if ms else None})
                if not ok:
                    killed["reason"], killed["code"] = "not 100% GPU (/api/ps size_vram != size or model not loaded)", 3
                    pr.terminate()
                    return
            except Exception as error:  # noqa: BLE001
                ps_log.append({"t": now().isoformat(timespec="seconds"), "error": str(error)[:200]})
    th = threading.Thread(target=watch, daemon=True)
    th.start()
    code = pr.wait()
    stop.set()
    th.join(timeout=5)
    plog.close()
    wall = time.perf_counter() - t0
    end = now()
    if code != 0 or killed:
        ts = end.strftime("%Y%m%dT%H%M%S")
        ab = Path(f"{tmp}.abort.json")
        rec = {"cell": name, "at": end.isoformat(timespec="seconds"), "code": code, "killed": killed, "ps_checks": ps_log, "proc_checks": proc_log,
               "abort": json.loads(ab.read_text(encoding="utf-8")) if ab.exists() else None, "gpu": args.gpu, "port": args.port}
        for f in (out_dir / f".{name}.log", tmp_raw, ab, tmp):
            if f.exists():
                f.rename(f.parent / f"ABORTED_{f.name.lstrip('.')}_{ts}")
        (out_dir / f"ABORTED_{name}_{ts}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"aborted": name, "code": code, "killed": killed}, ensure_ascii=False))
        sys.exit(killed.get("code") or (code if code in (3, 4) else 5))
    d = json.loads(tmp.read_text(encoding="utf-8"))
    if [r["id"] for r in d["rows"]] != ids:
        raise SystemExit("rows differ from requested items")
    tmp_raw.rename(final_raw)
    m = d["meta"]
    m["hf"]["raw_out"] = str(final_raw.resolve())
    m["jv"] = {"decision": 273, "plan": "sft_dpo_inventory/pilot_010/PLAN_JV.md", "cond": "s", "temperature": "0.6",
               "label": "학생·교사 4비트 빌드 참고 측정(판정 아님); Ollama 0.40.6 Q4_K_M; PF2·H-final 추가 사용",
               "session": "one server (one GPU, one model), sequential continuous session (decision 79)", "port": args.port, "gpu_index": args.gpu,
               "gpu_uuid": uuid, "server_pid": spid, "server_started_at": sm.get("started_at"), "sessions": 1, "ps_checks": len(ps_log),
               "ps_all_100_gpu": all(x.get("ok_100_gpu") for x in ps_log if "error" not in x), "ps_errors": sum("error" in x for x in ps_log),
               "proc_checks": len(proc_log), "other_process_seen": any(x.get("other") for x in proc_log), "context_length_seen": sorted({x.get("context_length") for x in ps_log if x.get("context_length")}),
               "wall_seconds": round(wall, 1), "started": start.isoformat(timespec="seconds"), "ended": end.isoformat(timespec="seconds")}
    final.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.unlink()
    rows = d["rows"]
    calls = [c for r in rows for c in r["hf_calls"]]
    tail = {"items": len(rows), "wall_seconds": round(wall, 1), "calls": len(calls), "truncated_calls": sum(c["done_reason"] == "length" for c in calls),
            "render_all_equal": m["ollama"]["render_all_equal"], "ps_checks": len(ps_log)}
    if not args.sealed:
        tail = {"grounding_ok": sum(bool(r["grounding_ok"]) for r in rows), **tail}
    body = (out_dir / f".{name}.log").read_text(encoding="utf-8")
    log.write_text(body + json.dumps(tail, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / f".{name}.log").unlink()
    print(json.dumps(tail, ensure_ascii=False))


if __name__ == "__main__":
    main()
