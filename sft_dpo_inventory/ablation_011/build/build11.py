# -*- coding: utf-8 -*-
"""ablation_011 arm 빌드(결정 261). 입력 = pilot_010 V4 빌드 결과(``pilot_010/build/V4``, 그대로 둠). 모델 호출 없음. ``build10w.py``는 고치지 않는다.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/build/build11.py
    # -> build/{A1,A2,A3}/full/{sft_train,sft_valid}.jsonl·manifest.json, build/removed_{A2,A3}.json,
    #    build/orders/order_b2_o<seed>.json(A0의 O4' 순서, train_b7b 형식), build/orders/record_order_<arm>_o<seed>.json, build/build_summary.json

- A0: ``pilot_010/build/V4/full/sft_train.jsonl``을 그대로 쓴다(복사·재빌드 없음). 파일 sha256 = V4 manifest 값, 질문 목록 sha256 = ``d559b3e1…``인지 확인.
- A1: V4와 같은 레코드·같은 줄. 근접 대조 teacher 레코드(``metadata.contrast_source == "teacher"``, TEACH-C 통과분, ``loss_scope: full_response``)에만
  ``metadata.a11_loss_scope_override = "json_only"``를 더한다. ``loss_scope``·``source``는 바꾸지 않는다(``order7.within_key``가 ``loss_scope``를 써서
  바꾸면 질문 안 순서가 달라지고, ``by_source``가 teacher 레코드의 json_only 표시를 거부하므로). 학습 wrapper ``train_a11.py``가 이 표시가 있는 레코드만
  ``training.data.thinking``의 json_only 렌더(추론을 prompt 쪽에 두고 JSON + EOS만 손실)로 바꾼다 — 입력 token은 같고 마스크만 다르다(``mask_audit11.py``가 확인).
- A2: 거부 비중 ρ = 0.02, R = round(ρ·N/(1−ρ)), N = V4 답하는 레코드(1,905). 거부 레코드는 V4 거부 레코드의 부분집합으로, build10w 4단계 채우기 규칙을
  R로 다시 적용한다: S-1 먼저(R보다 많으면 가장 많은 질문부터 줄임), 다음 teacher 거부 trace를 질문별 합이 가장 적은 질문부터, 같은 합이면
  ``Random(f"20261016:refusal_tie:V4")``로 섞은 질문 순서(= build10w ``refusal_tie`` 순서), 질문 안은 V4에 든 순서. 이 규칙은 R = 79(V4 값)로 돌리면
  V4 거부 레코드 전체를 그대로 다시 만들어야 한다(검사; 아니면 멈춤). 채우기는 앞쪽부터이므로 R = 39 결과는 V4 채우기 순서의 앞쪽 R개다.
- A3: V4에서 (a) batch013 c1(corpus v6 ``provenance.group == "c1"``, 요금 지표 근접 대조) 질문의 모든 레코드(8b ``json_only``·근접 대조 teacher)와
  (b) 근접 대조 teacher 레코드 중 요금 지표 질문(``get_billing_metrics``로 실행되는 측정, pilot_010 ``select_teachc10.py`` 정의 = 측정 subtype ∈ BILLING; corpus ``execution``이 있으면 그 정답 호출과 일치 확인)의 것을 뺀다. 같은 질문의 RC7 레코드는 남긴다.
- 순서(결정 261 4절): 순서 seed마다 A0 레코드로 ``order7b.order_file``(O4')을 만들고(``orders/order_b2_o<seed>.json``, train_b7b 형식),
  그 순서로 놓은 A0 레코드 키(``질문 id|trace id``) 열을 기준으로 arm마다 레코드 순서 파일을 쓴다. A1 = A0와 같은 열, A2·A3 = A0 열에서 빠진 레코드만 지움
  (상대 순서 유지, 다시 섞지 않음). 지운 뒤 같은 질문 연속 길이 ≤ 4를 검사한다(넘으면 멈춤).
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
A11 = HERE.parent
INV = A11.parent
ROOT = INV.parent
sys.path.insert(0, str(INV / "pilot_007/train_data"))
import order7b  # noqa: E402

V4 = INV / "pilot_010/build/V4"
CORPUS = INV / "pilot_006_prep/approved/approved_train_v6.jsonl"
V4_QLIST_SHA = "d559b3e1acca8c8dbd3592d3e0c2302e1890b88801f5df5d160a35938ef54b98"
ORDER_SEEDS = (1102, 211102, 2026113)  # 결정 261 실행 기록: 제안값 3·20261102는 기존 seed와 겹쳐 바꿈
RHO_A2 = 0.02
REF_CAP, SEED = 4, 20261016  # build10w와 같은 값
MAX_RUN = order7b.MAX_RUN
BILLING = {"revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"}  # pilot_010/teacher/select_teachc10.py와 같음


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    return sha_bytes(Path(p).read_bytes())


def key(r):
    m = r["metadata"]
    return f"{m['source_record_id']}|{m['trace_id']}"


def qlist_sha(recs):
    return hashlib.sha256("\n".join(sorted({r["metadata"]["source_record_id"] for r in recs})).encode()).hexdigest()


def a2_refusal(recs, corpus, R):
    """build10w 4단계 채우기 규칙을 V4 거부 레코드 안에서 R로 다시 적용 → 남길 레코드 키 집합, 채운 순서."""
    kind = lambda c: corpus[c]["provenance"]["kind"]  # noqa: E731
    grp = lambda g: sorted(c for c in corpus if corpus[c]["corpus_group"] == g and kind(c) == "r1_refusal")  # noqa: E731
    r1q = grp("batch011") + grp("batch012")
    s1, teach = defaultdict(list), defaultdict(list)
    for r in recs:
        src = r["metadata"].get("refusal_source")
        if src == "S-1":
            s1[r["metadata"]["source_record_id"]].append(key(r))
        elif src == "teacher":
            teach[r["metadata"]["source_record_id"]].append(key(r))
    if not set(s1) | set(teach) <= set(r1q):
        raise SystemExit("refusal question outside r1q")
    refusal = {c: list(s1.get(c, [])) for c in r1q}
    seq = [k for c in r1q for k in refusal[c]]
    while sum(len(v) for v in refusal.values()) > R:  # build10w: S-1이 R보다 많으면 가장 많은 질문부터(같으면 id 큰 쪽) 뒤에서 줄임
        top = max(refusal, key=lambda c: (len(refusal[c]), c))
        refusal[top].pop()
    tie = list(r1q)
    random.Random(f"{SEED}:refusal_tie:V4").shuffle(tie)
    tie_rank = {c: i for i, c in enumerate(tie)}
    t_count = Counter()
    fill = []
    while sum(len(refusal[c]) for c in r1q) < R:
        open_q = [c for c in r1q if len(refusal[c]) < REF_CAP and t_count[c] < len(teach.get(c, []))]
        if not open_q:
            break
        c = min(open_q, key=lambda x: (len(refusal[x]), tie_rank[x]))
        k = teach[c][t_count[c]]
        refusal[c].append(k)
        fill.append(k)
        t_count[c] += 1
    kept = {k for c in r1q for k in refusal[c]}
    return kept, {"r1q": len(r1q), "s1_records": sum(len(v) for v in s1.values()), "teacher_fill_order": fill,
                  "refusal_tie_first10": tie[:10], "per_question": dict(sorted(Counter(len(refusal[c]) for c in r1q).items()))}


def write_arm(name, lines, recs, v4_manifest, note):
    d = HERE / name / "full"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sft_train.jsonl").write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    (d / "sft_valid.jsonl").write_text("", encoding="utf-8")
    man = json.loads(json.dumps(v4_manifest))
    s = man["sft"]
    q = sorted({r["metadata"]["source_record_id"] for r in recs})
    s.update(generated_at=datetime.now(timezone.utc).isoformat(), release_candidate=f"ablation_011 {name}", note=note, train_count=len(recs), validation_count=0,
             questions=len(q), question_list_sha256=hashlib.sha256("\n".join(q).encode()).hexdigest(),
             by_source=dict(Counter(r["metadata"]["loss_scope"] for r in recs)),
             output_hashes={"sft_train.jsonl": sha_file(d / "sft_train.jsonl"), "sft_valid.jsonl": sha_file(d / "sft_valid.jsonl")})
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return s["output_hashes"]["sft_train.jsonl"], s["question_list_sha256"]


def main():
    v4_path = V4 / "full/sft_train.jsonl"
    v4_manifest = json.loads((V4 / "full/manifest.json").read_text(encoding="utf-8"))
    lines = v4_path.read_text(encoding="utf-8").splitlines()
    recs = [json.loads(l) for l in lines]
    checks = {"v4_file_sha256": sha_file(v4_path), "v4_file_sha256_matches_manifest": sha_file(v4_path) == v4_manifest["sft"]["output_hashes"]["sft_train.jsonl"],
              "v4_question_list_sha256": qlist_sha(recs), "v4_question_list_sha256_ok": qlist_sha(recs) == V4_QLIST_SHA,
              "v4_lines_roundtrip": all(json.dumps(r, ensure_ascii=False) == l for r, l in zip(recs, lines)),
              "record_keys_unique": len({key(r) for r in recs}) == len(recs)}
    if not all(v for k, v in checks.items() if k.endswith(("_ok", "_matches_manifest", "_roundtrip", "_unique"))):
        raise SystemExit(f"V4 input check failed: {checks}")
    corpus = {r["id"]: r for r in (json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines() if l.strip())}
    summary = {"label": "ablation_011 build11", "built": datetime.now(timezone.utc).isoformat(), "input": {"v4_train": str(v4_path.relative_to(ROOT)),
               "v4_manifest_sha256": sha_file(V4 / "full/manifest.json"), "corpus_v6_sha256": sha_file(CORPUS), "v4_build_summary_sha256": sha_file(V4 / "build_summary.json")},
               "checks": checks, "order_seeds": list(ORDER_SEEDS), "arms": {}}
    n_ans = sum(1 for r in recs if not r["metadata"].get("refusal_source"))
    n_ref = len(recs) - n_ans
    keep = {"A0": [True] * len(recs)}
    # A1
    a1_lines, n_override = [], 0
    for r, l in zip(recs, lines):
        if r["metadata"].get("contrast_source") == "teacher":
            if r["metadata"]["loss_scope"] != "full_response" or r["metadata"]["source"] != "teacher":
                raise SystemExit(f"contrast teacher record not full_response/teacher: {key(r)}")
            r2 = json.loads(l)
            r2["metadata"]["a11_loss_scope_override"] = "json_only"
            a1_lines.append(json.dumps(r2, ensure_ascii=False))
            n_override += 1
        else:
            a1_lines.append(l)
    # A2
    R2 = round(RHO_A2 * n_ans / (1 - RHO_A2))
    kept_v4, info_v4 = a2_refusal(recs, corpus, n_ref)
    v4_ref_keys = {key(r) for r in recs if r["metadata"].get("refusal_source")}
    if kept_v4 != v4_ref_keys:
        raise SystemExit("build10w refusal rule with R=79 does not reproduce V4 refusal records")
    kept_a2, info_a2 = a2_refusal(recs, corpus, R2)
    if not kept_a2 <= v4_ref_keys or len(kept_a2) != R2:
        raise SystemExit(f"A2 refusal subset check failed ({len(kept_a2)} vs R {R2})")
    if info_a2["teacher_fill_order"] != info_v4["teacher_fill_order"][:len(info_a2["teacher_fill_order"])]:
        raise SystemExit("A2 teacher fill order is not a prefix of V4 fill order")
    keep["A2"] = [not r["metadata"].get("refusal_source") or key(r) in kept_a2 for r in recs]
    # A3
    c1 = {c for c, x in corpus.items() if x["corpus_group"] == "batch013" and x["provenance"].get("group") == "c1"}
    # 요금 지표 문항 = pilot_010 ``select_teachc10.py`` 정의(측정 subtype ∈ BILLING; get_billing_metrics로 실행되는 측정). corpus ``execution``이 있는 문항은
    # 정답 호출의 get_billing_metrics 여부와 같아야 한다(다르면 멈춤). ``execution``이 None인 문항(pilot_006 ann 등)도 이 정의로 잡힌다.
    billing = {c for c, x in corpus.items() if ((x.get("view") or {}).get("measure") or {}).get("subtype") in BILLING}
    by_exec = {c for c, x in corpus.items() if any(e.get("tool") == "get_billing_metrics" for e in (x.get("execution") or []))}
    disagree = sorted(c for c, x in corpus.items() if x.get("execution") and (c in billing) != (c in by_exec))
    if disagree:
        raise SystemExit(f"billing definition disagrees with execution for {disagree[:10]}")
    summary["billing_definition"] = {"rule": "view.measure.subtype ∈ " + str(sorted(BILLING)), "corpus_billing_questions": len(billing),
                                     "with_execution_checked": sum(1 for c in billing if corpus[c].get("execution")), "disagree": 0}
    reason = {}
    for r in recs:
        m = r["metadata"]
        q = m["source_record_id"]
        if q in c1:
            reason[key(r)] = "batch013_c1:" + ("contrast_teacher" if m.get("contrast_source") == "teacher" else m["loss_scope"])
        elif m.get("contrast_source") == "teacher" and q in billing:
            reason[key(r)] = f"contrast_teacher_billing:{m.get('contrast_set')}"
    keep["A3"] = [key(r) not in reason for r in recs]
    removed = {"A2": {"rule": f"거부 레코드 V4 {n_ref} → R = round({RHO_A2}·{n_ans}/(1−{RHO_A2})) = {R2}; build10w 채우기 규칙(S-1 먼저, teacher는 (질문별 합, refusal_tie 순위))",
                      "removed": [{"key": key(r), "refusal_source": r["metadata"]["refusal_source"]} for r, k in zip(recs, keep["A2"]) if not k], "fill": info_a2},
               "A3": {"rule": "batch013 c1 질문의 모든 레코드 + 근접 대조 teacher 레코드 중 정답 호출에 get_billing_metrics가 있는 질문",
                      "c1_questions_in_corpus": len(c1), "removed": [{"key": k, "reason": v} for k, v in reason.items()]}}
    for arm in ("A2", "A3"):
        (HERE / f"removed_{arm}.json").write_text(json.dumps(removed[arm], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    hashes = {"A0": (sha_file(v4_path), qlist_sha(recs))}
    hashes["A1"] = write_arm("A1", a1_lines, recs, v4_manifest,
                             f"ablation_011 A1 = V4 + 근접 대조 teacher {n_override}레코드에 a11_loss_scope_override=json_only(입력 같음, 마스크만 다름); build11.py")
    for arm, note in (("A2", f"ablation_011 A2 = V4에서 거부 레코드 {n_ref} → {R2}(ρ 0.02, build10w 채우기 규칙); build11.py"),
                      ("A3", "ablation_011 A3 = V4에서 batch013 c1 레코드 + 요금 지표 근접 대조 teacher 레코드를 뺌; build11.py")):
        sel = [i for i, k in enumerate(keep[arm]) if k]
        hashes[arm] = write_arm(arm, [lines[i] for i in sel], [recs[i] for i in sel], v4_manifest, note)
    # 순서
    od = HERE / "orders"
    od.mkdir(exist_ok=True)
    orders = {}
    for s in ORDER_SEEDS:
        o = order7b.order_file({"full": recs}, s)
        (od / f"order_b2_o{s}.json").write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        a0_seq = [key(r) for r in order7b.order_records(recs, o["order"])]
        orders[s] = {"order_b2_sha256": o["order_sha256"], "a0_run_stats": o["arms"]["full"]["run_stats"], "arms": {}}
        for arm in ("A0", "A1", "A2", "A3"):
            ks = {key(r) for r, k in zip(recs, keep.get(arm, keep["A0"])) if k}
            seq = [k for k in a0_seq if k in ks]
            if len(seq) != len(ks):
                raise SystemExit(f"order {arm} {s}: missing records")
            rs = order7b.run_stats([k.split("|", 1)[0] for k in seq])
            body = {"arm": arm, "seed": s, "rule": "A0 O4' 순서(order_b2_o<seed>.json, order7b.order_records)에서 이 arm에 없는 레코드만 지움(상대 순서 유지)",
                    "a0_order_file": f"order_b2_o{s}.json", "a0_order_sha256": o["order_sha256"], "a0_record_sequence_sha256": order7b.sha(a0_seq),
                    "records": len(seq), "record_sequence_sha256": order7b.sha(seq), "run_stats": rs, "max_run_limit": MAX_RUN,
                    "max_run_ok": rs["max_run"] <= MAX_RUN, "a0_record_sequence": a0_seq, "record_sequence": seq}
            (od / f"record_order_{arm}_o{s}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            orders[s]["arms"][arm] = {"records": len(seq), "record_sequence_sha256": body["record_sequence_sha256"], "run_stats": rs, "max_run_ok": body["max_run_ok"]}
            if not body["max_run_ok"]:
                raise SystemExit(f"STOP: {arm} o{s} max run {rs['max_run']} > {MAX_RUN}")
    for arm in ("A0", "A1", "A2", "A3"):
        sel = [r for r, k in zip(recs, keep.get(arm, keep["A0"])) if k]
        summary["arms"][arm] = {
            "train_file": str(v4_path.relative_to(ROOT)) if arm == "A0" else f"sft_dpo_inventory/ablation_011/build/{arm}/full/sft_train.jsonl",
            "train_sha256": hashes[arm][0], "question_list_sha256": hashes[arm][1], "records": len(sel), "steps": len(sel),
            "questions": len({r["metadata"]["source_record_id"] for r in sel}),
            "refusal_records": sum(1 for r in sel if r["metadata"].get("refusal_source")),
            "refusal_by_source": dict(Counter(r["metadata"]["refusal_source"] for r in sel if r["metadata"].get("refusal_source"))),
            "refusal_share": round(sum(1 for r in sel if r["metadata"].get("refusal_source")) / len(sel), 4),
            "contrast_teacher_records": sum(1 for r in sel if r["metadata"].get("contrast_source") == "teacher"),
            "batch013_self_records": sum(1 for r in sel if r["metadata"]["corpus_group"] == "batch013" and not r["metadata"].get("contrast_source")),
            "json_only_override_records": n_override if arm == "A1" else 0,
            "removed_from_v4": len(recs) - len(sel)}
    summary["arms"]["A2"]["R"] = R2
    summary["arms"]["A3"]["removed_by_reason"] = dict(Counter(v.split(":")[0] + ":" + v.split(":")[1] for v in reason.values()))
    summary["arms"]["A3"]["removed_questions_entirely"] = len({r["metadata"]["source_record_id"] for r in recs}) - summary["arms"]["A3"]["questions"]
    summary["orders"] = orders
    (HERE / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "arms": summary["arms"], "orders": {s: {a: (v["records"], v["run_stats"]["max_run"]) for a, v in o["arms"].items()} for s, o in orders.items()}},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
