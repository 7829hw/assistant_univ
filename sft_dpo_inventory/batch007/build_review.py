# -*- coding: utf-8 -*-
"""batch007 사람 검토 시트를 만든다(JSONL + XLSX). 승인하지 않고, 어떤 corpus에도 넣지 않는다(결정 104).

    python sft_dpo_inventory/batch007/build_review.py [--xlsx-only]

batch006(``../batch006/build_review.py``)와 같은 형식이다. 다른 점: 모델 출력이 vLLM BF16 base(greedy)이고(``vllm_outputs.json``, 시트 이름 vllm_outputs),
대조가 다섯 가지(occupied·vacant·plain·trip_pickup·trip_dropoff)이며, 학습 데이터 기준이 ``reviewed_gold_v006_t2pc``다. 그 밖은 batch006과 같다:
- 응답 원문(thinking 포함)은 커밋하지 않는다. queue의 ``model_output``에는 원문 sha256·경로(ignore)·길이·종료 이유와 파싱한 JSON만 둔다.
  XLSX의 "모델 응답 JSON 본문" 칸은 ignore 경로의 원문에서 본문을 잘라 채운다(원문이 없으면 파싱한 JSON을 쓴다).
- 결정 6 표시: 조건 계층 뒤 초안과 같아지는 차이(운영 경로에서 뜻이 같아짐)는 ``decision_6_same_after_condition_layer``로 표시한다.
  그런 쌍은 DPO 쌍으로 쓰지 않는 것이 결정 6이다. 표시만 하고 빼지 않는다(검토자가 확인한다).
- 대조 묶음(결정 104): family = 의도, variant = occupied·vacant·plain·trip_pickup·trip_dropoff.
출력(``review/``): ``review_queue.jsonl`` + ``manifest.json``(커밋), ``batch007_review.xlsx``(``*.xlsx`` ignore, ``--xlsx-only``로 다시 만든다).
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

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v006_t2pc"
RAW = ROOT / "training/generated/batch007/raw/vllm_outputs_raw.jsonl"
SUFFIX = "-vllm"
REVIEW = HERE / "review"
VARIANT_NOTE = {
    "occupied": "'실차' 없이 손님·승객이 탄 택시의 통행량 = passage_count + taxi_status occupied(결정 62·66·104)",
    "vacant": "빈 택시(손님 없이 다닌 택시)의 통행량 = passage_count + taxi_status vacant",
    "plain": "상태 없는 통행량 = passage_count(taxi_status 없음)",
    "trip_pickup": "손님을 태운 건수 = 승차 실차 건수 = trip_count(taxi_status 없음, 장소 od_role pickup, dimension_target pickup)",
    "trip_dropoff": "손님을 내려준 건수 = 하차 실차 건수 = trip_count(taxi_status 없음, 장소 od_role dropoff, dimension_target dropoff)",
}


def raw_answers():
    from training.data.thinking import split_response
    if not RAW.exists():
        return {}
    out = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        out[r["id"]] = split_response(r["raw_text"])[1] if "</think>" in r["raw_text"] else None
    return out


def queue_rows(checked, vo):
    by_id = {r["id"]: r for r in vo["rows"]}
    rows = []
    for item in checked["candidates"]:
        base = {
            "status": "pending", "question": item["question"], "parent_intent": item["intent"],
            "semantic_family": item["family"], "contrast_group": item["family"], "category": item["type"],
            "contrast_variant": item["variant"], "expected_outcome": "answered",
            "provenance": {"origin": "claude_authored_review_only", "source": "batch007",
                           "source_record_id": item["id"], "authored_at": "2026-10-15",
                           "protected_sources_used": False, "basis": "decision 104: occupied traffic without the word 실차 (selection_v2 n33 gap)"},
            "eligibility": {"eligible_after_human_review": True, "training_blockers": []},
            "rationale": item["rationale"], "review_checks": list(CHECKS),
            "semantic_correctness": "unreviewed", "suggestion_state": "requires_semantic_review",
            "chosen_trust": {"human_approval_required": True, "level": "claude_draft"},
            "quality": item["results"]["t2pc"], "quality_by_mode": item["results"],
            "leakage": item["leakage"], "note": VARIANT_NOTE[item["variant"]],
        }
        gold = {**base, "candidate_id": item["id"], "candidate_type": "targeted_gold", "record_type": "sft_gold",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": None,
                "negative_type": None, "failure_hints": None, "evidence": [], "model_output": None}
        gold["candidate_hash"] = digest(gold)
        rows.append(gold)
        out = by_id.get(item["id"])
        if out is None or out["matches_draft"]:
            continue
        rejected = out["parsed"] if out["parse_state"] == "ok" else None
        after_layer = B4.diffs_after_condition_layer(item, rejected) if rejected is not None else None
        same_after = bool(after_layer and after_layer.get("matches_draft"))
        pair = {**base, "candidate_id": f"{item['id']}{SUFFIX}", "candidate_type": "actual_model_prediction",
                "record_type": "dpo_pair" if rejected is not None else "model_output_note",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": rejected,
                "negative_type": "vllm_base_prediction_mismatch", "failure_hints": out["error_tags"],
                "evidence": out["grounding_diffs"], "diffs_after_condition_layer": after_layer,
                "decision_6_same_after_condition_layer": same_after,
                "model_output": {"raw_sha256": out["raw_sha256"], "raw_out": "training/generated/batch007/raw/vllm_outputs_raw.jsonl",
                                 "thinking_chars": out["thinking_chars"], "generated_tokens": out["generated_tokens"],
                                 "done_reason": out["done_reason"], "parse_state": out["parse_state"],
                                 "model_quality": out["model_quality"], "source": "vllm_outputs.json"},
                "review_question": "초안(chosen)과 모델 출력(rejected) 중 어느 쪽이 질문의 뜻에 맞는가? 모델이 맞으면 "
                                   "이 쌍은 제외하고 SFT 행의 초안을 수정한다."
                                   + (" 조건 계층 뒤 초안과 같아진다(결정 6: DPO 쌍으로 쓰지 않음)." if same_after else "")}
        pair["provenance"] = {**base["provenance"], "origin": "vllm_base_prediction",
                              "model": "Qwen/Qwen3-8B@b968826d", "engine": "vllm 0.30.0 BF16 flashinfer, greedy",
                              "enable_thinking": True, "max_new_tokens": 8192}
        blockers = [] if rejected is not None else ["no_parseable_rejected"]
        if same_after:
            blockers.append("decision_6_same_after_condition_layer")
        pair["eligibility"] = {"eligible_after_human_review": not blockers, "training_blockers": blockers}
        pair["candidate_hash"] = digest(pair)
        rows.append(pair)
    return rows


GUIDE_ROWS = [
    ["이 시트는 무엇인가", "batch007 annotation 후보(Claude 초안, 결정 104: '실차'라는 말 없이 운행 상태를 표현한 통행량과 헷갈리는 대조)와 "
     "같은 질문에 대한 base 모델(Qwen3-8B, thinking 켬, vLLM BF16 greedy) 첫 응답을 모은 사람 검토 화면이다."],
    ["승인이 아니다", "초안 gold와 근거는 Claude가 썼다. validator·compose·compile 통과는 형식 검사일 뿐 질문의 뜻이 맞다는 증거가 아니다. "
     "사람이 질문을 읽고 판단한 결정만 승인이다."],
    ["대조 묶음", "의도 7개마다 같은 장소·날짜·시간·묶음 기준으로 네 질문을 만들었다. occupied='실차' 없이 손님·승객이 탄 택시의 통행량"
     "(passage_count + taxi_status occupied), vacant=빈 택시의 통행량(+ vacant), plain=상태 없는 통행량(passage_count), trip_pickup=손님을 태운 "
     "건수(trip_count, 승차), trip_dropoff=손님을 내려준 건수(trip_count, 하차). 같은 의도 안의 질문 정답이 서로 구별되는지 함께 본다."],
    ["결정 칸", f"{B4.DECISION_CHOICES} 중 하나를 적는다. 승인=초안 그대로 학습에 써도 된다. 수정=뜻을 고친 grounding을 '수정 grounding' 칸에 "
     "JSON으로 적는다. 보류=지금 판단할 수 없다(이유를 메모에). 제외=학습에 쓰지 않는다."],
    ["batch007 시트 열", "후보 id, 대조(variant), family(의도), 질문, 초안 grounding, 근거, 현재 코드 결과(T2PC 경로: 계약·멈춤 코드·compile), "
     "겹침 검사(업체 100 문자 3-gram 최댓값), 비고, 결정, 수정 grounding, 메모, 검토자, 검토일."],
    ["vllm_outputs 시트 열", "쌍 id, 대조, 질문, 초안 grounding, 모델 응답 JSON 본문, thinking 길이·생성 token·종료 이유, 초안과의 차이(첫 응답 기준), "
     "조건 계층 적용 뒤 차이(참고), 결정 6 표시, 오류 태그, 검토 질문. 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다. 모델이 맞으면 batch007 "
     "시트의 해당 초안을 '수정'하고 이 쌍은 '제외'한다. 초안이 맞고 모델이 틀렸으면 '승인'(DPO rejected 후보)."],
    ["결정 6 표시", "조건 계층을 적용하면 초안과 같아지는 쌍이다. 운영 경로에서 코드가 고쳐 뜻이 같아지므로 DPO 쌍으로 쓰지 않는다(결정 6). "
     "표시가 맞는지 확인하고 '제외'로 둔다."],
    ["판단 기준", "(1) 손님·승객이 탄 택시의 통행량(지나간 양)은 passage_count + taxi_status occupied, 손님을 태운·내려준 건수는 "
     "trip_count다. '실차'라는 말이 없어도 운행 상태 표현이면 occupied·vacant다. '태운'이 있어도 측정이 통행량이면 trip_count로 읽지 않는다. (2) 질문에 없는 운행 상태·집계·묶음을 지어내지 않는다. (3) 통행량(passage)에는 장소 od_role과 dimension_target이 없다. "
     "(4) 실차 건수(trip)는 장소가 제한하는 끝(od_role)과 묶는 끝(dimension_target)을 질문대로 적는다. (5) 근처·주변이 있을 때만 vicinity. "
     "(6) 문장이 보호된 평가 셋 문장을 바꿔 쓴 것처럼 보이면 '제외'하고 메모한다."],
    ["가져오기", "XLSX 편집은 자동으로 가져오지 않는다. 결정은 workflow decide로 decisions 파일에 사람 이름과 함께 남긴다(review/README.md)."],
]


def write_sheet(rows):
    answers = raw_answers()
    blank = ["", "", "", "", ""]
    tail = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "메모", "검토자", "검토일"]
    gold_rows = [r for r in rows if r["record_type"] == "sft_gold"]
    sheet_b = [[r["candidate_id"], r["contrast_variant"], r["semantic_family"], r["question"], r["proposed_grounding"], r["rationale"],
                {"outcome": r["quality"].get("outcome"), "error_code": r["quality"].get("error_code"),
                 "compile_ok": r["quality"].get("compile_ok")},
                r["leakage"]["vendor100_char3_jaccard_top"][0], r["note"] or "", *blank] for r in gold_rows]
    pair_rows = [r for r in rows if r["record_type"] != "sft_gold"]
    sheet_hf = [[r["candidate_id"], r["contrast_variant"], r["question"], r["proposed_grounding"],
                 answers.get(r["candidate_id"][:-len(SUFFIX)]) or r["proposed_rejected"] or "(본문 없음)",
                 {k: r["model_output"][k] for k in ("thinking_chars", "generated_tokens", "done_reason", "parse_state")},
                 r["evidence"], r["diffs_after_condition_layer"], "결정 6: 조건 계층 뒤 같음" if r["decision_6_same_after_condition_layer"] else "",
                 r["failure_hints"], r["review_question"], *blank] for r in pair_rows]
    B4.write_workbook(REVIEW / "batch007_review.xlsx", [
        ("안내", ["항목", "설명"], GUIDE_ROWS),
        ("batch007", ["후보 id", "대조", "family(의도)", "질문", "초안 grounding", "근거", "현재 코드 결과(T2PC)", "업체 100 3-gram 최댓값",
                      "비고", *tail], sheet_b),
        ("vllm_outputs", ["쌍 id", "대조", "질문", "초안 grounding(chosen)", "모델 응답 JSON 본문(rejected 후보)", "thinking·생성",
                        "차이(첫 응답)", "조건 계층 적용 뒤 차이(참고)", "결정 6", "오류 태그", "검토 질문", *tail], sheet_hf),
    ])


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-only", action="store_true")
    args = parser.parse_args()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    vo = json.loads((HERE / "vllm_outputs.json").read_text(encoding="utf-8"))
    REVIEW.mkdir(exist_ok=True)
    rows = queue_rows(checked, vo)
    if args.xlsx_only:
        if rows != read_jsonl(REVIEW / "review_queue.jsonl"):
            raise SystemExit("커밋된 queue와 다시 만든 행이 다르다. 입력이 바뀌었는지 확인한다")
        write_sheet(rows)
        return
    write_jsonl(REVIEW / "review_queue.jsonl", rows)
    sources = [HERE / "candidates_draft.yaml", HERE / "candidates_checked.json", HERE / "vllm_outputs.json"]
    info = provenance(sources, 42)
    guard = Protection.current(GOLD_DIR)
    pairs = [r for r in rows if r["record_type"] != "sft_gold"]
    manifest = {**info, "batch": "batch007", "gold_dir": str(GOLD_DIR.relative_to(ROOT)), "protection": guard.manifest(),
                "source_files": {str(p.relative_to(ROOT)): sha256(p) for p in sources},
                "counts": {"queue_rows": len(rows), "sft_gold": sum(r["record_type"] == "sft_gold" for r in rows),
                           "dpo_pair": sum(r["record_type"] == "dpo_pair" for r in rows),
                           "dpo_pair_decision_6_marked": sum(r.get("decision_6_same_after_condition_layer", False) for r in pairs),
                           "model_output_note": sum(r["record_type"] == "model_output_note" for r in rows)},
                "approval": "none; Claude drafts and model outputs require human decisions",
                "raw_outputs": "training/generated/batch007/raw/vllm_outputs_raw.jsonl (ignored, not committed)",
                "output_hashes": {"review_queue.jsonl": sha256(REVIEW / "review_queue.jsonl")}}
    manifest["protection"].pop("fingerprints", None)
    (REVIEW / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_sheet(rows)
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
