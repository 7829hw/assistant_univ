# -*- coding: utf-8 -*-
"""protected_final_v2 검사(결정 239 Z7, 명세 2판 4.5). **질문과 정답 내용은 어디에도 출력하지 않는다** — 수치, 문제 행 번호, 문제 코드만. 모델 호출 없음.
``pilot_006/protected_final/validate_v2.py``(그대로 둠)의 검사를 v2 서식(거부 형·거부 범주·근접 대조 열)에 맞춰 새로 쓴 파일이다.

    hfvenv/bin/python validate_pf2.py --xlsx /home/hwkim/sftdpo_work/protected_final_v2/protected_final_v2.xlsx [--report OUT.json] [--test]

검사:
1. 형식: 시트·열 이름(``common_pf2.COLUMNS``), 번호 중복 없음, 질문 있음, 코드(거부 문항 예/아니오, 거부 형 M/P/C/-, 거부 범주, 근접 대조, 난이도, hard factor).
   거부 문항 '예'면 거부 형 M/P/C, '아니오'면 거부 형 '-'·거부 범주 '-'. M이면 거부 범주가 M 범주 여섯 중 하나. 근접 대조는 답하는 문항에만.
2. 답하는 문항: 정답 호출 읽기·schema(업체 tool 정의) → grounding 역산 → 현재 파이프라인(mock, ``_GoldPlanner``) 실행 → 업체 채점 match.
   장소 이름(``get_scope_name``) 문항은 scope가 결정 238 허용 5개 중 하나.
3. 거부 문항 결과: M은 정답 호출이 비어 있어야 함(``m_has_calls``). P는 mock 결과 ``unsupported``(``p_not_unsupported:<결과>:<코드>``),
   C는 mock 결과 ``needs_clarification``(``c_not_clarification:<결과>:<코드>``). P·C 호출은 계산할 수 없는 조합이라 schema는 보지 않는다(정보로만 셈).
4. 분포(명세 2판 + 결정 238 변경 1): 유형(±2), 거부 50·형(M 34·P 10·C 6), M 범주 최소, P·C 서로 다른 범주 수, 근접 대조 25,
   factor 최소(답하는 문항 정답 호출에서 자동 + 작성자 표시), 난이도(±8). 모자라거나 벗어나면 문제 코드(행 번호 없음).
5. 겹침(명세 2판 4.5): 대상 = ``batch012/build_candidates12.targets()``(결정 120 규칙 대상, 보호 셋·개발 셋, RC5·RC6 학습 레코드, 승인 corpus v4, batch008–011,
   refusal_dev v1 승인본·초안, refusal_dev 확장 초안, pg, aug300) + RC7 학습 레코드(승인 corpus v5로 질문·grounding 찾음) + 승인 corpus v5 + refusal_dev v2 승인본 +
   batch012 전체(초안·수정 문장). 정규화 질문 같음, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding(답하는 문항만) → 행 번호와 대상 이름.
   거부 문항은 정규화 질문과 Jaccard만. template·family는 개수만(정보). 셋 안 같은 정규화 질문도 문제.
6. 파일 위치: 저장소 안이면 문제(``--test``일 때만 허용).
exit: 문제가 없으면 0, 있으면 1. ``--test``(합성 서식 시험)에서는 크기·분포 부족을 정보로만 낸다.
"""
import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common_pf2 import (COLUMNS, CONTRAST_TARGET, DIFFICULTY, DIFFICULTY_TARGET, DIFFICULTY_TOL, FACTOR_MIN, FORM_DISTINCT_MIN, FORM_TARGET, FORMS, M_CATEGORIES,
                        M_CATEGORY_MIN, MARKS, NONE, REFUSAL, REFUSAL_TARGET, ROOT, SCOPE_NAME_ALLOWED, SHEET, SIZE, TYPE_BY_TOOL, TYPE_TARGET, TYPE_TOL)

for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006_prep/aug300", ROOT / "sft_dpo_inventory/batch004", ROOT / "sft_dpo_inventory/pilot_006/protected_final",
          ROOT / "sft_dpo_inventory/batch012", ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
RC7 = "sft_dpo_inventory/pilot_009/build/RC7/full/sft_train.jsonl"
V5 = "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v5.jsonl"
RDEV_V2 = ROOT / "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"
B012_DRAFT = ROOT / "sft_dpo_inventory/batch012/candidates_draft.yaml"
B012_ACCEPT = ROOT / "sft_dpo_inventory/pilot_009/review/b012_accept_list.json"


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


def targets():
    """겹침 대상 {이름: [(id, 질문, grounding 또는 None)]}."""
    import yaml
    sys_argv = sys.argv
    sys.argv = [sys.argv[0]]  # build_candidates12는 import 때 --set을 읽는다(기본 batch012)
    try:
        import build_candidates12 as BC
    finally:
        sys.argv = sys_argv
    import evaluate_vendor100 as EV
    import validate_v2
    from grounding.full_renderer import render_full
    from training.data.common import read_jsonl
    tg = BC.targets()
    tt, missing = validate_v2.train_targets([RC7], V5)
    if missing:
        raise SystemExit(f"RC7 ids missing in corpus v5: {len(missing)}")
    tg.update(tt)
    tg["approved_v5"] = [(r["id"], r["question"], render_full(r["semantics"]) if not (r["semantics"] or {}).get("unsupported") else None) for r in read_jsonl(ROOT / V5)]
    der = lambda c: EV.derive_grounding(EV.parse_calls(c["gold_text"])) if c.get("gold_text") else None  # noqa: E731
    tg["refusal_dev_v2"] = [(c["id"], c["question"], der(c)) for c in yaml.safe_load(RDEV_V2.read_text(encoding="utf-8"))["items"]]
    tg["batch012"] = [(c["id"], c["question"], der(c)) for c in yaml.safe_load(B012_DRAFT.read_text(encoding="utf-8"))["candidates"]]
    tg["batch012"] += [(f"{r['id']}:modified", r["corrected_question"], None) for r in json.loads(B012_ACCEPT.read_text(encoding="utf-8"))["rows"] if r.get("corrected_question")]
    return tg


def mock_outcome(calls, question):
    import evaluate_vendor100 as EV
    payload = EV.derive_grounding(calls)
    observed = EV.run_item(EV._pipeline(EV._GoldPlanner(payload)), question)
    return payload, observed


def check_rows(rows, schemas):
    """형식·실행·거부 결과 검사 → (문제 {번호: [코드]}, 집계, 답하는 문항 payload)."""
    import evaluate_vendor100 as EV
    from jsonschema import Draft202012Validator
    from validate_v2 import factors_of
    problems = defaultdict(list)
    numbers = Counter(r["번호"] for r in rows)
    agg = {"types": Counter(), "forms": Counter(), "m_categories": Counter(), "form_categories": defaultdict(set), "contrast": Counter(), "marks": Counter(),
           "difficulty": Counter(), "auto_factors": Counter(), "p_codes": Counter(), "c_codes": Counter(), "pc_schema_outside(info)": 0}
    payloads = {}
    for r in rows:
        n = r["번호"]
        if numbers[n] > 1:
            problems[n].append("duplicate_number")
        if not r["질문"]:
            problems[n].append("question_empty")
        refusal = r["거부 문항"]
        if refusal not in REFUSAL:
            problems[n].append("refusal_code")
        form, cat, contrast = r["거부 형"] or NONE, r["거부 범주"] or NONE, r["근접 대조"] or NONE
        if r["난이도"] not in DIFFICULTY:
            problems[n].append("difficulty_code")
        else:
            agg["difficulty"][r["난이도"]] += 1
        ms = [x.strip() for x in r["hard factor"].replace("，", ",").split(",") if x.strip()]
        if [x for x in ms if x not in MARKS]:
            problems[n].append("hard_factor_code")
        if refusal == "예":
            if form not in FORMS:
                problems[n].append("form_code")
                continue
            agg["forms"][form] += 1
            if contrast != NONE:
                problems[n].append("contrast_on_refusal")
            if form == "M":
                if cat not in M_CATEGORIES:
                    problems[n].append("m_category_code")
                else:
                    agg["m_categories"][cat] += 1
                if r["정답 호출"]:
                    problems[n].append("m_has_calls")
                continue
            if cat == NONE:
                problems[n].append("pc_category_empty")
            else:
                agg["form_categories"][form].add(cat)
            try:
                calls = EV.parse_calls(r["정답 호출"])
                if not calls:
                    raise ValueError("no calls")
            except Exception:  # noqa: BLE001
                problems[n].append("calls_unreadable")
                continue
            for call in calls:
                if call["tool"] not in schemas:
                    problems[n].append("unknown_tool")
                    continue
                concrete = {k: ("scope:district:0000000000" if isinstance(v, str) and EV._BINDING.match(v) else v) for k, v in call["args"].items()}
                agg["pc_schema_outside(info)"] += bool(list(Draft202012Validator(schemas[call["tool"]]).iter_errors(concrete)))
            try:
                _, obs = mock_outcome(calls, r["질문"])
            except Exception as error:  # noqa: BLE001
                problems[n].append(f"compile_failed:{type(error).__name__}")
                continue
            out, code = obs.get("outcome"), obs.get("error_code")
            want = "unsupported" if form == "P" else "needs_clarification"
            if out != want:
                problems[n].append(f"{'p_not_unsupported' if form == 'P' else 'c_not_clarification'}:{out}:{code}")
            else:
                agg["p_codes" if form == "P" else "c_codes"][code] += 1
            continue
        # 답하는 문항
        agg["marks"].update(x for x in ms if x in MARKS)
        if form != NONE:
            problems[n].append("form_on_answered")
        if cat != NONE:
            problems[n].append("category_on_answered")
        if contrast != NONE:
            if contrast not in M_CATEGORIES:
                problems[n].append("contrast_code")
            else:
                agg["contrast"][contrast] += 1
        try:
            calls = EV.parse_calls(r["정답 호출"])
            if not calls:
                raise ValueError("no calls")
        except Exception:  # noqa: BLE001
            problems[n].append("calls_unreadable")
            continue
        bad_schema = False
        for call in calls:
            if call["tool"] not in schemas:
                problems[n].append("unknown_tool")
                bad_schema = True
                continue
            concrete = {k: ("scope:district:0000000000" if isinstance(v, str) and EV._BINDING.match(v) else v) for k, v in call["args"].items()}
            if list(Draft202012Validator(schemas[call["tool"]]).iter_errors(concrete)):
                problems[n].append("schema_error")
                bad_schema = True
        if bad_schema:
            continue
        agg["types"][TYPE_BY_TOOL.get(calls[-1]["tool"], "기타")] += 1
        if calls[-1]["tool"] == "get_scope_name" and calls[-1]["args"].get("scope") not in SCOPE_NAME_ALLOWED:
            problems[n].append("scope_name_not_allowed")
        try:
            payload, observed = mock_outcome(calls, r["질문"])
            category, _ = EV.score({"id": n, "question": r["질문"], "gold": calls, "expected_outcome": "answered", "vendor_verdict": "-"}, observed)
            if category != "match":
                problems[n].append(f"mock_not_match:{observed.get('error_code') or category}")
            payloads[n] = payload
            agg["auto_factors"].update(k for k, v in factors_of(payload).items() if v)
        except Exception as error:  # noqa: BLE001
            problems[n].append(f"compile_failed:{type(error).__name__}")
    return problems, agg, payloads


def overlap(rows, payloads, problems, tg):
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    from training.annotations.inventory import as_record, family_key
    from training.data.split import question_key, template_key
    idx = {}
    for name, items in tg.items():
        i = {"q": set(), "g": [], "view": set(), "t": set(), "f": set()}
        for _, q, pl in items:
            qk = question_key(q)
            i["q"].add(qk)
            i["g"].append(W6.grams(qk))
            if pl and not pl.get("unsupported"):
                try:
                    i["view"].add(json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str))
                    i["t"].add(template_key(as_record(pl)))
                    i["f"].add(family_key(pl))
                except Exception:  # noqa: BLE001
                    pass
        idx[name] = i
    own = Counter(question_key(r["질문"]) for r in rows if r["질문"])
    weak, jmax = Counter(), 0.0
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
            j = max((len(g & vg) / len(g | vg) for vg in i["g"]), default=0.0)
            jmax = max(jmax, j)
            if j >= W6.STRONG_AT:
                problems[n].append(f"overlap_jaccard:{name}")
            if view and view in i["view"]:
                problems[n].append(f"overlap_same_grounding:{name}")
            if pl:
                weak[f"template:{name}"] += template_key(as_record(pl)) in i["t"]
                weak[f"family:{name}"] += family_key(pl) in i["f"]
    return weak, round(jmax, 3), {n: len(v) for n, v in tg.items()}


def distribution(rows, agg):
    marks, autof = agg["marks"], agg["auto_factors"]
    dist = {"size": {"rows": len(rows), "target": SIZE},
            "types": {k: {"count": agg["types"].get(k, 0), "target": v} for k, v in TYPE_TARGET.items()},
            "refusal": {"count": sum(agg["forms"].values()), "target": REFUSAL_TARGET},
            "forms": {k: {"count": agg["forms"].get(k, 0), "target": v} for k, v in FORM_TARGET.items()},
            "m_categories": {k: {"count": agg["m_categories"].get(k, 0), "min": v} for k, v in M_CATEGORY_MIN.items()},
            "form_distinct_categories": {k: {"count": len(agg["form_categories"].get(k, ())), "min": v} for k, v in FORM_DISTINCT_MIN.items()},
            "contrast": {"count": sum(agg["contrast"].values()), "target": CONTRAST_TARGET, "by_category": dict(agg["contrast"])},
            "factors": {k: {"count": (autof.get(k, 0) if k not in MARKS else marks.get(k, 0)), "min": v} for k, v in FACTOR_MIN.items()},
            "difficulty": {k: {"count": agg["difficulty"].get(k, 0), "target": v} for k, v in DIFFICULTY_TARGET.items()},
            "p_error_codes": dict(agg["p_codes"]), "c_error_codes": dict(agg["c_codes"]), "pc_schema_outside(info)": agg["pc_schema_outside(info)"]}
    dp = []
    if len(rows) != SIZE:
        dp.append("size_not_target")
    dp += [f"type_off_target:{k}" for k, v in dist["types"].items() if abs(v["count"] - v["target"]) > TYPE_TOL]
    dp += ["refusal_off_target"] if dist["refusal"]["count"] != REFUSAL_TARGET else []
    dp += [f"form_off_target:{k}" for k, v in dist["forms"].items() if v["count"] != v["target"]]
    dp += [f"m_category_below_min:{k}" for k, v in dist["m_categories"].items() if v["count"] < v["min"]]
    dp += [f"form_categories_below_min:{k}" for k, v in dist["form_distinct_categories"].items() if v["count"] < v["min"]]
    dp += ["contrast_off_target"] if dist["contrast"]["count"] != CONTRAST_TARGET else []
    dp += [f"factor_below_min:{k}" for k, v in dist["factors"].items() if v["count"] < v["min"]]
    dp += [f"difficulty_off_target:{k}" for k, v in dist["difficulty"].items() if abs(v["count"] - v["target"]) > DIFFICULTY_TOL]
    return dist, dp


def validate(path, test=False, tg=None):
    from build import build
    path = Path(path).resolve()
    file_problems = ["file_inside_repository"] if str(path).startswith(str(ROOT)) and not test else []
    rows, errs = load_rows(path)
    if rows is None:
        return {"file_problems": errs, "ok": False}
    tools, _ = build()
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    problems, agg, payloads = check_rows(rows, schemas)
    weak, jmax, target_sizes = overlap(rows, payloads, problems, tg if tg is not None else targets())
    dist, dist_problems = distribution(rows, agg)
    return {"file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(rows), "file_problems": file_problems,
            "row_problems": {n: sorted(set(v)) for n, v in sorted(problems.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 10**9)},
            "row_problem_counts": dict(Counter(c.split(":")[0] for v in problems.values() for c in set(v))),
            "distribution": dist, "distribution_problems": dist_problems, "jaccard_max_any_target": jmax,
            "weak_overlap_counts(info)": {k: v for k, v in weak.items() if v}, "overlap_target_sizes": target_sizes, "test_mode": test,
            "ok": not file_problems and not problems and (test or not dist_problems)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--report", default=None, help="요약 JSON을 쓸 경로(수치·행 번호·코드만)")
    p.add_argument("--test", action="store_true", help="도구 시험(합성 서식): 저장소 안 파일 허용, 크기·분포 부족은 정보로만")
    a = p.parse_args()
    report = validate(a.xlsx, a.test)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if a.report:
        Path(a.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
