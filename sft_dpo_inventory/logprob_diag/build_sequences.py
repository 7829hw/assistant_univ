# -*- coding: utf-8 -*-
"""경로별 token 확률 비교(결정 75, 작업 2)의 기준 token id열을 만든다. CPU(tokenizer만), 모델 호출 없음.

    HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 /home/hwkim/sftdpo_work/hfvenv/bin/python \
        sft_dpo_inventory/logprob_diag/build_sequences.py

- 묶음 (i) ``sft``: pilot_002 SFT 학습 레코드 30개(HF 출처 15, teacher 출처 15, seed 20261012로 뽑음).
  렌더링은 학습과 같은 ``render_records``(prompt + completion)다.
- 묶음 (ii) ``cal``: calibration_001 selection_v1의 HF-최종 표본 30개. 문항 우선순위는 (HF-최종 정답 표본 비율 −
  Ollama-최종 정답 표본 비율)이 큰 순서이고, 같은 값은 seed로 섞는다. 문항마다 HF-최종이 맞고 호출이 하나뿐인 표본 중
  하나를 seed로 고른다. prompt는 HF 평가와 같은 pipeline 구성으로 첫 호출 messages를 잡아(모델 호출 없이) ``render_prompt``로
  렌더링하고, 응답은 그 표본의 원문(``raw_text``) + ``<|im_end|>``다.
- token id: prompt와 응답을 따로 tokenize해 이어 붙인다(``add_special_tokens=False``). 이후 모든 경로는 이 id열만 쓴다.
- 구간: 응답 token 중 ``</think>``까지가 thinking, 그 뒤가 JSON(끝 ``<|im_end|>`` 포함)이다.
- 출력:
  - 저장소 밖 ``/data/hwkim/sftdpo_work/logprob_diag/sequences.jsonl``(token id) · ``sequences.txt``(token_logprobs 입력).
  - 저장소 ``sequences_manifest.json``(id, 출처, 길이, 구간 경계, 원문 sha256; 원문은 넣지 않음).
"""
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
WORK = Path("/data/hwkim/sftdpo_work/logprob_diag")
CONFIG = ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot002_sft.yaml"
CAL = ROOT / "sft_dpo_inventory/calibration_001"
RAW = ROOT / "training/generated/calibration_001/raw"
GOLD = ROOT / "sft_dpo_inventory/conversion_diag/selection_gold.yaml"
SEED = 20261012
N_EACH = 30
THINK_END_ID = 151668


class _Captured(Exception):
    pass


class _CaptureClient:
    """첫 호출의 messages만 잡고 멈춘다(모델을 부르지 않는다)."""
    def __init__(self):
        self.messages = None
        self.model = "capture"

    def chat(self, messages, tools=None, **kwargs):
        self.messages = messages
        raise _Captured()


def first_call_messages(question):
    import evaluate_vendor100 as EV
    from datetime import date
    from geoflow import providers
    from geoflow.pipeline import GeoFlowPipeline
    EV.REFERENCE_DATE = date(2026, 9, 25)
    client = _CaptureClient()
    pipeline = GeoFlowPipeline.create(
        client=client, tool_executor=EV._executor(), aggregation_grounding="flat", clock=lambda: EV.REFERENCE_DATE,
        condition_check=True, execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY),
        condition_notes=False)
    try:
        EV.run_item(pipeline, question)
    except _Captured:
        pass
    if client.messages is None:
        raise SystemExit(f"messages not captured: {question}")
    return client.messages


def segments(tok, resp_ids):
    if THINK_END_ID not in resp_ids:
        raise SystemExit("response without </think>")
    return resp_ids.index(THINK_END_ID) + 1     # thinking = [0, k), JSON = [k, n)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_sft(tok, config, rng):
    from training.data import thinking  # noqa: F401
    from training.trainer_common import load_records, render_prompt, render_records
    records, _ = load_records(config, "sft")
    train = records["train"]
    groups = defaultdict(list)
    for i, r in enumerate(train):
        groups["teacher" if r["metadata"]["source"] == "teacher" else "hf"].append(i)
    chosen = []
    for src in ("hf", "teacher"):
        picks = sorted(rng.sample(groups[src], N_EACH // 2))
        chosen += [(src, i) for i in picks]
    rows = render_records(tok, [train[i] for _, i in chosen], config, "sft")
    out = []
    for (src, i), row in zip(chosen, rows):
        rec = train[i]
        gen_prompt = render_prompt(tok, rec["messages"][:2], config)
        full = row["prompt"] + row["completion"]
        if not full.startswith(gen_prompt):
            raise SystemExit(f"prefix mismatch {rec['metadata']['trace_id']}")
        response = full[len(gen_prompt):]
        out.append({"key": f"sft/{rec['metadata']['trace_id']}", "set": "sft", "source": src,
                    "prompt": gen_prompt, "response": response})
    return out


def build_cal(tok, config, rng):
    import evaluate_vendor100 as EV
    from training.trainer_common import render_prompt
    gold = {i["id"]: i for i in EV.load_gold(GOLD)["items"]}
    rate = defaultdict(lambda: defaultdict(list))
    okmap = {}
    for line in (CAL / "samples.jsonl").read_text(encoding="utf-8").splitlines():
        s = json.loads(line)
        if s["cell"] in ("HF-final", "Ollama-final"):
            rate[s["id"]][s["cell"]].append(s["ok"])
        if s["cell"] == "HF-final":
            okmap[(s["id"], s["sample"])] = (s["ok"], s["calls"])
    items = []
    for key, cells in rate.items():
        good = [k for k in range(1, 5) if okmap[(key, k)][0] and okmap[(key, k)][1] == 1]
        if not good:
            continue
        diff = sum(cells["HF-final"]) / 4 - sum(cells["Ollama-final"]) / 4
        items.append((diff, rng.random(), key, good))
    items.sort(key=lambda x: (-x[0], x[1]))
    out = []
    for diff, _, key, good in items[:N_EACH]:
        k = rng.choice(good)
        raw = next(r for r in map(json.loads, (RAW / f"HF-final_s{k}_raw.jsonl").read_text(encoding="utf-8").splitlines())
                   if r["id"] == key and r["call"] == 0)
        prompt = render_prompt(tok, first_call_messages(gold[key]["question"]), config)
        out.append({"key": f"cal/{key}#s{k}", "set": "cal", "source": f"HF-final_s{k}", "priority_diff": diff,
                    "prompt": prompt, "response": raw["raw_text"] + "<|im_end|>"})
    return out


def main():
    from training.trainer_common import load_config, tokenizer_for
    config = load_config(CONFIG, "sft")
    tok = tokenizer_for(config)
    rng = random.Random(SEED)
    seqs = build_sft(tok, config, rng) + build_cal(tok, config, rng)
    WORK.mkdir(parents=True, exist_ok=True)
    manifest, lines = [], []
    with (WORK / "sequences.jsonl").open("w", encoding="utf-8") as jf:
        for n, s in enumerate(seqs):
            p_ids = tok(s["prompt"], add_special_tokens=False)["input_ids"]
            r_ids = tok(s["response"], add_special_tokens=False)["input_ids"]
            k = segments(tok, r_ids)
            ids = p_ids + r_ids
            jf.write(json.dumps({"index": n, "key": s["key"], "ids": ids, "resp_start": len(p_ids),
                                 "think_end": len(p_ids) + k}) + "\n")
            lines.append(f"{n} {len(p_ids)} {len(ids)} " + " ".join(map(str, ids)))
            manifest.append({"index": n, "key": s["key"], "set": s["set"], "source": s["source"],
                             **({"priority_diff": s["priority_diff"]} if "priority_diff" in s else {}),
                             "prompt_tokens": len(p_ids), "thinking_tokens": k, "json_tokens": len(r_ids) - k,
                             "prompt_sha256": sha(s["prompt"]), "response_sha256": sha(s["response"]),
                             "ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest()})
    (WORK / "sequences.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {"seed": SEED, "tokenizer": "Qwen/Qwen3-8B@b968826d (training.trainer_common.tokenizer_for, pilot_002 SFT config)",
            "chat_template_kwargs": config.get("chat_template_kwargs"),
            "sequences_jsonl_sha256": hashlib.sha256((WORK / "sequences.jsonl").read_bytes()).hexdigest(),
            "sequences": manifest}
    (HERE / "sequences_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m in manifest:
        print(m["index"], m["key"], m["source"], m.get("priority_diff"), m["prompt_tokens"], m["thinking_tokens"], m["json_tokens"])


if __name__ == "__main__":
    main()
