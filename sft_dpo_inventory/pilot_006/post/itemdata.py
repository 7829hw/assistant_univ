# -*- coding: utf-8 -*-
"""세션 4 사후 분석 공통: 셀 → 표본 단위 행. 채점은 ``gates/compute_gates``와 같다(``analyze_cal.load_sample`` + 견고성 패치). 모델 호출 없음.

행: model, set, id, k, ok, U, silent, cls(report_class), u_flags, code(첫 응답 오류 코드), struct, repair, gfail, dt_missing, mm_nm,
    thinking(첫 계획 호출의 ``</think>`` 앞), think_tokens(Qwen3-8B tokenizer), concl(결론 문장 유형 집합: i·ii·iii·iv), completion_fail(Partial 보완 실패 흔적).

"결론" 문장 유형(A2, 결정 158 위험):
  (i) 결론 다섯 줄 형식 — "결론" 근처에 측정/끝/묶음/집계/주변 줄이 이어지는 경우(예: "결론을 확인:\\n측정: …")
  (ii) 숨은 결론이 있다는 듯한 문장 — 받은·주어진·확정된 결론, "결론과 일치", "결론에서", "결론을 보면", "결론에도"
  (iii) 영어 — "conclusion"
  (iv) 기타 "결론"(예: "따라서 결론은 …")
"""
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(HERE))
import robust_scoring  # noqa: E402

robust_scoring.patch()
import compute_gates as CG  # noqa: E402

GOLD = {"sel": "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
        "vendor100": "evaluation/vendor100/gold.yaml"}
LINE5 = re.compile(r"(측정|끝|묶음|집계|주변)\s*[:：]")
TYPE_II = re.compile(r"(받은|주어진|확정된|제시된|참고)\s*(다섯\s*줄|결론|판단)|결론(과|에|을)\s*(일치|대조|비교|확인)|결론(에서|을\s*보면|에도|이\s*주어)")


def concl_types(text):
    out = set()
    if re.search(r"conclusion", text or "", re.I):
        out.add("iii")
    for m in re.finditer(r"결론", text or ""):
        seg = text[max(0, m.start() - 20): m.end() + 120]
        if TYPE_II.search(seg):
            out.add("ii")
        elif len(LINE5.findall(text[m.end(): m.end() + 200])) >= 3:
            out.add("i")
        else:
            out.add("iv")
    return out


@lru_cache(maxsize=1)
def tok():
    sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))
    import hf_thinking as H
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)


@lru_cache(maxsize=8)
def gold(st):
    import evaluate_vendor100 as EV
    return {i["id"]: i for i in EV.load_gold(ROOT / GOLD[st])["items"]}


def first_thinking(cell_path):
    meta = json.loads((ROOT / cell_path).read_text(encoding="utf-8"))["meta"]
    raw = (meta.get("hf") or {}).get("raw_out")
    out = {}
    if raw and Path(raw).exists():
        for line in Path(raw).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["id"] not in out:
                out[r["id"]] = (r.get("raw_text") or "").split("</think>")[0]
    return out


def rows(cell_path, st, model, k, with_tokens=True):
    A = CG.scorer()
    p = ROOT / cell_path
    raw_dir = Path((json.loads(p.read_text(encoding="utf-8"))["meta"].get("hf") or {}).get("raw_out") or ".").parent
    A.RAW = raw_dir
    _, scored = A.load_sample(p, gold(st))
    src = {r["id"]: r for r in json.loads(p.read_text(encoding="utf-8"))["rows"]}
    think = first_thinking(cell_path)
    out = []
    t = tok() if with_tokens else None
    for i, r in scored.items():
        s = src[i]
        code = CG.first_code(s)
        th = think.get(i, "")
        out.append({"model": model, "set": st, "id": i, "k": k, "ok": bool(r["ok"]), "U": r["class"] == A.CS.U_CLASS, "silent": r["class"] == A.CS.SILENT,
                    "cls": r["class"], "u_flags": r["u_flags"], "outcome": r["outcome"], "code": code,
                    "struct": code is not None and (code in CG.STRUCT_CODES or code.startswith("INVALID_")), "mm_nm": code in ("MULTIPLE_MEASURES", "NO_MEASURE"),
                    "repair": len(s.get("llm_calls") or []) > 1,
                    "gfail": s.get("outcome") == "failed" and (s.get("planner_trace") or {}).get("error_stage") == "planner",
                    "dt_missing": bool(r.get("dt_missing")) if "dt_missing" in r else None,
                    "think_tokens": len(t(th, add_special_tokens=False)["input_ids"]) if t is not None and th else 0,
                    "concl": sorted(concl_types(th)), "thinking": th})
    return out


def cell_rows(prefix, st, model, k=4, with_tokens=True):
    allr = []
    for j in range(1, k + 1):
        allr += rows(f"{prefix}_s{j}.json", st, model, j, with_tokens)
    return allr
