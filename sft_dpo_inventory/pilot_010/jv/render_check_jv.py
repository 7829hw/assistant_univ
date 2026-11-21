# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 2절) 측정 전 렌더링·요청 확인: base Q4, GPU 0, H-dev 앞 5문항 × 1(S). 결과 → ``gpu/JV/render_check.json``.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/render_check_jv.py --main /home/hwkim/assistant_univ

1. 서버(``serve_jv.sh``)를 띄워 ``/api/show``에 renderer·parser가 없는지, manifest template 층 = hfthink인지(등록 기록) 본다.
2. 하네스 경로 셀(``run_cell_jv.py``, ``--save-first-messages``): 문항마다 첫 호출 ``prompt_eval_count`` = HF chat template(``enable_thinking=True``) token 수(다르면 client가 멈춤).
3. 같은 첫 호출 messages를 HF template 문자열로 렌더링해 ``/api/generate``(``raw: true``, 같은 options·seed)로 다시 생성: ``prompt_eval_count``, 원문을 ``hf_thinking.split_thinking``으로
   나눈 (thinking, content)가 ``/api/chat``의 것과 같은지. 같지 않으면 구조 검사(content에 think 태그 없음, thinking이 태그로 시작하지 않음).
4. 서버 로그의 요청마다 sampler 값(temp·top_k·top_p·min_p·repeat_penalty·presence_penalty) = 기대값인지, ``task.n_tokens``, 잘림 줄, speculative decoding 여부.
"""
import argparse
import json
import sys
import threading
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[2]))
sys.path.insert(0, str(HERE.parents[2] / "sft_dpo_inventory/thinking_prep_001"))
import common_jv as C  # noqa: E402
import models_jv as M  # noqa: E402

N = 5


def post(port, path, body, timeout=3600):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    a = ap.parse_args()
    ctx = C.Ctx(a.main, "jv-render")
    import evaluate_vendor100 as EV
    import hf_thinking as H
    import ollama_eval_jv as OE
    base = M.model("base", "base")
    reg = json.loads((HERE / "registration" / f"{base['name']}.json").read_text(encoding="utf-8"))
    g, job = 0, "render_base"
    stop = threading.Event()
    th = threading.Thread(target=C.mem_sampler, args=(ctx, stop), daemon=True)
    th.start()
    ok, sj, work = C.start_server(ctx, g, job, base["ollama"], reg["digest"], C.JV_MODELS)
    out = {"decision": 273, "model": base, "registration": {k: reg.get(k) for k in ("digest", "show_renderer", "show_parser", "show_template_sha256")},
           "manifest_check": {k: (reg.get("manifest_check") or {}).get(k) for k in ("template_layer_equals_sent_hfthink", "config_has_renderer_or_parser", "runner", "params_layer")},
           "server_ready": ok, "server": {k: (sj or {}).get(k) for k in ("version", "digest", "gpu_100", "backend_cuda", "only_own_gpu", "context_length", "show_renderer",
                                                                           "show_parser", "show_keys", "show_capabilities", "show_parameters", "llama_server_cmd")}}
    try:
        if not ok:
            out["ok"] = False
            out["stop_reason"] = "server not ready"
            return
        ids = [i["id"] for i in EV.load_gold(C.WT / C.HDEV_GOLD)["items"]][:N]
        first = ctx.cells / "render" / "first_messages_base.jsonl"
        ctx.running[g] = job
        cmd = [C.PY, str(HERE / "run_cell_jv.py"), "--port", str(C.PORTS[g]), "--gpu", str(g), "--model", base["ollama"], "--digest", reg["digest"], "--render", "hf8b",
               "--label", "renderjv_base_q4", "--k", "1", "--gold", C.HDEV_GOLD, "--only", ",".join(ids), "--out-dir", str(ctx.cells / "render"),
               "--raw-dir", str(ctx.raw), "--min-tok-s", "30", "--server-meta", str(work / f"server_{C.PORTS[g]}.json"),
               "--model-meta", json.dumps(base), "--save-first-messages", str(first)]
        import subprocess
        rc = subprocess.run(cmd, cwd=C.WT, env=ctx.env).returncode
        out["harness_cell_rc"] = rc
        cell = ctx.cells / "render" / "renderjv_base_q4_s1.json"
        if rc != 0 or not cell.exists():
            out["ok"] = False
            out["stop_reason"] = f"harness cell rc {rc}"
            return
        d = json.loads(cell.read_text(encoding="utf-8"))
        out["render_checks"] = d["meta"]["ollama"]["render_checks"]
        out["request_example"] = d["meta"]["ollama"]["request_example(no message content)"]
        comps = []
        for line in first.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            text = OE.hf8b_text(r["messages"])
            gen = post(C.PORTS[g], "/api/generate", {"model": base["ollama"], "prompt": text, "raw": True, "stream": False, "options": r["options_sent"], "keep_alive": -1})
            if gen.get("thinking"):
                th_, ct_, how = gen["thinking"].strip(), (gen.get("response") or "").strip(), "generate thinking field"
            else:
                th_, ct_, closed = H.split_thinking(gen.get("response") or "")
                how = "hf_thinking.split_thinking(response)"
            chat_th, chat_ct = (r["thinking"] or "").strip(), (r["content"] or "").strip()
            comps.append({"id": r["id"], "chat_prompt_eval_count": r["prompt_eval_count"], "generate_prompt_eval_count": gen.get("prompt_eval_count"),
                          "hf_tokens": OE.expected_prompt_tokens("hf8b", r["messages"]), "chat_eval_count": r["eval_count"], "generate_eval_count": gen.get("eval_count"),
                          "generate_split": how, "same_generation": th_ == chat_th and ct_ == chat_ct, "thinking_equal": th_ == chat_th, "content_equal": ct_ == chat_ct,
                          "chat_content_has_think_tag": "<think>" in chat_ct or "</think>" in chat_ct, "chat_thinking_starts_with_tag": chat_th.startswith("<think>"),
                          "generate_response_starts_with_think": (gen.get("response") or "").lstrip().startswith("<think>"),
                          "generate_done_reason": gen.get("done_reason"), "chat_done_reason": r["done_reason"]})
        out["split_compare"] = comps
        out["server_log"] = C.server_log_summary(job, g)
        sl = out["server_log"] or {}
        out["render_all_equal"] = all(c["diff"] == 0 for c in out["render_checks"]) and len(out["render_checks"]) == N
        out["generate_prompt_equal_hf"] = all(c["generate_prompt_eval_count"] == c["hf_tokens"] for c in comps)
        out["split_same_all"] = all(c["same_generation"] for c in comps)
        out["split_structure_ok"] = all(not c["chat_content_has_think_tag"] and not c["chat_thinking_starts_with_tag"] for c in comps)
        out["sampler_log_present"] = bool(sl.get("sampler_blocks"))
        out["sampler_all_expected"] = sl.get("sampler_all_expected")
        out["use_ollama_debug"] = not out["sampler_log_present"]
        out["no_renderer"] = not (sj.get("show_renderer") or sj.get("show_parser")) and not out["manifest_check"]["config_has_renderer_or_parser"]
        out["ok"] = bool(out["render_all_equal"] and out["no_renderer"] and out["manifest_check"]["template_layer_equals_sent_hfthink"]
                         and out["split_structure_ok"] and (out["sampler_all_expected"] or not out["sampler_log_present"]) and not sl.get("truncation_lines"))
    finally:
        ctx.running.pop(g, None)
        C.stop_server(ctx, g, job)
        stop.set()
        out["finished_at"] = C.now().isoformat(timespec="seconds")
        (ctx.G / "render_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: out.get(k) for k in ("ok", "render_all_equal", "generate_prompt_equal_hf", "split_same_all", "split_structure_ok",
                                                  "sampler_log_present", "sampler_all_expected", "no_renderer", "stop_reason")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
