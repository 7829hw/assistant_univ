# -*- coding: utf-8 -*-
"""첫 계획 원출력의 MEASURE와 정답 grounding의 MEASURE를 교차 집계한다(모델 호출 없음).

    python evaluation/grounding_v12/measure_confusion.py NAME=DIR [NAME=DIR ...]

정답과 다른 측정값을 고른 문항을 (정답 → 출력) 쌍으로 센다. 측정값·반환 대상 혼동(장소를 측정값으로)과 측정값끼리의 혼동
(통행량 ↔ trip)을 따로 보기 위한 진단이다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "grounding_v9"))
sys.path.insert(0, str(HERE.parents[1]))

import compare as C  # noqa: E402
import evaluate_vendor100 as E  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

C.GOLD_FILES["heldout"] = "evaluation/grounding_v10/heldout_questions.yaml"
C.GOLD_FILES["measure"] = "evaluation/grounding_v12/measure_contrast_questions.yaml"
SETS = C.SETS + ("measure",)


def measure_of(payload):
    for concept in (payload or {}).get("concepts") or []:
        if concept.get("role") == "MEASURE":
            return f"{concept.get('concept')}/{concept.get('subtype')}"
    return None


def main():
    for spec in sys.argv[1:]:
        name, directory = spec.split("=", 1)
        pairs, examples, total = Counter(), {}, 0
        for set_name in SETS:
            path = Path(directory) / f"{set_name}.json"
            if not path.is_file():
                continue
            gold = C._gold(set_name, None)
            for row in json.loads(path.read_text(encoding="utf-8"))["rows"]:
                item = gold[row["id"]]
                want = measure_of(E.gold_grounding(item))
                if want is None:
                    continue
                text = next((c.get("content") for c in row.get("llm_calls") or [] if c["kind"] == "plan" and not c.get("failed")), None)
                try:
                    got = measure_of(parse_planner_json(text)) if text else None
                except Exception:  # noqa: BLE001
                    got = "(parse error)"
                total += 1
                if got != want:
                    pairs[(want, got)] += 1
                    examples.setdefault((want, got), []).append(f"{set_name}/{row['id']}")
        print(f"== {name}: 정답 측정값이 있는 문항 {total}, 첫 출력 측정값이 다른 문항 {sum(pairs.values())}")
        for (want, got), n in pairs.most_common():
            print(f"   {want} → {got}: {n}  {examples[(want, got)][:8]}")


if __name__ == "__main__":
    main()
