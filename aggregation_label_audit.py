# -*- coding: utf-8 -*-
"""inner 미지정 사례 감사표를 만든다. LLM 호출 없음.

``geoflow_replay_compare.py``로 재판정한 관측(기준선과 현재 코드)과 v2 의미 라벨
(``evaluation/labels/aggregation_semantics_v2.yaml``)을 관측 단위로 맞춘다. v1 라벨과
기존 결과는 읽기만 한다.

사용:
    python aggregation_label_audit.py --label M0 BASE.json HEAD.json \
        --label M2 BASE.json HEAD.json --out-json X.json --out-md X.md
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import yaml

import aggregation_plan as AP

BASE_DIR = Path(__file__).resolve().parent
LABELS = BASE_DIR / "evaluation" / "labels" / "aggregation_semantics_v2.yaml"
CLASS_NAMES = {
    1: "명시된 inner를 LLM이 누락", 2: "질문의 뜻으로 inner가 정해짐",
    3: "질문이 여러 해석을 허용", 4: "명확하지만 현재 도구·계약이 지원하지 않음",
    5: "기존 라벨·평가 변환 오류",
}


def load_labels(path=LABELS):
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    labels = {}
    for intent_id, label in document["intents"].items():
        base = {key: value for key, value in label.items() if key != "paraphrases"}
        labels[intent_id] = (base, label.get("paraphrases") or {})
    return labels


def label_for(labels, intent_id, observation_id):
    base, overrides = labels[intent_id]
    return {**base, **overrides.get(observation_id, {}), "intent": intent_id}


def grounding_semantic(factors):
    semantic = AP.flat_to_semantic(factors or {})
    if semantic is not None:
        semantic = {key: value for key, value in semantic.items() if value is not None}
    return semantic


def judge(label, grounding, head):
    """관측 하나의 오류 단계와 판정.

    계획 일치는 최종 grounding(재질의 뒤)의 집계 의미를 v2 계획과 비교한다. 모호한
    질문에서 grounding이 inner를 unspecified로 적었다면 합성이 확인 요청으로 멈춰도
    계획 표현은 맞은 것이다.
    """
    plan = label.get("plan")
    if plan is None:
        # 질문 모양 자체가 확정되지 않는다. 계획을 만들지 않은 것이 옳다.
        stage = "none" if head["run_outcome"] == "needs_clarification" else "grounding"
        return stage, head["run_outcome"] == label["outcome"], None
    grounding_ok = grounding is not None and all(
        grounding.get(key) == value for key, value in plan.items())
    plan_match = grounding_ok
    if not grounding_ok:
        stage = "grounding"
    elif head["run_outcome"] != "answered" and label["outcome"] == "unsupported":
        stage = "execution_contract"
    else:
        stage = "none"
    return stage, head["run_outcome"] == label["outcome"], plan_match


def audit(runs, labels):
    rows = []
    for name, base_path, head_path in runs:
        base = {row["id"]: row for row in json.load(open(base_path, encoding="utf-8"))["rows"]}
        head = {row["id"]: row for row in json.load(open(head_path, encoding="utf-8"))["rows"]}
        for observation_id in sorted(head):
            intent = head[observation_id]["intent_id"]
            if intent not in labels:
                continue
            label = label_for(labels, intent, observation_id)
            row_head, row_base = head[observation_id], base[observation_id]
            grounding = grounding_semantic(row_head.get("factors_after_repair")
                                           or row_head.get("factors"))
            stage, outcome_ok, plan_match = judge(label, grounding, row_head)
            observed_class = list(label["class"])
            if grounding and label.get("plan") and grounding.get("inner") == AP.UNSPECIFIED \
                    and label["plan"].get("inner") not in (None, AP.UNSPECIFIED):
                # 라벨이 정한 inner를 모델이 적지 않았다.
                observed_class = sorted(set(observed_class) | {1 if 1 in label["class"] else 2})
            invented = bool(grounding and label.get("plan")
                            and label["plan"].get("inner") == AP.UNSPECIFIED
                            and grounding.get("inner") not in (None, AP.UNSPECIFIED))
            rows.append({
                "run": name, "id": observation_id, "intent": intent,
                "question": row_head["question"],
                "v1_expected_tool_args": row_head.get("expected_tool_args"),
                "recorded_grounding": {k: v for k, v in (row_head.get("factors") or {}).items()
                                       if k in ("bucket", "aggregation", "rollup",
                                                "taxi_type", "date")},
                "before": {"outcome": row_base["outcome"], "status": row_base["status"]},
                "after": {"outcome": row_head["outcome"], "run_outcome": row_head["run_outcome"],
                          "code": row_head["status"] if row_head["status"] != "OK"
                          else row_head["exec_code"],
                          "plan": row_head.get("plan_aggregation")},
                "v2": {"plan": label.get("plan"), "outcome": label["outcome"]},
                "plan_match": plan_match,
                "outcome_match": outcome_ok,
                "grounding_invented_inner": invented,
                "error_stage": stage,
                "class": observed_class,
                "fix": label["fix"] if "fix" in label else [],
                "rationale": label.get("rationale", "").strip(),
            })
    return rows


def summarize(rows):
    summary = {}
    for name in sorted({row["run"] for row in rows}):
        mine = [row for row in rows if row["run"] == name]
        summary[name] = {
            "observations": len(mine),
            "v1_before_correct": sum(r["before"]["outcome"] == "CORRECT" for r in mine),
            "after_outcome": dict(Counter(r["after"]["run_outcome"] for r in mine)),
            "v2_outcome_match": sum(bool(r["outcome_match"]) for r in mine),
            "v2_plan_match": sum(bool(r["plan_match"]) for r in mine),
            "error_stage": dict(Counter(r["error_stage"] for r in mine)),
            "grounding_invented_inner": sum(r["grounding_invented_inner"] for r in mine),
        }
    return summary


def to_markdown(rows, summary):
    lines = ["# inner 미지정 사례 감사표 (자동 생성)", "",
             "생성: `aggregation_label_audit.py`. 라벨: `evaluation/labels/aggregation_semantics_v2.yaml`.",
             "기준선 = c547e5c, 현재 = 작업 트리. 재생(LLM 호출 없음), development census.", "",
             "| run | 관측 | v2 기대 | 전: v1 결과 | 후: 결과(code) | 계획 일치 | 결과 일치 | 오류 단계 | 유형 | 수정 대상 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for row in rows:
        v2 = row["v2"]
        expected = f"{v2['outcome']} {json.dumps(v2['plan'], ensure_ascii=False) if v2['plan'] else '(계획 확정 불가)'}"
        lines.append(
            f"| {row['run']} | {row['id']} {row['question']}<br>grounding "
            f"`{json.dumps(row['recorded_grounding'], ensure_ascii=False)}` | {expected} | "
            f"{row['before']['outcome']} | {row['after']['run_outcome']} ({row['after']['code']}) | "
            f"{'-' if row['plan_match'] is None else ('예' if row['plan_match'] else '아니오')} | "
            f"{'예' if row['outcome_match'] else '아니오'} | {row['error_stage']} | "
            f"{', '.join(str(c) for c in row['class'])} | {', '.join(row['fix'])} |")
    lines += ["", "## 요약", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2),
              "```", "", "유형: " + "; ".join(f"{k} {v}" for k, v in CLASS_NAMES.items())]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--label", nargs=3, action="append", metavar=("RUN", "BASE", "HEAD"),
                        required=True)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    args = parser.parse_args(argv)
    rows = audit(args.label, load_labels())
    summary = summarize(rows)
    if args.out_json:
        with open(args.out_json, "x", encoding="utf-8") as handle:
            json.dump({"summary": summary, "rows": rows}, handle, ensure_ascii=False, indent=2)
    if args.out_md:
        with open(args.out_md, "x", encoding="utf-8") as handle:
            handle.write(to_markdown(rows, summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
