# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272, PLAN_JU) 교사 4비트 빌드 평가 client: **Ollama ``qwen3.8:27b``(Q4_K_M, digest aaee06c3…), 참고 측정(판정 아님)**.
``jt/vllm_eval_jt.py``(그대로 둠)의 사본이며 모델 호출 부분만 하네스의 Ollama 경로로 바꿨다(규칙 15).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/ju/ollama_eval_ju.py --host http://127.0.0.1:11441 --gold G --only IDS \
        --condition-check --temperature 0.6 --top-p 0.95 --top-k 20 --seed 20261101 --min-tok-s 33.71 --out OUT.json --raw-out RAW.jsonl

- 모델 호출 = 하네스 ``evaluate_vendor100.py llm``의 Ollama 경로 그대로: ``ollama_client.OllamaClient``(``/api/chat``, ``stream: false``, messages·tools 변환 없음),
  ``think: true``(``--model-think on``과 같음), 문항마다 ``EV._SeededClient``(호출 seed = ``EV.call_seed``, options = temperature·top_p·top_k·seed),
  ``EV._RecordingClient``(``llm_calls``·원문). 기본 options ``{"temperature": 0}``은 ``_SeededClient``가 호출마다 sampling 값으로 바꾼다(하네스와 같음).
- 하네스에 더한 것 하나: 생성 상한 ``num_predict`` = 학생 셀 max_new_tokens(8,192, ``hf_thinking.MAX_NEW_TOKENS``)를 요청 options에 넣는다
  (``ollama_client.chat_options``; 하네스 ``llm``은 상한을 보내지 않음 — 지시 "생성 상한은 학생 셀과 같게"). num_ctx·min_p·repeat_penalty 등은 보내지 않는다
  (모델 params·서버 기본값; ``ollama show`` 기록).
- 행 형식은 JT 셀과 같게 둔다: ``llm_calls``(하네스 기록, 채점기가 ``done_reason``을 읽음)와 ``hf_calls`` 자리에 호출별 Ollama 응답 수치
  (``finish_reason`` = ``done_reason``, ``generated_tokens`` = ``eval_count``, ``prompt_tokens`` = ``prompt_eval_count``, ``server_seconds`` = ``total_duration``,
  ``eval_seconds``, ``decode_tok_s`` = eval_count / eval_duration, ``think_closed``(추정: 최종 content가 비지 않았는가), 보낸 options).
- 원문(``--raw-out``, 저장소 밖이나 ignore 경로): 호출마다 ``thinking``·``content``(Ollama parser가 나눈 값)와 ``raw_text`` = ``<think>\\n`` + thinking + ``\\n</think>\\n\\n`` + content
  (분석 호환용 재구성 — 모델이 낸 token열 그대로가 아님).
- guard(결정 55를 Docker 없이, PLAN_JU 3절): 호출마다 ``eval_count ≥ 64``이고 ``decode_tok_s < --min-tok-s``면 그 조각을 즉시 멈춘다(``<out>.abort.json``, exit 3).
  ``--check-input``(smoke): 조각의 첫 응답 ``prompt_eval_count``가 Ollama ``qwen3.8`` renderer(think true = effort 문장 없음) 기준 기대 token 수보다 16 넘게 적으면
  입력이 잘린 것으로 보고 멈춘다(exit 4). 기대 token 수는 27B HF tokenizer로 센다(같은 어휘 가정, 기록).
- PF2(저장소 밖 gold)는 vllm_eval_jt와 같이 ``EV._meta``를 감싸 절대 경로·sha256을 적는다. 요청 예시는 messages 내용 없이(역할·길이·sha256) 남긴다.
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

MODEL = "qwen3.8:27b"
DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"
LOCAL27 = "/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B"   # 기대 입력 token 수 세기에만 씀(같은 어휘 가정)
_ORIG_META = EV._meta


def _meta_outside_gold(kind, extra=None):
    """vllm_eval_jt와 같음: 저장소 밖 gold면 gold_file(절대 경로)·gold_sha256만 실제 gold로 바꾼다."""
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


def expected_prompt_tokens(messages):
    """Ollama 0.40.6 ``qwen3.8`` renderer(tools 없음, think true → effort 문장 없음)의 문자열을 27B HF tokenizer로 센다. 비교용으로 xhigh 문장을 넣은 값도."""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(LOCAL27)
    sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = [m["content"] for m in messages if m["role"] == "user"][-1]
    xhigh = ("Reasoning effort is set to xhigh. Please think carefully through the task, validate key assumptions, consider plausible alternatives, "
             "and prioritize correctness, consistency, and clarity in the final answer.")

    def render(effort):
        s = "<|im_start|>system\n" + (effort + "\n\n" if effort else "") + sys_msg.strip() + "<|im_end|>\n"
        return s + "<|im_start|>user\n" + user.strip() + "<|im_end|>\n<|im_start|>assistant\n<think>\n"
    n = lambda s: len(tok(s, add_special_tokens=False)["input_ids"])  # noqa: E731
    return {"no_effort_sentence": n(render(None)), "with_xhigh_sentence": n(render(xhigh))}


class OllamaClientJU(OllamaClient):
    """하네스 OllamaClient + num_predict + 호출 기록(hf_calls 자리) + 속도·입력 guard."""

    def __init__(self, host, *, num_predict, chat_timeout, min_tok_s, abort_path, check_input):
        super().__init__(host, MODEL, {"temperature": 0}, chat_timeout=chat_timeout, think=True)
        self.num_predict = num_predict
        self.min_tok_s = min_tok_s
        self.abort_path = abort_path
        self.check_input = check_input
        self.log, self.last, self.request_example, self.first_input = [], None, None, None
        self.calls_total = 0

    def _abort(self, code, reason):
        Path(self.abort_path).write_text(json.dumps({"at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), "reason": reason,
                                                     "host": self.host, "calls_done": self.calls_total}, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"ABORT {reason}", flush=True)
        os._exit(code)

    def chat(self, messages, tools=None):
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
        self.log.append(rec)
        raw_text = "<think>\n" + thinking + "\n</think>\n\n" + content
        self.last = {"raw_text": raw_text, "raw_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(), "generated_tokens": ec, "done_reason": dr,
                     "finish_reason": dr, "think_closed": rec["think_closed"], "thinking": thinking, "content": content,
                     "prompt_eval_count": resp.get("prompt_eval_count"), "eval_count": ec}
        if self.request_example is None:
            self.request_example = {"model": self.model, "stream": False, "think": self.think, "options": sent, "tools": None if tools is None else len(tools),
                                    "messages": [{"role": m["role"], "chars": len(m.get("content") or ""),
                                                  "sha256": hashlib.sha256((m.get("content") or "").encode("utf-8")).hexdigest()} for m in messages]}
        if self.first_input is None:
            exp = expected_prompt_tokens(messages)
            got = resp.get("prompt_eval_count") or 0
            self.first_input = {"prompt_eval_count": got, "expected": exp, "diff_vs_no_effort": got - exp["no_effort_sentence"],
                                "diff_vs_xhigh": got - exp["with_xhigh_sentence"], "checked": self.check_input}
            if self.check_input and got < exp["no_effort_sentence"] - 16:
                self._abort(4, f"input truncated? prompt_eval_count {got} < expected {exp['no_effort_sentence']} - 16")
        if self.min_tok_s and ec >= 64 and rate is not None and rate < self.min_tok_s:
            self._abort(3, f"slow decode {rate:.2f} tok/s < {self.min_tok_s} (eval_count {ec})")
        return resp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
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
    parser.add_argument("--check-input", action="store_true")
    parser.add_argument("--server-meta", default=None)
    args = parser.parse_args()
    if args.min_p is not None or args.repetition_penalty is not None:
        raise SystemExit("JU는 min_p·repeat_penalty를 보내지 않는다(하네스 운영 options 그대로, PLAN_JU 2절)")
    sampling = HE.sampling_settings(args)
    if sampling is None:
        raise SystemExit("JU는 sampling 셀만 잰다")
    if ROOT in Path(args.raw_out).resolve().parents and "generated" not in Path(args.raw_out).parts:
        raise SystemExit("--raw-out은 저장소 밖이나 ignore 경로(generated)여야 한다")

    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    from geoflow.planner import GeoFlowPlanner
    import execution_spec

    EV.REFERENCE_DATE = args.reference_date
    prompt_sha = hashlib.sha256(GeoFlowPlanner(client=None).system_prompt().encode("utf-8")).hexdigest()
    version = get(args.host, "/api/version").get("version")
    tags = {m["name"]: m for m in get(args.host, "/api/tags").get("models", [])}
    if tags.get(MODEL, {}).get("digest") != DIGEST or version != "0.40.6":
        raise SystemExit(f"server model/version differs: {version} {tags.get(MODEL, {}).get('digest')}")
    client = OllamaClientJU(args.host, num_predict=H.MAX_NEW_TOKENS, chat_timeout=args.chat_timeout, min_tok_s=args.min_tok_s,
                            abort_path=f"{args.out}.abort.json", check_input=args.check_input)
    gold_path = Path(args.gold).resolve()
    EV.GOLD_PATH = gold_path
    items = [i for i in EV.load_gold(gold_path)["items"] if not args.only or i["id"] in args.only.split(",")]
    Path(args.raw_out).parent.mkdir(parents=True, exist_ok=True)
    harness_sampling = {"temperature": sampling["params"]["temperature"], "top_p": sampling["params"]["top_p"], "top_k": sampling["params"]["top_k"],
                        "round_seed": sampling["round_seed"], "seed_rule": EV.SEED_RULE}
    rows = []
    started_all = time.perf_counter()
    with open(args.raw_out, "w", encoding="utf-8") as raw_stream:
        for item in items:
            item_started = datetime.now(ZoneInfo("Asia/Seoul"))
            client.log = []
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
    try:
        ps = get(args.host, "/api/ps")
    except Exception as error:  # noqa: BLE001
        ps = {"error": str(error)}
    meta = EV._meta("llm", {
        "model": MODEL, "model_digest": DIGEST, "ollama_version": version, "model_details": tags[MODEL].get("details"),
        "hf": {"model": f"ollama:{MODEL}", "revision": None, "adapter": None,
               "note": "Ollama qwen3.8:27b (Q4_K_M, digest aaee06c3) — 교사 응답 수집·운영 빌드; JT의 Qwen/Qwen3.8-27B BF16 (vLLM)과 다른 빌드",
               "decoding": {"do_sample": True, **sampling["params"], "num_predict": H.MAX_NEW_TOKENS, "round_seed": sampling["round_seed"],
                            "seed_rule": EV.SEED_RULE, "seed_application": "Ollama options.seed(호출마다, EV._SeededClient)",
                            "not_sent": "num_ctx·min_p·repeat_penalty·presence_penalty(모델 params·서버 기본값)"},
               "raw_out": str(Path(args.raw_out).resolve()),
               "raw_out_sha256": hashlib.sha256(Path(args.raw_out).read_bytes()).hexdigest(),
               "raw_text_note": "raw_text = '<think>\\n' + thinking + '\\n</think>\\n\\n' + content (Ollama parser 출력의 재구성)"},
        "ollama": {"host": args.host, "server_meta": json.loads(Path(args.server_meta).read_text(encoding="utf-8")) if args.server_meta else None,
                   "request_example(no message content)": client.request_example, "first_input_check": client.first_input,
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
