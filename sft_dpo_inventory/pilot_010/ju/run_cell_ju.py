# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272, PLAN_JU 3절) 셀 실행기: Ollama 서버 4벌에 한 셀의 문항을 나눠 잰다. ``jt/run_cell_jt.py``(그대로 둠)의 구조를 따른다(규칙 15).
**교사 4비트 빌드 참고 측정(판정 아님)**.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/ju/run_cell_ju.py --ports 11441,11442,11443,11444 --cond s --label L --k 1 \
        --gold G (--only IDS | --all-items) --out-dir D --raw-dir R --min-tok-s X [--check-input] [--sealed] [--reference-date 2026-10-26]

- 나누기: 문항 i(파일 순서) → 조각 i % 4 → 서버 ports[i % 4]. 조각 하나 = ``ollama_eval_ju.py`` 프로세스 하나(조각 안은 순차), 서버마다 동시 요청 1
  (OLLAMA_NUM_PARALLEL=1). 서버마다 독립된 연속 세션(결정 79, 모델을 올린 채)이고 한 셀은 세션 4개다(meta ``ju.sessions``).
- 회차 seed = seed_base + k, 호출 seed = ``EV.call_seed``(문항 id 기준이라 조각 나누기와 무관). S = T 0.6, G1 = T 0.2, top-p 0.95·top-k 20.
- guard: 조각 프로세스가 느린 decode(exit 3)·입력 잘림(exit 4)으로 멈추거나, 이 실행기가 60초마다 보는 ``/api/ps``에서 ``size_vram < size``(100% GPU 아님)면
  그 조각을 멈춘다. 멈춘 조각의 원문·로그는 ``ABORTED_<조각>_<시각>``으로 남기고(판정·분석에 쓰지 않음) 실행기는 exit 3(입력 잘림은 exit 4).
  끝난 조각 파일(``.<label>_s<k>_part<j>.json``)은 남겨 두며, 같은 명령을 다시 실행하면 **끝나지 않은 조각만 처음부터** 다시 잰다(이어 돌리지 않음).
- 모든 조각이 끝나면 문항 순서대로 합쳐 ``<out>/<label>_s<k>.json``·``<raw>/<label>_s<k>_raw.jsonl``을 쓰고 조각 파일을 지운다. 출력이 있으면 멈춘다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EVAL = HERE / "ollama_eval_ju.py"
sys.path.insert(0, str(ROOT))
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
WORK = Path("/data/hwkim/sftdpo_work/pilot_010_ju/servers")
TEMPERATURE = {"s": "0.6", "g1": "0.2"}
KST = ZoneInfo("Asia/Seoul")


def now():
    return datetime.now(KST)


def sampling(cond):
    return ["--do-sample", "--temperature", TEMPERATURE[cond], "--top-p", "0.95", "--top-k", "20"]


def api_ps(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ps", timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ports", required=True)
    p.add_argument("--cond", choices=("s", "g1"), required=True)
    p.add_argument("--reference-date", default=None)
    p.add_argument("--seed-base", type=int, default=20261100)
    p.add_argument("--label", required=True)
    p.add_argument("--k", type=int, required=True)
    p.add_argument("--only", default=None)
    p.add_argument("--all-items", action="store_true")
    p.add_argument("--gold", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--raw-dir", required=True)
    p.add_argument("--min-tok-s", type=float, required=True)
    p.add_argument("--check-input", action="store_true")
    p.add_argument("--sealed", action="store_true")
    args = p.parse_args()
    RAW, out_dir = Path(args.raw_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    name = f"{args.label}_s{args.k}"
    final, final_raw = out_dir / f"{name}.json", RAW / f"{name}_raw.jsonl"
    if final.exists() or final_raw.exists():
        raise SystemExit(f"{final} exists")
    import evaluate_vendor100 as EV
    if args.all_items:
        ids = [i["id"] for i in EV.load_gold(ROOT / args.gold if not Path(args.gold).is_absolute() else Path(args.gold))["items"]]
    else:
        ids = args.only.split(",")
    ports = [int(x) for x in args.ports.split(",")]
    P = len(ports)
    shards = [ids[j::P] for j in range(P)]
    start = now()
    t0 = time.perf_counter()
    procs, reused = {}, []
    for j, shard in enumerate(shards):
        sp = out_dir / f".{name}_part{j}"
        rawp = RAW / f"{sp.name}_raw.jsonl"
        if Path(f"{sp}.json").exists() and rawp.exists():
            reused.append(j)
            continue
        for f in (Path(f"{sp}.json"), Path(f"{sp}.log"), rawp, Path(f"{sp}.json.abort.json")):
            f.unlink(missing_ok=True)
        port = ports[j]
        cmd = [PY, str(EVAL), "--host", f"http://127.0.0.1:{port}", "--gold", args.gold, "--only", ",".join(shard), "--condition-check",
               *sampling(args.cond), "--seed", str(args.seed_base + args.k), "--min-tok-s", str(args.min_tok_s),
               "--server-meta", str(WORK / f"server_{port}.json"), *(["--check-input"] if args.check_input else []),
               *(["--reference-date", args.reference_date] if args.reference_date else []), "--out", f"{sp}.json", "--raw-out", str(rawp)]
        procs[j] = subprocess.Popen(cmd, cwd=ROOT, stdout=open(f"{sp}.log", "w"), stderr=subprocess.STDOUT)
    ps_log, killed, stop = [], {}, threading.Event()

    def watch():
        while not stop.wait(60):
            for j, pr in procs.items():
                if pr.poll() is not None:
                    continue
                try:
                    ms = [m for m in api_ps(ports[j]).get("models", []) if m.get("name") == "qwen3.8:27b"]
                    ok = bool(ms) and ms[0].get("size_vram") == ms[0].get("size")
                    ps_log.append({"t": now().isoformat(timespec="seconds"), "port": ports[j], "ok_100_gpu": ok,
                                   "size": ms[0].get("size") if ms else None, "size_vram": ms[0].get("size_vram") if ms else None,
                                   "context_length": ms[0].get("context_length") if ms else None})
                    if not ok:
                        killed[j] = "not 100% GPU (/api/ps size_vram != size or model not loaded)"
                        pr.terminate()
                except Exception as error:  # noqa: BLE001
                    ps_log.append({"t": now().isoformat(timespec="seconds"), "port": ports[j], "error": str(error)[:200]})
    th = threading.Thread(target=watch, daemon=True)
    th.start()
    codes = {j: pr.wait() for j, pr in procs.items()}
    stop.set()
    th.join(timeout=5)
    wall = time.perf_counter() - t0
    end = now()
    bad = {j: c for j, c in codes.items() if c != 0}
    if bad:
        ts = end.strftime("%Y%m%dT%H%M%S")
        rec = {"cell": name, "at": end.isoformat(timespec="seconds"), "codes": bad, "killed_by_ps_guard": killed, "ps_checks": ps_log, "shards": {}}
        for j in bad:
            sp = out_dir / f".{name}_part{j}"
            ab = Path(f"{sp}.json.abort.json")
            rec["shards"][j] = {"port": ports[j], "items": len(shards[j]), "abort": json.loads(ab.read_text(encoding="utf-8")) if ab.exists() else None}
            for f in (Path(f"{sp}.log"), RAW / f"{sp.name}_raw.jsonl", ab, Path(f"{sp}.json")):
                if f.exists():
                    f.rename(f.parent / f"ABORTED_{f.name.lstrip('.')}_{ts}")
        (out_dir / f"ABORTED_{name}_{ts}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"aborted": name, "codes": bad, "killed": killed}, ensure_ascii=False))
        guard = all(c == 3 or j in killed for j, c in bad.items() if c != 4)
        sys.exit(4 if 4 in bad.values() else 3 if guard else 5)   # 5 = guard가 아닌 실패(코드 오류 등) → 실행기가 서버를 다시 띄우지 않고 멈춤
    parts = [json.loads(Path(f"{out_dir / f'.{name}_part{j}'}.json").read_text(encoding="utf-8")) for j in range(P)]
    rows = {r["id"]: r for d in parts for r in d["rows"]}
    if sorted(rows) != sorted(ids):
        raise SystemExit("merged items differ from requested items")
    merged_rows = [rows[i] for i in ids]
    raws = {}
    for j in range(P):
        for line in (RAW / f".{name}_part{j}_raw.jsonl").read_text(encoding="utf-8").splitlines():
            raws.setdefault(json.loads(line)["id"], []).append(line)
    with open(final_raw, "w", encoding="utf-8") as out:
        for i in ids:
            for line in raws.get(i, []):
                out.write(line + "\n")
    meta = parts[0]["meta"]
    meta["item_order"] = ids
    meta["hf"]["raw_out"] = str(final_raw.resolve())
    meta["hf"]["raw_out_sha256"] = hashlib.sha256(final_raw.read_bytes()).hexdigest()
    sessions = {}
    for j in range(P):
        m = parts[j]["meta"]
        sm = (m.get("ollama") or {}).get("server_meta") or {}
        rws = parts[j]["rows"]
        sessions[str(ports[j])] = {"shard": j, "items": len(shards[j]), "reused_from_earlier_run": j in reused,
                                   "first_item_started": rws[0]["started_at"] if rws else None, "last_item_finished": rws[-1]["finished_at"] if rws else None,
                                   "server_pid": sm.get("pid"), "server_started_at": sm.get("started_at"), "gpu_uuid": sm.get("gpu_uuid"), "gpu_index": sm.get("gpu_index"),
                                   "ollama_version": m.get("ollama_version"), "model_digest": m.get("model_digest"),
                                   "first_input_check": (m.get("ollama") or {}).get("first_input_check"),
                                   "api_ps_at_end": (m.get("ollama") or {}).get("api_ps_at_end"), "wall_seconds": (m.get("ollama") or {}).get("wall_seconds")}
    meta["ollama"] = {k: v for k, v in (meta.get("ollama") or {}).items() if k not in ("server_meta", "first_input_check", "api_ps_at_end")}
    meta["ollama"]["servers"] = {str(ports[j]): {k: ((parts[j]["meta"].get("ollama") or {}).get("server_meta") or {}).get(k)
                                                 for k in ("gpu_index", "gpu_uuid", "env", "binary_sha256", "show_parameters", "show_template", "log")} for j in range(P)}
    meta["ju"] = {"decision": 272, "plan": "sft_dpo_inventory/pilot_010/PLAN_JU.md", "cond": args.cond, "temperature": TEMPERATURE[args.cond],
                  "label": "교사 4비트 빌드 참고 측정(판정 아님); Ollama qwen3.8:27b(Q4_K_M, aaee06c3) — JT의 Qwen/Qwen3.8-27B BF16 (vLLM)과 다른 빌드; PF2·H-final 추가 사용",
                  "split": "item i -> shard i % 4 -> server ports[i % 4]; one sequential continuous session (decision 79) per server; one cell = 4 sessions",
                  "ports": ports, "shards": [len(s) for s in shards], "sessions": sessions, "ps_checks": len(ps_log),
                  "ps_all_100_gpu": all(x.get("ok_100_gpu") for x in ps_log if "error" not in x), "ps_errors": sum("error" in x for x in ps_log),
                  "reused_shards": reused, "wall_seconds": round(wall, 1), "started": start.isoformat(timespec="seconds"), "ended": end.isoformat(timespec="seconds")}
    result = {"meta": meta, "summary": EV._summary(merged_rows), "rows": merged_rows}
    final.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log = out_dir / f"{name}.log"
    with open(log, "w", encoding="utf-8") as lg:
        for j in range(P):
            lg.write(Path(f"{out_dir / f'.{name}_part{j}'}.log").read_text(encoding="utf-8"))
        calls = [c for r in merged_rows for c in r["hf_calls"]]
        tail = {"items": len(merged_rows), "servers": P, "wall_seconds": round(wall, 1), "calls": len(calls),
                "truncated_calls": sum(c["done_reason"] == "length" for c in calls), "ps_checks": len(ps_log)}
        if not args.sealed:
            tail = {"grounding_ok": sum(bool(r["grounding_ok"]) for r in merged_rows), **tail}
        lg.write(json.dumps(tail, ensure_ascii=False) + "\n")
    for j in range(P):
        sp = out_dir / f".{name}_part{j}"
        for f in (Path(f"{sp}.json"), Path(f"{sp}.log"), RAW / f"{sp.name}_raw.jsonl"):
            f.unlink(missing_ok=True)
    print(log.read_text(encoding="utf-8").splitlines()[-1])


if __name__ == "__main__":
    main()
