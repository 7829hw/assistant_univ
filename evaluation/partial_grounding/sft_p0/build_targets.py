"""Full 학습 target → Partial P0 target 결정적 변환과 불변식 검사(모델 호출·학습 없음).

변환 규칙(P0 prompt `evaluation/partial_grounding/prompts/partial_p0.yaml` output_format 기준):
- concept마다 id, concept, role, source를 지운다(`replay_partial.STRUCTURAL_KEYS`). text, subtype, value, attributes는 둔다.
- 측정 대상 사건 concept(concept == EVENT)를 지운다.
- factors와 최상위 unsupported는 그대로 둔다. 자연어를 읽지 않는다.

불변식(문항마다, 하나라도 어긋나면 자동 통과에서 빼고 manual_review.jsonl로 보낸다):
1. 형식: P0 concept key ⊆ {text, subtype, value, attributes}, 최상위 key ⊆ {concepts, factors, unsupported}.
2. 실행: Full과 P0를 같은 T2PC 운영 경로(`training.data.validation.assess_t2pc`: stub client → planner(조건 계층·정규화) →
   compose → validate → compile, 기준일 2026-09-25)에 넣은 결과(parse·outcome·error_code·validation·compile)가 같다.
3. 의미: 같은 경로의 grounding 서명(`grounding_signature`: concept/subtype/role/source/value/attributes와 factors)이
   EVENT concept를 빼고 같고, (P0는 계약상 측정 대상 사건을 적지 않는다. 사건은 composer가 측정값으로 붙이므로 2의
   operators 비교가 사건 차이를 잡는다)
   평가 비교 정규형(`evaluate_vendor100._grounding_view`: 측정값·장소·od_role·scope·factor·집계 IR)이 같다.

입력: training/generated/reviewed_gold_v005_t2pc(SFT 111, DPO 75), training/generated/thinking_pilot002_t2pc(SFT 379, 참고).
출력(이 디렉터리): conversion_report.json, manual_review.jsonl, targets_v005_sft_p0.jsonl, inventory.json.

    /data/hwkim/path_repeat_001/venv/py/bin/python evaluation/partial_grounding/sft_p0/build_targets.py
"""
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "partial_grounding"))

import evaluate_vendor100 as V  # noqa: E402
from geoflow.grounding import complete_grounding_payload  # noqa: E402
from replay_partial import to_partial  # noqa: E402
from training.data.validation import assess_t2pc  # noqa: E402

GEN = ROOT / "training/generated"
V005 = GEN / "reviewed_gold_v005_t2pc"
THINKING = GEN / "thinking_pilot002_t2pc"
P0_PROMPT = ROOT / "evaluation/partial_grounding/prompts/partial_p0.yaml"
P0_CONCEPT_KEYS = {"text", "subtype", "value", "attributes"}
P0_TOP_KEYS = {"concepts", "factors", "unsupported"}
EXEC_KEYS = ("parse_ok", "outcome", "error_code", "validation_ok", "validation_codes", "operators", "compile_ok",
             "compile_error_code")
#: 평가셋(학습 target에 넣지 않음). 질문 문장으로 겹침을 본다.
EVAL_SETS = {
    "vendor100": ("yaml", ROOT / "evaluation" / "vendor100" / "gold.yaml"),
    "valid98": ("yaml", ROOT / "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml"),
    "sel154": ("yaml", ROOT / "evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml"),
    "aux_test_v1": ("items", ROOT / "sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json"),
}
#: thinking trace에 Full 구조 필드를 계획하는 말이 있는지(참고 지표).
FULL_FIELD_WORDS = re.compile(r"\b(role|MEASURE|SUPPORT|SUBCOND|COND|source|implicit|EVENT|concept)\b")


def norm(question):
    return re.sub(r"[\s\W_]+", "", question or "")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def eval_questions():
    out = {}
    for name, (kind, path) in EVAL_SETS.items():
        if not path.exists():
            out[name] = None
            continue
        if kind == "yaml":
            out[name] = {norm(i["question"]) for i in yaml.safe_load(path.read_text(encoding="utf-8"))["items"]}
        else:
            items = json.loads(path.read_text(encoding="utf-8"))["items"]
            qs = set()
            cache = {}
            for it in items:
                src = cache.setdefault(it["path"], {str(x["id"]): x for x in yaml.safe_load(
                    (ROOT / it["path"]).read_text(encoding="utf-8"))["items"]})
                qs.add(norm(src[str(it["id"])]["question"]))
            out[name] = qs
    return out


def json_part(content):
    """assistant 내용에서 JSON 부분(thinking 뒤)."""
    text = content.split("</think>", 1)[-1]
    i, j = text.find("{"), text.rfind("}")
    return json.loads(text[i:j + 1])


def exec_view(result):
    return {k: result.get(k) for k in EXEC_KEYS}


def intra_area_form(payload):
    """같은 장소가 양 끝을 거르는 표현: 'both_single'(결정 47 표기), 'two_places', None."""
    places = [c for c in payload.get("concepts") or [] if c.get("subtype") in ("place", "scope") and c.get("value")]
    roles = [(json.dumps(c.get("value"), ensure_ascii=False, sort_keys=True), (c.get("attributes") or {}).get("od_role"))
             for c in places]
    if any(r == "both" for _, r in roles):
        return "both_single"
    by_value = collections.defaultdict(set)
    for v, r in roles:
        by_value[v].add(r)
    if any({"pickup", "dropoff"} <= rs for rs in by_value.values()):
        return "two_places"
    return None


def strip_events(signature):
    if not signature:
        return signature
    return {"concepts": [c for c in signature["concepts"] if json.loads(c).get("concept") != "EVENT"],
            "factors": signature["factors"]}


def convert(question, full):
    """한 target의 변환과 불변식. (p0, 기록)."""
    p0, dropped = to_partial(json.loads(json.dumps(full)))
    rec = {"dropped": dropped}
    problems = []
    if isinstance(p0, dict) and not p0.get("unsupported"):
        extra_top = set(p0) - P0_TOP_KEYS
        extra_concept = sorted({k for c in p0.get("concepts") or [] for k in c} - P0_CONCEPT_KEYS)
        if extra_top or extra_concept:
            problems.append(f"format: top {sorted(extra_top)} concept {extra_concept}")
    rf, rp = assess_t2pc(full, question), assess_t2pc(p0, question)
    rec["full_exec"], rec["p0_exec"] = exec_view(rf), exec_view(rp)
    if exec_view(rf) != exec_view(rp):
        problems.append("exec_differs")
    if strip_events(rf.get("signature")) != strip_events(rp.get("signature")):
        problems.append("signature_differs")
    if not (isinstance(full, dict) and full.get("unsupported")):
        vf = V._grounding_view(full)
        vp = V._grounding_view(complete_grounding_payload(json.loads(json.dumps(p0))))
        if vf != vp:
            problems.append("grounding_view_differs")
            rec["views"] = {"full": vf, "p0": vp}
    rec["problems"] = problems
    rec["auto_pass"] = not problems
    return p0, rec


def factor_stats(payloads):
    c = collections.defaultdict(collections.Counter)
    for p in payloads:
        if p.get("unsupported"):
            c["unsupported"]["true"] += 1
            continue
        f = p.get("factors") or {}
        for key in ("dimension_target", "bucket", "dimension", "aggregation", "rollup", "answer"):
            c[key][str(f.get(key, "-"))] += 1
        for concept in p.get("concepts") or []:
            st = concept.get("subtype")
            if st == "place":
                c["place"]["with_value" if concept.get("value") else "answer_place(no_value)"] += 1
                c["od_role"][str((concept.get("attributes") or {}).get("od_role", "-"))] += 1
            elif st == "scope":
                c["scope"]["count"] += 1
                c["od_role"][str((concept.get("attributes") or {}).get("od_role", "-"))] += 1
        c["intra_area_form"][str(intra_area_form(p))] += 1
        c["dimension_target_with_dimension"][str(bool(f.get("dimension")) and "dimension_target" in f)] += 1
    return {k: dict(v.most_common()) for k, v in c.items()}


def main():
    evalq = eval_questions()
    report = {"inputs": {}, "p0_prompt_sha256": sha(P0_PROMPT), "rules": __doc__.split("입력:")[0].strip()}
    manual, targets = [], []

    # 1) 주 입력: v005 승인 gold SFT target
    sft = read_jsonl(V005 / "sft_train.jsonl")
    report["inputs"]["v005_sft_train"] = {"path": str((V005 / "sft_train.jsonl").relative_to(ROOT)),
                                          "sha256": sha(V005 / "sft_train.jsonl"), "records": len(sft)}
    rows, p0s = [], []
    for r in sft:
        q = r["messages"][1]["content"]
        full = json.loads(r["messages"][-1]["content"])
        p0, rec = convert(q, full)
        overlaps = sorted(name for name, qs in evalq.items() if qs and norm(q) in qs)
        if overlaps:
            rec["problems"].append(f"eval_overlap:{','.join(overlaps)}")
            rec["auto_pass"] = False
        rec.update(id=r["metadata"].get("source_record_id"), question=q,
                   origin=r["metadata"].get("corpus_origin_v005") or r["metadata"].get("corpus_origin"),
                   family=r["metadata"].get("family"), intra_area_form=intra_area_form(full))
        rows.append(rec)
        p0s.append(p0)
        if rec["auto_pass"]:
            targets.append({"id": rec["id"], "question": q, "target_p0": p0, "target_full": full,
                            "metadata": {k: r["metadata"].get(k) for k in ("source_record_id", "family", "corpus_origin",
                                                                            "corpus_origin_v005", "review_decision_hash")}})
        else:
            manual.append({"source": "v005_sft_train", "id": rec["id"], "question": q, "problems": rec["problems"],
                           "full": full, "p0": p0, "full_exec": rec["full_exec"], "p0_exec": rec["p0_exec"],
                           **({"views": rec["views"]} if "views" in rec else {})})
    report["v005_sft"] = {
        "records": len(rows), "auto_pass": sum(r["auto_pass"] for r in rows),
        "manual_review": sum(not r["auto_pass"] for r in rows),
        "problems": dict(collections.Counter(p for r in rows for p in r["problems"])),
        "outcome_full": dict(collections.Counter(r["full_exec"]["outcome"] for r in rows)),
        "compile_ok_full": dict(collections.Counter(str(r["full_exec"]["compile_ok"]) for r in rows)),
        "unsupported_targets": sum(1 for p in p0s if p.get("unsupported")),
        "needs_clarification_targets": 0,
        "dropped_fields_total": sum((r["dropped"] or {}).get("fields", 0) for r in rows),
        "dropped_event_concepts_total": sum((r["dropped"] or {}).get("events", 0) for r in rows),
        "by_origin": dict(collections.Counter(r["origin"] for r in rows)),
        "eval_overlap_questions": {name: sum(1 for r in rows if qs and norm(r["question"]) in qs)
                                   for name, qs in evalq.items()},
        "factor_stats_p0": factor_stats(p0s),
        "json_chars": {"full_mean": round(sum(len(json.dumps(json.loads(s["messages"][-1]["content"]), ensure_ascii=False))
                                              for s in sft) / len(sft), 1),
                       "p0_mean": round(sum(len(json.dumps(p, ensure_ascii=False)) for p in p0s) / len(p0s), 1)},
    }

    # 2) DPO 쌍(참고: chosen·rejected 각각 변환 가능성만)
    dpo = read_jsonl(V005 / "dpo_train.jsonl")
    dstats = collections.Counter()
    for r in dpo:
        q = [m for m in r["prompt"] if m["role"] == "user"][-1]["content"]
        for side in ("chosen", "rejected"):
            try:
                payload = json_part(r[side][-1]["content"])
            except (ValueError, KeyError, IndexError):
                dstats[f"{side}:parse_fail"] += 1
                continue
            _, rec = convert(q, payload)
            dstats[f"{side}:{'same' if not rec['problems'] else 'differs'}"] += 1
    report["v005_dpo"] = {"pairs": len(dpo), "sha256": sha(V005 / "dpo_train.jsonl"), "conversion": dict(dstats)}

    # 3) thinking SFT(pilot_002): JSON 부분 변환 가능성과 thinking 안의 Full 구조 언급(참고)
    th = read_jsonl(THINKING / "sft_train.jsonl")
    tstats = collections.Counter()
    mentions = []
    for r in th:
        content = r["messages"][-1]["content"]
        thinking = content.split("</think>", 1)[0]
        mentions.append(len(FULL_FIELD_WORDS.findall(thinking)))
        try:
            payload = json_part(content)
        except ValueError:
            tstats["parse_fail"] += 1
            continue
        q = r["messages"][1]["content"]
        _, rec = convert(q, payload)
        tstats["same" if not rec["problems"] else "differs"] += 1
    report["thinking_pilot002_sft"] = {
        "records": len(th), "sha256": sha(THINKING / "sft_train.jsonl"), "json_conversion": dict(tstats),
        "thinking_full_field_mentions": {"records_with_any": sum(1 for m in mentions if m),
                                         "median": sorted(mentions)[len(mentions) // 2]}}

    (HERE / "conversion_report.json").write_text(json.dumps({**report, "items": rows}, ensure_ascii=False, indent=1)
                                                 + "\n", encoding="utf-8")
    (HERE / "manual_review.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manual),
                                              encoding="utf-8")
    (HERE / "targets_v005_sft_p0.jsonl").write_text("".join(json.dumps(t, ensure_ascii=False) + "\n" for t in targets),
                                                    encoding="utf-8")
    summary = {k: report[k] for k in ("v005_sft", "v005_dpo", "thinking_pilot002_sft")}
    summary["v005_sft"] = {k: v for k, v in summary["v005_sft"].items() if k != "factor_stats_p0"}
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
