# -*- coding: utf-8 -*-
"""protected_final_v2 P·C 거부 패턴 확인(결정 239 Z7). 현재 코드(지문 791c4a68)와 mock에서 업체 형식 호출 뼈대가 실제로 어떤 결과로 끝나는지 본다. 모델 호출 없음.

    hfvenv/bin/python pc_patterns9.py   # -> pc_patterns9.json

- 뼈대마다 장소·기간 자리표시를 mock gazetteer 장소 둘(``대구``, ``부산``)과 기간 둘로 채운 두 벌을 돌린다. 질문 자리에는 뜻 없는 고정 문자열 ``"질문"``을 넣는다
  (이 경로의 결과는 grounding만으로 정해짐 — 질문 문장은 쓰지 않는다).
- 실행: ``evaluate_vendor100.derive_grounding`` → ``_pipeline(_GoldPlanner)`` → 결과 상태·오류 코드. 두 벌의 결과가 같아야 "확인"으로 친다.
- 후보: 설계표의 P-1–P-5·C-1–C-3 + 이 세션에서 찾은 대체 패턴(P-a…·C-a…).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
FILLS = ({"<장소>": "대구", "<기간>": "last_month", "<여러 달 기간>": "last_year"}, {"<장소>": "부산", "<기간>": "this_month", "<여러 달 기간>": "this_year"})
PLACE = "get_place_scope(name=<장소>)\n"
#: (번호, 구분(설계표 후보/대체), 기대 형, 뼈대, 설명)
PATTERNS = [
    ("P-1", "설계표", "P", PLACE + "get_trip_metrics(metric=fare, scope=$resolve.scope, date=<기간>, taxi_type=private, aggregation=avg)", "통행 지표에 택시 유형"),
    ("P-2", "설계표", "P", PLACE + "get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, taxi_type=private, aggregation=avg)", "통과량 지표에 택시 유형"),
    ("P-3", "설계표", "P", PLACE + "get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, taxi_status=occupied, aggregation=avg)", "통과량 지표에 운행 상태"),
    ("P-4", "설계표", "P", PLACE + "get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, dimension=sigungu, aggregation=avg)", "운행 지표에 차원"),
    ("P-5", "설계표", "P", PLACE + "get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<여러 달 기간>, aggregation=avg, bucket=month, rollup=max)",
     "운행 지표에 묶음·rollup"),
    ("C-1", "설계표", "C", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, bucket=month, rollup=max)",
     "요금 지표에 묶음·rollup만, 구간 안 집계 없음"),
    ("C-2", "설계표", "C", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, bucket=month)", "요금 지표에 묶음만, 집계 없음"),
    ("C-3", "설계표", "C", "get_trip_count(date=<기간>)", "질문에 장소 이름 없음(\"거기\" 등) — 정답 호출에 장소 없음"),
    ("P-a", "대체", "P", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<기간>, dimension=sido)", "요금 지표: 장소 scope와 시도 차원을 함께(scope가 막는 차원)"),
    ("P-b", "대체", "P", "get_billing_metrics(metric=revenue, date=<기간>, dimension=h3)", "요금 지표: H3 차원인데 장소 scope 없음"),
    ("P-c", "대체", "P", PLACE + "get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, aggregation=sum)", "속도의 합계(정의되지 않은 측정값 집계)"),
    ("P-d", "대체", "P", PLACE + "get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, aggregation=sum)", "공차율의 합계(정의되지 않은 측정값 집계)"),
    ("P-e", "대체", "P", PLACE + "get_trip_count(scope_pickup=$resolve.scope, date=<여러 달 기간>, bucket=month, aggregation=sum, rollup=avg)",
     "통행 건수에 월 묶음(묶음을 받지 않는 측정값)"),
    ("P-f", "대체", "P", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, dimension=dayofweek, aggregation=sum, bucket=month, rollup=avg)",
     "요금 지표: 요일 차원과 월 묶음을 함께"),
    ("P-g", "대체", "P", PLACE + "get_passage_metrics(metric=rpm, scope=$resolve.scope, date=<여러 달 기간>, aggregation=avg, bucket=month, rollup=max)",
     "통과량 지표에 묶음·rollup"),
    ("P-h", "대체", "P", PLACE + "get_trip_count(scope_pickup=$resolve.scope, date=<기간>, taxi_type=private)", "통행 건수에 택시 유형"),
    ("P-i", "대체", "P", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<기간>, taxi_status=occupied, aggregation=sum)", "요금 지표에 운행 상태"),
    ("C-a", "대체", "C", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, aggregation=sum, bucket=month)",
     "요금 지표: 묶음과 구간 안 집계는 있으나 구간별 결과를 모으는 방법(rollup) 없음"),
    ("C-b", "대체", "C", PLACE + "get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, aggregation=sum, rollup=max)",
     "요금 지표: rollup만 있고 묶음 없음"),
    ("C-c", "대체", "C", PLACE + "get_passage_count(scope=$resolve.scope, date=<기간>, dimension=h3, order=top)", "통과량 건수: 차원·순위 방향만, 개수(limit) 없음"),
    ("C-d", "대체", "C", PLACE + "get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<여러 달 기간>, bucket=month, rollup=max)",
     "운행 지표: 묶음·rollup만, 구간 안 집계 없음"),
    ("C-e", "대체", "C", PLACE + "get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, order=top, limit=3)", "운행 지표: 차원 없이 순위·개수"),
]


def fill(skeleton, f):
    for k, v in f.items():
        skeleton = skeleton.replace(k, v)
    return skeleton


def run(text):
    import evaluate_vendor100 as EV
    try:
        calls = EV.parse_calls(text)
        obs = EV.run_item(EV._pipeline(EV._GoldPlanner(EV.derive_grounding(calls))), "질문")
        return obs.get("outcome"), obs.get("error_code")
    except Exception as error:  # noqa: BLE001
        return "exception", type(error).__name__


def main():
    import execution_spec
    out = []
    for pid, group, form, sk, desc in PATTERNS:
        res = [run(fill(sk, f)) for f in FILLS]
        same = len(set(res)) == 1
        outcome, code = res[0]
        want = "unsupported" if form == "P" else "needs_clarification"
        status = ("확인" if same and outcome == want else "다른 형" if same and outcome in ("unsupported", "needs_clarification")
                  else "답함" if same and outcome == "answered" else "실패" if same else "벌마다 다름")
        out.append({"id": pid, "group": group, "form": form, "skeleton": sk, "description": desc, "results": [list(r) for r in res], "outcome": outcome,
                    "error_code": code, "consistent": same, "status": status, "usable_as": form if status == "확인" else None})
    conf = [p for p in out if p["status"] == "확인"]
    summary = {"code_fingerprint": execution_spec.code_fingerprint(ROOT)["sha256"][:8], "fills": FILLS, "patterns": len(out),
               "confirmed": {"P": [p["id"] for p in conf if p["form"] == "P"], "C": [p["id"] for p in conf if p["form"] == "C"]},
               "distinct_error_codes": {f: dict(Counter(p["error_code"] for p in conf if p["form"] == f)) for f in ("P", "C")},
               "candidates(설계표)": {p["id"]: f"{p['status']} ({p['outcome']}, {p['error_code']})" for p in out if p["group"] == "설계표"}}
    (HERE / "pc_patterns9.json").write_text(json.dumps({"summary": summary, "patterns": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
