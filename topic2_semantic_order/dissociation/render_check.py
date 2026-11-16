"""X1·X2 렌더링 게이트(PREREGISTRATION 3.2-1·2). CPU 전용, 모델 호출 없음.

평가 하네스(``sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py``)와 같은 방식으로 pipeline을 만들고, 첫 계획 호출의 messages를
가로채 ``render_prompt``(enable_thinking=True) + 같은 tokenizer로 id열을 만든 뒤 ``sha256(json.dumps(ids))``를 셀에 기록된
첫 계획 호출 ``prompt_ids_sha256``과 대조한다. 풀이 원문 ``raw_text``를 재토큰화한 길이도 기록된 ``generated_tokens``와 대조한다.

    CUDA_VISIBLE_DEVICES= HF_HOME=... HF_HUB_OFFLINE=1 python render_check.py REPO OUT.json
출력 JSON에는 (run, 문항)마다 해시 일치 여부와 토큰 길이 비교, 문항별 prompt id열 sha256이 들어간다.
id열 자체는 ``--ids-out``(jsonl, 저장소 밖 권장)에 쓸 수 있다.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from datetime import date
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("repo")
ap.add_argument("out")
ap.add_argument("--ids-out", default=None)
args = ap.parse_args()
ROOT = Path(args.repo).resolve()
for p in (ROOT, ROOT / "sft_dpo_inventory/thinking_prep_001", ROOT / "sft_dpo_inventory/pilot_005", ROOT / "sft_dpo_inventory/serving_vllm"):
    sys.path.insert(0, str(p))

import evaluate_vendor100 as EV  # noqa: E402
import hf_thinking as H  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402
from training.trainer_common import render_prompt  # noqa: E402
from geoflow import providers  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402

spec = importlib.util.spec_from_file_location("fdc", ROOT / "topic2_semantic_order/dissociation/fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["fare_dissociation_check.py", str(ROOT)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv

tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
CONFIG = {"chat_template_kwargs": {"enable_thinking": True}}


class _Stop(Exception):
    pass


class _Capture:
    """첫 chat 호출의 messages만 잡고 멈춘다."""
    model = "capture"

    def __init__(self):
        self.messages = None

    def chat(self, messages, tools=None, **kwargs):
        self.messages = messages
        raise _Stop()


def first_messages(question, reference_date):
    EV.REFERENCE_DATE = reference_date
    cap = _Capture()
    recorder = EV._RecordingClient(cap)
    pipeline = GeoFlowPipeline.create(
        client=recorder, tool_executor=EV._executor(), aggregation_grounding="flat",
        clock=lambda: EV.REFERENCE_DATE, condition_check=True,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY), condition_notes=False)
    try:
        EV.run_item(pipeline, question)
    except _Stop:
        pass
    except Exception:  # noqa: BLE001  run_item이 예외를 감싸도 messages는 잡혀 있다
        pass
    if cap.messages is None:
        raise SystemExit(f"첫 계획 호출 messages를 잡지 못함: {question}")
    return cap.messages


gold = {it["id"]: it for it in fdc.gold["items"]}
EV.GOLD_PATH = ROOT / "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
cache = {}
rows = []
ids_stream = open(args.ids_out, "w", encoding="utf-8") if args.ids_out else None
summary = {"pairs": 0, "hash_equal": 0, "hash_mismatch": [], "missing_record": [], "len_equal": 0, "len_diff": []}
for run in fdc.RUNS:
    label = f"{run[0]}-{run[1]}-r{run[2]}"
    cell = json.load(open(ROOT / fdc.cell_path(*run), encoding="utf-8"))
    ref = date.fromisoformat(str(cell["meta"].get("reference_date", "2026-09-25"))[:10]) if cell["meta"].get("reference_date") else date(2026, 9, 25)
    by_id = {r["id"]: r for r in cell["rows"]}
    raws = {}
    for line in open(ROOT / fdc.raw_path(*run), encoding="utf-8"):
        d = json.loads(line)
        if d.get("call", 0) == 0 and d["id"] not in raws:
            raws[d["id"]] = d
    for i in fdc.need:
        key = (i, ref)
        if key not in cache:
            msgs = first_messages(gold[i]["question"], ref)
            ids = tok(render_prompt(tok, msgs, CONFIG), add_special_tokens=False)["input_ids"]
            cache[key] = (hashlib.sha256(json.dumps(ids).encode()).hexdigest(), len(ids))
            if ids_stream:
                ids_stream.write(json.dumps({"id": i, "reference_date": str(ref), "prompt_ids": ids}) + "\n")
        sha, n_prompt = cache[key]
        calls = by_id[i].get("hf_calls") or []
        rec = calls[0].get("prompt_ids_sha256") if calls else None
        raw = raws[i]
        n_re = len(tok(raw["raw_text"], add_special_tokens=False)["input_ids"])
        n_gen = raw["generated_tokens"]
        ok_hash = rec == sha
        summary["pairs"] += 1
        if rec is None:
            summary["missing_record"].append([label, i])
        elif ok_hash:
            summary["hash_equal"] += 1
        else:
            summary["hash_mismatch"].append([label, i])
        # 생성 id열 끝의 정지 token(<|im_end|> 등)은 skip_special_tokens decode로 사라지므로 done_reason=stop이면 1을 뺀다
        expect = n_gen - (1 if raw.get("done_reason") == "stop" else 0)
        if n_re == expect:
            summary["len_equal"] += 1
        else:
            summary["len_diff"].append([label, i, n_re, n_gen, raw.get("done_reason")])
        rows.append({"run": label, "id": i, "reference_date": str(ref), "prompt_ids_sha256": sha, "prompt_tokens": n_prompt,
                     "recorded_prompt_ids_sha256": rec, "hash_equal": ok_hash, "retokenized_len": n_re,
                     "generated_tokens": n_gen, "done_reason": raw.get("done_reason")})
summary["len_diff_rate"] = len(summary["len_diff"]) / summary["pairs"]
summary["gate_hash"] = (summary["hash_equal"] == summary["pairs"])
summary["gate_len"] = summary["len_diff_rate"] <= 0.01
Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in summary.items()}, ensure_ascii=False))
