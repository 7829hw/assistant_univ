# -*- coding: utf-8 -*-
"""C3: A단계 모델이 JSON에 학습 데이터에 없는 ``"od_role":"none"``을 쓴 원인 보기(진단). 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_007/analysis/od_none.py   # -> analysis/od_none.json (A2 셀이 생기면 다시 돌림)

- 학습 데이터(RC3c Full·Partial, 비교로 RC3): teacher thinking에 "끝: 없음"(다섯 줄 형식의 끝 줄, 또는 "끝은 없음/끝: … 없음")이 나오는 비율,
  레코드 JSON(``</think>`` 뒤)에 od_role이 아예 없는 비율, od_role 값 분포(``"none"``이 있는지).
- 모델 출력(주 셋 셀 원문 첫 응답): thinking의 "끝 없음"과 JSON의 ``"od_role":"none"``이 함께 나오는지(2 × 2 표), 모델별 none 비율.
  대상: base(pilot_006 B5), pilot_006 F-s43 e1, A단계 R1·R2 여섯, A2 (a)·(b) 여섯(있으면).
"""
import glob
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
END_NONE = re.compile(r"끝\s*[:：]\s*(\"?없음|없다)|끝(은|이)\s*(\"?없음\"?|없다)|→\s*끝\s*없음")
OD_NONE = re.compile(r'"od_role"\s*:\s*"none"')
OD_ANY = re.compile(r'"od_role"\s*:\s*"([a-z_]+)"')


def data_stats(path):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = {}
    for scope in ("full_response", "json_only"):
        rs = [r for r in rows if r["metadata"]["loss_scope"] == scope]
        th = [r["messages"][-1]["content"].split("</think>")[0] for r in rs]
        js = [r["messages"][-1]["content"].split("</think>")[-1] for r in rs]
        out[scope] = {"records": len(rs), "thinking_end_none_pct": round(100 * sum(bool(END_NONE.search(t)) for t in th) / max(1, len(rs)), 1),
                      "json_without_od_role_pct": round(100 * sum(not OD_ANY.search(j) for j in js) / max(1, len(rs)), 1),
                      "json_od_role_none_pct": round(100 * sum(bool(OD_NONE.search(j)) for j in js) / max(1, len(rs)), 1),
                      "od_role_values": dict(Counter(v for j in js for v in OD_ANY.findall(j)).most_common())}
    return out


def outputs(pattern):
    tab, n = Counter(), 0
    for f in sorted(glob.glob(str(ROOT / pattern))):
        raw = json.loads(Path(f).read_text(encoding="utf-8"))["meta"]["hf"]["raw_out"]
        seen = set()
        for line in Path(raw).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["id"] in seen:  # 첫 계획 호출만
                continue
            seen.add(r["id"])
            t = r.get("raw_text") or ""
            th, js = t.split("</think>")[0], t.split("</think>")[-1]
            tab[(bool(END_NONE.search(th)), bool(OD_NONE.search(js)))] += 1
            n += 1
    if not n:
        return None
    none = tab[(True, True)] + tab[(False, True)]
    end = tab[(True, True)] + tab[(True, False)]
    return {"samples": n, "od_none_pct": round(100 * none / n, 1), "thinking_end_none_pct": round(100 * end / n, 1),
            "both": tab[(True, True)], "od_none_without_end_none": tab[(False, True)], "end_none_without_od_none": tab[(True, False)], "neither": tab[(False, False)],
            "P(od_none | end_none)_pct": round(100 * tab[(True, True)] / end, 1) if end else None,
            "P(od_none | no end_none)_pct": round(100 * tab[(False, True)] / (n - end), 1) if n - end else None}


def main():
    C6, C7 = "sft_dpo_inventory/pilot_006/cells/", "sft_dpo_inventory/pilot_007/cells/"
    out = {"patterns": {"end_none": END_NONE.pattern, "od_none": OD_NONE.pattern}, "data": {}, "outputs": {}}
    for name, rc in (("RC3", "sft_dpo_inventory/pilot_006/build/RC3"), ("RC3c", "sft_dpo_inventory/pilot_007/build/RC3c")):
        out["data"][name] = {arm: data_stats(ROOT / rc / arm / "sft_train.jsonl") for arm in ("full", "partial")}
    models = {"base(B5)": C6 + "b5_sel_base_s3_s*.json", "pilot006_F43e1": C6 + "f43_e1_sel_s*.json", "pilot006_F1016e1": C6 + "f1016_e1_sel_s*.json"}
    for r in ("r1", "r2"):
        for o in ("o43", "o1016", "o7"):
            models[f"A_{r.upper()}_{o}"] = C7 + f"a_{r}_{o}_sel_s*.json"
    for s in ("s43", "s1016", "s7"):
        models[f"C_{s}(A2 a)"] = C7 + f"c_{s}_sel_s*.json"
    for o in ("o43", "o1016", "o7"):
        models[f"R1p_{o}(A2 b)"] = C7 + f"r1p_{o}_sel_s*.json"
    for m, p in models.items():
        res = outputs(p)
        if res:
            out["outputs"][m] = res
    (HERE / "od_none.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for name, d in out["data"].items():
        for arm, v in d.items():
            print(name, arm, {k: {kk: vv for kk, vv in x.items() if kk != "od_role_values"} for k, x in v.items()}, v["full_response"]["od_role_values"])
    for m, v in out["outputs"].items():
        print(m, v)


if __name__ == "__main__":
    main()
