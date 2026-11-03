# -*- coding: utf-8 -*-
"""ablation_012 E2 — 새 holdout H-dev(개발용)·H-final(봉인) 빌드(결정 262 D1·E2). 모델 호출 없음.

    python3 sft_dpo_inventory/ablation_012/e2/build_e2.py
    # -> e2/h_dev.yaml, e2/h_final.yaml(봉인), e2/e2_summary.json(H-dev 구성 + H-final은 크기·sha256·template_group 수·pool 분포만), e2/pool_rule_check.json

1. 원천 ``/data/hwkim/sftdpo_work/sources/llm-finetuning-30000.jsonl``(sha256 ``63d445b8…`` 확인).
2. CT10K 모집단(``qa_test_10000.yaml`` selection.population): tool_call 18,000 중 정답 호출의 날짜(8자리) 최댓값 > 20260925인 문항을 뺀 16,206. 재현 수가 16,206이 아니면 멈춘다.
3. CT10K 10,000문항을 뺀다(모두 모집단 안이어야 함).
4. 겹침(pool) 판정 — **client_test_10000의 겹침 도구는 저장소에 없다**(CT10K 파일은 사용자가 만든 업로드 파일이고 pool 값만 들어 있다). 그래서 규칙을 다시 만들고,
   CT10K 10,000문항의 pool 라벨을 **모두 그대로 재현할 때만** 쓴다(아니면 멈춤):
   - verbatim_vendor100: 질문 문자열이 vendor100 질문과 같다.
   - 날짜 변형 후보: 정답 호출을 줄마다 (tool, 인자 집합)으로 파싱하고 ``date`` 인자만 뺀 뼈대가 vendor100 정답 뼈대와 같다. 단 vendor100 쪽 date가
     ``last_year``·``weekday``인 문항은 짝이 되지 않는다(CT10K 라벨에서 이 두 값의 짝은 모두 independent).
   - train_skeleton: 짝 vendor100 문항이 CT10K에서 train_skeleton으로 라벨된 vendor100 문항(13개) 중 하나. 그 밖의 짝은 vendor100_date_variant.
   - 짝이 없으면 independent.
   모집단 문항의 짝 vendor100 문항이 CT10K에 한 번도 나오지 않아 train_skeleton 여부를 모르면(라벨 근거 없음) 보수적으로 뺀다(수를 적는다).
5. 남은 문항에서 train_skeleton·verbatim_vendor100을 뺀다(D1). 참고로 학습 corpus v6·E1 셋(valid98·aux·refusal_dev v2)과 질문 문자열이 같은 문항 수도 센다.
6. template_group 층화: ``numpy.random.default_rng(20261103)``. template_group(정렬)마다 문항 id(정렬)를 ``rng.permutation``으로 섞고,
   H-dev n = min(2,000, N)을 그룹 크기에 비례해 최대 잉여 배분(같은 잉여는 그룹 이름 순), 그룹마다 섞은 앞쪽을 H-dev로; 남은 문항에서 같은 방식으로
   H-final n = min(3,000, 남은 수)(섞은 순서의 다음 것). 나머지는 쓰지 않는다.
7. H-ref: 비-tool_call 12,000의 원천 라벨(task_type·response)에는 '거부' 기대 결과가 없다(구조화·정의·설명 응답이 정답으로 적혀 있다).
   원천 라벨만으로 기대 결과 '거부'가 확정되지 않으므로 H-ref를 만들지 않고 기술 통계만 낸다.
- H-final은 문항별 내용·결과를 화면·요약에 쓰지 않는다(크기·sha256·template_group 수·pool 분포만).
"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
INV = HERE.parents[1]
ROOT = INV.parent
SRC = Path("/data/hwkim/sftdpo_work/sources/llm-finetuning-30000.jsonl")
SRC_SHA = "63d445b86bfb4a3444ba9eea632ba1ff03e51263f125ae4b35587b0c85102def"
CT = INV / "client_test_10000/qa_test_10000.yaml"
VENDOR = ROOT / "evaluation/vendor100/gold.yaml"
CUTOFF = "20260925"
SEED = 20261103
N_DEV, N_FINAL = 2000, 3000
NO_PAIR_DATES = {"last_year", "weekday"}
E1_GOLD = {"valid98": INV / "pilot_004/valid98/valid98_gold.yaml", "aux": INV / "pilot_002/aux_test/aux_test_gold.yaml",
           "rdevv2": INV / "pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"}
CORPUS = INV / "pilot_006_prep/approved/approved_train_v6.jsonl"
NOTE_DEV = ("evaluation-only. 평가 전용: 학습·checkpoint 선택·annotation 후보에 쓰지 않는다. ablation_012 H-dev(개발 비교용, 결정 262). "
            "최종 판정 셋이 아니다.")
NOTE_FINAL = ("evaluation-only, SEALED. 평가 전용: 학습·checkpoint 선택·annotation 후보에 쓰지 않는다. PLAN_J 판정 전용, 측정은 사용자 지시 뒤(결정 262). "
              "문항 내용·결과를 개발·분석·보고에 쓰지 않는다.")


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(g):
    out = []
    for line in g.strip().split("\n"):
        m = re.match(r"(\w+)\((.*)\)$", line.strip())
        if not m:
            raise ValueError(f"unparsed gold line: {line[:80]}")
        args = {}
        for a in (re.split(r",\s*(?=\w+=)", m.group(2)) if m.group(2) else []):
            k, _, v = a.partition("=")
            args[k.strip()] = v.strip()
        out.append((m.group(1), args))
    return out


def skeleton(g):
    return tuple((t, tuple(sorted((k, v) for k, v in a.items() if k != "date"))) for t, a in parse(g))


def max_date(g):
    ds = re.findall(r"\b(20\d{6})\b", g)
    return max(ds) if ds else None


def vendor_date(g):
    ds = [a["date"] for _, a in parse(g) if "date" in a]
    return ds[0] if ds else None


class PoolRule:
    def __init__(self, vendor, ts_ids):
        self.vq = {x["question"].strip(): x["id"] for x in vendor}
        self.idx = defaultdict(list)
        for x in vendor:
            if vendor_date(x["gold_text"]) not in NO_PAIR_DATES:
                self.idx[skeleton(x["gold_text"])].append(x["id"])
        self.ts = set(ts_ids)

    def __call__(self, question, gold, seen_vendor=None):
        hits = self.idx.get(skeleton(gold), [])
        if question.strip() in self.vq:
            return "verbatim_vendor100", hits
        if not hits:
            return "independent", hits
        if seen_vendor is not None and not set(hits) <= seen_vendor:
            return "unknown_vendor_pair", hits
        return ("train_skeleton" if set(hits) & self.ts else "vendor100_date_variant"), hits


def stratified(groups, n, rng_perm):
    """groups: {tg: [ids 섞은 순서]}, 이미 쓴 수 used[tg]. 최대 잉여 배분."""
    total = sum(len(v) for v in groups.values())
    quota = {g: n * len(v) / total for g, v in groups.items()}
    alloc = {g: int(q) for g, q in quota.items()}
    rest = n - sum(alloc.values())
    for g in sorted(groups, key=lambda g: (-(quota[g] - alloc[g]), g))[:rest]:
        alloc[g] += 1
    return alloc


def main():
    if sha_file(SRC) != SRC_SHA:
        raise SystemExit("STOP: source sha256 mismatch (E2만 뺀다)")
    src = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    tc = [s for s in src if s["task_type"] == "tool_call"]
    pop = [s for s in tc if not (max_date(s["response"]) and max_date(s["response"]) > CUTOFF)]
    if len(tc) != 18000 or len(pop) != 16206:
        raise SystemExit(f"STOP: population {len(tc)}/{len(pop)} != 18000/16206")
    ct = yaml.safe_load(CT.read_text(encoding="utf-8"))
    ct_items = ct["items"]
    ct_ids = {i["id"] for i in ct_items}
    pop_ids = {s["id"] for s in pop}
    if not ct_ids <= pop_ids:
        raise SystemExit("STOP: CT10K item outside population")
    vendor = yaml.safe_load(VENDOR.read_text(encoding="utf-8"))["items"]
    ts_ids = sorted({i["vendor100_base"] for i in ct_items if i["pool"] == "train_skeleton"})
    seen_vendor = {i["vendor100_base"] for i in ct_items if i.get("vendor100_base")}
    rule = PoolRule(vendor, ts_ids)
    # 규칙 재현 검사(CT10K 10,000)
    mism, base_ok = Counter(), 0
    for i in ct_items:
        p, hits = rule(i["question"], i["gold_text"])
        if p != i["pool"]:
            mism[(i["pool"], p)] += 1
        if i.get("vendor100_base"):
            base_ok += i["vendor100_base"] in hits
    n_base = sum(1 for i in ct_items if i.get("vendor100_base"))
    check = {"ct10k_items": len(ct_items), "pool_reproduced": len(ct_items) - sum(mism.values()), "pool_mismatch": {f"{a}->{b}": c for (a, b), c in mism.items()},
             "vendor100_base_in_pairs": base_ok, "items_with_vendor100_base": n_base, "train_skeleton_vendor_ids": ts_ids,
             "vendor_ids_seen_in_ct10k": len(seen_vendor), "no_pair_vendor_dates": sorted(NO_PAIR_DATES),
             "rule": "verbatim = 질문 문자열 같음; 날짜 변형 = date 인자 뺀 (tool, 인자 집합) 뼈대가 vendor100 정답 뼈대와 같음(vendor date last_year·weekday 제외); "
                     "train_skeleton = 짝 vendor100 id가 CT10K train_skeleton 라벨 id 13개 중 하나"}
    (HERE / "pool_rule_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if mism or base_ok != n_base:
        raise SystemExit(f"STOP: pool rule does not reproduce CT10K labels: {check}")
    # 남은 모집단
    rest = [s for s in pop if s["id"] not in ct_ids]
    lab = {}
    for s in rest:
        p, hits = rule(s["instruction"], s["response"], seen_vendor)
        lab[s["id"]] = (p, hits)
    excl = Counter(p for p, _ in lab.values() if p in ("train_skeleton", "verbatim_vendor100", "unknown_vendor_pair"))
    keep = [s for s in rest if lab[s["id"]][0] in ("independent", "vendor100_date_variant")]
    # 참고 겹침: 학습 corpus·E1 질문 문자열
    corpus_q = {json.loads(l)["question"].strip() for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()}
    e1_q = set()
    for p in E1_GOLD.values():
        e1_q |= {str(x["question"]).strip() for x in yaml.safe_load(p.read_text(encoding="utf-8"))["items"]}
    ref_overlap = {"corpus_v6_question_text": sum(s["instruction"].strip() in corpus_q for s in keep),
                   "e1_question_text": sum(s["instruction"].strip() in e1_q for s in keep),
                   "ct10k_question_text": sum(s["instruction"].strip() in {i["question"].strip() for i in ct_items} for s in keep)}
    # 층화 나눔
    rng = np.random.default_rng(SEED)
    by_tg = defaultdict(list)
    for s in keep:
        by_tg[s["template_group"]].append(s["id"])
    shuffled = {}
    for g in sorted(by_tg):
        ids = sorted(by_tg[g])
        shuffled[g] = [ids[i] for i in rng.permutation(len(ids))]
    n_dev = min(N_DEV, len(keep))
    a_dev = stratified(shuffled, n_dev, rng)
    dev_ids = {x for g, ids in shuffled.items() for x in ids[:a_dev[g]]}
    left = {g: ids[a_dev[g]:] for g, ids in shuffled.items() if len(ids) > a_dev[g]}
    n_final = min(N_FINAL, sum(len(v) for v in left.values()))
    a_fin = stratified(left, n_final, rng)
    fin_ids = {x for g, ids in left.items() for x in ids[:a_fin[g]]}
    if dev_ids & fin_ids or len(dev_ids) != n_dev or len(fin_ids) != n_final:
        raise SystemExit("split check failed")
    by_id = {s["id"]: s for s in keep}

    def item(s):
        p, hits = lab[s["id"]]
        d = {"id": s["id"], "question": s["instruction"], "gold_text": s["response"], "category": s["category"], "template_group": s["template_group"], "pool": p}
        if p == "vendor100_date_variant":
            d["vendor100_pairs"] = sorted(hits)
        return d

    sel = {"population": f"CT10K 모집단 16,206(tool_call 18,000 − 날짜 > {CUTOFF} 1,794) − CT10K 10,000 = {len(rest)}; "
                         f"− train_skeleton {excl['train_skeleton']} − verbatim_vendor100 {excl['verbatim_vendor100']} − 짝 근거 없음 {excl['unknown_vendor_pair']} = {len(keep)}",
           "method": "template_group 비례 층화 무작위(최대 잉여 배분; 그룹 안 numpy default_rng permutation, H-dev 먼저 그다음 H-final)", "seed": SEED,
           "pool_rule": "e2/build_e2.py PoolRule(CT10K 10,000 라벨 재현 확인, e2/pool_rule_check.json)"}
    out = {}
    for name, ids, note, size in (("h_dev", dev_ids, NOTE_DEV, n_dev), ("h_final", fin_ids, NOTE_FINAL, n_final)):
        items = [item(by_id[x]) for x in sorted(ids)]
        doc = {"source": SRC.name, "source_sha256": SRC_SHA, "note": note, "set": name, "decision": 262, "selection": dict(sel, size=size), "items": items}
        p = HERE / f"{name}.yaml"
        p.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8")
        out[name] = {"file": f"sft_dpo_inventory/ablation_012/e2/{name}.yaml", "sha256": sha_file(p), "items": len(items),
                     "template_groups": len({i["template_group"] for i in items}), "pool": dict(Counter(i["pool"] for i in items))}
        if name == "h_dev":
            out[name]["category"] = dict(Counter(i["category"] for i in items))
            out[name]["analysis_tool"] = dict(Counter(parse(i["gold_text"])[-1][0] for i in items))
            out[name]["template_group_sizes"] = dict(Counter(Counter(i["template_group"] for i in items).values()))
    nontc = [s for s in src if s["task_type"] != "tool_call"]
    summary = {"label": "ablation_012 E2(결정 262)", "source_sha256": SRC_SHA, "population_16206_reproduced": True, "ct10k_excluded": len(ct_ids), "rest": len(rest),
               "rest_pool": dict(Counter(p for p, _ in lab.values())), "excluded": dict(excl), "kept": len(keep), "kept_template_groups": len(by_tg),
               "reference_text_overlap_in_kept": ref_overlap, "sets": out,
               "h_ref": {"built": False, "reason": "비-tool_call 원천 라벨(task_type·response)에 '거부' 기대 결과가 없음 — 원천 라벨만으로 거부가 확정되지 않음(결정 262)",
                         "non_tool_call": len(nontc), "by_task_type": dict(Counter(s["task_type"] for s in nontc)), "by_category": dict(Counter(s["category"] for s in nontc)),
                         "by_source_type": dict(Counter(s["source_type"] for s in nontc)),
                         "response_starts_with_brace": sum(s["response"].lstrip().startswith("{") for s in nontc),
                         "response_mentions_unsupported": sum(bool(re.search(r"unsupported|지원하지 않|답할 수 없|제공하지 않", s["response"])) for s in nontc)}}
    (HERE / "e2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "h_ref"} | {"h_ref_built": False}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
