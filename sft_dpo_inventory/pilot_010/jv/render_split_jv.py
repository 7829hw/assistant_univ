# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 2절) thinking·JSON 나눔 추가 확인(측정 전): ``render_check_jv.py``의 raw 생성도 Ollama parser가 thinking을 나눠 돌려줘서
학생 vLLM 방식(``hf_thinking.split_thinking``: 원문을 ``</think>``에서 나눔)과 직접 비교가 되지 않았다. 그래서 같은 5문항 첫 호출을
``/api/generate``(``raw: true``, ``think: false``, 같은 options·seed)로 원문 그대로 받아(parser가 나누지 않는지 확인) ``split_thinking``으로 나눈 값을
``/api/chat``(``think: true``) 응답의 thinking·content와 비교한다. 결과 → ``gpu/JV/render_split.json``.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/render_split_jv.py --main /home/hwkim/assistant_univ
"""
import argparse
import json
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
sys.path.insert(0, str(HERE.parents[2] / "sft_dpo_inventory/thinking_prep_001"))
import common_jv as C  # noqa: E402
import models_jv as M  # noqa: E402
from render_check_jv import post  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    a = ap.parse_args()
    ctx = C.Ctx(a.main, "jv-split")
    import hf_thinking as H
    import ollama_eval_jv as OE
    base = M.model("base", "base")
    reg = json.loads((HERE / "registration" / f"{base['name']}.json").read_text(encoding="utf-8"))
    g, job = 0, "render_split_base"
    stop = threading.Event()
    threading.Thread(target=C.mem_sampler, args=(ctx, stop), daemon=True).start()
    ok, sj, work = C.start_server(ctx, g, job, base["ollama"], reg["digest"], C.JV_MODELS)
    out = {"decision": 273, "server_ready": ok, "first_messages": "cells/JV/render/first_messages_base.jsonl"}
    try:
        if not ok:
            out["ok"] = False
            return
        ctx.running[g] = job
        comps = []
        for line in (ctx.cells / "render" / "first_messages_base.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            text = OE.hf8b_text(r["messages"])
            gen = post(C.PORTS[g], "/api/generate", {"model": base["ollama"], "prompt": text, "raw": True, "think": False, "stream": False,
                                                     "options": r["options_sent"], "keep_alive": -1})
            resp = gen.get("response") or ""
            th, ct, closed = H.split_thinking(resp)
            cth, cct = (r["thinking"] or "").strip(), (r["content"] or "").strip()
            comps.append({"id": r["id"], "generate_has_thinking_field": bool(gen.get("thinking")), "response_has_think_close": "</think>" in resp,
                          "response_starts": resp[:8], "generate_eval_count": gen.get("eval_count"), "chat_eval_count": r["eval_count"],
                          "same_tokens_count": gen.get("eval_count") == r["eval_count"], "closed": closed,
                          "thinking_equal_split": th == cth, "content_equal_split": ct == cct,
                          "content_equal_split_json": (json.loads(ct) == json.loads(cct)) if ct and cct and ct[:1] == "{" and cct[:1] == "{" else None})
        out["compare"] = comps
        raw_ok = [c for c in comps if not c["generate_has_thinking_field"] and c["response_has_think_close"]]
        same = [c for c in raw_ok if c["same_tokens_count"]]
        out["raw_text_returned"] = len(raw_ok)
        out["same_generation_count"] = len(same)
        out["split_equal_on_same_generation"] = all(c["thinking_equal_split"] and c["content_equal_split"] for c in same) if same else None
        out["server_log"] = C.server_log_summary(job, g, expect=C.SL.EXPECT_S)
        out["ok"] = bool(raw_ok) and out["split_equal_on_same_generation"] is True
    finally:
        ctx.running.pop(g, None)
        C.stop_server(ctx, g, job)
        stop.set()
        out["finished_at"] = C.now().isoformat(timespec="seconds")
        (ctx.G / "render_split.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: out.get(k) for k in ("ok", "raw_text_returned", "same_generation_count", "split_equal_on_same_generation")}, ensure_ascii=False))
        print(json.dumps(out.get("compare"), ensure_ascii=False))


if __name__ == "__main__":
    main()
