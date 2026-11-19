# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271, PLAN_JT 1절) 모델 기록·vLLM 지원 확인(GPU 없음, 모델 호출 없음).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/jt/record_model_jt.py

- ``model_manifest.json``: 로컬 사본(저장소 밖) 파일별 크기·sha256, Hub의 LFS sha256(``HfApi.model_info(files_metadata=True)``)과 대조, revision.
- ``vllm_support.json``: 학생용 vLLM 환경(``runtime/envs/vllm``)에서 버전, registry의 모델 구조 항목, ``qwen3_5.py``의 TP 관련 코드 존재,
  ``--language-model-only`` 인자, 그 환경 transformers가 config를 읽는지(``AutoConfig``), head 수가 TP 2로 나뉘는지. 실제 기동은 2단계 smoke.
- ``render_check.json``: hf env의 tokenizer·chat template로 운영 프롬프트(87048d0c)를 렌더링해 effort 문장·본문·``<think>\\n`` 위치, 정지 token, decode에서
  ``<think>``·``</think>``가 남는지 확인(질문은 가짜 문자열).
"""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
REPO, REV = "Qwen/Qwen3.8-27B", "37561816e66b5b9153b1b64c10968c18c1e6f4a0"
LOCAL = Path("/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B")
VENV = Path("/data/hwkim/sftdpo_work/runtime/envs/vllm")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def manifest():
    from huggingface_hub import HfApi
    info = HfApi().model_info(REPO, revision=REV, files_metadata=True)
    hub = {s.rfilename: {"size": s.size, "lfs_sha256": (s.lfs.sha256 if s.lfs else None), "blob_id": s.blob_id} for s in info.siblings}
    files, bad = {}, []
    for name, h in sorted(hub.items()):
        p = LOCAL / name
        if not p.exists():
            bad.append(f"missing {name}")
            continue
        d = sha(p)
        size = p.stat().st_size
        ok = (size == h["size"]) and (h["lfs_sha256"] is None or d == h["lfs_sha256"])
        if h["lfs_sha256"] is None:  # 작은 파일: git blob sha1과 대조
            data = p.read_bytes()
            ok = ok and hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == h["blob_id"]
        files[name] = {"size": size, "sha256": d, "hub_lfs_sha256": h["lfs_sha256"], "ok": ok}
        if not ok:
            bad.append(name)
    w = sum(v["size"] for k, v in files.items() if k.endswith(".safetensors"))
    return {"repo": REPO, "revision": REV, "hub_sha": info.sha, "local_dir": str(LOCAL), "files": files, "all_ok": not bad, "problems": bad,
            "safetensors_bytes": w, "safetensors_gb": round(w / 1e9, 3)}


def vllm_support():
    py = str(VENV / "bin/python")
    code = r'''
import json, os, vllm, transformers
from pathlib import Path
vp = Path(vllm.__file__).parent
reg = (vp / "model_executor/models/registry.py").read_text()
m = (vp / "model_executor/models/qwen3_5.py").read_text()
gdn = (vp / "model_executor/layers/mamba/gdn/qwen_gdn_linear_attn.py").read_text()
args = (vp / "engine/arg_utils.py").read_text()
from transformers import AutoConfig
c = AutoConfig.from_pretrained("%s")
t = c.text_config
heads = {k: getattr(t, k) for k in ("num_attention_heads", "num_key_value_heads", "linear_num_value_heads", "linear_num_key_heads", "num_hidden_layers")}
print(json.dumps({"vllm": vllm.__version__, "transformers": transformers.__version__, "config_class": type(c).__name__,
  "registry_has_Qwen3_5ForConditionalGeneration": '"Qwen3_5ForConditionalGeneration"' in reg,
  "qwen3_5_classes": sorted(set(__import__("re").findall(r"^class (Qwen3_5\w+)", m, __import__("re").M))),
  "gdn_uses_tp_size": "tp_size" in gdn, "language_model_only_arg": "--language-model-only" in args,
  "heads": heads, "heads_divisible_by_tp2": all(v %% 2 == 0 for k, v in heads.items() if k != "num_hidden_layers"),
  "layer_types": dict(__import__("collections").Counter(t.layer_types)), "architectures": c.architectures}))
''' % str(LOCAL)
    out = subprocess.run([py, "-c", code], capture_output=True, text=True)
    if out.returncode:
        return {"error": out.stderr[-2000:]}
    rec = json.loads(out.stdout.strip().splitlines()[-1])
    rec["conclusion"] = ("학생용 vLLM 0.30.0 환경이 구조(Qwen3_5ForConditionalGeneration)·TP 2·--language-model-only를 코드상 지원 → 별도 환경 없음"
                         if rec["registry_has_Qwen3_5ForConditionalGeneration"] and rec["gdn_uses_tp_size"] and rec["language_model_only_arg"] and rec["heads_divisible_by_tp2"]
                         else "지원 확인 실패")
    return rec


def render_check():
    from transformers import AutoTokenizer
    from geoflow.planner import GeoFlowPlanner
    from training.trainer_common import render_prompt
    t = AutoTokenizer.from_pretrained(str(LOCAL))
    sp = GeoFlowPlanner(client=None).system_prompt()
    s = render_prompt(t, [{"role": "system", "content": sp}, {"role": "user", "content": "<QUESTION>"}], {"chat_template_kwargs": {"enable_thinking": True}})
    effort = "Reasoning effort is set to xhigh."
    head = "<|im_start|>system\n"
    ids = t("<think>\nx\n</think>\n\n{}", add_special_tokens=False)["input_ids"]
    return {"prompt_sha256": hashlib.sha256(sp.encode()).hexdigest(), "chat_template_sha256": sha(LOCAL / "chat_template.jinja"),
            "starts_with_system_then_effort": s.startswith(head + effort), "effort_sentence": re.match(r"<\|im_start\|>system\n(.*?)\n\n", s, re.S).group(1),
            "prompt_body_verbatim_after_effort": (sp.strip() in s), "ends_with_assistant_think_open": s.endswith("<|im_start|>assistant\n<think>\n"),
            "input_tokens_dummy_question": len(t(s, add_special_tokens=False)["input_ids"]),
            "stop_ids": {"eos": t.eos_token_id, "im_end": t.convert_tokens_to_ids("<|im_end|>"), "pad": t.pad_token_id},
            "think_tokens_kept_on_decode": t.decode(ids, skip_special_tokens=True) == "<think>\nx\n</think>\n\n{}",
            "tokenizer_class": type(t).__name__, "transformers(hf env)": __import__("transformers").__version__}


def main():
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    for name, fn in (("render_check.json", render_check), ("vllm_support.json", vllm_support), ("model_manifest.json", manifest)):
        rec = {"decision": 271, "generated_at": now, **fn()}
        (HERE / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(name, {k: rec[k] for k in rec if k in ("all_ok", "problems", "conclusion", "starts_with_system_then_effort", "ends_with_assistant_think_open",
                                                     "prompt_body_verbatim_after_effort", "think_tokens_kept_on_decode", "safetensors_gb")})


if __name__ == "__main__":
    main()
