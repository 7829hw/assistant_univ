# -*- coding: utf-8 -*-
"""세션 2c GPU 입력(P4, J13). 실행 전에 커밋한다. 모델 호출 없음.

    hfvenv/bin/python build_inputs2c.py   # -> inputs2c/{s64p,s64f,j13}.jsonl, inputs2c/manifest.json

- S64P / S64F(결정 146 K9): arm마다 **S32 보강을 받은 뒤에도**(S32*-a·S32*-b 입력에 있던 질문) 승인 gold v2 판정으로 그 arm에 정답 표본이 하나도 없는 승인 질문.
  판정은 그 arm의 모든 판정 파일(``self_samples/r1/*_approved.json``)을 합친다. 같은 정규화 질문은 trunk id로 하나.
  S32를 받지 않은 질문(batch009·K4 복원 등)은 대상이 아니다(보고만: ``not_s32_no_correct``).
- J13: w1 예외 9건(결정 140, b009-01·03·04·05·09·10·13·19·20) — base 첫 응답과 두 arm 자체 표본(greedy 1 + 8).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREP = HERE.parent
sys.path.insert(0, str(PREP.parents[1]))
sys.path.insert(0, str(PREP / "self_samples"))
OUT = HERE / "inputs2c"
W1 = ["b009-01", "b009-03", "b009-04", "b009-05", "b009-09", "b009-10", "b009-13", "b009-19", "b009-20"]


def main():
    import approved6 as AP
    from training.data.split import question_key
    corpus = AP.load()
    order = {"trunk": 0, "pg": 1, "aug300": 2, "batch007": 3, "batch008": 4, "batch009": 5}
    by_key, alias = {}, {}
    for cid, rec in sorted(corpus.items(), key=lambda kv: (order[kv[1]["corpus_group"]], kv[0])):
        k = question_key(rec["question"])
        if k in by_key:
            alias[cid] = by_key[k]
        else:
            by_key[k] = cid
    canon = lambda c: alias.get(c, c)  # noqa: E731
    correct = {"full": set(), "partial": set()}
    for f in (PREP / "self_samples/r1").glob("*_approved.json"):
        if "first" in f.name:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for q in d["per_question"]:
            if q["status"] == "approved" and q["correct"] > 0:
                correct[d["arm"]].add(canon(q["id"]))
    OUT.mkdir(exist_ok=True)
    man = {}
    for arm, files, name in (("partial", ("s32p_a", "s32p_b"), "s64p"), ("full", ("s32f_a", "s32f_b"), "s64f")):
        s32 = {canon(json.loads(l)["id"]) for f in files for l in (HERE / f"inputs2b/{f}.jsonl").read_text(encoding="utf-8").splitlines()}
        ids = sorted(c for c in s32 if c in corpus and c not in correct[arm])
        rows = [{"id": c, "source": f"s32_still_no_correct_{arm}", "question": corpus[c]["question"]} for c in ids]
        p = OUT / f"{name}.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        all_q = {canon(c) for c in corpus}
        man[name] = {"items": len(rows), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "rule": f"S32 뒤에도 {arm} 정답 없음(결정 146)",
                     "not_s32_no_correct": sorted(c for c in all_q if c not in s32 and c not in correct[arm])}
    rows = [{"id": f"b009:{i}", "source": "w1_exception", "question": corpus[f"b009:{i}"]["question"]} for i in W1]
    p = OUT / "j13.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    man["j13"] = {"items": len(rows), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "rule": "w1 예외 9(결정 140)"}
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print({k: (v["items"], len(v.get("not_s32_no_correct", []))) for k, v in man.items()})


if __name__ == "__main__":
    main()
