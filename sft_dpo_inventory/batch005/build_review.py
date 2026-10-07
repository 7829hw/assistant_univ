# -*- coding: utf-8 -*-
"""batch005 사람 검토 시트를 만든다(JSONL + XLSX). 승인하지 않고, 어떤 corpus에도 넣지 않는다(결정 45).

    python sft_dpo_inventory/batch005/build_review.py [--xlsx-only]

batch004(``../batch004/build_review.py``)와 같은 형식이다. 다른 점:
- HF 출력은 thinking 켬(8192)이다. 시트에는 응답 JSON 본문과 thinking 길이를 보이고, 원문(thinking 포함)은 queue JSONL에 둔다.
- 정지 후보(현재 코드가 계약 오류로 멈추는 초안)는 결정 14의 T2PC식 정지 grounding target(``t2pc_stop_grounding``)으로 둔다.
- v003 표시 항목과 지원 불가 형식 결정 요청은 없다(결정 14로 정해졌다).
출력(``review/``):
- ``review_queue.jsonl`` + ``manifest.json``: thor ``training.annotations.workflow`` queue 형식(커밋).
- ``batch005_review.xlsx``: 검토 화면. 저장소의 ``*.xlsx`` ignore 규칙에 따라 커밋하지 않는다. ``--xlsx-only``로 커밋된 JSON에서 다시 만든다.
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import Protection, digest  # noqa: E402
from training.annotations.workflow import CHECKS  # noqa: E402
from training.data.common import provenance, read_jsonl, sha256, write_jsonl  # noqa: E402

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v004_t2pc"
REVIEW = HERE / "review"
STOP_NOTE = ("결정 14: 현재 코드에서 계약 오류로 멈춘다. 측정값과 조건을 grounding으로 적고 코드가 멈추는 T2PC식 정지 target이다. "
             "질문의 조건(예: 택시 유형)을 이 측정값의 Tool이 받지 않는다.")


def diffs_after_condition_layer(item, payload):
    return B4.diffs_after_condition_layer(item, payload)


def queue_rows(checked, hf):
    from geoflow.planner import parse_planner_json
    from training.data.thinking import split_response
    by_id = {r["id"]: r for r in hf["rows"]}
    rows = []
    for item in checked["candidates"]:
        stop = not item["contract_ok"]["t2pc"]
        base = {
            "status": "pending", "question": item["question"], "parent_intent": item["intent"],
            "semantic_family": item["family"], "contrast_group": item["family"], "category": item["type"],
            "expected_outcome": "t2pc_stop_grounding" if stop else "answered",
            "provenance": {"origin": "claude_authored_review_only", "source": "batch005",
                           "source_record_id": item["id"], "authored_at": "2026-10-07",
                           "protected_sources_used": False},
            "eligibility": {"eligible_after_human_review": True, "training_blockers": []},
            "rationale": item["rationale"], "review_checks": list(CHECKS),
            "semantic_correctness": "unreviewed", "suggestion_state": "requires_semantic_review",
            "chosen_trust": {"human_approval_required": True, "level": "claude_draft"},
            "quality": item["results"]["t2pc"], "quality_by_mode": item["results"],
            "leakage": item["leakage"], "note": STOP_NOTE if stop else None,
        }
        gold = {**base, "candidate_id": item["id"], "candidate_type": "targeted_gold", "record_type": "sft_gold",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": None,
                "negative_type": None, "failure_hints": None, "evidence": [], "model_output": None}
        gold["candidate_hash"] = digest(gold)
        rows.append(gold)
        out = by_id.get(item["id"])
        if out is None or out["matches_draft"]:
            continue
        rejected, after_layer, answer_text = None, None, None
        if out["think_closed"]:
            answer_text = split_response(out["raw_text"])[1]
        if out["parse_state"] == "ok":
            rejected = parse_planner_json(answer_text)
            after_layer = diffs_after_condition_layer(item, rejected)
        pair = {**base, "candidate_id": f"{item['id']}-hf", "candidate_type": "actual_model_prediction",
                "record_type": "dpo_pair" if rejected is not None else "model_output_note",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": rejected,
                "negative_type": "hf_base_prediction_mismatch", "failure_hints": out["error_tags"],
                "evidence": out["grounding_diffs"], "diffs_after_condition_layer": after_layer,
                "model_output": {"raw_text": out["raw_text"], "answer_text": answer_text,
                                 "thinking_chars": out["thinking_chars"], "generated_tokens": out["generated_tokens"],
                                 "done_reason": out["done_reason"], "parse_state": out["parse_state"],
                                 "model_quality": out["model_quality"], "source": "hf_outputs.json"},
                "review_question": "초안(chosen)과 모델 출력(rejected) 중 어느 쪽이 질문의 뜻에 맞는가? 모델이 맞으면 "
                                   "이 쌍은 제외하고 SFT 행의 초안을 수정한다."}
        pair["provenance"] = {**base["provenance"], "origin": "hf_base_prediction",
                              "model": "Qwen/Qwen3-8B@b968826d", "enable_thinking": True, "max_new_tokens": 8192}
        pair["eligibility"] = {"eligible_after_human_review": rejected is not None,
                               "training_blockers": [] if rejected is not None else ["no_parseable_rejected"]}
        pair["candidate_hash"] = digest(pair)
        rows.append(pair)
    return rows


GUIDE_ROWS = [
    ["이 시트는 무엇인가", "batch005 annotation 후보(Claude 초안)와 같은 질문에 대한 base 모델(Qwen3-8B, thinking 켬) 첫 응답을 모은 "
     "사람 검토 화면이다(결정 40-C·45)."],
    ["승인이 아니다", "초안 gold와 근거는 Claude가 썼다. validator·compose·compile 통과는 형식 검사일 뿐 질문의 뜻이 맞다는 증거가 아니다. "
     "사람이 질문을 읽고 판단한 결정만 승인이다."],
    ["결정 칸", f"{B4.DECISION_CHOICES} 중 하나를 적는다. 승인=초안 그대로 학습에 써도 된다. 수정=뜻을 고친 grounding을 '수정 grounding' 칸에 "
     "JSON으로 적는다. 보류=지금 판단할 수 없다(이유를 메모에). 제외=학습에 쓰지 않는다."],
    ["batch005 시트 열", "후보 id, 유형 칸(결정 40-C 배분), family, 질문, 초안 grounding, 근거, 현재 코드 결과(T2PC 경로: 계약·멈춤 코드·compile), "
     "기대 결과(answered 또는 결정 14의 정지 target), 비고, 결정, 수정 grounding, 메모, 검토자, 검토일."],
    ["hf_outputs 시트 열", "쌍 id, 질문, 초안 grounding, 모델 응답 JSON 본문, thinking 길이·생성 token·종료 이유, 초안과의 차이(첫 응답 기준), "
     "조건 계층 적용 뒤 차이(참고), 오류 태그, 검토 질문. 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다. 모델이 맞으면 batch005 시트의 해당 "
     "초안을 '수정'하고 이 쌍은 '제외'한다. 초안이 맞고 모델이 틀렸으면 '승인'(DPO rejected 후보)."],
    ["판단 기준", "(1) 측정값 subtype과 사건이 질문과 맞는가(실차 건수=trip_count, 통행량=passage_count, rpm, 공차율=vacant_ratio, "
     "가동률=active_taxi_ratio, 수입=revenue). (2) 질문에 있는 조건만 있는가. 없는 조건이나 집계를 지어내지 않았는가. (3) 집계어가 없으면 "
     "aggregation이 없어야 한다. (4) od_role(장소가 제한하는 끝: 한 장소 안 이동이면 both)과 dimension_target(결과를 묶는 끝)을 구분했는가. "
     "(5) 그룹 단위(시도·시군구·읍면동·H3·요일)가 질문과 같은가. (6) 근처·주변·부근이 있을 때만 vicinity. (7) 문장이 보호된 평가 셋 문장을 "
     "바꿔 쓴 것처럼 보이면 '제외'하고 메모한다."],
    ["정지 후보", "현재 코드가 계약 오류(UNCONSUMED_CONDITION)로 멈추는 초안이다. 결정 14에 따라 조건을 grounding으로 적고 코드가 멈추는 "
     "정지 target으로 쓴다. 이 질문이 정지 target으로 적절한지(조건을 버리고 답하는 것이 아니라 멈추는 것이 맞는지)도 본다."],
    ["가져오기", "XLSX 편집은 자동으로 가져오지 않는다. 결정은 workflow decide로 decisions 파일에 사람 이름과 함께 남긴다(review/README.md)."],
]


def write_sheet(rows):
    blank = ["", "", "", "", ""]
    tail = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "메모", "검토자", "검토일"]
    gold_rows = [r for r in rows if r["record_type"] == "sft_gold"]
    sheet_b = [[r["candidate_id"], r["category"], r["semantic_family"], r["question"], r["proposed_grounding"], r["rationale"],
                {"outcome": r["quality"].get("outcome"), "error_code": r["quality"].get("error_code"),
                 "compile_ok": r["quality"].get("compile_ok")}, r["expected_outcome"], r["note"] or "", *blank] for r in gold_rows]
    pair_rows = [r for r in rows if r["record_type"] != "sft_gold"]
    sheet_hf = [[r["candidate_id"], r["question"], r["proposed_grounding"], r["model_output"]["answer_text"] or "(본문 없음)",
                 {k: r["model_output"][k] for k in ("thinking_chars", "generated_tokens", "done_reason", "parse_state")},
                 r["evidence"], r["diffs_after_condition_layer"], r["failure_hints"], r["review_question"], *blank]
                for r in pair_rows]
    B4.write_workbook(REVIEW / "batch005_review.xlsx", [
        ("안내", ["항목", "설명"], GUIDE_ROWS),
        ("batch005", ["후보 id", "유형 칸", "family", "질문", "초안 grounding", "근거", "현재 코드 결과(T2PC)", "기대 결과", "비고", *tail],
         sheet_b),
        ("hf_outputs", ["쌍 id", "질문", "초안 grounding(chosen)", "모델 응답 JSON 본문(rejected 후보)", "thinking·생성",
                        "차이(첫 응답)", "조건 계층 적용 뒤 차이(참고)", "오류 태그", "검토 질문", *tail], sheet_hf),
    ])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-only", action="store_true")
    args = parser.parse_args()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    hf = json.loads((HERE / "hf_outputs.json").read_text(encoding="utf-8"))
    REVIEW.mkdir(exist_ok=True)
    rows = queue_rows(checked, hf)
    if args.xlsx_only:
        if rows != read_jsonl(REVIEW / "review_queue.jsonl"):
            raise SystemExit("커밋된 queue와 다시 만든 행이 다르다. 입력이 바뀌었는지 확인한다")
        write_sheet(rows)
        return
    write_jsonl(REVIEW / "review_queue.jsonl", rows)
    sources = [HERE / "candidates_draft.yaml", HERE / "candidates_checked.json", HERE / "hf_outputs.json"]
    info = provenance(sources, 42)
    guard = Protection.current(GOLD_DIR)
    manifest = {**info, "batch": "batch005", "gold_dir": str(GOLD_DIR.relative_to(ROOT)), "protection": guard.manifest(),
                "source_files": {str(p.relative_to(ROOT)): sha256(p) for p in sources},
                "counts": {"queue_rows": len(rows), "sft_gold": sum(r["record_type"] == "sft_gold" for r in rows),
                           "sft_gold_t2pc_stop": sum(r["record_type"] == "sft_gold" and r["expected_outcome"] == "t2pc_stop_grounding"
                                                     for r in rows),
                           "dpo_pair": sum(r["record_type"] == "dpo_pair" for r in rows),
                           "model_output_note": sum(r["record_type"] == "model_output_note" for r in rows)},
                "approval": "none; Claude drafts and model outputs require human decisions",
                "output_hashes": {"review_queue.jsonl": sha256(REVIEW / "review_queue.jsonl")}}
    manifest["protection"].pop("fingerprints", None)
    (REVIEW / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_sheet(rows)
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
