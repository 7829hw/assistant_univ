# -*- coding: utf-8 -*-
"""세션 2d GPU 입력(P3, S128). ``build_inputs2c.py``의 사본. 실행 전에 커밋한다. 모델 호출 없음.

    hfvenv/bin/python build_inputs2d.py   # -> inputs2d/{s128p,s128f}.jsonl, inputs2d/manifest.json

- S128P / S128F(세션 2d 지시 2.2): arm마다 **S64 보강을 받은 뒤에도**(inputs2c/s64p·s64f에 있던 질문) 승인 gold v2 판정으로 그 arm에 정답 표본이
  하나도 없는 승인 질문. 출처·손실 범위는 결정 98과 같다.

- S64P / S64F(결정 146 K9): arm마다 **S32 보강을 받은 뒤에도**(S32*-a·S32*-b 입력에 있던 질문) 승인 gold v2 판정으로 그 arm에 정답 표본이 하나도 없는 승인 질문.
  판정은 그 arm의 모든 판정 파일(``self_samples/r1/*_approved.json``)을 합친다. 같은 정규화 질문은 trunk id로 하나.
  S32를 받지 않은 질문(batch009·K4 복원 등)은 대상이 아니다(보고만: ``not_s32_no_correct``).
- J13: w1 예외 9건(결정 140, b009-01·03·04·05·09·10·13·19·20) — base 첫 응답과 두 arm 자체 표본(greedy 1 + 8).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path("/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_006_prep/gpu")
PREP = HERE.parent
CODE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(CODE_ROOT))
sys.path.insert(0, str(CODE_ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples"))
OUT = HERE / "inputs2d"
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
    for arm, src, name in (("partial", "s64p", "s128p"), ("full", "s64f", "s128f")):
        prev = {canon(json.loads(l)["id"]) for l in (HERE / f"inputs2c/{src}.jsonl").read_text(encoding="utf-8").splitlines()}
        ids = sorted(c for c in prev if c in corpus and c not in correct[arm])
        rows = [{"id": c, "source": f"s64_still_no_correct_{arm}", "question": corpus[c]["question"]} for c in ids]
        p = OUT / f"{name}.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        man[name] = {"items": len(rows), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "rule": f"S64 뒤에도 {arm} 정답 없음"}
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print({k: v["items"] for k, v in man.items()})


if __name__ == "__main__":
    main()
