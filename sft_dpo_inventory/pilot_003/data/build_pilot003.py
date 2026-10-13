# -*- coding: utf-8 -*-
"""pilot_003 thinking 학습 데이터(``thinking_pilot003_t2pc``)를 만든다(pilot_003 작업 지시 4). 모델·GPU를 쓰지 않는다(tokenizer만 CPU).

    HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/pilot_003/data/build_pilot003.py

``pilot_002/data/build_pilot002.py``를 그대로 이어받는다. pilot_002의 원천·필터·순서는 같고(같은 함수, 같은 seed), batch006 HF trace와
batch006 teacher를 더한다. 질문 id 정렬에서 b006은 b005 뒤라 pilot_002 질문의 상한 seed 순번은 바뀌지 않는다.

원천(고치지 않는다):
- gold: ``reviewed_gold_v006_t2pc``(135문항 = v005 111 + batch006 24, 전부 train).
- HF trace
  - v004 결합분: ``pilot_prep_003/combined_traces.jsonl``와 pilot_001 후보 ``pilot_001/data/candidates_v004_r1.json``
    (결정 4·6·7·18·27과 계약 필터를 이미 적용한 후보. pilot_001 데이터 r1과 같다).
  - batch005: ``thinking_traces/batch005/traces.jsonl``와 ``pilot_prep_005/traces/batch005_filtered.json``의 남은 후보
    (결정 4·40-D·18·계약·6 적용).
  - batch006(결정 80): ``thinking_traces/batch006/traces.jsonl``와 ``pilot_003/traces/batch006_filtered.json``의 남은 후보(같은 필터).
- teacher(source=teacher, SFT만)
  - 기존 17질문 68개: ``pilot_prep_005/teacher/selected_teacher.json``(결정 48·49, 우연히 정답 0이라 모두 쓴다).
  - batch005 27질문: ``teacher_qwen3.8_27b/batch005_no_correct/traces.jsonl``(결정 50). 기존 teacher와 같은 필터
    (``pilot_prep_004/teacher_scale/count_teacher.py``: 정답 원응답, 같은 응답 하나로, tokenize 왕복·렌더 경계, 계약, 길이, 루프)를
    적용한 뒤 질문당 4개를 ``select_teacher.py``와 같은 방법(질문 id 정렬 순번 i, ``random.Random(20261008 + i).sample``)으로 고른다.
  - batch006 정답 표본 없는 질문(결정 81): ``teacher_qwen3.8_27b/batch006_no_correct/traces.jsonl``. batch005 teacher와 같은 필터·선택
    (순번 i는 batch006 대상 질문의 id 정렬 순번).

모든 후보에 다시 적용하는 검사(같은 함수, 같은 순서):
1. 결정 40-D 루프(``pilot_prep_004/loop_filter``의 ``is_loop``): SFT target, chosen, rejected 어느 자리든.
2. 계약 필터: SFT target·DPO chosen의 응답 JSON이 ``target_ok``를 통과. DPO rejected는 응답 JSON 파싱 가능(``rejected_parse == ok``).
3. 결정 18 길이: 학습 config(pilot_001과 같은 한도, 결정 53)의 렌더링 검사(``trainer_common.render_records``)를 레코드마다 돌려
   한도를 넘거나 token 경계가 바뀌는 레코드를 자르지 않고 뺀다. SFT ``max_seq_length`` 11,392(``json_only``), DPO ``max_length``
   11,392·``max_prompt_length`` 7,424·``max_completion_length`` 4,096(``full_response``). pilot_prep_002 추정 안전 한도
   (SFT 12,887, DPO 13,833)보다 작다.
4. 결정 51: 검토 queue의 HF 첫 응답 쌍은 thinking DPO에 쓰지 않는다(chosen에 추론이 없다. pilot_001과 같음). 그 14개 쌍의
   rejected와 같은 응답(raw_sha256)을 rejected로 쓰는 trace 쌍이 남아 있지 않은지 확인한다(결정 6이 이미 뺀다).
   batch006도 같다: 결정 80에서 뺀 검토 쌍(b006-14·17·18·19·22·23·24·26-hf, 01-hf는 gold 제외)의 응답을 rejected로 쓰는 trace 쌍을 뺀다.
5. 결정 52 DPO 상한: 질문당 최대 8쌍(v004·batch005 모두). 질문 id 정렬 순번 i, ``random.Random(20261008 + i)``.
   rejected의 오류 유형(``rejected_grounding_diffs``의 필드 이름 집합)으로 묶고, 묶음을 돌아가며 하나씩 고른다. 묶음 안에서는
   아직 쓰지 않은 rejected, 그다음 아직 쓰지 않은 chosen을 먼저 고른다.
6. 교차 DPO(teacher chosen × HF rejected)는 만들지 않는다(결정 48·50).

출력:
- ``training/generated/pilot_003/combined_traces.jsonl``(trace 원본 모음, ignore 경로, 커밋하지 않음).
- ``training/generated/thinking_pilot003_t2pc``(학습 데이터, 결정 33에 따라 커밋).
- ``data/``: ``candidates_pilot003.json``(후보 id와 판정, 원문 없음), ``teacher_batch005.json``, ``teacher_batch006.json``, ``summary.json``.
  ``summary.json``에는 실차 통행량 대조 유형(결정 66)의 레코드 수를 ``passage_status_contrast``로 더한다.
"""
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_003/data"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/loop_filter"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/type_target"))

from build_v004_thinking import tokenizer  # noqa: E402  (sys.path에 provider_eval 등을 더한다)
from apply_filter import is_loop, loop_metrics, split_think  # noqa: E402

GEN = ROOT / "training/generated"
P5 = ROOT / "sft_dpo_inventory/pilot_prep_005"
CORPUS = GEN / "reviewed_gold_v006_t2pc"
P3 = ROOT / "sft_dpo_inventory/pilot_003"
V004_TRACES = GEN / "pilot_prep_003/combined_traces.jsonl"
V004_CANDIDATES = ROOT / "sft_dpo_inventory/pilot_001/data/candidates_v004_r1.json"
B5_TRACES = GEN / "thinking_traces/batch005/traces.jsonl"
B5_CANDIDATES = P5 / "traces/batch005/candidates.json"
B5_FILTERED = P5 / "traces/batch005_filtered.json"
T17_SELECTED = P5 / "teacher/selected_teacher.json"
TB5_TRACES = GEN / "thinking_traces/teacher_qwen3.8_27b/batch005_no_correct/traces.jsonl"
TB5_SUMMARY = P5 / "teacher/batch005_no_correct/summary.json"
HF_OUTPUTS = ROOT / "sft_dpo_inventory/batch005/hf_outputs.json"
B6_TRACES = GEN / "thinking_traces/batch006/traces.jsonl"
B6_CANDIDATES = P3 / "traces/batch006/candidates.json"
B6_FILTERED = P3 / "traces/batch006_filtered.json"
TB6_TRACES = GEN / "thinking_traces/teacher_qwen3.8_27b/batch006_no_correct/traces.jsonl"
TB6_SUMMARY = P3 / "teacher/batch006_no_correct/summary.json"
TB6_TARGETS = P3 / "teacher/batch006_no_correct_targets.json"
B6_HF_OUTPUTS = ROOT / "sft_dpo_inventory/batch006/hf_outputs.json"
B6_CHECKED = ROOT / "sft_dpo_inventory/batch006/candidates_checked.json"
B6_REVIEW_EXCLUDED = [f"b006-{n:02d}" for n in (1, 14, 17, 18, 19, 22, 23, 24, 26)]
CONFIG = {"sft": ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot003_sft.yaml",
          "dpo": ROOT / "training/configs/qwen3_8b_t2pc_thinking_pilot003_dpo.yaml"}
COMBINED = GEN / "pilot_003/combined_traces.jsonl"
OUT = GEN / "thinking_pilot003_t2pc"
SEED = 20261008
TEACHER_CAP = 4
DPO_CAP = 8
DECISION51 = ["b005-11", "b005-12", "b005-20", "b005-22", "b005-23", "b005-25", "b005-27", "b005-28", "b005-30",
              "b005-46", "b005-48", "b005-49", "b005-50", "b005-57"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def origin(sid):
    return "batch006" if sid.startswith("b006-") else "batch005" if sid.startswith("b005-") else "v004(batch004)" if sid.startswith("b004-") else "v003"


def diff_kinds(cand):
    return tuple(sorted({d[0] for d in cand.get("rejected_grounding_diffs") or []})) or ("(none)",)


def cap_pairs(pairs, rng):
    """결정 52: 오류 유형 묶음을 돌아가며 최대 DPO_CAP개."""
    if len(pairs) <= DPO_CAP:
        return list(pairs)
    groups = defaultdict(list)
    for p in sorted(pairs, key=lambda p: (p["chosen"], p["rejected"])):
        groups[diff_kinds(p)].append(p)
    for g in groups.values():
        rng.shuffle(g)
    order = sorted(groups)
    rng.shuffle(order)
    picked, used_r, used_c = [], set(), set()
    while len(picked) < DPO_CAP and any(groups.values()):
        for kind in order:
            g = groups[kind]
            if not g or len(picked) >= DPO_CAP:
                continue
            p = (next((p for p in g if p["rejected"] not in used_r), None)
                 or next((p for p in g if p["chosen"] not in used_c), None) or g[0])
            g.remove(p)
            picked.append(p)
            used_r.add(p["rejected"])
            used_c.add(p["chosen"])
    return picked


def main():
    from training.data import build_thinking, thinking
    from training.data.validation import assess, target_ok
    from training.trainer_common import load_config, render_records
    from type_target import profile, tv
    if OUT.exists() or COMBINED.exists():
        raise SystemExit("output already exists")
    tok = tokenizer()
    configs = {s: load_config(p, s) for s, p in CONFIG.items()}
    gold = {r["metadata"]["source_record_id"]: r for r in read(CORPUS / "sft_train.jsonl")}

    # 원천 무결성
    b5_summary = json.loads((P5 / "traces/batch005/summary.json").read_text(encoding="utf-8"))["summary"]
    if sha256(B5_TRACES) != b5_summary["traces_sha256"]:
        raise SystemExit("batch005 trace hash differs")
    if sha256(TB5_TRACES) != json.loads(TB5_SUMMARY.read_text(encoding="utf-8"))["traces_sha256"]:
        raise SystemExit("batch005 teacher trace hash differs")
    b6_summary = json.loads((P3 / "traces/batch006/summary.json").read_text(encoding="utf-8"))["summary"]
    if sha256(B6_TRACES) != b6_summary["traces_sha256"]:
        raise SystemExit("batch006 trace hash differs")
    tb6_targets = [t["source_record_id"] for t in json.loads(TB6_TARGETS.read_text(encoding="utf-8"))]
    if tb6_targets and sha256(TB6_TRACES) != json.loads(TB6_SUMMARY.read_text(encoding="utf-8"))["traces_sha256"]:
        raise SystemExit("batch006 teacher trace hash differs")
    t17 = json.loads(T17_SELECTED.read_text(encoding="utf-8"))
    for path, digest in t17["inputs"].items():
        if sha256(ROOT / path) != digest:
            raise SystemExit(f"teacher input changed: {path}")

    # trace 모음(정규화)
    traces, trace_file = {}, {}
    files = [V004_TRACES, B5_TRACES, *[ROOT / p for p in t17["inputs"]], TB5_TRACES, B6_TRACES] + ([TB6_TRACES] if tb6_targets else [])
    for path in files:
        for row in read(path):
            if row["trace_id"] in traces:
                raise SystemExit(f"duplicate trace id {row['trace_id']}")
            traces[row["trace_id"]] = thinking.normalize_trace(row)
            trace_file[row["trace_id"]] = str(path.relative_to(ROOT))

    loops = {}

    def loop_of(tid):
        if tid not in loops:
            t = traces[tid]
            m = loop_metrics(t.get("thinking") or split_think(t["raw_text"])[0])
            loops[tid] = (is_loop(m) if m else ["empty_thinking"]) or []
        return loops[tid]

    contract = {}

    def contract_ok(tid):
        if tid not in contract:
            t = traces[tid]
            rec = gold[t["source_record_id"]]
            try:
                contract[tid] = bool(target_ok(assess(thinking.response_json(t["raw_text"]), rec["messages"][1]["content"]),
                                               rec["metadata"]))
            except Exception:  # noqa: BLE001
                contract[tid] = False
        return contract[tid]

    def sft_length_ok(tid):
        rec = thinking.sft_record(traces[tid], gold[traces[tid]["source_record_id"]], source="length-check")
        try:
            render_records(tok, [rec], configs["sft"], "sft")
            return True, None
        except ValueError as error:
            return False, str(error)[:80]

    def dpo_length_ok(ch, rj):
        sid = traces[ch]["source_record_id"]
        pair = thinking.dpo_pair(traces[ch], traces[rj], gold[sid], source="length-check", negative_category="semantic",
                                 details={})
        try:
            render_records(tok, [pair], configs["dpo"], "dpo")
            return True, None
        except ValueError as error:
            return False, str(error)[:80]

    # ---- 1. teacher batch005(결정 50)·batch006(결정 81): 기존 teacher와 같은 필터 → 질문당 4개
    def teacher_pool(path, targets, decision):
        rows_, steps = [], Counter()
        seen = defaultdict(set)
        for raw in read(path):
            t = traces[raw["trace_id"]]
            sid = t["source_record_id"]
            if not t["verdict"]["raw_match"]:
                steps["wrong"] += 1
                continue
            if t["raw_sha256"] in seen[sid]:
                steps["duplicate_response"] += 1
                continue
            seen[sid].add(t["raw_sha256"])
            ids = tok(t["raw_text"] + tok.eos_token, add_special_tokens=False)["input_ids"]
            roundtrip = tok.decode(ids) == t["raw_text"] + tok.eos_token and \
                tok(tok.decode(ids), add_special_tokens=False)["input_ids"] == ids
            ok_len, why_len = sft_length_ok(t["trace_id"])
            reason = ("tokenize_roundtrip" if not roundtrip else
                      "contract" if not contract_ok(t["trace_id"]) else
                      "length_or_render_boundary" if not ok_len else
                      "loop" if loop_of(t["trace_id"]) else None)
            steps[f"sft:{reason or 'kept'}"] += 1
            rows_.append({"trace_id": t["trace_id"], "source_record_id": sid, "response_tokens": len(ids),
                          "excluded": reason, "length_detail": why_len})
        kept = defaultdict(list)
        for r in rows_:
            if r["excluded"] is None:
                kept[r["source_record_id"]].append(r["trace_id"])
        selected = {}
        for index, sid in enumerate(sorted(kept)):
            ids = sorted(kept[sid])
            selected[sid] = sorted(random.Random(SEED + index).sample(ids, min(TEACHER_CAP, len(ids))))
        info = {"decision": decision, "seed": SEED, "cap_per_question": TEACHER_CAP, "traces": str(path.relative_to(ROOT)),
                "traces_sha256": sha256(path) if path.exists() else None, "target_questions": len(targets), "steps": dict(steps),
                "kept": sum(len(v) for v in kept.values()), "kept_questions": len(kept),
                "selected": sum(len(v) for v in selected.values()), "selected_questions": len(selected),
                "questions_without_kept_trace": sorted(set(targets) - set(kept)),
                "per_question": {sid: {"kept": len(kept.get(sid, [])), "selected": len(selected.get(sid, []))}
                                 for sid in sorted(targets)},
                "selected_trace_ids": selected, "cross_model_dpo_pairs": "not built (decisions 48, 50, 81)",
                "rows": rows_}
        return selected, info

    targets = [t["source_record_id"] for t in json.loads((P5 / "teacher/batch005_no_correct_targets.json").read_text(encoding="utf-8"))]
    tb5_selected, teacher_b5 = teacher_pool(TB5_TRACES, targets, "50")
    (HERE / "teacher_batch005.json").write_text(json.dumps(teacher_b5, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if tb6_targets:
        tb6_selected, teacher_b6 = teacher_pool(TB6_TRACES, tb6_targets, "81")
    else:
        tb6_selected, teacher_b6 = {}, {"decision": "81", "target_questions": 0, "steps": {}, "kept": 0, "kept_questions": 0,
                                         "selected": 0, "selected_questions": 0, "questions_without_kept_trace": []}
    (HERE / "teacher_batch006.json").write_text(json.dumps(teacher_b6, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- 2. SFT 후보
    v004 = json.loads(V004_CANDIDATES.read_text(encoding="utf-8"))
    b5c = json.loads(B5_CANDIDATES.read_text(encoding="utf-8"))
    b5f = json.loads(B5_FILTERED.read_text(encoding="utf-8"))
    b5_sft_ids = set(b5f["sft_kept_trace_ids"])
    b5_pairs = {(p["chosen"], p["rejected"]) for p in b5f["dpo_kept_pairs"]}
    b6c = json.loads(B6_CANDIDATES.read_text(encoding="utf-8"))
    b6f = json.loads(B6_FILTERED.read_text(encoding="utf-8"))
    b6_sft_ids = set(b6f["sft_kept_trace_ids"])
    b6_pairs = {(p["chosen"], p["rejected"]) for p in b6f["dpo_kept_pairs"]}
    sft_in = ([{**c, "pool": "hf_v004"} for c in v004["sft"]]
              + [{**c, "pool": "hf_batch005"} for c in b5c["sft"] if c["trace_id"] in b5_sft_ids]
              + [{"trace_id": t, "source_record_id": sid, "pool": "teacher17"}
                 for sid, ids in t17["selected_trace_ids"].items() for t in ids]
              + [{"trace_id": t, "source_record_id": sid, "pool": "teacher_batch005"}
                 for sid, ids in tb5_selected.items() for t in ids]
              + [{**c, "pool": "hf_batch006"} for c in b6c["sft"] if c["trace_id"] in b6_sft_ids]
              + [{"trace_id": t, "source_record_id": sid, "pool": "teacher_batch006"}
                 for sid, ids in tb6_selected.items() for t in ids])
    if len([c for c in sft_in if c["pool"] == "hf_batch006"]) != len(b6_sft_ids):
        raise SystemExit("batch006 kept SFT ids not all found in candidates.json")
    if len([c for c in sft_in if c["pool"] == "hf_batch005"]) != len(b5_sft_ids):
        raise SystemExit("batch005 kept SFT ids not all found in candidates.json")
    sft_steps, sft_keep, sft_rows = Counter(), [], []
    for c in sft_in:
        tid = c["trace_id"]
        ok_len, why = sft_length_ok(tid)
        reason = ("decision40D_loop" if loop_of(tid) else
                  "contract_target_ok_failed" if not contract_ok(tid) else
                  "decision18_length(config)" if not ok_len else None)
        sft_steps[f"{c['pool']}:{reason or 'kept'}"] += 1
        sft_rows.append({"trace_id": tid, "source_record_id": c["source_record_id"], "pool": c["pool"], "excluded": reason,
                         "length_detail": why})
        if reason is None:
            sft_keep.append({k: v for k, v in c.items() if k != "pool"} | {"pool": c["pool"]})

    # ---- 3. DPO 후보(HF trace 쌍만) → 필터 → 질문당 8쌍
    dpo_in = ([{**c, "pool": "hf_v004"} for c in v004["dpo"]]
              + [{**c, "pool": "hf_batch005"} for c in b5c["dpo"] if (c["chosen"], c["rejected"]) in b5_pairs]
              + [{**c, "pool": "hf_batch006"} for c in b6c["dpo"] if (c["chosen"], c["rejected"]) in b6_pairs])
    if len([c for c in dpo_in if c["pool"] == "hf_batch006"]) != len(b6_pairs):
        raise SystemExit("batch006 kept DPO pairs not all found in candidates.json")
    if len([c for c in dpo_in if c["pool"] == "hf_batch005"]) != len(b5_pairs):
        raise SystemExit("batch005 kept DPO pairs not all found in candidates.json")
    hf = {o["id"]: o for o in json.loads(HF_OUTPUTS.read_text(encoding="utf-8"))["rows"]}
    decision51_raw = {hf[sid]["raw_sha256"]: sid for sid in DECISION51}
    hf6 = {o["id"]: o for o in json.loads(B6_HF_OUTPUTS.read_text(encoding="utf-8"))["rows"]}
    decision51_raw.update({hf6[sid]["raw_sha256"]: sid for sid in B6_REVIEW_EXCLUDED})
    dpo_steps, dpo_ok, dpo_rows = Counter(), [], []
    for c in dpo_in:
        ch, rj = c["chosen"], c["rejected"]
        ok_len, why = (True, None)
        reason = ("decision40D_loop" if loop_of(ch) or loop_of(rj) else
                  "chosen_contract_failed" if not contract_ok(ch) else
                  f"rejected_{c['rejected_parse']}" if c["rejected_parse"] != "ok" else
                  "decision51_reviewed_pair_response" if traces[rj]["raw_sha256"] in decision51_raw else None)
        if reason is None:
            ok_len, why = dpo_length_ok(ch, rj)
            if not ok_len:
                reason = "decision18_length(config)"
        dpo_steps[f"{c['pool']}:{reason or 'kept'}"] += 1
        dpo_rows.append({"chosen": ch, "rejected": rj, "source_record_id": c["source_record_id"], "pool": c["pool"],
                         "excluded": reason, "length_detail": why})
        if reason is None:
            dpo_ok.append(c)
    by_q = defaultdict(list)
    for c in dpo_ok:
        by_q[c["source_record_id"]].append(c)
    dpo_keep, cap_info = [], {}
    for index, sid in enumerate(sorted(by_q)):
        picked = cap_pairs(by_q[sid], random.Random(SEED + index))
        dpo_keep += picked
        cap_info[sid] = {"before": len(by_q[sid]), "after": len(picked),
                         "kinds_before": len({diff_kinds(p) for p in by_q[sid]}),
                         "kinds_after": len({diff_kinds(p) for p in picked}),
                         "rejected_after": len({p["rejected"] for p in picked}),
                         "chosen_after": len({p["chosen"] for p in picked})}
    kept_pairs = {(p["chosen"], p["rejected"]) for p in dpo_keep}
    for row in dpo_rows:
        if row["excluded"] is None and (row["chosen"], row["rejected"]) not in kept_pairs:
            row["excluded"] = "decision52_cap8"
            dpo_steps[f"{row['pool']}:decision52_cap8"] += 1
            dpo_steps[f"{row['pool']}:kept"] -= 1

    # ---- 4. build
    COMBINED.parent.mkdir(parents=True, exist_ok=True)
    with open(COMBINED, "w", encoding="utf-8") as stream:
        for path in files:
            stream.write(path.read_text(encoding="utf-8"))
    candidates = {"sft": [{k: c[k] for k in ("trace_id", "source_record_id") if k in c} | {"v003_flags": c.get("v003_flags", []),
                                                                                         "pool": c["pool"]} for c in sft_keep],
                  "dpo": [{k: c[k] for k in ("chosen", "rejected", "source_record_id", "rejected_error_tags",
                                             "rejected_grounding_diffs", "rejected_parse",
                                             "rejected_correct_after_condition_layer")}
                          | {"v003_flags": c.get("v003_flags", {}), "pool": c["pool"],
                             "operational_rejudgment": c.get("operational_rejudgment")} for c in dpo_keep]}
    cand_path = HERE / "candidates_pilot003.json"
    cand_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    built = build_thinking.build(COMBINED.relative_to(ROOT), cand_path.relative_to(ROOT), CORPUS.relative_to(ROOT), "train",
                                 OUT)
    sft_rows_out = read(OUT / "sft_train.jsonl")
    dpo_rows_out = read(OUT / "dpo_train.jsonl")
    if len(sft_rows_out) != len(sft_keep) or len(dpo_rows_out) != len(dpo_keep):
        raise SystemExit(f"builder dropped records: {built}")

    # ---- 5. 기록
    pool_of = {c["trace_id"]: c["pool"] for c in sft_keep}
    stop = {sid for sid, r in gold.items() if r["metadata"].get("target_kind") == "t2pc_stop_grounding"}
    prof = {sid: profile(json.loads(r["messages"][-1]["content"]), sid not in stop) for sid, r in gold.items()}
    dev = json.loads((ROOT / "sft_dpo_inventory/pilot_prep_004/type_target/type_target.json").read_text(encoding="utf-8"))[
        "dev_distribution"]["share"]

    def share(counter, n):
        return {k: round(v / n, 4) for k, v in sorted(counter.items())}

    sft_sids = [r["metadata"]["source_record_id"] for r in sft_rows_out]
    variant = {c["id"]: c["variant"] for c in json.loads(B6_CHECKED.read_text(encoding="utf-8"))["candidates"]}
    dpo_sids = [r["metadata"]["source_record_id"] for r in dpo_rows_out]
    q_cells = Counter(prof[s]["cell"] for s in set(sft_sids))
    r_cells = Counter(prof[s]["cell"] for s in sft_sids)
    d_cells = Counter(prof[s]["cell"] for s in dpo_sids)
    lengths_sft = sorted(len(tok(r["messages"][-1]["content"] + tok.eos_token, add_special_tokens=False)["input_ids"])
                         for r in sft_rows_out)
    lengths_dpo = sorted(max(len(tok(r[k][0]["content"] + tok.eos_token, add_special_tokens=False)["input_ids"])
                             for k in ("chosen", "rejected")) for r in dpo_rows_out)

    def dist(v):
        return {"min": v[0], "p50": v[len(v) // 2], "p90": v[int(0.9 * (len(v) - 1))], "max": v[-1]}

    summary = {
        "inputs": {"corpus": str(CORPUS.relative_to(ROOT)), "corpus_sft_sha256": sha256(CORPUS / "sft_train.jsonl"),
                   **{str(p.relative_to(ROOT)): sha256(p) for p in (V004_CANDIDATES, B5_CANDIDATES, B5_FILTERED, T17_SELECTED,
                                                                     B6_CANDIDATES, B6_FILTERED, TB6_TARGETS)},
                   "trace_files": {str(p.relative_to(ROOT)): sha256(p) for p in files}},
        "configs": {s: {"path": str(p.relative_to(ROOT)), "sha256": sha256(p)} for s, p in CONFIG.items()},
        "length_limits(config)": {"sft_max_seq_length": configs["sft"]["training"]["max_seq_length"],
                                  "dpo_max_length": configs["dpo"]["training"]["max_length"],
                                  "dpo_max_prompt_length": configs["dpo"]["training"]["max_prompt_length"],
                                  "dpo_max_completion_length": configs["dpo"]["training"]["max_completion_length"]},
        "teacher_batch005": {k: teacher_b5[k] for k in ("steps", "kept", "kept_questions", "selected", "selected_questions",
                                                        "questions_without_kept_trace")},
        "teacher_batch006": {k: teacher_b6[k] for k in ("target_questions", "steps", "kept", "kept_questions", "selected",
                                                        "selected_questions", "questions_without_kept_trace")},
        "sft_steps": dict(sorted(sft_steps.items())),
        "dpo_steps": dict(sorted(sft for sft in dpo_steps.items() if sft[1])),
        "loop_flagged_traces": {t: r for t, r in loops.items() if r},
        "decision51": {"reviewed_pairs_excluded": [s + "-hf" for s in DECISION51],
                       "note": "검토 queue의 HF 첫 응답 쌍은 thinking DPO에 쓰지 않는다(chosen에 추론 없음, pilot_001과 같음). "
                               "같은 응답을 rejected로 쓰는 trace 쌍 수는 dpo_steps의 decision51_reviewed_pair_response"},
        "decision52_cap": {"questions_capped": sum(v["before"] > DPO_CAP for v in cap_info.values()),
                           "per_question": cap_info},
        "final": {
            "sft_records": len(sft_rows_out), "sft_questions": len(set(sft_sids)),
            "dpo_pairs": len(dpo_rows_out), "dpo_questions": len(set(dpo_sids)),
            "sft_by_source": {k: {"records": v, "share": round(v / len(sft_rows_out), 3)}
                              for k, v in sorted(Counter(pool_of[r["metadata"]["trace_id"]] for r in sft_rows_out).items())},
            "sft_hf_vs_teacher": dict(Counter("teacher" if r["metadata"].get("source") == "teacher" else "hf"
                                              for r in sft_rows_out)),
            "sft_by_origin": dict(sorted(Counter(origin(s) for s in sft_sids).items())),
            "sft_questions_by_origin": dict(sorted(Counter(origin(s) for s in set(sft_sids)).items())),
            "dpo_by_origin": dict(sorted(Counter(origin(s) for s in dpo_sids).items())),
            "dpo_negative_category": dict(Counter(r["metadata"]["negative_category"] for r in dpo_rows_out)),
            "stop_target_sft_records(decision 14)": sum(s in stop for s in sft_sids),
            "gold_questions_without_sft": sorted(set(gold) - set(sft_sids)),
            "type": {"dev": dev, "sft_question_cells": share(q_cells, len(set(sft_sids))),
                     "sft_record_cells": share(r_cells, len(sft_sids)), "dpo_pair_cells": share(d_cells, len(dpo_sids)),
                     "tv_vs_dev": {"sft_question": tv(share(q_cells, len(set(sft_sids))), dev),
                                   "sft_record": tv(share(r_cells, len(sft_sids)), dev),
                                   "dpo_pair": tv(share(d_cells, len(dpo_sids)), dev)}},
            "response_tokens(incl. EOS)": {"sft": dist(lengths_sft), "dpo_longer_of_pair": dist(lengths_dpo)},
            "passage_status_contrast(decision 66)": {
                "sft_records_by_variant": dict(sorted(Counter(variant[s] for s in sft_sids if s in variant).items())),
                "sft_questions_by_variant": dict(sorted(Counter(variant[s] for s in set(sft_sids) if s in variant).items())),
                "dpo_pairs_by_variant": dict(sorted(Counter(variant[s] for s in dpo_sids if s in variant).items())),
                "sft_records_by_variant_and_source": dict(sorted(Counter(
                    f"{variant[r['metadata']['source_record_id']]}:{pool_of[r['metadata']['trace_id']]}"
                    for r in sft_rows_out if r["metadata"]["source_record_id"] in variant).items())),
                "approved_questions_without_sft": sorted(s for s in variant if s in gold and s not in set(sft_sids))},
        },
        "build": built,
        "combined_traces": {"path": str(COMBINED.relative_to(ROOT)), "sha256": sha256(COMBINED), "committed": False},
        "output": str(OUT.relative_to(ROOT)),
        "output_sha256": {p.name: sha256(p) for p in sorted(OUT.iterdir())},
        "sft_rows": sft_rows, "dpo_rows": dpo_rows,
    }
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("teacher_batch005", "teacher_batch006", "sft_steps", "dpo_steps", "loop_flagged_traces", "final")},
                     ensure_ascii=False, indent=1))
    print({k: v for k, v in summary["decision52_cap"].items() if k != "per_question"})


if __name__ == "__main__":
    main()
