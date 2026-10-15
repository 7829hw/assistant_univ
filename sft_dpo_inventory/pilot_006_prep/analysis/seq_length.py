# -*- coding: utf-8 -*-
"""2a: Partial 입력이 길어져(P0.3) 학습 길이 한도(max_seq_length 11,392)를 넘는 레코드 추정. CPU만, 추정이지 판정이 아니다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/analysis/seq_length.py

- 레코드 길이 = 그 질문의 prompt token(학습과 같은 ``render_prompt``, enable_thinking, arm별 system prompt) + 응답 token
  (``<think>``thinking``</think>`` + 최종 JSON, 학습 target과 같은 형태) + 끝 token 1. 응답은 ``tokenizer(content)``로 센다.
- Full 레코드: 응답 = 원래 thinking + Full JSON(레코드 그대로). Partial 레코드: 같은 thinking + ``render_partial``로 바꾼 JSON(thinking은 같다고 가정;
  표현 중립 teacher 지시를 쓰면 teacher thinking은 두 arm이 같다 — 계획서 v2 8.1).
- 자료:
  1. pilot_004 데이터 판(``thinking_pilot004_t2pc`` SFT 467, 131질문): 출처별(teacher ``full_response`` / 8b 자체 ``json_only``).
  2. J1 원문(Full 8b 자체 표본, 지금까지 모인 것): greedy + 표본, 401문항 중 모인 문항. Partial은 같은 thinking + Partial JSON으로 추정.
     JSON이 없는 생성(잘림 등)은 학습에 쓰이지 않으므로 뺀다.
  3. canonical Partial 렌더(다음 판 후보 질문 풀): 최종 JSON 길이 분포(Full 대 Partial).
- 질문별: 어느 arm에서든 한도를 넘는 레코드가 있는 질문 목록.
- 선택지(고르지 않음): (A) 두 arm 모두 max_seq_length를 같은 값으로 올림(메모리 확인 필요, 다음 세션 GPU), (B) 어느 arm에서든 넘는 질문은 두 arm 모두에서 뺌.
출력: ``seq_length.json``.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

LIMIT = 11392


def main():
    import grounding as GT
    import hf_thinking as H
    from geoflow.planner import parse_planner_json
    from grounding.canonical import semantics_from_full
    from grounding.partial_renderer import render_partial
    from training.data.thinking import split_response
    from training.trainer_common import render_prompt
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    cfg = {"chat_template_kwargs": {"enable_thinking": True}}
    planners = {t: GT.make_planner(t, client=None) for t in ("full", "partial")}
    cache = {}

    def prompt_len(arm, question):
        key = (arm, question)
        if key not in cache:
            cache[key] = len(tok(render_prompt(tok, planners[arm].messages(question), cfg), add_special_tokens=False)["input_ids"])
        return cache[key]

    def n(text):
        return len(tok(text, add_special_tokens=False)["input_ids"])

    def response(thinking, answer):
        return f"<think>\n{thinking.strip()}\n</think>\n\n{answer}"

    def record_lengths(question, thinking, full_json):
        partial_json = json.dumps(render_partial(semantics_from_full(full_json)), ensure_ascii=False)
        full_text = json.dumps(full_json, ensure_ascii=False)
        return {"full": prompt_len("full", question) + n(response(thinking, full_text)) + 1,
                "partial": prompt_len("partial", question) + n(response(thinking, partial_json)) + 1,
                "thinking": n(thinking), "json_full": n(full_text), "json_partial": n(partial_json)}

    def summarize(rows):
        out = {"records": len(rows)}
        for arm in ("full", "partial"):
            over = [r for r in rows if r[arm] > LIMIT]
            out[arm] = {"over_limit": len(over), "over_pct": round(100 * len(over) / len(rows), 2) if rows else None,
                        "p50": float(np.percentile([r[arm] for r in rows], 50)), "p99": float(np.percentile([r[arm] for r in rows], 99)),
                        "max": max(r[arm] for r in rows)}
        only_p = [r for r in rows if r["partial"] > LIMIT >= r["full"]]
        out["partial_only_over"] = len(only_p)
        out["partial_only_over_pct"] = round(100 * len(only_p) / len(rows), 2) if rows else None
        out["room_for_response(median prompt)"] = {arm: LIMIT - statistics.median(r[arm] - r["thinking"] - r["json_" + arm] for r in rows) for arm in ("full", "partial")}
        return out

    result, by_q = {}, defaultdict(lambda: {"full": 0, "partial": 0, "records": 0})
    # 1. pilot_004 데이터 판
    src_rows = defaultdict(list)
    for line in (ROOT / "training/generated/thinking_pilot004_t2pc/sft_train.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        q = next(m["content"] for m in r["messages"] if m["role"] == "user")
        thinking, answer = split_response(r["messages"][-1]["content"])
        lens = record_lengths(q, thinking, json.loads(answer))
        src = "teacher(full_response)" if r["metadata"].get("loss_scope") == "full_response" else "8b_self(json_only)"
        src_rows[src].append(lens)
        key = r["metadata"]["source_record_id"]
        by_q[key]["records"] += 1
        by_q[key]["full"] += lens["full"] > LIMIT
        by_q[key]["partial"] += lens["partial"] > LIMIT
    result["pilot004_data"] = {s: summarize(v) for s, v in src_rows.items()}
    result["pilot004_data"]["all"] = summarize([x for v in src_rows.values() for x in v])
    result["pilot004_questions_over"] = {k: v for k, v in by_q.items() if v["full"] or v["partial"]}
    # 2. J1 원문
    items = {json.loads(l)["id"]: json.loads(l)["question"] for l in
             (ROOT / "sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl").read_text(encoding="utf-8").splitlines()}
    j1_rows, j1_q, no_json = [], defaultdict(lambda: {"full": 0, "partial": 0, "records": 0}), 0
    raw = ROOT / "training/generated/pilot_006/self_full/raw/self_full_raw.jsonl"
    if not raw.exists():  # 세션 1b: 큐가 manifest 단계 실패 뒤 이름을 바꿈(원문은 완전, j1_posthoc_manifest.py)
        raw = raw.with_name("ABORTED_self_full_raw.jsonl")
    for line in raw.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if "</think>" not in r["raw_text"]:
            no_json += 1
            continue
        thinking, answer = split_response(r["raw_text"])
        try:
            payload = parse_planner_json(answer)
            if not isinstance(payload, dict) or "concepts" not in payload:
                raise ValueError
        except Exception:  # noqa: BLE001 - JSON 없음
            no_json += 1
            continue
        try:
            lens = record_lengths(items[r["id"]], thinking, payload)
        except (KeyError, TypeError):  # subtype 없는 concept 등 렌더링할 수 없는 모델 출력(학습 필터에서 빠짐)
            no_json += 1
            continue
        lens["source"] = r.get("source")
        j1_rows.append(lens)
        q = j1_q[r["id"]]
        q["records"] += 1
        q["full"] += lens["full"] > LIMIT
        q["partial"] += lens["partial"] > LIMIT
    result["j1_full_self_samples"] = {"raw_lines": sum(1 for _ in raw.open(encoding="utf-8")), "no_json_unparsed_or_unrenderable": no_json,
                                      "questions_covered": len(j1_q), **summarize(j1_rows),
                                      "by_source": {s: summarize([x for x in j1_rows if x["source"] == s]) for s in sorted({x["source"] for x in j1_rows})}}
    result["j1_questions_over"] = {k: v for k, v in j1_q.items() if v["full"] or v["partial"]}
    # 3. canonical 렌더(최종 JSON 길이)
    canon = [json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/canonical/canonical_records.jsonl").read_text(encoding="utf-8").splitlines()]
    canon += [json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review/semantics_draft.jsonl").read_text(encoding="utf-8").splitlines()]
    from grounding.full_renderer import render_full
    jf = [n(json.dumps(render_full(c["semantics"]), ensure_ascii=False)) for c in canon]
    jp = [n(json.dumps(render_partial(c["semantics"]), ensure_ascii=False)) for c in canon]
    result["canonical_render_json_tokens"] = {"records": len(canon), "full_p50": statistics.median(jf), "full_max": max(jf),
                                              "partial_p50": statistics.median(jp), "partial_max": max(jp)}
    pf = [prompt_len("full", c["question"]) for c in canon]
    pp = [prompt_len("partial", c["question"]) for c in canon]
    result["prompt_tokens(canonical questions)"] = {"full": {"min": min(pf), "p50": statistics.median(pf), "max": max(pf)},
                                                    "partial": {"min": min(pp), "p50": statistics.median(pp), "max": max(pp)},
                                                    "room_for_thinking_plus_json(limit - max prompt)": {"full": LIMIT - max(pf), "partial": LIMIT - max(pp)}}
    all_rows = [x for v in src_rows.values() for x in v] + j1_rows
    result["partial_only_over_pct(all records above)"] = round(100 * sum(r["partial"] > LIMIT >= r["full"] for r in all_rows) / len(all_rows), 2)
    result["stop_check(>5%)"] = result["partial_only_over_pct(all records above)"] > 5
    result["options(not chosen)"] = {"A": "두 arm 모두 max_seq_length를 같은 값으로 올린다(필요 값 = 위 max; 메모리 확인은 다음 세션 GPU 작업)",
                                     "B": "어느 arm에서든 한도를 넘는 레코드의 질문은 두 arm 모두에서 뺀다(질문 목록 위)"}
    result["assumptions"] = ["Partial 레코드의 thinking은 같은 질문 Full 레코드와 같다", "J1은 이 분석 시점까지 모인 원문만", "최종 JSON 직렬화는 json.dumps(ensure_ascii False)"]
    (HERE / "seq_length.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    brief = {k: v for k, v in result.items() if not k.endswith("questions_over")}
    brief["pilot004_questions_over(count)"] = len(result["pilot004_questions_over"])
    brief["j1_questions_over(count)"] = len(result["j1_questions_over"])
    print(json.dumps(brief, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
