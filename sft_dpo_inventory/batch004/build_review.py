# -*- coding: utf-8 -*-
"""batch004 사람 검토 시트를 만든다(JSONL + XLSX). 승인하지 않고, 어떤 corpus에도 넣지 않는다.

    python sft_dpo_inventory/batch004/build_review.py

출력(``review/``, 커밋 대상):
- ``review_queue.jsonl`` + ``manifest.json``: thor ``training.annotations.workflow``가 읽는 queue 형식. batch004 후보의
  SFT gold 행과, HF 출력이 초안과 다른 경우의 DPO 행(rejected = 모델 출력). 결정은 ``workflow decide``로 별도 파일에 남긴다.
- ``v003_flag_items.jsonl``: reviewed_gold_v003_t2pc에서 표시한 항목(compile 정지 SFT 17, DPO 4쌍). workflow로 가져오지 않는다.
- ``decision_requests.jsonl``: 지원 불가 target 형식 결정 요청.
- ``batch004_review.xlsx``: 위 세 가지와 안내를 시트로 나눈 검토 화면. 결정·수정 grounding·메모 칸이 비어 있다.
  XLSX는 보기·기록용이며 권위 있는 기록은 JSONL과 ``workflow decide``가 만든 decisions 파일이다(thor 관례).
"""
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from training.annotations.inventory import Protection, digest  # noqa: E402
from training.annotations.workflow import CHECKS  # noqa: E402
from training.data.canonicalize import canonical_json  # noqa: E402
from training.data.common import provenance, sha256, write_jsonl  # noqa: E402

GOLD_DIR = ROOT / "training/generated/reviewed_gold_v003_t2pc"
REVIEW = HERE / "review"
DECISION_CHOICES = "승인 / 수정 / 보류 / 제외"
STOP_IDS_NOTE = "현재 코드에서 계약 오류로 멈춘다. 지원 불가 target 형식이 정해지기 전에는 학습 target으로 쓰지 않는다."


def diffs_after_condition_layer(item, payload):
    """모델 첫 응답에 조건 계층(기준일 2026-09-25)을 적용한 뒤의 초안 대비 차이. 운영 경로에서 코드가 고치는 차이를 가른다."""
    from datetime import date
    import evaluate_vendor100 as EV
    from geoflow import conditions
    from geoflow.errors import GeoFlowError
    try:
        fixed, _ = conditions.reconcile_payload(payload, item["question"], reference_date=date(2026, 9, 25))
    except GeoFlowError as error:
        return {"stopped": getattr(error, "code", type(error).__name__)}
    same, diffs = EV.grounding_check({"gold_grounding": item["draft_grounding"], "gold": None}, fixed)
    return {"matches_draft": bool(same), "grounding_diffs": json.loads(json.dumps(diffs, ensure_ascii=False))}


def queue_rows(checked, hf):
    by_id = {r["id"]: r for r in hf["rows"]}
    rows = []
    for item in checked["candidates"]:
        stop = not item["contract_ok"]["t2pc"]
        blockers = ["unsupported_target_format_undecided"] if stop else []
        base = {
            "status": "pending", "question": item["question"], "parent_intent": item["intent"],
            "semantic_family": item["family"], "contrast_group": item["family"], "category": item["type"],
            "expected_outcome": "stop_pending_format_decision" if stop else "answered",
            "provenance": {"origin": "claude_authored_review_only", "source": "batch004",
                           "source_record_id": item["id"], "authored_at": "2026-10-06",
                           "protected_sources_used": False},
            "eligibility": {"eligible_after_human_review": not stop, "training_blockers": blockers},
            "rationale": item["rationale"], "review_checks": list(CHECKS),
            "semantic_correctness": "unreviewed", "suggestion_state": "requires_semantic_review",
            "chosen_trust": {"human_approval_required": True, "level": "claude_draft"},
            "quality": item["results"]["t2pc"], "quality_by_mode": item["results"],
            "leakage": item["leakage"], "note": STOP_IDS_NOTE if stop else None,
        }
        gold = {**base, "candidate_id": item["id"], "candidate_type": "targeted_gold", "record_type": "sft_gold",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": None,
                "negative_type": None, "failure_hints": None, "evidence": [], "model_output": None}
        gold["candidate_hash"] = digest(gold)
        rows.append(gold)
        out = by_id.get(item["id"])
        if out is None or out["matches_draft"]:
            continue
        rejected, after_layer = None, None
        if out["parse_state"] == "ok":
            from geoflow.planner import parse_planner_json
            rejected = parse_planner_json(out["raw_text"])
            after_layer = diffs_after_condition_layer(item, rejected)
        pair = {**base, "candidate_id": f"{item['id']}-hf", "candidate_type": "actual_model_prediction",
                "record_type": "dpo_pair" if rejected is not None else "model_output_note",
                "proposed_grounding": item["draft_grounding"], "proposed_rejected": rejected,
                "negative_type": "hf_base_prediction_mismatch", "failure_hints": out["error_tags"],
                "evidence": out["grounding_diffs"], "diffs_after_condition_layer": after_layer,
                "model_output": {"raw_text": out["raw_text"], "parse_state": out["parse_state"],
                                 "model_quality": out["model_quality"], "source": "hf_outputs.json"},
                "review_question": "초안(chosen)과 모델 출력(rejected) 중 어느 쪽이 질문의 뜻에 맞는가? 모델이 맞으면 "
                                   "이 쌍은 제외하고 SFT 행의 초안을 수정한다."}
        pair["provenance"] = {**base["provenance"], "origin": "hf_base_prediction",
                              "model": "Qwen/Qwen3-8B@b968826d", "enable_thinking": False}
        pair["eligibility"] = {"eligible_after_human_review": rejected is not None and not stop,
                               "training_blockers": blockers + ([] if rejected is not None else ["no_parseable_rejected"])}
        pair["candidate_hash"] = digest(pair)
        rows.append(pair)
    return rows


def v003_rows():
    flags = json.loads((ROOT / "training/records/corpora/reviewed_gold_v003_t2pc/review_flags.json").read_text())
    index = json.loads((ROOT / "training/records/corpora/reviewed_gold_v003/dataset_index.json").read_text())
    rows = []
    for flag in flags["sft"]:
        if not any(m.startswith("compile_stop") for m in flag["marks"]):
            continue
        record = index[f"sft_{flag['split']}"][flag["position"]]
        rows.append({"item_id": f"v003-sft-{flag['split']}-{flag['position']:02d}", "kind": "sft_compile_stop",
                     "source_record_id": flag["source_record_id"], "batch_item_ids": flag["batch_item_ids"],
                     "split": flag["split"], "question": record["messages"][1]["content"],
                     "target": json.loads(record["messages"][-1]["content"]), "marks": flag["marks"],
                     "options": "SFT 유지(실행 benchmark에서만 제외) / SFT에서 제외 / 보류",
                     "context": "grounding 계약은 통과한다. mock·legacy 실행 계약에서 주·월 구간 + rollup 계산 방법이 확인되지 않아 compile에서 멈춘다."})
    for flag in flags["dpo"]:
        marks = [m for m in flag["marks"] if m.startswith("t2pc_")]
        if not marks:
            continue
        record = index[f"dpo_{flag['split']}"][flag["position"]]
        kind = "dpo_rejected_equals_chosen" if "t2pc_rejected_equals_chosen" in marks else "dpo_constraint_rejected_executable"
        rows.append({"item_id": f"v003-dpo-{flag['split']}-{flag['position']:02d}", "kind": kind,
                     "source_record_id": flag["source_record_id"], "batch_item_ids": flag["batch_item_ids"],
                     "split": flag["split"], "question": record["prompt"][1]["content"],
                     "negative_type": flag["negative_type"], "negative_category": flag["negative_category"],
                     "chosen": json.loads(record["chosen"][0]["content"]),
                     "rejected": json.loads(record["rejected"][0]["content"]), "marks": marks,
                     "t2pc_rejected": flag["t2pc"]["rejected"],
                     "options": ("유지(원응답 수준 선호로 둠) / 제외 / 보류" if kind == "dpo_rejected_equals_chosen"
                                 else "유지(constraint) / semantic으로 재분류 / 제외 / 보류"),
                     "context": ("조건 계층을 거치면 rejected가 chosen과 같아진다. 운영 경로의 최종 grounding에서는 차이가 없다."
                                 if kind == "dpo_rejected_equals_chosen" else
                                 "thor에서는 parse 단계 실패(constraint)였지만 T2PC 경로에서는 조건 계층의 날짜 교정 뒤 계약을 통과해 실행된다. 장소가 빠진 다른 의미의 답이 된다.")})
    return rows


DECISION_REQUESTS = [{
    "item_id": "decision-unsupported-target-format",
    "question": "지원 불가(또는 확인 요청) 질문의 학습 target 형식을 무엇으로 할까?",
    "options": ['{"unsupported": true} (thor 형식)',
                "T2PC식 정지 grounding: 질문의 조건을 grounding으로 적고 코드가 멈춘다(현재 prompt의 계약)",
                "보류(이번 학습에서 지원 불가 target을 쓰지 않음)"],
    "context": ("현재 prompt(87048d0c)는 측정값·조건을 적을 수 있으면 실행 가능 여부와 관계없이 grounding을 적으라고 한다. "
                "thor corpus와 registry paraphrase corpus의 지원 불가 라벨 54 intent는 {\"unsupported\": true}다. batch004의 "
                "b004-34/35/40/41은 현재 코드에서 계약 오류로 멈추는 질문이며 이 결정을 기다린다."),
    "affects": ["b004-34", "b004-35", "b004-40", "b004-41", "thor unsupported 라벨", "registry corpus unsupported intent 54"]}]


def _cell(value):
    if value is None:
        return ""
    text = value if isinstance(value, str) else canonical_json(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text if len(text) <= 32700 else text[:32700] + " … 전체 내용은 JSONL"


def _letter(n):
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(65 + r) + out
    return out


def _sheet_xml(columns, rows):
    xml_rows = []
    for i, cells in enumerate([list(columns)] + rows, 1):
        parts = [f'<c r="{_letter(j)}{i}" t="inlineStr"><is><t xml:space="preserve">{escape(_cell(c))}</t></is></c>'
                 for j, c in enumerate(cells, 1)]
        xml_rows.append(f'<row r="{i}">' + "".join(parts) + "</row>")
    return ('<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>'
            "<sheetData>" + "".join(xml_rows) + "</sheetData>"
            f'<autoFilter ref="A1:{_letter(len(columns))}{len(rows) + 1}"/></worksheet>')


def write_workbook(path, sheets):
    """의존성 없는 XLSX(문자열 셀만, 수식 없음). sheets = [(이름, 열 목록, 행 목록)]."""
    names = [name for name, _, _ in sheets]
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets) + 1))
        + "</Types>",
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)) + "</sheets></workbook>",
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
        + "</Relationships>",
    }
    for i, (_, columns, rows) in enumerate(sheets, 1):
        files[f"xl/worksheets/sheet{i}.xml"] = _sheet_xml(columns, rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value.encode("utf-8"))


GUIDE_ROWS = [
    ["이 시트는 무엇인가", "batch004 annotation 후보(Claude 초안), 같은 질문에 대한 base 모델(Qwen3-8B, thinking 끔) 출력, "
     "reviewed_gold_v003_t2pc에서 표시한 항목, 결정 요청을 모은 사람 검토 화면이다."],
    ["승인이 아니다", "초안 gold와 근거는 Claude가 썼다. validator·compose·compile 통과는 형식 검사일 뿐 질문의 뜻이 맞다는 증거가 아니다. "
     "사람이 질문을 읽고 판단한 결정만 승인이다."],
    ["결정 칸", f"{DECISION_CHOICES} 중 하나를 적는다. 승인=초안 그대로 학습에 써도 된다. 수정=뜻을 고친 grounding을 '수정 grounding' 칸에 "
     "JSON으로 적는다. 보류=지금 판단할 수 없다(이유를 메모에). 제외=학습에 쓰지 않는다."],
    ["batch004 시트 열", "후보 id, 유형(공백 유형), family(대조 묶음), 질문, 초안 grounding, 근거, 현재 코드 결과(T2PC 경로: 계약·compile), "
     "보호 셋 겹침(확장 대조, 정보), 비고, 결정, 수정 grounding, 메모, 검토자, 검토일."],
    ["hf_outputs 시트 열", "후보 id, 질문, 초안 grounding, 모델 첫 응답 원문, 초안과의 차이(grounding_diffs), 오류 태그, 질문. "
     "초안과 모델 중 어느 쪽이 맞는지 먼저 정한다. 모델이 맞으면 batch004 시트의 해당 초안을 '수정'하고 이 쌍은 '제외'한다. "
     "초안이 맞고 모델이 틀렸으면 '승인'(이 쌍을 DPO rejected로 쓴다)."],
    ["판단 기준", "(1) 측정값 subtype과 사건이 질문과 맞는가(통행량=passage_count, 실차 건수=trip_count, 공차율=vacant_ratio). "
     "(2) 질문에 있는 조건만 있는가(날짜·시간·택시 유형·운행 상태·근처). 없는 조건을 지어내지 않았는가. "
     "(3) 집계어가 없으면 aggregation을 적지 않았는가. (4) 장소의 od_role(장소가 제한하는 끝)과 dimension_target(묶는 끝)을 "
     "구분했는가. (5) 그룹 단위(시도·시군구·읍면동·요일)가 질문과 같은가. (6) 문장이 보호된 평가 셋의 문장을 바꿔 쓴 것처럼 "
     "보이면 '제외'하고 메모한다."],
    ["v003_flags 시트", "reviewed_gold_v003_t2pc에서 표시만 하고 빼지 않은 항목이다. 각 행의 '선택지'에서 처분을 고른다."],
    ["결정 요청 시트", "지원 불가 target 형식. batch004의 정지 후보 4건과 기존 unsupported 라벨이 이 결정을 기다린다."],
    ["가져오기", "XLSX 편집은 자동으로 가져오지 않는다. 결정은 workflow decide로 decisions 파일에 사람 이름과 함께 남긴다(review/README.md)."],
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx-only", action="store_true",
                        help="커밋된 queue·manifest를 바꾸지 않고 XLSX(ignored)만 다시 만든다")
    args = parser.parse_args()
    checked = json.loads((HERE / "candidates_checked.json").read_text(encoding="utf-8"))
    hf = json.loads((HERE / "hf_outputs.json").read_text(encoding="utf-8"))
    REVIEW.mkdir(exist_ok=True)
    rows = queue_rows(checked, hf)
    flags = v003_rows()
    if args.xlsx_only:
        from training.data.common import read_jsonl
        if rows != read_jsonl(REVIEW / "review_queue.jsonl") or flags != read_jsonl(REVIEW / "v003_flag_items.jsonl"):
            raise SystemExit("커밋된 queue와 다시 만든 행이 다르다. 입력이 바뀌었는지 확인한다")
        manifest = json.loads((REVIEW / "manifest.json").read_text(encoding="utf-8"))
        write_sheet(rows, flags)
        print(json.dumps(manifest["counts"], ensure_ascii=False))
        return
    write_jsonl(REVIEW / "review_queue.jsonl", rows)
    write_jsonl(REVIEW / "v003_flag_items.jsonl", flags)
    write_jsonl(REVIEW / "decision_requests.jsonl", DECISION_REQUESTS)
    sources = [HERE / "candidates_draft.yaml", HERE / "candidates_checked.json", HERE / "hf_outputs.json"]
    info = provenance(sources, 42)
    guard = Protection.current(GOLD_DIR)
    manifest = {**info, "batch": "batch004", "gold_dir": str(GOLD_DIR.relative_to(ROOT)),
                "protection": guard.manifest(),
                "source_files": {str(p.relative_to(ROOT)): sha256(p) for p in sources},
                "counts": {"queue_rows": len(rows), "sft_gold": sum(r["record_type"] == "sft_gold" for r in rows),
                           "dpo_pair": sum(r["record_type"] == "dpo_pair" for r in rows),
                           "model_output_note": sum(r["record_type"] == "model_output_note" for r in rows),
                           "v003_flag_items": len(flags), "decision_requests": len(DECISION_REQUESTS)},
                "approval": "none; Claude drafts and model outputs require human decisions",
                "output_hashes": {"review_queue.jsonl": sha256(REVIEW / "review_queue.jsonl"),
                                  "v003_flag_items.jsonl": sha256(REVIEW / "v003_flag_items.jsonl"),
                                  "decision_requests.jsonl": sha256(REVIEW / "decision_requests.jsonl")}}
    manifest["protection"].pop("fingerprints", None)   # 지문 목록은 크다. source_hashes로 대조한다
    (REVIEW / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_sheet(rows, flags)
    print(json.dumps(manifest["counts"], ensure_ascii=False))


def write_sheet(rows, flags):
    blank = ["", "", "", "", ""]
    tail_cols = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "메모", "검토자", "검토일"]
    gold_rows = [r for r in rows if r["record_type"] == "sft_gold"]
    sheet_b004 = [[r["candidate_id"], r["category"], r["semantic_family"], r["question"], r["proposed_grounding"],
                   r["rationale"],
                   {"t2pc_contract_ok": r["eligibility"]["eligible_after_human_review"] or r["note"] is None,
                    "outcome": r["quality"].get("outcome"), "error_code": r["quality"].get("error_code"),
                    "compile_ok": r["quality"].get("compile_ok")},
                   r["leakage"]["extended_overlap_info_only"], r["note"] or "", *blank] for r in gold_rows]
    pair_rows = [r for r in rows if r["record_type"] != "sft_gold"]
    sheet_hf = [[r["candidate_id"], r["question"], r["proposed_grounding"], r["model_output"]["raw_text"],
                 r["evidence"], r["diffs_after_condition_layer"], r["failure_hints"], r["review_question"], *blank]
                for r in pair_rows]
    sheet_v003 = [[f["item_id"], f["kind"], f["split"], ",".join(f["batch_item_ids"]) or f["source_record_id"], f["question"],
                   f.get("target") or {"chosen": f.get("chosen"), "rejected": f.get("rejected")}, f["context"],
                   f["options"], "", "", "", ""] for f in flags]
    sheet_req = [[d["item_id"], d["question"], " | ".join(d["options"]), d["context"], ", ".join(d["affects"]),
                  "", "", "", ""] for d in DECISION_REQUESTS]
    write_workbook(REVIEW / "batch004_review.xlsx", [
        ("안내", ["항목", "설명"], GUIDE_ROWS),
        ("batch004", ["후보 id", "유형", "family", "질문", "초안 grounding", "근거", "현재 코드 결과(T2PC)",
                      "평가 셋 겹침(확장 대조, 정보)", "비고", *tail_cols], sheet_b004),
        ("hf_outputs", ["쌍 id", "질문", "초안 grounding(chosen)", "모델 첫 응답(rejected 후보)", "차이(grounding_diffs, 첫 응답)",
                        "조건 계층 적용 뒤 차이(참고)", "오류 태그", "검토 질문", *tail_cols], sheet_hf),
        ("v003_flags", ["항목 id", "종류", "split", "출처 id", "질문", "target 또는 chosen/rejected", "설명", "선택지",
                        "결정", "메모", "검토자", "검토일"], sheet_v003),
        ("결정요청", ["항목 id", "질문", "선택지", "설명", "영향", "결정", "메모", "검토자", "검토일"], sheet_req),
    ])


if __name__ == "__main__":
    main()
