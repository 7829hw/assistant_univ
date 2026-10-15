# -*- coding: utf-8 -*-
"""300문항 v2 semantics 초안 사람 검토 시트(W7a). batch007(``../../batch007/build_review.py``)과 같은 형식이다. 승인하지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/aug300_review/build_review.py

- 입력: ``semantics_draft.jsonl``(초안 273: train 220 + holdout 53), ``../aug300/check_results.json``(겹침), ``../aug300/status_proposals.json``,
  J3 base 첫 응답(``../aug300/base_first_response.jsonl``, train만; 원문은 ignore 경로 ``training/generated/pilot_006_prep/raw/aug300_base_first_raw.jsonl``).
- holdout 53문항은 모델 출력 열이 비어 있다(J2 셀은 봉인, 학습 데이터가 고정된 뒤에 집계).
- 출력(``review/``): ``review_queue.jsonl``, ``manifest.json``, ``aug300_review.xlsx``(결정 115로 커밋한다).
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from grounding.full_renderer import render_full  # noqa: E402
from grounding.partial_renderer import render_partial  # noqa: E402
from training.annotations.inventory import digest  # noqa: E402
from training.annotations.workflow import CHECKS  # noqa: E402
from training.data.common import read_jsonl, sha256, write_jsonl  # noqa: E402

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)

AUG = ROOT / "sft_dpo_inventory/pilot_006_prep/aug300"
RAW = ROOT / "training/generated/pilot_006_prep/raw/aug300_base_first_raw.jsonl"
REVIEW = HERE / "review"

GUIDE_ROWS = [
    ["이 시트는 무엇인가", "300문항 v2(사용자 제공 xlsx) 가운데 train 220·holdout 53문항의 semantics 초안이다. 뜻(측정값·장소·od_role·묶음·순위·집계·조건)은 "
     "xlsx의 정답 Tool 호출에서 역산했고, 질문 span(장소명·측정 표현)만 Claude가 규칙으로 붙였다(2026-10-15, pilot_006 준비 W7a)."],
    ["승인이 아니다", "초안과 검증 사슬(Full·Partial 같은 실행, 정답 호출과 같은 실행) 통과는 형식 검사다. 질문의 뜻이 맞다는 증거가 아니다. "
     "사람이 질문을 읽고 내린 결정만 승인이다."],
    ["무엇을 보나", "(1) 정답 호출 자체가 질문의 뜻과 맞는가(xlsx 정답이 틀릴 수 있다). (2) span이 질문의 그 표현을 가리키는가(빈 칸이면 규칙이 못 찾은 것). "
     "(3) od_role(출발·도착)과 dimension_target(묶는 끝), 집계어 유무, 근처·주변(vicinity)이 질문대로인가."],
    ["holdout", "holdout 53문항(augmentation_holdout_v1, 2026-10-15 고정)은 평가 전용이다. 초안 검토만 하고 학습·prompt 예시·보강 설계에 쓰지 않는다. "
     "모델 출력 열은 비어 있다(봉인)."],
    ["결정 칸", f"{B4.DECISION_CHOICES} 중 하나. 승인=초안 그대로, 수정='수정 grounding'에 JSON, 보류=이유를 메모, 제외=쓰지 않음."],
    ["vllm_outputs 시트", "train 문항에서 base 모델(Qwen3-8B, thinking 켬, vLLM BF16 greedy, J3) 첫 응답이 초안과 다른 경우. 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다. "
     "모델이 맞으면 aug300 시트의 초안을 '수정'하고 이 쌍은 '제외'."],
    ["status_proposals 시트", "저장소 겹침 도구로 다시 검사해 새로 걸린 문항(보호 셋과 같은 grounding·Jaccard ≥ 0.5)과 현재 코드에서 정답 호출이 실행되지 않는 문항. "
     "상태(train/holdout/제외/축소)는 바꾸지 않았다. 제외·보류 여부를 정한다."],
    ["가져오기", "XLSX 편집은 자동으로 가져오지 않는다. 결정은 workflow decide로 decisions 파일에 사람 이름과 함께 남긴다."],
]


def raw_answers():
    from training.data.thinking import split_response
    if not RAW.exists():
        return {}
    out = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        out[r["id"]] = split_response(r["raw_text"])[1] if "</think>" in r["raw_text"] else None
    return out


def main():
    drafts = read_jsonl(HERE / "semantics_draft.jsonl")
    check = {r["id"]: r for r in json.loads((AUG / "check_results.json").read_text(encoding="utf-8"))["items"]}
    items = {i["id"]: i for i in read_jsonl(AUG / "augmentation_300.jsonl")}
    first = {r["id"]: r for r in read_jsonl(AUG / "base_first_response.jsonl")[1:]}
    proposals = json.loads((AUG / "status_proposals.json").read_text(encoding="utf-8"))["proposals"]
    rows = []
    for rec in drafts:
        item, chk = items[rec["id"]], check[rec["id"]]
        base = {"status": "pending", "question": rec["question"], "parent_intent": f"aug300-{item['family_id']}",
                "semantic_family": item["family_id"], "category": item["semantic_type"], "expected_outcome": "answered",
                "split": item["status"], "risk_tags": item["risk_tags"],
                "provenance": {"origin": "user_supplied_xlsx_v2+claude_span_draft", "source": "aug300_v2", "source_record_id": rec["id"],
                               "xlsx_sha256": "2aeaaffb3b2ba4f0b4b47e3ec78f20d4057bf1a8ba6e01335afcb640a599a039", "authored_at": "2026-10-15"},
                "eligibility": {"eligible_after_human_review": item["status"] == "train",
                                "training_blockers": [] if item["status"] == "train" else ["augmentation_holdout_v1(evaluation only)"]},
                "review_checks": list(CHECKS), "semantic_correctness": "unreviewed", "suggestion_state": "requires_semantic_review",
                "chosen_trust": {"human_approval_required": True, "level": "claude_draft"},
                "validation_chain": {k: rec["validation"][k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")},
                "span_flags": rec["draft_flags"],
                "leakage": {"strong": chk["strong_overlap"], "new_strong": chk["new_strong_overlap"], "weak_count": len(chk["weak_overlap"]),
                            "vendor100_jaccard": chk["per_set"]["vendor100"]["jaccard_max"]}}
        gold = {**base, "candidate_id": rec["id"], "candidate_type": "targeted_gold", "record_type": "sft_gold",
                "gold_text": item["gold_text"], "proposed_grounding": render_full(rec["semantics"]),
                "proposed_partial": render_partial(rec["semantics"]), "semantics_view": rec["view"],
                "proposed_rejected": None, "model_output": None}
        gold["candidate_hash"] = digest(gold)
        rows.append(gold)
        out = first.get(rec["id"])
        if item["status"] != "train" or out is None or out["matches_gold"]:
            continue
        pair = {**base, "candidate_id": f"{rec['id']}-vllm", "candidate_type": "actual_model_prediction",
                "record_type": "dpo_pair" if out["parse_state"] == "ok" else "model_output_note",
                "proposed_grounding": render_full(rec["semantics"]), "proposed_rejected": out["parsed"],
                "negative_type": "vllm_base_prediction_mismatch", "failure_hints": out["error_tags"], "evidence": out["grounding_diffs"],
                "model_output": {k: out[k] for k in ("raw_sha256", "thinking_chars", "generated_tokens", "done_reason", "parse_state")},
                "review_question": "초안(chosen)과 모델 출력(rejected) 중 어느 쪽이 질문의 뜻에 맞는가? 모델이 맞으면 이 쌍은 제외하고 초안을 수정한다."}
        pair["candidate_hash"] = digest(pair)
        rows.append(pair)
    REVIEW.mkdir(exist_ok=True)
    write_jsonl(REVIEW / "review_queue.jsonl", rows)
    answers = raw_answers()
    blank = ["", "", "", "", ""]
    tail = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "메모", "검토자", "검토일"]
    golds = [r for r in rows if r["record_type"] == "sft_gold"]
    sheet_a = [[r["candidate_id"], r["split"], r["category"], r["semantic_family"], ", ".join(r["risk_tags"]), r["question"], r["gold_text"],
                r["semantics_view"], r["proposed_grounding"], r["proposed_partial"], ", ".join(r["span_flags"]),
                r["validation_chain"], {"new_strong": r["leakage"]["new_strong"], "vendor100_jaccard": r["leakage"]["vendor100_jaccard"]}, *blank]
               for r in golds]
    pairs = [r for r in rows if r["record_type"] != "sft_gold"]
    sheet_b = [[r["candidate_id"], r["question"], r["proposed_grounding"],
                answers.get(r["candidate_id"][:-5]) or r["proposed_rejected"] or "(본문 없음)", r["model_output"], r["evidence"], r["failure_hints"],
                r["review_question"], *blank] for r in pairs]
    sheet_c = [[p["id"], p["status_v2"], p["status_d1"], items[p["id"]]["question"], p["new_strong_overlap"], p["current_code"], p["proposal"], *blank]
               for p in proposals]
    B4.write_workbook(REVIEW / "aug300_review.xlsx", [
        ("안내", ["항목", "설명"], GUIDE_ROWS),
        ("aug300", ["id", "분할", "유형", "family", "risk_tags", "질문", "정답 호출(xlsx)", "semantics 요약", "초안 Full grounding", "초안 Partial",
                    "span 표시", "검증 사슬", "겹침(새 강한 겹침, 업체 100 Jaccard)", *tail], sheet_a),
        ("vllm_outputs", ["쌍 id", "질문", "초안(chosen)", "모델 응답 JSON 본문(rejected 후보)", "생성 정보", "차이", "오류 태그", "검토 질문", *tail], sheet_b),
        ("status_proposals", ["id", "상태(v2)", "상태(결정 106)", "질문", "새 강한 겹침", "현재 코드", "제안", *tail], sheet_c),
    ])
    manifest = {"batch": "aug300_review", "approval": "none; Claude span drafts and model outputs require human decisions",
                "counts": {"queue_rows": len(rows), "sft_gold": len(golds), "sft_gold_train": sum(r["split"] == "train" for r in golds),
                           "sft_gold_holdout": sum(r["split"] == "holdout" for r in golds),
                           "dpo_pair": sum(r["record_type"] == "dpo_pair" for r in rows),
                           "model_output_note": sum(r["record_type"] == "model_output_note" for r in rows),
                           "status_proposals": len(proposals), "span_flagged": sum(bool(r["span_flags"]) for r in golds)},
                "source_files": {str(p.relative_to(ROOT)): sha256(p) for p in (HERE / "semantics_draft.jsonl", AUG / "check_results.json",
                                                                               AUG / "status_proposals.json", AUG / "base_first_response.jsonl")},
                "raw_outputs": str(RAW.relative_to(ROOT)) + " (ignored, not committed)",
                "output_hashes": {n: sha256(REVIEW / n) for n in ("review_queue.jsonl", "aug300_review.xlsx")}}
    (REVIEW / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
