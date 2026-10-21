# -*- coding: utf-8 -*-
"""다음 보호 셋용 검사 v2(pilot_007 B2 C4): ``validate.py``(protected_final_v1 고정에 쓴 판, 그대로 둠)의 사본에 겹침 대상 **실제 학습 레코드**를 더함.
고정된 protected_final_v1에는 쓰지 않는다(그 셋은 PF3에서 RC5와 겹침 0 확인). 바뀐 것:
- ``--train-jsonl``(여러 개, 기본 RC5 full·partial ``sft_train.jsonl``): 레코드의 ``metadata.source_record_id``로 승인 corpus(``--corpus``, 기본 v3)의 질문·semantics를 찾아
  겹침 대상 ``train_rc:<arm 디렉터리 상위/arm>``에 넣는다(질문 = corpus 질문, grounding = ``render_full(semantics)``; ``pf3_overlap_t.py``와 같은 방법).
  corpus에 없는 id는 ``train_ids_missing_in_corpus``로 보고(문제 코드 ``train_target_unresolved``, 파일 문제).
- 기존 대상(v1 승인 corpus 등)은 그대로.

원 설명: protected_final_v1 검사(결정 135 G5, H5). **질문과 정답 내용은 어디에도 출력하지 않는다** — 요약 수치와 문제 행 번호·문제 코드만. 모델 호출 없음.

    hfvenv/bin/python validate.py --xlsx /home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx [--report OUT.json] [--test]

검사:
1. 형식: 시트·열 이름(``common.COLUMNS``), 번호 1..N 중복 없음, 질문 있음, 거부 문항 = 예/아니오, 난이도 코드, hard factor 표시 코드,
   정답 호출 읽기(``evaluate_vendor100.parse_calls``)와 schema(업체 tool 정의), 거부 문항이면 정답 호출 없음.
2. compile·mock: 정답 호출 → grounding 역산 → 현재 파이프라인(``_GoldPlanner``)으로 실행 → 업체 채점에서 match(check_aug300과 같은 방법).
3. 분포: 유형(마지막 tool, 거부)·hard factor(정답 호출에서 자동: dt, dt 승차·하차, od≠dt, 주변, 묶음·기간 단위, 집계; 작성자 표시: 동사형끝점, 운행상태표현,
   값없는장소)·난이도를 SPEC 목표와 비교(모자라면 문제 코드, 행 번호 없음).
4. 겹침: 학습·개발 셋 전체(보호 셋 5, holdout, aug300 전체, batch007·008·009, 학습 데이터 v006·pilot004, pg 세 가지, pilot_006 승인 corpus)와
   정규화 질문 같음, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding → 행 번호와 셋 이름만. template·family 겹침은 개수만(정보).
   protected_final 안에서 같은 정규화 질문도 문제.
5. 파일 위치: 저장소 안이면 문제(``--test``일 때만 허용).
exit: 문제가 없으면 0, 있으면 1.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import COLUMNS, DIFFICULTY, DIFFICULTY_TARGET, FACTOR_MIN, MARKS, REFUSAL, ROOT, SHEET, SIZE, TYPE_BY_TOOL, TYPE_TARGET

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))


def load_rows(path):
    from xlsx_read import read_workbook
    wb = read_workbook(path)
    if SHEET not in wb:
        return None, ["sheet_missing"]
    rows = wb[SHEET]["rows"]
    head = [str(c or "").strip() for c in rows[0]]
    if head[:len(COLUMNS)] != COLUMNS:
        return None, ["columns_mismatch"]
    out = []
    for r in rows[1:]:
        d = {c: (str(r[i]).strip() if i < len(r) and r[i] is not None else "") for i, c in enumerate(COLUMNS)}
        if d["질문"] or d["정답 호출"]:
            out.append(d)
    return out, []


DEFAULT_TRAIN = ["sft_dpo_inventory/pilot_007/build/RC5/full/sft_train.jsonl", "sft_dpo_inventory/pilot_007/build/RC5/partial/sft_train.jsonl"]
DEFAULT_CORPUS = "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v3.jsonl"


def train_targets(train_paths, corpus_path):
    """실제 학습 레코드 → {대상 이름: [(질문 id, 질문, grounding payload)]}, corpus에 없는 id 목록."""
    from grounding.full_renderer import render_full
    corpus = {}
    for line in (ROOT / corpus_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            corpus[c["id"]] = c
    out, missing = {}, set()
    for tp in train_paths:
        p = Path(tp) if Path(tp).is_absolute() else ROOT / tp
        name = f"train_rc:{p.parent.parent.name}/{p.parent.name}"
        seen = set()
        out[name] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            cid = json.loads(line)["metadata"]["source_record_id"]
            if cid in seen:
                continue
            seen.add(cid)
            if cid not in corpus:
                missing.add(cid)
                continue
            out[name].append((cid, corpus[cid]["question"], render_full(corpus[cid]["semantics"])))
    return out, sorted(missing)


def targets():
    spec = importlib.util.spec_from_file_location("b009", ROOT / "sft_dpo_inventory/batch009/build_candidates.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    tg = m.targets()
    for row in json.loads((ROOT / "sft_dpo_inventory/batch009/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]:
        tg["batch009"].append((row["id"], row["question"], row["draft_grounding"]))
    return tg


def factors_of(payload):
    from training.data.canonicalize import flatten_source
    raw = flatten_source(payload)
    f = raw.get("factors") or {}
    od = {(c.get("attributes") or {}).get("od_role", c.get("od_role")) for c in raw.get("concepts") or [] if c.get("concept") == "LOCATION"} - {None, ""}
    dt = f.get("dimension_target")
    return {"dt": bool(dt), "dt_pickup": dt in ("pickup", "both"), "dt_dropoff": dt in ("dropoff", "both"),
            "od_ne_dt": bool(dt and od and od != {dt}), "vicinity": bool(f.get("vicinity")), "bucket_or_dimension": bool(f.get("bucket") or f.get("dimension")),
            "aggregation": bool(f.get("aggregation"))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--report", default=None, help="요약 JSON을 쓸 경로(수치·행 번호만)")
    p.add_argument("--test", action="store_true", help="도구 시험(가짜 문항): 저장소 안 파일 허용, 크기·분포 부족은 정보로만")
    p.add_argument("--train-jsonl", nargs="+", default=DEFAULT_TRAIN, help="겹침 대상에 넣을 실제 학습 레코드(RC 빌드 sft_train.jsonl)")
    p.add_argument("--corpus", default=DEFAULT_CORPUS, help="학습 레코드 source_record_id를 찾을 승인 corpus")
    a = p.parse_args()
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    from build import build
    from jsonschema import Draft202012Validator
    from training.annotations.inventory import as_record, family_key
    from training.data.split import question_key, template_key
    path = Path(a.xlsx).resolve()
    file_problems = []
    if str(path).startswith(str(ROOT)) and not a.test:
        file_problems.append("file_inside_repository")
    rows, errs = load_rows(path)
    if rows is None:
        print(json.dumps({"file_problems": errs}, ensure_ascii=False))
        raise SystemExit(1)
    tools, _ = build()
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    problems = defaultdict(list)
    numbers = Counter(r["번호"] for r in rows)
    types, marks, diffs, autof = Counter(), Counter(), Counter(), Counter()
    payloads = {}
    for r in rows:
        n = r["번호"]
        if numbers[n] > 1:
            problems[n].append("duplicate_number")
        if not r["질문"]:
            problems[n].append("question_empty")
        refusal = r["거부 문항"] or "아니오"
        if refusal not in REFUSAL:
            problems[n].append("refusal_code")
        if r["난이도"] not in DIFFICULTY:
            problems[n].append("difficulty_code")
        else:
            diffs[r["난이도"]] += 1
        ms = [x.strip() for x in r["hard factor"].replace("，", ",").split(",") if x.strip()]
        bad = [x for x in ms if x not in MARKS]
        if bad:
            problems[n].append("hard_factor_code")
        marks.update(x for x in ms if x in MARKS)
        if refusal == "예":
            types["거부"] += 1
            if r["정답 호출"]:
                problems[n].append("refusal_with_calls")
            continue
        try:
            calls = EV.parse_calls(r["정답 호출"])
            if not calls:
                raise ValueError("no calls")
        except Exception:  # noqa: BLE001
            problems[n].append("calls_unreadable")
            continue
        for i, call in enumerate(calls):
            if call["tool"] not in schemas:
                problems[n].append("unknown_tool")
                continue
            concrete = {k: ("scope:district:0000000000" if isinstance(v, str) and EV._BINDING.match(v) else v) for k, v in call["args"].items()}
            if list(Draft202012Validator(schemas[call["tool"]]).iter_errors(concrete)):
                problems[n].append("schema_error")
        types[TYPE_BY_TOOL.get(calls[-1]["tool"], "기타")] += 1
        try:
            payload = EV.derive_grounding(calls)
            observed = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), r["질문"])
            category, _ = EV.score({"id": n, "question": r["질문"], "gold": calls, "expected_outcome": "answered", "vendor_verdict": "-"}, observed)
            if category != "match":
                problems[n].append(f"mock_not_match:{observed.get('error_code') or category}")
            payloads[n] = payload
            autof.update(k for k, v in factors_of(payload).items() if v)
        except Exception as error:  # noqa: BLE001
            problems[n].append(f"compile_failed:{type(error).__name__}")
    # 겹침
    tg = targets()
    train_tg, train_missing = train_targets(a.train_jsonl, a.corpus)
    tg.update(train_tg)
    if train_missing:
        file_problems.append("train_target_unresolved")
    idx = {}
    for name, items in tg.items():
        i = {"q": set(), "g": [], "view": set(), "t": set(), "f": set()}
        for _, q, pl in items:
            qk = question_key(q)
            i["q"].add(qk)
            i["g"].append(W6.grams(qk))
            if pl:
                try:
                    i["view"].add(json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str))
                    i["t"].add(template_key(as_record(pl)))
                    i["f"].add(family_key(pl))
                except Exception:  # noqa: BLE001
                    pass
        idx[name] = i
    own = Counter(question_key(r["질문"]) for r in rows if r["질문"])
    weak = Counter()
    for r in rows:
        n = r["번호"]
        if not r["질문"]:
            continue
        qk = question_key(r["질문"])
        if own[qk] > 1:
            problems[n].append("duplicate_question_within_set")
        g = W6.grams(qk)
        pl = payloads.get(n)
        view = json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str) if pl else None
        for name, i in idx.items():
            if qk in i["q"]:
                problems[n].append(f"overlap_question:{name}")
            if max((len(g & vg) / len(g | vg) for vg in i["g"]), default=0) >= W6.STRONG_AT:
                problems[n].append(f"overlap_jaccard:{name}")
            if view and view in i["view"]:
                problems[n].append(f"overlap_same_grounding:{name}")
            if pl:
                weak[f"template:{name}"] += template_key(as_record(pl)) in i["t"]
                weak[f"family:{name}"] += family_key(pl) in i["f"]
    dist = {"size": {"rows": len(rows), "target": SIZE},
            "types": {k: {"count": types.get(k, 0), "target": v} for k, v in TYPE_TARGET.items()},
            "factors": {k: {"count": (autof.get(k, 0) if k not in MARKS else marks.get(k, 0)), "min": v} for k, v in FACTOR_MIN.items()},
            "difficulty": {k: {"count": diffs.get(k, 0), "target": v} for k, v in DIFFICULTY_TARGET.items()}}
    dist_problems = []
    if len(rows) != SIZE:
        dist_problems.append("size_not_target")
    dist_problems += [f"factor_below_min:{k}" for k, v in dist["factors"].items() if v["count"] < v["min"]]
    dist_problems += [f"type_off_target:{k}" for k, v in dist["types"].items() if abs(v["count"] - v["target"]) > 2]
    dist_problems += [f"difficulty_off_target:{k}" for k, v in dist["difficulty"].items() if abs(v["count"] - v["target"]) > 6]
    report = {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows), "file_problems": file_problems,
              "row_problems": {n: sorted(set(v)) for n, v in sorted(problems.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 10**9)},
              "row_problem_counts": dict(Counter(c.split(":")[0] for v in problems.values() for c in set(v))),
              "distribution": dist, "distribution_problems": dist_problems,
              "weak_overlap_counts(info)": {k: v for k, v in weak.items() if v}, "test_mode": a.test,
              "train_targets": {k: len(v) for k, v in train_tg.items()}, "train_ids_missing_in_corpus": len(train_missing),
              "ok": not file_problems and not problems and (a.test or not dist_problems)}
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if a.report:
        Path(a.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
