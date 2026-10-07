# -*- coding: utf-8 -*-
"""결정 40-D 1단계: 루프 판정 기준을 정하기 위한 분포. 업체 100 기록은 쓰지 않는다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_004/loop_filter/distributions.py

- 지표: ``pilot_001_analysis/analyze.loop_metrics``와 같다(thinking 부분의 zlib 압축률, 20자 이상 줄의 최다 반복 수,
  끝부분의 같은 덩어리(20–4000자) 연속 반복 수).
- 분포 대상:
  - valid98 기록(HF): base(``training/generated/pilot_prep_003/valid100_base_raw.jsonl``의 valid98 문항)와 pilot_001
    checkpoint 8개(``training/generated/pilot_001/{sft,dpo}_step*_raw.jsonl``). 호출 단위. 생성 상한에 걸린 호출(``length``)과
    정상 종료(``stop``)를 나눈다.
  - 학습 trace: HF base trace(``pilot_prep_003/combined_traces.jsonl``)와 teacher trace(``thinking_traces/teacher_qwen3.8_27b``).
    여기서는 분포 요약(분위수)만 낸다. trace별 판정과 제외 수는 기준을 커밋한 뒤 ``apply_filter.py``가 센다.
- 결과: ``distributions.json``.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_001_analysis"))

GEN = ROOT / "training/generated"
VALID98 = ROOT / "sft_dpo_inventory/pilot_001/valid98/valid98_items.json"


from analyze import loop_metrics, split_think  # noqa: E402  (pilot_001 분석과 같은 함수)



def quantiles(values):
    values = sorted(values)
    if not values:
        return None
    pick = lambda q: values[min(len(values) - 1, int(q * (len(values) - 1) + 0.5))]  # noqa: E731
    return {"n": len(values), "min": values[0], "p01": pick(0.01), "p05": pick(0.05), "p10": pick(0.10),
            "median": pick(0.5), "p90": pick(0.9), "p99": pick(0.99), "max": values[-1]}


def summarize(metrics):
    return {"zlib_ratio": quantiles([m["zlib_ratio"] for m in metrics]),
            "chars": quantiles([m["chars"] for m in metrics]),
            "top_line_repeats": quantiles([m["top_line_repeats"] for m in metrics]),
            "tail_repeats>=3": sum(m["tail_repeats"] >= 3 for m in metrics)}


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    valid_ids = {f"{r['set']}/{r['id']}" for r in json.loads(VALID98.read_text(encoding="utf-8"))["items"]}
    files = {"base": GEN / "pilot_prep_003/valid100_base_raw.jsonl"}
    files.update({p.name.replace("_raw.jsonl", ""): p for p in sorted((GEN / "pilot_001").glob("*_step*_raw.jsonl"))})
    valid = {"stop": [], "length": []}
    by_file = {}
    for name, path in files.items():
        rows = [r for r in read(path) if r["id"] in valid_ids]
        ms = {"stop": [], "length": []}
        for r in rows:
            thinking = split_think(r["raw_text"])[0] or r["raw_text"]
            m = loop_metrics(thinking)
            if m:
                ms["length" if r["done_reason"] == "length" else "stop"].append(m)
        by_file[name] = {k: summarize(v) for k, v in ms.items()}
        for k in ms:
            valid[k].extend(ms[k])
    train = {"hf_base_traces": [], "teacher_traces": []}
    for r in read(GEN / "pilot_prep_003/combined_traces.jsonl"):
        m = loop_metrics(r.get("thinking") or split_think(r["raw_text"])[0])
        if m:
            train["hf_base_traces"].append(m)
    for path in sorted((GEN / "thinking_traces/teacher_qwen3.8_27b").glob("*/traces.jsonl")):
        for r in read(path):
            m = loop_metrics(r["thinking"])
            if m:
                train["teacher_traces"].append(m)
    out = {"valid98_calls": {k: summarize(v) for k, v in valid.items()}, "valid98_by_file": by_file,
           "training_traces(분포 요약만)": {k: summarize(v) for k, v in train.items()}}
    (HERE / "distributions.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("valid98_calls", "training_traces(분포 요약만)")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
