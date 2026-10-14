# -*- coding: utf-8 -*-
"""입력 일치 확인(결정 89, 작업 3, 측정 전에 한다). selection_v2 앞 10문항의 첫 호출 prompt token id를 비교한다.

    hfvenv/bin/python sft_dpo_inventory/serving_vllm/check_inputs.py --base-url http://127.0.0.1:8100

- 첫 호출 messages는 HF 평가와 같은 pipeline 구성으로 잡는다(모델 호출 없음, logprob_diag ``first_call_messages``).
- (1) HF 평가 경로의 id열: ``render_prompt``(enable_thinking) + 같은 tokenizer. pilot_003 HF-base 기록의 첫 호출 prompt token 수와 대조한다.
- (2) vLLM이 받은 id열: 그 id열을 ``/v1/completions`` prompt로 넘기고(max_tokens 1, temperature 0) 응답의 ``prompt_token_ids``와 비교한다.
  평가 client(``vllm_thinking.py``)가 쓰는 방식이다. **하나라도 다르면 exit 1(측정하지 않는다).**
- (3) 참고: vLLM 서버 자체 렌더링(``/tokenize``에 messages와 ``chat_template_kwargs.enable_thinking``)과 비교한다. 평가에는 쓰지 않는다.
- 결과: ``input_check.json``(id열 sha256과 길이만).
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/logprob_diag"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
sys.path.insert(0, str(HERE))

IDS = (ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")[:10]
GOLD = ROOT / "sft_dpo_inventory/conversion_diag/selection_gold.yaml"


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def sha(ids):
    return hashlib.sha256(json.dumps(ids).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", required=True)
    args = p.parse_args()
    import evaluate_vendor100 as EV
    from build_sequences import first_call_messages
    from vllm_thinking import VLLMThinkingClient
    client = VLLMThinkingClient(args.base_url, "base")
    gold = {i["id"]: i for i in EV.load_gold(GOLD)["items"]}
    hf_rec = {r["id"]: r for r in json.loads((ROOT / "sft_dpo_inventory/pilot_003/selection/runs/HF-base_s1.json")
                                              .read_text(encoding="utf-8"))["rows"]}
    rows, ok = [], True
    for i in IDS:
        messages = first_call_messages(gold[i]["question"])
        ids = client.prompt_ids(messages)
        recorded = (hf_rec[i]["llm_calls"] or [{}])[0].get("prompt_eval_count")
        echo = None
        for model in ("base", "final"):
            out = post(args.base_url + "/v1/completions", {"model": model, "prompt": ids, "max_tokens": 1, "temperature": 0.0,
                                                           "return_token_ids": True})
            ch = out["choices"][0]
            back = ch.get("prompt_token_ids") or out.get("prompt_token_ids")
            same = back is not None and [int(x) for x in back] == ids
            echo = same if echo is None else (echo and same)
        tok = post(args.base_url + "/tokenize", {"model": "base", "messages": messages, "add_generation_prompt": True,
                                                  "chat_template_kwargs": {"enable_thinking": True}})
        server_ids = tok.get("tokens") or []
        row = {"id": i, "hf_ids_len": len(ids), "hf_ids_sha256": sha(ids), "hf_record_prompt_eval_count": recorded,
               "hf_len_matches_record": recorded == len(ids), "vllm_received_equal(base,final)": echo,
               "server_render_len": len(server_ids), "server_render_equal(reference only)": server_ids == ids}
        if not server_ids == ids:
            first = next((k for k, (a, b) in enumerate(zip(ids, server_ids)) if a != b), min(len(ids), len(server_ids)))
            row["server_render_first_diff_pos"] = first
        ok = ok and echo and row["hf_len_matches_record"]
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    out = {"items": IDS, "all_received_equal_and_hf_len_matches": bool(ok), "rows": rows,
           "method": "평가 client는 HF render_prompt id열을 직접 넘긴다. 서버 렌더링 비교는 참고."}
    (HERE / "input_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ALL_OK" if ok else "MISMATCH")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
