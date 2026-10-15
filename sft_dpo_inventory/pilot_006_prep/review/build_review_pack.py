# -*- coding: utf-8 -*-
"""C4: 사람 검토를 빨리 끝내기 위한 보조 자료(새 버전 시트). 원본 시트·검토 상태는 바꾸지 않는다. 승인 아님. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/review/build_review_pack.py

출력:
- ``aug300_review/review/aug300_review_v2.xlsx``: 273문항(결정 119로 제외된 13은 "검토 불필요") + 신호 열 + 우선순위.
- ``batch007/review/batch007_review_v2.xlsx``: 27 + 신호(batch007 base greedy, J1 표본) + 우선순위.
- ``batch008/review/batch008_review_v1.xlsx``: 남은 10 + 신호(J7) + 우선순위.
- ``pg_imports/review/pg_edit_required_v1.xlsx``: EDIT_REQUIRED 7 — pg 수정 전·후, 수정안 초안(Claude)과 근거.
- ``review/priority_counts.json``: 우선순위별 건수와 예상 소요 시간.

우선순위 규칙(결과를 보기 전에 정한 것이 아니라 검토 순서를 정하는 보조 규칙이다. 판정·상태에는 쓰지 않는다):
- 어려운 risk tag = dt_pickup·dt_dropoff·dt_both·od_both_dt_one·occupied_passage·silcha_trip·vicinity·bucket_week·bucket_month.
- aug300 train: **높음** = J1 표본 9개 중 초안과 같은 grounding ≤ 3, 또는 J3 첫 응답이 초안과 다르고 J1 ≤ 5, 또는 span 미확인, 또는 어려운 tag.
  **낮음** = J3 일치이고 J1 ≥ 7이고 span 확인이고 어려운 tag 없음. 그 밖 **보통**.
- aug300 holdout(모델 출력 봉인): 높음 = span 미확인 또는 어려운 tag, 그 밖 보통.
- batch007·batch008: 높음 = base greedy 첫 응답이 초안과 다르거나(J1이 있으면) J1 ≤ 3, 그 밖 보통. pg EDIT_REQUIRED: 모두 높음.
예상 시간 가정: 높음 2분, 보통 1분, 낮음 0.5분, 모델 출력 비교 쌍 1분, pg 수정 검토 3분(문항당).
"""
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from training.data.common import read_jsonl  # noqa: E402

_spec = importlib.util.spec_from_file_location("b004_review", ROOT / "sft_dpo_inventory/batch004/build_review.py")
B4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B4)

INV = ROOT / "sft_dpo_inventory"
HARD = {"dt_pickup", "dt_dropoff", "dt_both", "od_both_dt_one", "occupied_passage", "silcha_trip", "vicinity", "bucket_week", "bucket_month"}
MIN = {"높음": 2.0, "보통": 1.0, "낮음": 0.5}
TAIL = ["결정(승인/수정/보류/제외)", "수정 grounding(JSON)", "메모", "검토자", "검토일"]
BLANK = [""] * 5


def j1_counts():
    j = json.loads((INV / "pilot_006_prep/self_samples/j1_judgement.json").read_text(encoding="utf-8"))
    return {q["id"]: q for q in j["per_question"]}


def first(path, skip_header=True):
    rows = read_jsonl(path)
    return {r["id"]: r for r in (rows[1:] if skip_header else rows)}


def aug300(j1):
    drafts = read_jsonl(INV / "pilot_006_prep/aug300_review/semantics_draft.jsonl")
    e4 = {r["id"]: r for r in json.loads((INV / "pilot_006_prep/aug300/status_e4.json").read_text(encoding="utf-8"))["items"]}
    j3 = first(INV / "pilot_006_prep/aug300/base_first_response.jsonl")
    items = {i["id"]: i for i in read_jsonl(INV / "pilot_006_prep/aug300/augmentation_300.jsonl")}
    rows, counts = [], Counter()
    for d in drafts:
        i = d["id"]
        st = e4[i]["status_e4"]
        tags = set(items[i]["risk_tags"])
        span = bool(d["draft_flags"])
        j3m = j3[i]["matches_gold"] if i in j3 else None
        j1c = j1[i]["correct"] if i in j1 else None
        if st == "제외":
            pr = "검토 불필요(결정 119 제외)"
        elif st == "holdout":
            pr = "높음" if span or tags & HARD else "보통"
        else:
            if (j1c is not None and j1c <= 3) or (j3m is False and (j1c or 0) <= 5) or span or tags & HARD:
                pr = "높음"
            elif j3m and (j1c or 0) >= 7 and not span:
                pr = "낮음"
            else:
                pr = "보통"
        counts[pr] += 1
        rows.append([i, st, pr, items[i]["semantic_type"], ", ".join(sorted(tags)), d["question"], items[i]["gold_text"], d["view"],
                     "" if j3m is None else ("같음" if j3m else "다름"), "" if j1c is None else f"{j1c}/9",
                     "미확인: " + ", ".join(d["draft_flags"]) if span else "확인", d["validation"]["ok"], *BLANK])
    order = {"높음": 0, "보통": 1, "낮음": 2}
    rows.sort(key=lambda r: (order.get(r[2], 3), r[0]))
    pairs = sum(1 for i, r in j3.items() if not r["matches_gold"] and e4.get(i, {}).get("status_e4") == "train")
    guide = [["무엇인가", "300문항 v2 semantics 초안 검토 시트 v2(원본 v1 `aug300_review.xlsx`는 그대로). 신호 열과 우선순위를 더했다. 승인 아님."],
             ["신호 열", "J3 = base greedy 첫 응답(vLLM BF16)이 초안과 같은가. J1 = base 표본 9개(greedy 1 + sampling 8) 중 초안과 같은 grounding(조건 계층 전) 수. "
              "span = 측정 표현 span을 규칙이 찾았는가. risk tag = xlsx 열. holdout은 모델 출력이 봉인이라 신호가 비어 있다."],
             ["우선순위", "높음 = J1 ≤ 3/9, 또는 J3 다름이고 J1 ≤ 5/9, 또는 span 미확인, 또는 어려운 tag(dt·OD endpoint·실차·vicinity·bucket). "
              "낮음 = J3 같음, J1 ≥ 7/9, span 확인, 어려운 tag 없음. 그 밖 보통. 위에서부터 보면 된다. 우선순위는 판정이 아니다."],
             ["base와 다르면", "base 모델이 초안과 다르게 답한 문항은 초안이 틀렸을 수도, 모델이 틀렸을 수도 있다. xlsx 정답 호출과 질문을 직접 대조한다."],
             ["결정 칸", "승인 / 수정 / 보류 / 제외, 수정 grounding(JSON), 메모, 검토자, 검토일. 상세는 pilot_006_prep/review_guide.md"]]
    B4.write_workbook(INV / "pilot_006_prep/aug300_review/review/aug300_review_v2.xlsx", [
        ("안내", ["항목", "설명"], guide),
        ("aug300", ["id", "상태(결정 119)", "우선순위", "유형", "risk_tags", "질문", "정답 호출(xlsx)", "semantics 요약", "J3 첫 응답", "J1 일치(9개 중)",
                    "span", "검증 사슬", *TAIL], rows)])
    return counts, pairs


def contrast(name, items, base_out, j1):
    rows, counts = [], Counter()
    for it in items:
        i = it["id"]
        bm = base_out.get(i, {}).get("matches_gold", base_out.get(i, {}).get("matches_draft"))
        j1c = j1[i]["correct"] if i in j1 else None
        pr = "높음" if (bm is False) or (j1c is not None and j1c <= 3) else "보통"
        counts[pr] += 1
        rows.append([i, pr, it.get("variant") or it.get("gap"), it["question"], it.get("draft_grounding") or it.get("gold"), it.get("rationale", ""),
                     "" if bm is None else ("같음" if bm else "다름"), "" if j1c is None else f"{j1c}/9", *BLANK])
    rows.sort(key=lambda r: (r[1] != "높음", r[0]))
    return rows, counts


def pg_edit():
    rows = [r for r in read_jsonl(INV / "pg_imports/pg_batch006/approved.jsonl") if r["review_decision"] == "EDIT_REQUIRED"]
    notes = {
        "pg-b006-09": ("pg 수정(측정 text 삭제)을 그대로 쓴다. 남은 쟁점: '어디서 타서 어디서 내렸는지를 동 단위 짝' = 승차·하차 읍면동 쌍 묶음 = dimension emd + dimension_target both가 맞는지.",
                       "dimension_target both가 'OD 쌍으로 묶음'을 뜻하는지 확인(계약 문서 기준). 맞으면 승인."),
        "pg-b006-21": ("pg 수정 그대로. 남은 쟁점은 b006-09와 같다(h3 쌍, both).", "b006-09와 같이 판단."),
        "pg-b006-27": ("pg 수정(측정 text '택시' 삭제) 그대로. od_role pickup(동성로에서 태움) ≠ dimension_target dropoff(내려준 위치로 나눔) — od≠dt 예.", "승인 권고."),
        "pg-b006-17": ("pg 수정본 질문 '부산진구에서 손님을 내려준 곳 중 하차가 가장 적은 H3 셀 세 개'. od_role dropoff + dt dropoff + bottom 3. 측정 text '하차'.",
                       "'부산진구에서 내려준'이 하차 제한으로 읽힌다. 승인 권고. (batch008 b008-10·18과 같은 동사형 endpoint 계열)"),
        "pg-b006-33": ("pg 수정본 '대구에 도착한 실차를 출발한 시도 기준으로'. od_role dropoff + dt pickup + sido, 순위 없음.", "승인 권고(순위 없는 dt 예)."),
        "pg-b006-26": ("pg 수정본 '수성구에서 손님을 가장 적게 태운 H3 셀 세 곳'. od_role pickup + dt pickup + bottom 3. 측정 text '손님을 가장 적게 태운'은 순위어까지 포함해 길다.",
                       "측정 text를 '손님을 … 태운'으로 줄일지 확인(semantics에는 영향 없음). 그 밖은 승인 권고."),
        "pg-b006-39": ("pg 수정('운행' → '실차'). od_role both(부산진구 안에서 출발·도착) + dt pickup + top 3. 장소 region이 비어 있다(부산진구는 mock에서 이름이 하나라 실행에는 영향 없음).",
                       "region '부산'을 넣을지 확인(다른 pg 레코드는 region을 넣은 경우가 많다). 그 밖은 승인 권고."),
    }
    out = []
    for r in rows:
        note, rec = notes[r["id"]]
        out.append([r["id"], r["gap"], r["original"].get("question") if r.get("original") else "", r["question"], r["gold"], r["rationale"],
                    note, rec, "수정안 초안 = pg 수정본(현재 approved.jsonl). Claude 초안 의견, 승인 아님", *BLANK])
    return out


def main():
    j1 = j1_counts()
    a_counts, a_pairs = aug300(j1)
    b7 = json.loads((INV / "batch007/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    b7_out = {r["id"]: r for r in json.loads((INV / "batch007/vllm_outputs.json").read_text(encoding="utf-8"))["rows"]}
    rows7, c7 = contrast("batch007", b7, b7_out, j1)
    B4.write_workbook(INV / "batch007/review/batch007_review_v2.xlsx", [
        ("안내", ["항목", "설명"], [["무엇인가", "batch007 검토 시트 v2(원본 batch007_review.xlsx는 그대로). 신호 열과 우선순위를 더했다. 승인 아님."],
                                ["신호", "base 첫 응답 = vLLM BF16 greedy(2026-10-15)가 초안과 같은가. J1 = 표본 9개 중 초안과 같은 grounding 수."],
                                ["우선순위", "높음 = base 첫 응답이 초안과 다름 또는 J1 ≤ 3/9. 그 밖 보통."]]),
        ("batch007", ["id", "우선순위", "대조", "질문", "초안 grounding", "근거", "base 첫 응답", "J1 일치(9개 중)", *TAIL], rows7)])
    b8 = json.loads((INV / "batch008/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    b8_out = first(INV / "batch008/base_first_response.jsonl")
    rows8, c8 = contrast("batch008", b8, b8_out, j1)
    (INV / "batch008/review").mkdir(exist_ok=True)
    B4.write_workbook(INV / "batch008/review/batch008_review_v1.xlsx", [
        ("안내", ["항목", "설명"], [["무엇인가", "batch008 남은 후보 10건 검토 시트 v1(Claude 초안, 승인 아님). 설계와 겹침 검사는 batch008/README.md."],
                                ["신호", "base 첫 응답 = J7(vLLM BF16 greedy)이 초안과 같은가."],
                                ["우선순위", "높음 = base 첫 응답이 초안과 다름. 그 밖 보통."]]),
        ("batch008", ["id", "우선순위", "gap", "질문", "초안 grounding", "근거", "base 첫 응답", "J1", *TAIL], rows8)])
    pg_rows = pg_edit()
    (INV / "pg_imports/review").mkdir(exist_ok=True)
    B4.write_workbook(INV / "pg_imports/review/pg_edit_required_v1.xlsx", [
        ("안내", ["항목", "설명"], [["무엇인가", "partial-grounding batch006 EDIT_REQUIRED 7건. pg 쪽에서 Claude가 고친 뒤 재검사 통과로 승인했던 것(pg_imports/reports/batch006_REPORT.md 2절)."
                                              " 결정 121로 trunk에서는 사람 검토 전까지 뺐다."],
                                ["수정안 초안", "pg 수정본(현재 approved.jsonl)을 초안으로 두고 Claude가 남은 쟁점과 권고를 적었다. 승인 아님."]]),
        ("edit_required", ["id", "gap", "수정 전 질문", "수정 후 질문", "gold(수정 후)", "pg 근거", "남은 쟁점(Claude)", "권고(Claude)", "비고", *TAIL], pg_rows)])
    total = {"aug300": dict(a_counts), "aug300_model_output_pairs(vllm_outputs v1 시트)": a_pairs, "batch007": dict(c7), "batch008": dict(c8),
             "pg_edit_required": {"높음": len(pg_rows)}}
    minutes = sum(MIN.get(k, 0) * v for k, v in a_counts.items()) + a_pairs * 1.0 + sum(MIN[k] * v for k, v in c7.items()) \
        + 25 * 1.0 + sum(MIN[k] * v for k, v in c8.items()) + 5 * 1.0 + len(pg_rows) * 3.0
    total["estimated_minutes"] = round(minutes)
    total["assumptions"] = "높음 2분, 보통 1분, 낮음 0.5분, 모델 출력 비교 쌍 1분(aug300 vllm_outputs, batch007 25쌍, batch008 5쌍), pg 수정 3분"
    (HERE / "priority_counts.json").write_text(json.dumps(total, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(total, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
