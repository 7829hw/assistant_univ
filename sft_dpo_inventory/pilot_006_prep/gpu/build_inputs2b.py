# -*- coding: utf-8 -*-
"""세션 2b GPU 입력(H2, J8·J9·J10; S32*-b는 H6 뒤 ``--s32b``로). 실행 전에 커밋한다. 모델 호출 없음.

    python3 build_inputs2b.py          # -> inputs2b/{s32f_a,s32p_a,trunk131,j10}.jsonl, inputs2b/manifest.json
    python3 build_inputs2b.py --s32b [partial|full]   # -> inputs2b/s32p_b.jsonl·s32f_b.jsonl (J8·J9 판정 r1/j8_approved.json·j9_approved.json 뒤, arm마다 따로 가능)

- 질문·id는 승인 corpus(R0) 그대로(``pilot_006_prep/approved/approved_train_v1.jsonl``). id는 corpus id.
- S32F-a / S32P-a: R1(``self_samples/r1/r1_summary.json``) arm별 "승인 질문 가운데 그 arm의 J1·J6 정답 표본 없음"(결정 133 G3: arm마다 그 arm에 정답이 없는 질문만).
- trunk131: 승인 trunk 131(J8 Partial, J9 Full). J10: batch008 10 + 질문이 바뀐 aug300(R0 통과 3; 348은 보류).
- S32*-b: J8(Partial)·J9(Full) 승인 gold 판정에서 그 arm에 정답 표본이 없는 trunk 질문(같은 질문이 S32*-a에 이미 있으면 뺌).
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREP = HERE.parent
OUT = HERE / "inputs2b"


def rows(ids, corpus, source):
    return [{"id": i, "source": source, "question": corpus[i]["question"]} for i in ids]


def write(name, data):
    p = OUT / f"{name}.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data), encoding="utf-8")
    return {"file": p.name, "items": len(data), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def main():
    corpus = {json.loads(l)["id"]: json.loads(l) for l in (PREP / "approved/approved_train_v1.jsonl").read_text(encoding="utf-8").splitlines()}
    OUT.mkdir(exist_ok=True)
    man_p = OUT / "manifest.json"
    man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
    if "--s32b" in sys.argv:
        only = sys.argv[sys.argv.index("--s32b") + 1] if len(sys.argv) > sys.argv.index("--s32b") + 1 else None
        for arm, j, name in (("partial", "j8", "s32p_b"), ("full", "j9", "s32f_b")):
            if only and arm != only:
                continue
            jd = json.loads((PREP / f"self_samples/r1/{j}_approved.json").read_text(encoding="utf-8"))
            ids = sorted(jd["no_correct_approved"])
            assert all(corpus[i]["corpus_group"] == "trunk" for i in ids)
            # 같은 질문(pg v005 = trunk)이 이미 S32*-a에 있으면 다시 뽑지 않는다
            prev = {r["question"] for r in map(json.loads, (OUT / f"{name[:-2]}_a.jsonl").read_text(encoding="utf-8").splitlines())}
            ids = [i for i in ids if corpus[i]["question"] not in prev]
            man[name] = {**write(name, rows(ids, corpus, f"trunk_no_correct_{j}")), "rule": f"{j.upper()}({arm}) 승인 gold 판정 정답 없음 trunk"}
    else:
        r1 = json.loads((PREP / "self_samples/r1/r1_summary.json").read_text(encoding="utf-8"))
        inval = json.loads((PREP / "approved/invalidated_outputs.json").read_text(encoding="utf-8"))["questions"]
        man["s32f_a"] = {**write("s32f_a", rows(r1["arms"]["full"]["no_correct_approved(S32 target)"], corpus, "r1_no_correct_full")),
                         "rule": "R1 J1(Full) 승인 gold 정답 없음"}
        man["s32p_a"] = {**write("s32p_a", rows(r1["arms"]["partial"]["no_correct_approved(S32 target)"], corpus, "r1_no_correct_partial")),
                         "rule": "R1 J6(Partial) 승인 gold 정답 없음"}
        man["trunk131"] = {**write("trunk131", rows(sorted(i for i, r in corpus.items() if r["corpus_group"] == "trunk"), corpus, "trunk")),
                           "rule": "승인 trunk 131(J8 Partial, J9 Full)"}
        man["j10"] = {**write("j10", rows(sorted(i for i, r in corpus.items() if r["corpus_group"] == "batch008") + sorted(inval), corpus, "j10")),
                      "rule": "batch008 10 + 질문 변경 aug300(R0 통과분)"}
    man_p.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v["items"] for k, v in man.items()}))


if __name__ == "__main__":
    main()
