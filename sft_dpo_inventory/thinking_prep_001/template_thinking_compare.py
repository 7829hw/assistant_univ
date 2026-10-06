# -*- coding: utf-8 -*-
"""thinking용 Modelfile TEMPLATE 초안을 HF Qwen3 chat template 렌더링과 비교한다(모델·Ollama 호출 없음).

    HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/thinking_prep_001/template_thinking_compare.py

- ``render_draft``: ``template/Modelfile.template.thinking.draft``를 이 프로젝트의 요청 형태(system+user, 재질의는
  system+user+assistant+user, tools 없음)에 대해 Python으로 옮긴 것. think: None(미지정) | True | False.
- ``render_library``: Ollama 0.34.4 qwen3:8b template(pilot_prep_001에서 읽어 둔 사본)의 Python 옮김(pilot_prep_001에서
  기록된 prompt_eval_count와 100/100 맞음을 확인). 학습 렌더링 선택지 비교에 쓴다.
- 결과: 초안이 HF와 바이트 단위로 같은지, 라이브러리 template(think 켬)과 HF(enable_thinking=True)의 차이.
"""
import difflib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("pilot_template", ROOT / "sft_dpo_inventory/pilot_prep_001/template_compare.py")
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)


def render_draft(messages, think):
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    rest = [m for m in messages if m["role"] != "system"]
    out = "<|im_start|>system\n" + system + "<|im_end|>\n" if system else ""
    for i, m in enumerate(rest):
        last = i == len(rest) - 1
        if m["role"] == "user":
            out += "<|im_start|>user\n" + m["content"] + "<|im_end|>\n"
        elif m["role"] == "assistant":
            out += "<|im_start|>assistant\n"
            if last and m.get("thinking"):
                out += "<think>\n" + m["thinking"] + "\n</think>\n\n"
            out += m["content"] + ("" if last else "<|im_end|>\n")
        if m["role"] != "assistant" and last:
            out += "<|im_start|>assistant\n"
            if think is False:
                out += "<think>\n\n</think>\n\n"
    return out


def main():
    from transformers import AutoTokenizer
    from geoflow.planner import GeoFlowPlanner
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    planner = GeoFlowPlanner(client=None)
    plan = planner.messages("2026년 9월 1일부터 7일까지 실차 승차가 가장 많은 시군구 세 곳은?")
    repair = plan + [{"role": "assistant", "content": '{"concepts": [], "factors": {}}'},
                     {"role": "user", "content": "수정 요청 문구"}]
    hf = lambda m, on: tok.apply_chat_template(m, tokenize=False, add_generation_prompt=True, enable_thinking=on)  # noqa
    count = lambda text: len(tok(text, add_special_tokens=False)["input_ids"])  # noqa: E731
    cases = {}
    for name, msgs in (("plan", plan), ("repair", repair)):
        for label, think, on in (("think_unset", None, True), ("think_true", True, True), ("think_false", False, False)):
            draft, reference = render_draft(msgs, think), hf(msgs, on)
            cases[f"{name}/{label}"] = {"hf_enable_thinking": on, "draft_equals_hf_bytes": draft == reference,
                                        "draft_tokens": count(draft), "hf_tokens": count(reference)}
        library = P.render_ollama(msgs, True)
        reference = hf(msgs, True)
        cases[f"{name}/library_think_on_vs_hf_true"] = {
            "library_tokens": count(library), "hf_tokens": count(reference),
            "diff": [line for line in difflib.unified_diff(reference.replace(msgs[0]["content"], "<SYSTEM>").splitlines(),
                                                           library.replace(msgs[0]["content"], "<SYSTEM>").splitlines(),
                                                           "hf_enable_thinking_true", "ollama_library_think_on", lineterm="")]}
    result = {"source_template": "sft_dpo_inventory/pilot_prep_001/template/ollama_qwen3_8b.template",
              "draft": "sft_dpo_inventory/thinking_prep_001/template/Modelfile.template.thinking.draft",
              "cases": cases,
              "unverified": ["think 미지정 요청이 thinking 켬으로 렌더링되는지(Ollama의 IsThinkSet·Think 기본값)",
                             "응답에서 thinking과 본문이 분리되는지(Ollama의 thinking parser가 이 template에서 동작하는지)",
                             "Ollama가 이 template의 모델을 thinking 지원 모델로 인식하는지"]}
    (HERE / "template" / "template_thinking_compare.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n",
                                                                     encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
