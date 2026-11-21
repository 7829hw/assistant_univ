# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 2·3절) 학생·교사 4비트 빌드 평가 client: **Ollama 0.40.6 Q4_K_M, 참고 측정(판정 아님)**.
``ju/ollama_eval_ju.py``(결정 272, 그대로 둠)의 사본이며 바꾼 것만 적는다(규칙 15).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jv/ollama_eval_jv.py --host http://127.0.0.1:11461 --model M --digest D --render hf8b \
        --gold G --only IDS --condition-check --do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --seed 20261101 --min-tok-s X --out OUT.json --raw-out RAW.jsonl

- 모델 이름·digest를 인자로 받는다(학생 ``geoflow-jv-…``, 교사 지연 셀 ``qwen3.8:27b``). 서버 버전 0.40.6·digest가 다르면 시작하지 않는다.
- **요청 options에 min_p 0·presence_penalty 0·repeat_penalty 1을 명시**한다(하네스 ``EV._SeededClient``의 ``extra_options``; JU 교사 셀은 보내지 않았고 모델 기본값이 같은 값). num_predict 8,192는 JU와 같음.
- 렌더링 검사(``--render``): 문항마다 **첫 호출**(messages = system + user)의 ``prompt_eval_count``를 기대 token 수와 비교해 다르면 즉시 멈춘다(exit 4).
  ``hf8b`` = Qwen3-8B@b968826d tokenizer의 chat template(``apply_chat_template(add_generation_prompt=True, enable_thinking=True)`` — 학생 vLLM 셀의 ``render_prompt``와 같음),
  ``qwen38`` = JU의 Ollama ``qwen3.8`` renderer 문자열(think true, effort 문장 없음)을 27B tokenizer로 셈. 모든 비교를 ``render_checks``에 남긴다.
- ``--save-first-messages``(렌더링 확인 셀만, 개발 셋만): 문항 첫 호출 messages·응답(thinking·content)·보낸 options를 파일로 남긴다(``render_check_jv.py``가 raw 생성과 대조).
- 나머지(행 형식·``hf_calls`` 기록·원문 재구성·속도 guard exit 3·PF2 gold 경로 처리)는 JU와 같다.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_005"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm"))

import evaluate_vendor100 as EV  # noqa: E402
import hf_eval_thinking as HE  # noqa: E402  (sampling_settings)
import hf_thinking as H  # noqa: E402  (MAX_NEW_TOKENS)
from ollama_client import OllamaClient, chat_options  # noqa: E402

LOCAL27 = "/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B"
EXTRA_OPTIONS = {"min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0}
_ORIG_META = EV._meta
_TOK = {}


def _meta_outside_gold(kind, extra=None):
    """JU와 같음: 저장소 밖 gold면 gold_file(절대 경로)·gold_sha256만 실제 gold로 바꾼다."""
    gp = Path(EV.GOLD_PATH or EV.GOLD_FILE).resolve()
    if EV.HERE in gp.parents:
        return _ORIG_META(kind, extra)
    saved = EV.GOLD_PATH
    try:
        EV.GOLD_PATH = None
        m = _ORIG_META(kind, extra)
    finally:
        EV.GOLD_PATH = saved
    m["gold_file"] = str(gp)
    m["gold_sha256"] = hashlib.sha256(gp.read_bytes()).hexdigest()
    return m


EV._meta = _meta_outside_gold


def get(host, path, body=None):
    req = urllib.request.Request(host.rstrip("/") + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def tokenizer(kind):
    if kind not in _TOK:
        from transformers import AutoTokenizer
        _TOK[kind] = AutoTokenizer.from_pretrained(LOCAL27) if kind == "qwen38" else \
            AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    return _TOK[kind]


def hf8b_text(messages):
    """학생 vLLM 셀과 같은 렌더링 문자열(training.trainer_common.render_prompt, enable_thinking=True)."""
    return tokenizer("hf8b").apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=True)


def expected_prompt_tokens(kind, messages):
    if kind == "hf8b":
        return len(tokenizer("hf8b")(hf8b_text(messages), add_special_tokens=False)["input_ids"])
    sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = [m["content"] for m in messages if m["role"] == "user"][-1]
    s = "<|im_start|>system\n" + sys_msg.strip() + "<|im_end|>\n<|im_start|>user\n" + user.strip() + "<|im_end|>\n<|im_start|>assistant\n<think>\n"
    return len(tokenizer("qwen38")(s, add_special_tokens=False)["input_ids"])


class OllamaClientJV(OllamaClient):
    """하네스 OllamaClient + num_predict + 호출 기록(hf_calls 자리) + 속도·렌더링 guard."""

    def __init__(self, host, model, *, num_predict, chat_timeout, min_tok_s, abort_path, render, save_first):
        super().__init__(host, model, {"temperature": 0}, chat_timeout=chat_timeout, think=True)
        self.num_predict, self.min_tok_s, self.abort_path, self.render = num_predict, min_tok_s, abort_path, render
        self.log, self.last, self.request_example = [], None, None
        self.render_checks, self.calls_total, self.item_id = [], 0, None
        self.save_first = save_first

    def _abort(self, code, reason):
        Path(self.abort_path).write_text(json.dumps({"at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), "reason": reason,
                                                     "host": self.host, "calls_done": self.calls_total}, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"ABORT {reason}", flush=True)
        os._exit(code)

    def chat(self, messages, tools=None):
        first = len(self.log) == 0
        sent = chat_options(self.options, self.num_predict)
        base = self.options
        self.options = sent
        t0 = time.perf_counter()
        try:
            resp = super().chat(messages, tools=tools)
        finally:
            self.options = base
        wall = time.perf_counter() - t0
        self.calls_total += 1
        msg = resp.get("message") or {}
        thinking, content = msg.get("thinking") or "", msg.get("content") or ""
        ec, ed = resp.get("eval_count") or 0, (resp.get("eval_duration") or 0) / 1e9
        rate = ec / ed if ed > 0 else None
        dr = resp.get("done_reason")
        rec = {"done_reason": dr, "finish_reason": dr, "generated_tokens": ec, "prompt_tokens": resp.get("prompt_eval_count"),
               "server_seconds": round((resp.get("total_duration") or 0) / 1e9, 3), "eval_seconds": round(ed, 3),
               "prompt_eval_seconds": round((resp.get("prompt_eval_duration") or 0) / 1e9, 3), "load_seconds": round((resp.get("load_duration") or 0) / 1e9, 3),
               "decode_tok_s": None if rate is None else round(rate, 2), "wall_seconds": round(wall, 3), "think_closed": bool(content.strip()),
               "thinking_chars": len(thinking), "content_chars": len(content), "options_sent": sent, "tools_sent": tools is not None,
               "sampling_seed": sent.get("seed")}
        raw_text = "<think>\n" + thinking + "\n</think>\n\n" + content
        self.last = {"raw_text": raw_text, "raw_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(), "generated_tokens": ec, "done_reason": dr,
                     "finish_reason": dr, "think_closed": rec["think_closed"], "thinking": thinking, "content": content,
                     "prompt_eval_count": resp.get("prompt_eval_count"), "eval_count": ec}
        if self.request_example is None:
            self.request_example = {"model": self.model, "stream": False, "think": self.think, "options": sent, "tools": None if tools is None else len(tools),
                                    "messages": [{"role": m["role"], "chars": len(m.get("content") or ""),
                                                  "sha256": hashlib.sha256((m.get("content") or "").encode("utf-8")).hexdigest()} for m in messages]}
        if first:
            exp = expected_prompt_tokens(self.render, messages)
            got = resp.get("prompt_eval_count") or 0
            chk = {"id": self.item_id, "roles": [m["role"] for m in messages], "prompt_eval_count": got, "expected": exp, "diff": got - exp, "render": self.render}
            rec["render_check"] = chk
            self.render_checks.append(chk)
            if self.save_first is not None:
                self.save_first.write(json.dumps({"id": self.item_id, "messages": messages, "options_sent": sent, "thinking": thinking, "content": content,
                                                  "done_reason": dr, "eval_count": ec, "prompt_eval_count": got}, ensure_ascii=False) + "\n")
                self.save_first.flush()
            if got != exp:
                self.log.append(rec)
                self._abort(4, f"render mismatch {self.item_id}: prompt_eval_count {got} != expected {exp} ({self.render})")
        self.log.append(rec)
        if self.min_tok_s and ec >= 64 and rate is not None and rate < self.min_tok_s:
            self._abort(3, f"slow decode {rate:.2f} tok/s < {self.min_tok_s} (eval_count {ec})")
        return resp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--render", choices=("hf8b", "qwen38"), required=True)
    parser.add_argument("--model-meta", default="{}", help="JSON: arm·seed·adapter 등(기록만)")
    parser.add_argument("--out", required=True)
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--condition-check", action="store_true")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=date(2026, 9, 25))
    parser.add_argument("--only", default="")
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--min-p", type=float, default=None)
    parser.add_argument("--repetition-penalty", type=float, default=None)
    parser.add_argument("--gold", required=True)
    parser.add_argument("--chat-timeout", type=float, default=3600.0)
    parser.add_argument("--min-tok-s", type=float, required=True)
    parser.add_argument("--server-meta", default=None)
    parser.add_argument("--save-first-messages", default=None)
    args = parser.parse_args()
    if args.min_p is not None or args.repetition_penalty is not None:
        raise SystemExit("JV는 min_p·repeat_penalty·presence_penalty를 EXTRA_OPTIONS로만 보낸다(PLAN_JV 2절)")
    sampling = HE.sampling_settings(args)
    if sampling is None:
        raise SystemExit("JV는 sampling 셀만 잰다")
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")
    gold_path = Path(args.gold).resolve()
    if args.save_first_messages and ROOT not in gold_path.parents:
        raise SystemExit("--save-first-messages는 저장소 안 개발 셋에만")

    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = args.reference_date
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    version = get(args.host, "/api/version").get("version")
    tags = {m["name"]: m for m in get(args.host, "/api/tags").get("models", [])}
    if tags.get(args.model, {}).get("digest") != args.digest or version != "0.40.6":
        raise SystemExit(f"server model/version differs: {version} {tags.get(args.model, {}).get('digest')}")
    save = open(args.save_first_messages, "w", encoding="utf-8") if args.save_first_messages else None
    client = OllamaClientJV(args.host, args.model, num_predict=H.MAX_NEW_TOKENS, chat_timeout=args.chat_timeout, min_tok_s=args.min_tok_s,
                            abort_path=f"{args.out}.abort.json", render=args.render, save_first=save)
    EV.GOLD_PATH = gold_path
    items = [i for i in EV.load_gold(gold_path)["items"] if not args.only or i["id"] in args.only.split(",")]
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    harness_sampling = {"temperature": sampling["params"]["temperature"], "top_p": sampling["params"]["top_p"], "top_k": sampling["params"]["top_k"],
                        "round_seed": sampling["round_seed"], "seed_rule": EV.SEED_RULE, "extra_options": dict(EXTRA_OPTIONS)}
    rows = []
    started_all = time.perf_counter()
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        for item in items:
            item_started = datetime.now(ZoneInfo("Asia/Seoul"))
            client.log = []
            client.item_id = item["id"]
            seeded = EV._SeededClient(client, harness_sampling, item["id"])
            recorder = EV._RecordingClient(seeded)
            options = {"condition_notes": False} if args.condition_check else {}
            pipeline = GeoFlowPipeline.create(
                client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
                clock=lambda: EV.REFERENCE_DATE, condition_check=args.condition_check,
                execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), **options)
            raws = []
            orig = client.chat

            def chat(messages, tools=None, **kwargs):
                response = orig(messages, tools=tools, **kwargs)
                raws.append(dict(client.last))
                return response
            client.chat = chat
            try:
                observed = EV.run_item(pipeline, item["question"])
            except Exception as error:  # noqa: BLE001
                observed = EV._crashed(error)
            finally:
                client.chat = orig
            category, checks = EV.score(item, observed)
            grounding_ok, grounding_diffs = EV.grounding_check(item, observed["grounding"])
            for index, raw in enumerate(raws):
                raw_stream.write(json.dumps({"id": item["id"], "call": index, "sampling_seed": client.log[index]["sampling_seed"], **raw},
                                            ensure_ascii=False) + "\n")
            raw_stream.flush()
            rows.append({"id": item["id"], "question": item["question"], "vendor_verdict": item.get("vendor_verdict"),
                         "category": category, "checks": checks, "reset_ok": None,
                         "grounding_ok": grounding_ok, "grounding_diffs": grounding_diffs,
                         "llm_calls": recorder.calls, "hf_calls": client.log,
                         "started_at": item_started.isoformat(),
                         "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), **observed})
            print(f"{item['id']} {category} {observed['outcome']} {observed['error_code'] or ''} "
                  f"{[(c['generated_tokens'], c['decode_tok_s']) for c in client.log]}", flush=True)
    wall = time.perf_counter() - started_all
    if save:
        save.close()
    try:
        ps = get(args.host, "/api/ps")
    except Exception as error:  # noqa: BLE001
        ps = {"error": str(error)}
    mm = json.loads(args.model_meta)
    meta = EV._meta("llm", {
        "model": args.model, "model_digest": args.digest, "ollama_version": version, "model_details": tags[args.model].get("details"),
        "hf": {"model": f"ollama:{args.model}", "revision": None, "adapter": mm.get("adapter"), "jv_model": mm,
               "note": "Ollama 0.40.6 Q4_K_M(JV, 결정 273) — 참고 측정; 학생은 공식 방식 Q4(attn_v F16) + hfthink TEMPLATE, 교사는 JU와 같은 qwen3.8:27b",
               "decoding": {"do_sample": True, **sampling["params"], "num_predict": H.MAX_NEW_TOKENS, "round_seed": sampling["round_seed"],
                            "seed_rule": EV.SEED_RULE, "seed_application": "Ollama options.seed(호출마다, EV._SeededClient)",
                            "extra_options_sent": EXTRA_OPTIONS, "not_sent": "num_ctx(서버 기본값 또는 OLLAMA_CONTEXT_LENGTH)"},
               "raw_out": str(Path(args.raw_out).resolve()),
               "raw_out_sha256": hashlib.sha256(Path(args.raw_out).read_bytes()).hexdigest(),
               "raw_text_note": "raw_text = '<think>\\n' + thinking + '\\n</think>\\n\\n' + content (Ollama parser 출력의 재구성)"},
        "ollama": {"host": args.host, "server_meta": json.loads(Path(args.server_meta).read_text(encoding="utf-8")) if args.server_meta else None,
                   "request_example(no message content)": client.request_example, "render": args.render,
                   "render_checks": client.render_checks, "render_all_equal": all(c["diff"] == 0 for c in client.render_checks),
                   "api_ps_at_end": ps, "wall_seconds": round(wall, 1), "chat_timeout_s": args.chat_timeout, "min_tok_s_guard": args.min_tok_s},
        "planner_prompt_sha256": prompt_sha, "code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"],
        "pipeline": {"aggregation_grounding": "flat", "condition_check": args.condition_check, "condition_notes": False,
                     "normalize_grounding": True, "semantic_reinterpretation": True, "provider": "mock",
                     "tims_execution": "legacy", "client": "ollama(evaluate_vendor100 llm 경로: OllamaClient·_SeededClient·_RecordingClient)",
                     "think": "on(think=true)", "isolation": "keep_loaded", "start_unload": False,
                     "temperature": sampling["params"]["temperature"], "sampling": harness_sampling},
        "run_settings": {"reference_date": args.reference_date.isoformat(), "model_state": "keep_loaded", "order": "file"},
        "item_order": [i["id"] for i in items], "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "scorer_version": EV.SCORER_VERSION})
    result = {"meta": meta, "summary": EV._summary(rows), "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(rows), "truncated_calls": sum(1 for r in rows for c in r["hf_calls"] if c["done_reason"] == "length"),
                      "wall_seconds": round(wall, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
