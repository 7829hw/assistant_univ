# -*- coding: utf-8 -*-
"""결정 68(J): Ollama-최종 s1 앞 5문항을 같은 seed로 GPU 3에서 다시 생성한 원문을 GPU 2 기록과 호출 단위로 바이트 비교한다.
모델 호출 없음.

    python sft_dpo_inventory/calibration_001/device_compare.py

- GPU 2: ``training/generated/calibration_001/raw/Ollama-final_s1_raw.jsonl``(그 5문항만).
- GPU 3: ``.../raw/device_Ollama-final_g3_raw.jsonl``.
- 비교 단위는 (문항, 호출 번호)이고 thinking과 content를 따로 본다. 호출 수가 다르면 그것도 불일치다.
- 결과(``repro/device_compare.json``)에는 일치 여부·sha256·처음 갈라진 위치만 남긴다.
"""
import hashlib
import json

from repro_compare import RAW, HERE, first_diff

A, B = "Ollama-final_s1", "device_Ollama-final_g3"


def load(name, ids=None):
    rows = [json.loads(line) for line in (RAW / f"{name}_raw.jsonl").read_text(encoding="utf-8").splitlines()]
    return {(r["id"], r["call"]): r for r in rows if ids is None or r["id"] in ids}


def h(text):
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def main():
    b = load(B)
    ids = {key[0] for key in b}
    a = load(A, ids)
    calls = []
    for key in sorted(set(a) | set(b)):
        ra, rb = a.get(key), b.get(key)
        row = {"id": key[0], "call": key[1], "in_gpu2": ra is not None, "in_gpu3": rb is not None}
        if ra and rb:
            for part in ("thinking", "content"):
                ta, tb = ra.get(part) or "", rb.get(part) or ""
                row[part] = {"same": ta == tb, "sha256": [h(ta), h(tb)], "chars": [len(ta), len(tb)],
                             "first_diff_char": None if ta == tb else first_diff(ta, tb)}
            row["seed"] = [ra.get("sampling_seed"), rb.get("sampling_seed")]
            row["eval_count"] = [ra.get("eval_count"), rb.get("eval_count")]
            row["same"] = row["thinking"]["same"] and row["content"]["same"]
        else:
            row["same"] = False
        calls.append(row)
    out = {"decision": 68, "gpu2": A, "gpu3": B, "items": sorted(ids), "calls": len(calls),
           "same_calls": sum(c["same"] for c in calls), "all_same": all(c["same"] for c in calls), "detail": calls}
    (HERE / "repro" / "device_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                                          encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("items", "calls", "same_calls", "all_same")}, ensure_ascii=False))
    for c in calls:
        print(c["id"], c["call"], c["same"], c.get("seed"), c.get("eval_count"),
              {p: c[p]["first_diff_char"] for p in ("thinking", "content") if p in c})


if __name__ == "__main__":
    main()
