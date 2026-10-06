# -*- coding: utf-8 -*-
"""Ollama qwen3:8b template과 HF chat template(enable_thinking=False)의 렌더링 차이를 찾는다. 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_prep_001/template_compare.py

1. ``template/ollama_qwen3_8b.template``(``/api/show``로 읽음)을 이 프로젝트의 요청 형태(system + user, 재질의는
   system + user + assistant + user, tools 없음)에 대해 Python으로 그대로 옮겨 렌더링한다(``render_ollama``).
2. 옮긴 렌더링의 token 수를 기존 기록의 Ollama ``prompt_eval_count``(baseline_conditions_001 B: think=false,
   grounding_v9 q8_cur: think 미지정)와 문항마다 비교해 옮긴 것이 맞는지 확인한다.
3. HF ``apply_chat_template(enable_thinking=False)``와 문자열 차이를 찾는다.
4. Modelfile TEMPLATE 초안(``template/Modelfile.template.draft``)을 같은 방식으로 옮겨(``render_draft``) HF 렌더링과
   바이트 단위로 같은지 본다. 실제 Ollama가 초안을 이렇게 렌더링하는지는 등록하지 않고는 확인할 수 없다(미검증).
"""
import difflib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))


def render_ollama(messages, think):
    """Ollama qwen3:8b template(tools 없음)의 Python 옮김. think: None(미지정) | True | False."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    last_user = max(i for i, m in enumerate(rest) if m["role"] == "user")
    out = ""
    if system:
        out += "<|im_start|>system\n" + "\n" + system + "<|im_end|>\n"
    for i, m in enumerate(rest):
        last = i == len(rest) - 1
        if m["role"] == "user":
            out += "<|im_start|>user\n" + m["content"]
            if think is not None and i == last_user:
                out += " /think" if think else " /no_think"
            out += "<|im_end|>\n"
        elif m["role"] == "assistant":
            out += "<|im_start|>assistant\n" + m["content"]
            if not last:
                out += "<|im_end|>\n"
        if m["role"] != "assistant" and last:
            out += "<|im_start|>assistant\n"
            if think is False:
                out += "<think>\n\n</think>\n\n"
    return out


def render_draft(messages):
    """Modelfile TEMPLATE 초안(Modelfile.template.draft)의 Python 옮김. think 설정과 관계없이 HF 비사고 형식을 낸다."""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    out = "<|im_start|>system\n" + system + "<|im_end|>\n" if system else ""
    for i, m in enumerate(rest):
        last = i == len(rest) - 1
        if m["role"] == "user":
            out += "<|im_start|>user\n" + m["content"] + "<|im_end|>\n"
        elif m["role"] == "assistant":
            out += "<|im_start|>assistant\n" + m["content"] + ("" if last else "<|im_end|>\n")
        if m["role"] != "assistant" and last:
            out += "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    return out


def first_plan(row):
    return next((c for c in row.get("llm_calls") or [] if c.get("kind") == "plan" and not c.get("failed")), None)


def main():
    from transformers import AutoTokenizer
    from geoflow.planner import GeoFlowPlanner
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    count = lambda text: len(tok(text, add_special_tokens=False)["input_ids"])   # noqa: E731
    hf = lambda msgs: tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,  # noqa: E731
                                              enable_thinking=False)
    # 522aa3b1 기록(B, q8_cur)은 그 prompt로 렌더링해야 한다. c1f2a08의 planner prompt를 git으로 꺼내 만들 수 없으므로
    # 기록에 남은 prompt_eval_count와 HF 렌더링의 차이만 본다. 87048d0c 기록(F, E)은 현재 planner로 직접 비교한다.
    planner = GeoFlowPlanner(client=None)
    records = {
        "F(87048d0c, think=false)": ("origin/geoflow/sft-dpo-t2pc",
                                     "sft_dpo_inventory/baseline_conditions_001/runs/F.json", False),
        "E(87048d0c, think 미지정)": ("origin/geoflow/sft-dpo-t2pc",
                                    "sft_dpo_inventory/baseline_conditions_001/runs/E.json", None),
    }
    checks = {}
    for label, (ref, path, think) in records.items():
        data = json.loads(subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT))
        emulated_match, hf_gap, n = 0, {}, 0
        as_think_on = 0   # 요청에 think가 없을 때 Ollama가 think=true처럼 렌더링하는지(E에서 확인)
        for row in data["rows"]:
            call = first_plan(row)
            if not call or call.get("prompt_eval_count") is None:
                continue
            messages = planner.messages(row["question"])
            n += 1
            emulated_match += count(render_ollama(messages, think)) == call["prompt_eval_count"]
            if think is None:
                as_think_on += count(render_ollama(messages, True)) == call["prompt_eval_count"]
            gap = call["prompt_eval_count"] - count(hf(messages))
            hf_gap[gap] = hf_gap.get(gap, 0) + 1
        checks[label] = {"items": n, "emulated_ollama_token_count_equals_record": emulated_match,
                         **({"emulated_as_think_true_equals_record": as_think_on} if think is None else {}),
                         "ollama_minus_hf_enable_thinking_false": hf_gap}
    sample = planner.messages("2026년 9월 1일부터 7일까지 실차 승차가 가장 많은 시군구 세 곳은?")
    repair = sample + [{"role": "assistant", "content": '{"concepts": [], "factors": {}}'},
                       {"role": "user", "content": "수정 요청 문구"}]
    diffs = {}
    for name, msgs in (("plan", sample), ("repair", repair)):
        a, b = render_ollama(msgs, False), hf(msgs)
        diffs[name] = {"ollama_think_false_tokens": count(a), "hf_tokens": count(b),
                       "unified_diff": [line for line in difflib.unified_diff(
                           b.replace(msgs[0]["content"], "<SYSTEM>").splitlines(),
                           a.replace(msgs[0]["content"], "<SYSTEM>").splitlines(), "hf", "ollama", lineterm="")],
                       "draft_equals_hf_bytes": render_draft(msgs) == b}
    result = {"template_sha256": __import__("hashlib").sha256((HERE / "template/ollama_qwen3_8b.template").read_bytes()).hexdigest(),
              "record_checks": checks, "sample_diffs": diffs,
              "draft_status": "미검증: Python 옮김에서만 HF와 같다. 실제 Ollama 렌더링은 ollama create 뒤 prompt_eval_count와 출력으로 확인해야 한다"}
    (HERE / "template" / "template_compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                                            encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
