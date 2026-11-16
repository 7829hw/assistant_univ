"""요금(T1) 문항의 추론–계획 해리 점검 (CPU 전용, 기존 산출물만 읽음).

사용법 (저장소 루트를 인자로):
    python fare_dissociation_check.py /path/to/assistant_univ

읽는 것: H-dev gold(h_dev.yaml), A/B 18개 실행의 H-dev 셀과 raw 생성 로그, base 2회, 재평가로 교체된 셀,
        V4 sft_train.jsonl. 읽지 않는 것: h_final.yaml, E1/E2(C/D/F0/F48) 셀, CT10K.
사후(post-hoc) 기술 분석이다. 사전등록된 어떤 검정도 대체하지 않는다.
"""
import collections
import glob
import json
import os
import re
import sys

import numpy as np
import yaml

repo = sys.argv[1]
G = "training/generated"
C12, C13 = "sft_dpo_inventory/ablation_012/cells", "sft_dpo_inventory/ablation_013/cells"
C2, CR = "topic2_semantic_order/cells", "topic2_semantic_order_repro/cells"


def parse_gold(text):
    calls = []
    for line in (text or "").split("\n"):
        m = re.match(r"\s*(\w+)\((.*)\)\s*$", line)
        if m:
            args = dict(kv.split("=", 1) for kv in m.group(2).split(", ") if "=" in kv)
            calls.append((m.group(1), {k.strip(): v.strip() for k, v in args.items()}))
    return calls


gold = yaml.safe_load(open(f"{repo}/sft_dpo_inventory/ablation_012/e2/h_dev.yaml", encoding="utf-8"))
T1 = {}
for it in gold["items"]:
    calls = parse_gold(it["gold_text"])
    analysis = [c for c in calls if c[0] != "get_place_scope"]
    place = [c for c in calls if c[0] == "get_place_scope"]
    if analysis and analysis[0][0] == "get_trip_metrics":
        T1[it["id"]] = place[0][1].get("name") if place else None
ids = sorted(T1)
need = [i for i in ids if T1[i]]  # 장소 조회가 필요한 요금 문항
print(f"H-dev 요금 문항 {len(ids)}개, 그중 장소 조회 필요 {len(need)}개")

RUNS = [(a, s, r) for a in "AB" for s in ("o1102", "o211102", "o2026131") for r in (1, 2, 3)]


def cell_path(arm, s, r):
    a = "a0" if arm == "A" else "b"
    if r == 1:
        return f"{C12 if s in ('o1102', 'o211102') else C13}/hdev_a0_{s}_s1.json" if arm == "A" else f"{C2}/hdev_t2_b_{s}_s1.json"
    if s == "o2026131" and r == 2:
        return f"{C2}/hdev_t2_{a}_o2026131_r2_s1.json"
    return f"{CR}/hdev_repro_{a}_{s}_r{r}_s1.json"


def raw_path(arm, s, r):
    a = "a0" if arm == "A" else "b"
    if r == 1:
        if arm == "A":
            return f"{G}/ablation_01{'2' if s in ('o1102', 'o211102') else '3'}/cells_raw/hdev_a0_{s}_s1_raw.jsonl"
        return f"{G}/topic2_semantic_order/cells_raw/hdev_t2_b_{s}_s1_raw.jsonl"
    if s == "o2026131" and r == 2:
        return f"{G}/topic2_semantic_order/cells_raw/hdev_t2_{a}_o2026131_r2_s1_raw.jsonl"
    return f"{G}/topic2_semantic_order_repro/cells_raw/hdev_repro_{a}_{s}_r{r}_s1_raw.jsonl"


def load_match(p):
    d = json.load(open(f"{repo}/{p}", encoding="utf-8"))
    return {r["id"]: r["category"] == "match" for r in d["rows"]}


def load_raw(p):
    out = {}
    for line in open(f"{repo}/{p}", encoding="utf-8"):
        d = json.loads(line)
        if d.get("call", 0) == 0 and d["id"] not in out:
            out[d["id"]] = d["raw_text"]
    return out


def features(text, place):
    think, plan = text.split("</think>", 1) if "</think>" in text else (text, "")
    analysis = ("측정:" in think) or bool(re.search(r"1\.\s*측정", think))
    refusal = ("나타낼 수 없는" in think) or ("무엇을 묻는지" in think)
    return {
        "template": "refusal" if (refusal and not analysis) else ("analysis" if analysis else "other"),
        "mentions_place": place in think,
        "states_region_condition": bool(re.search(r"소속[^\n]{0,80}(지역|시도|등록|조건|범위)|(지역|시도)[^\n]{0,40}(조건|지정|제한)", think)),
        "location": '"concept":"LOCATION"' in plan.replace(" ", ""),
        "taxi_type": '"taxi_type"' in plan,
    }


pct = lambda xs: 100 * float(np.mean(xs)) if len(xs) else float("nan")

print("\n[1] 실행별: 정확도(장소 필요 문항) | 거절형 추론 비율 | 분석형 추론 중 LOCATION 출력률")
pooled = []
for k in RUNS:
    ok = load_match(cell_path(*k))
    raw = load_raw(raw_path(*k))
    F = [features(raw[i], T1[i]) for i in need]
    ana = [f for f in F if f["template"] == "analysis"]
    pooled += F
    print(f"  {k[0]}-{k[1]}-r{k[2]}: 정확도 {pct([ok[i] for i in need]):5.1f} | 거절형 {pct([f['template'] == 'refusal' for f in F]):5.1f} | LOCATION {pct([f['location'] for f in ana]):5.1f}")

ana = [f for f in pooled if f["template"] == "analysis"]
print("\n[2] 18개 실행 합산, 분석형 추론")
for name, flag in (("LOCATION 출력", True), ("LOCATION 누락", False)):
    g = [f for f in ana if f["location"] == flag]
    print(f"  {name} n={len(g)}: 추론이 장소를 언급 {pct([f['mentions_place'] for f in g]):.1f}% | 지역 조건이라고 서술 {pct([f['states_region_condition'] for f in g]):.1f}% | 계획에 taxi_type {pct([f['taxi_type'] for f in g]):.1f}%")

print("\n[3] base 모델 (학습 전, 2회)")
B = []
for s in (1, 2):
    raw = load_raw(f"{G}/ablation_012/cells_raw/hdev_base_s{s}_raw.jsonl")
    B += [features(raw[i], T1[i]) for i in need]
print(f"  LOCATION 출력 {pct([f['location'] for f in B]):.1f}% | taxi_type {pct([f['taxi_type'] for f in B]):.1f}%")

print("\n[4] 같은 어댑터 재평가(교체된 1차 시도 vs 채택된 시도): 전체 문항 불일치 | 요금 문항 정확도 차")
for base in (C2, CR):
    for f in sorted(glob.glob(f"{repo}/{base}/replaced/hdev*.json")):
        name = os.path.basename(f)
        if not os.path.exists(f"{repo}/{base}/{name}"):
            continue
        x, y = load_match(f"{base}/replaced/{name}"), load_match(f"{base}/{name}")
        common = sorted(set(x) & set(y))
        print(f"  {name}: 불일치 {pct([x[i] != y[i] for i in common]):4.1f}% | 요금 {pct([x[i] for i in ids]):.1f} → {pct([y[i] for i in ids]):.1f}")

print("\n[5] 학습 데이터 V4")
recs = [json.loads(line) for line in open(f"{repo}/sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl", encoding="utf-8")]
c = collections.Counter()
for r in recs:
    q, a, scope = r["messages"][1]["content"], r["messages"][2]["content"], r["metadata"].get("loss_scope")
    plan = a.rsplit("</think>", 1)[-1] if "</think>" in a else a.rsplit("\n", 1)[-1]
    if "소속" in q:
        c["소속 문항"] += 1
        c["소속 문항 중 LOCATION 있음"] += '"concept":"LOCATION"' in plan.replace(" ", "")
        if scope == "full_response":
            c["소속 teacher 기록"] += 1
            c["소속 teacher 추론이 '택시 유형' 조건이라고 서술"] += "택시 유형" in a
    c["질문에 '요금'"] += "요금" in q
for k, v in c.items():
    print(f"  {k}: {v}")
