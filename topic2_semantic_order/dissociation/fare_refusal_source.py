"""등록 이후 추가한 탐색적 분석(PREREGISTRATION_ADDENDUM.md A1). CPU 전용, 기존 기록만 읽는다.

질문에 "요금"이 나오는 V4 레코드 2건(둘 다 {"unsupported": true})이 요금 문항 거절 풀이(지표 1)의 출처인지 본다.
  - b011:b011-054 (hf, json_only) "부산 택시 기본요금이 얼마야?"
  - b012:b012-043 (teacher 거절 풀이, full_response) "이번 달 대구 택시 요금 평균을 날마다 구해줘"
1. 기존 A/B 순서 파일 6개(run r1–r3은 같은 순서·같은 seed 43)에서 두 레코드의 스텝(배치 1, SequentialSampler → 스텝 = 순서 안 위치 + 1).
   비교용으로 거절 레코드 전체(최종 JSON unsupported)의 위치 요약도 낸다.
2. 위치와 run별 지표 1(원래 기록, x3/x3_results.json의 orig)의 관계: 기술(순서 6개뿐이라 검정하지 않음).
3. 요금 대상 147문항의 거절 양식 출력(18 run)이 b012-043 풀이와 얼마나 닮았는지:
   같은 줄(공백 정리 후 10자 이상, b012-043 풀이의 줄과 완전히 같음), 글자 6-gram 포함률(b012-043 풀이의 6-gram 중 출력에 있는 비율),
   V4 teacher 거절 풀이 전체 가운데 가장 닮은 레코드(6-gram 포함률 기준)가 b012-043인 비율, 이유 표현의 등장(아래 REASONS).
    python fare_refusal_source.py MAIN_REPO
출력: dissociation/addendum/fare_refusal_source.json, 표는 표준 출력.
"""
import collections
import contextlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import numpy as np

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
spec = importlib.util.spec_from_file_location("fdc", D / "fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["x", str(main)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv

KEYS = {"b011-054": "b011:b011-054", "b012-043": "b012:b012-043"}
ORDERS = {("A", "o1102"): "sft_dpo_inventory/ablation_011/build/orders/record_order_A0_o1102.json",
          ("A", "o211102"): "sft_dpo_inventory/ablation_011/build/orders/record_order_A0_o211102.json",
          ("A", "o2026131"): "sft_dpo_inventory/ablation_013/build/orders/record_order_A0_o2026131.json",
          ("B", "o1102"): "topic2_semantic_order/orders/semantic_order_o1102.json",
          ("B", "o211102"): "topic2_semantic_order/orders/semantic_order_o211102.json",
          ("B", "o2026131"): "topic2_semantic_order/orders/semantic_order_o2026131.json"}
REASONS = {"일 단위(날마다·하루 단위·일별·날짜별·매일)": r"날마다|하루 ?단위|하루마다|일별|날짜별|매일",
           "주별 대안(주별·주 단위)": r"주별|주 ?단위",
           "미래 기간(아직 오지 않은)": r"아직 오지 않은",
           "요금 언급": r"요금",
           "요금이 재는 값 목록에 없음": r"요금[^\n]{0,30}(없|아니|포함되지 않)",
           "소속 언급": r"소속",
           "택시 유형 언급": r"택시 유형"}

recs = [json.loads(line) for line in open(main / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", encoding="utf-8")]
rid = lambda r: f"{r['metadata']['source_record_id']}|{r['metadata']['trace_id']}"
by_rid = {rid(r): r for r in recs}
target_rid = {k: next(rid(r) for r in recs if r["metadata"]["source_record_id"] == v) for k, v in KEYS.items()}
for k, v in KEYS.items():
    assert sum(r["metadata"]["source_record_id"] == v for r in recs) == 1, v
    assert "요금" in by_rid[target_rid[k]]["messages"][1]["content"]
fare_q = [r for r in recs if "요금" in r["messages"][1]["content"]]
assert len(fare_q) == 2, len(fare_q)


def is_refusal(r):
    plan = r["messages"][2]["content"].split("</think>")[-1].strip()
    try:
        return bool(json.loads(plan).get("unsupported"))
    except Exception:  # noqa: BLE001
        return False


refusal_rids = {rid(r) for r in recs if is_refusal(r)}
teacher_ref = {rid(r): r["messages"][2]["content"].split("</think>")[0] for r in recs
               if is_refusal(r) and r["metadata"].get("loss_scope") == "full_response"}

# 1. 위치
pos = {}
for (arm, s), p in ORDERS.items():
    seq = json.loads((main / p).read_text(encoding="utf-8"))["record_sequence"]
    assert len(seq) == 1984 and set(seq) == set(by_rid), p
    idx = {x: i + 1 for i, x in enumerate(seq)}
    ref_steps = sorted(idx[x] for x in refusal_rids)
    pos[f"{arm}-{s}"] = {**{k: idx[v] for k, v in target_rid.items()},
                         "refusal_records": len(ref_steps), "refusal_median_step": float(np.median(ref_steps)),
                         "refusal_in_last_200": sum(x > 1784 for x in ref_steps),
                         "last_refusal_step": ref_steps[-1],
                         "teacher_refusal_after_b012_043": sum(idx[x] > idx[target_rid["b012-043"]] for x in teacher_ref)}

# 2. run별 지표 1
x3 = json.loads((D / "x3/x3_results.json").read_text(encoding="utf-8"))
m1 = {r["run"]: r["orig"]["m1_refusal"] for r in x3["runs"]}
runs = []
for arm, s, rep in fdc.RUNS:
    p = pos[f"{arm}-{s}"]
    runs.append({"run": f"{arm}-{s}-r{rep}", "arm": arm, "order": s, "step_b011_054": p["b011-054"], "step_b012_043": p["b012-043"],
                 "m1_refusal": m1[f"{arm}-{s}-r{rep}"]})


def ranks(x):
    return np.argsort(np.argsort(x)).astype(float)


def spearman(a, b):
    return float(np.corrcoef(ranks(np.array(a)), ranks(np.array(b)))[0, 1]) if len(set(a)) > 1 and len(set(b)) > 1 else None


order_level = []
for key in pos:
    sub = [r for r in runs if f"{r['arm']}-{r['order']}" == key]
    order_level.append({"order": key, "step_b011_054": pos[key]["b011-054"], "step_b012_043": pos[key]["b012-043"],
                        "m1_mean": float(np.mean([r["m1_refusal"] for r in sub])), "m1_runs": [r["m1_refusal"] for r in sub]})
rel = {"spearman_all6_step_b012_043_vs_m1": spearman([o["step_b012_043"] for o in order_level], [o["m1_mean"] for o in order_level]),
       "spearman_all6_step_b011_054_vs_m1": spearman([o["step_b011_054"] for o in order_level], [o["m1_mean"] for o in order_level])}
for arm in "AB":
    sub = [o for o in order_level if o["order"].startswith(arm)]
    rel[f"{arm}_step_b012_043_vs_m1"] = [(o["step_b012_043"], round(o["m1_mean"], 4)) for o in sorted(sub, key=lambda o: o["step_b012_043"])]
    rel[f"{arm}_step_b011_054_vs_m1"] = [(o["step_b011_054"], round(o["m1_mean"], 4)) for o in sorted(sub, key=lambda o: o["step_b011_054"])]
    rel[f"{arm}_within_order_m1_sd_mean"] = float(np.mean([np.std(o["m1_runs"], ddof=1) for o in sub]))
    rel[f"{arm}_between_order_m1_sd"] = float(np.std([o["m1_mean"] for o in sub], ddof=1))

# 3. 닮음
norm = lambda s: re.sub(r"\s+", " ", s).strip()
ref_think = teacher_ref[target_rid["b012-043"]]
ref_lines = {norm(x) for x in ref_think.split("\n") if len(norm(x)) >= 10}


def grams(s, n=6):
    s = norm(s)
    return {s[i:i + n] for i in range(len(s) - n + 1)}


tgrams = {k: grams(v) for k, v in teacher_ref.items()}
ref_g = tgrams[target_rid["b012-043"]]
outs = []
for arm, s, rep in fdc.RUNS:
    raw = fdc.load_raw(fdc.raw_path(arm, s, rep))
    for i in fdc.need:
        if fdc.features(raw[i], fdc.T1[i])["template"] != "refusal":
            continue
        think = raw[i].split("</think>")[0]
        g = grams(think)
        cont = {k: len(v & g) / len(v) for k, v in tgrams.items()}
        best = max(cont, key=cont.get)
        rank = 1 + sum(c > cont[target_rid["b012-043"]] for c in cont.values())
        lines = {norm(x) for x in think.split("\n") if len(norm(x)) >= 10}
        outs.append({"run": f"{arm}-{s}-r{rep}", "arm": arm, "id": i, "contain_b012_043": cont[target_rid["b012-043"]],
                     "rank_b012_043": rank, "nearest": best, "nearest_contain": cont[best],
                     "same_lines": sorted(lines & ref_lines),
                     "reasons": {k: bool(re.search(p, think)) for k, p in REASONS.items()}})
# 비교 기준: b012-043 자신을 뺀 teacher 거절 풀이끼리의 6-gram 포함률(같은 양식이라 생기는 기본 닮음)
base_cont = [len(ref_g & v) / len(ref_g) for k, v in tgrams.items() if k != target_rid["b012-043"]]
line_counter = collections.Counter(x for o in outs for x in o["same_lines"])
sim = {"n_refusal_outputs": len(outs), "by_arm_n": dict(collections.Counter(o["arm"] for o in outs)),
       "n_teacher_refusal_records": len(teacher_ref),
       "contain_b012_043_mean": float(np.mean([o["contain_b012_043"] for o in outs])),
       "contain_b012_043_median": float(np.median([o["contain_b012_043"] for o in outs])),
       "contain_b012_043_max": float(np.max([o["contain_b012_043"] for o in outs])),
       "baseline_other_teacher_refusals_contain_of_b012_043_mean": float(np.mean(base_cont)),
       "nearest_is_b012_043": sum(o["nearest"] == target_rid["b012-043"] for o in outs),
       "rank_b012_043_median": float(np.median([o["rank_b012_043"] for o in outs])),
       "nearest_counter_top5": collections.Counter(o["nearest"] for o in outs).most_common(5),
       "outputs_with_any_same_line": sum(bool(o["same_lines"]) for o in outs),
       "same_line_counts": line_counter.most_common(),
       "reasons_count": {k: sum(o["reasons"][k] for o in outs) for k in REASONS},
       "reasons_count_by_arm": {a: {k: sum(o["reasons"][k] for o in outs if o["arm"] == a) for k in REASONS} for a in "AB"}}
# 같은 이유 표현의 바탕 빈도: V4 teacher 거절 풀이 전체에서 이유 표현이 나오는 레코드 수
sim["reasons_in_v4_teacher_refusals"] = {k: sum(bool(re.search(p, t)) for t in teacher_ref.values()) for k, p in REASONS.items()}

res = {"records": {k: {"rid": target_rid[k], "question": by_rid[target_rid[k]]["messages"][1]["content"].split("\n")[-1][-80:],
                       "loss_scope": by_rid[target_rid[k]]["metadata"].get("loss_scope")} for k in KEYS},
       "positions": pos, "runs": runs, "order_level": order_level, "relation": rel, "similarity": sim, "outputs": outs}
(D / "addendum").mkdir(exist_ok=True)
(D / "addendum/fare_refusal_source.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

print("순서        b011-054  b012-043  거절레코드 중앙스텝  끝200스텝안 거절  마지막 거절  043뒤 teacher거절 | 지표1 평균(r1–r3)")
for o in order_level:
    p = pos[o["order"]]
    print(f"{o['order']:<11} {p['b011-054']:8d}  {p['b012-043']:8d}  {p['refusal_median_step']:10.0f}  {p['refusal_in_last_200']:14d}  {p['last_refusal_step']:10d}  {p['teacher_refusal_after_b012_043']:10d} | "
          f"{100 * o['m1_mean']:5.1f} ({', '.join(f'{100 * x:.1f}' for x in o['m1_runs'])})")
print(json.dumps(rel, ensure_ascii=False))
print(json.dumps({k: v for k, v in sim.items() if k != "same_line_counts"}, ensure_ascii=False, indent=1))
print("same lines:", sim["same_line_counts"][:10])
