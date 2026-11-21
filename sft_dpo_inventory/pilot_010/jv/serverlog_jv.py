# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273, PLAN_JV 2·3절) Ollama 0.40.6 llama-server 로그 읽기(모델 호출 없음).

- ``sampler(text)``: 요청마다 ``sampler params:`` 블록(repeat_penalty·presence_penalty·frequency_penalty·top_k·top_p·min_p·temp …) → dict 목록.
- ``summary(text, expect)``: sampler 값이 기대값(temp·top_k·top_p·min_p·repeat_penalty·presence_penalty)과 같은 요청 수, ``task.n_tokens`` 목록,
  입력 잘림 줄(``truncating input``·``truncated = [1-9]``), speculative decoding(``--spec-type``·``draft-mtp``), llama-server 명령 줄.
"""
import re

TRUNC_RE = re.compile(r"(?i)truncating input|truncated = [1-9]")
KV = re.compile(r"([a-z_]+) = (-?[0-9.]+)")


def sampler(text):
    out, lines = [], text.splitlines()
    for i, l in enumerate(lines):
        if "sampler params:" in l:
            d = {}
            for x in lines[i + 1:i + 6]:
                if not x.startswith("\t"):
                    break
                d.update({k: float(v) for k, v in KV.findall(x)})
            out.append(d)
    return out


def summary(text, expect):
    s = sampler(text)
    keys = ("temp", "top_k", "top_p", "min_p", "repeat_penalty", "presence_penalty")
    ok = [all(abs(d.get(k, float("nan")) - expect[k]) < 1e-6 for k in keys) for d in s]
    cmd = next((l.strip() for l in text.splitlines() if "starting llama-server" in l), None)
    vals = {k: sorted({d.get(k) for d in s}) for k in keys + ("frequency_penalty", "repeat_last_n", "typical_p", "xtc_probability", "dry_multiplier", "mirostat")}
    return {"sampler_blocks": len(s), "sampler_all_expected": bool(s) and all(ok), "sampler_not_expected": len(s) - sum(ok), "sampler_values_seen": vals,
            "expected": expect, "task_n_tokens": [int(x) for x in re.findall(r"task\.n_tokens = (\d+)", text)],
            "truncation_lines": [l.strip()[:200] for l in text.splitlines() if TRUNC_RE.search(l)][:20],
            "speculative": {"spec_type_in_cmd": bool(cmd and "--spec-type" in cmd), "draft_mtp_lines": text.count("draft-mtp")},
            "llama_server_cmd": cmd[:2000] if cmd else None}


EXPECT_S = {"temp": 0.6, "top_k": 20, "top_p": 0.95, "min_p": 0.0, "repeat_penalty": 1.0, "presence_penalty": 0.0}
