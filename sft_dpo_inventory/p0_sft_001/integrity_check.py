# -*- coding: utf-8 -*-
"""학습 전 target 무결성 재검사(지시 12절). 모델 호출 없음(tokenizer만 CPU).

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_001/integrity_check.py

1. 두 arm의 레코드마다 최종 답(thinking 레코드는 `</think>` 뒤)을 운영 경로(`assess_t2pc`: 조건 계층·compose·validate·compile)에
   넣은 실행 결과·의미 서명(EVENT 제외)이 Full canonical gold와 같다.
2. 두 arm의 같은 문항은 최종 답 문자열이 같다.
3. 기존 렌더링(`render_records`, json_only)에서 두 arm의 completion(손실 token: JSON + EOS)이 문항마다 같다.
   Clean-Hybrid의 thinking은 prompt 쪽에만 있다.
출력: integrity.json
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation/partial_grounding/sft_p0"))

import build_targets as BT  # noqa: E402
from training.data import thinking  # noqa: E402
from training.data.validation import assess_t2pc  # noqa: E402
from training.trainer_common import load_config, render_records, tokenizer_for  # noqa: E402


def answer(record):
    content = record["messages"][2]["content"]
    return thinking.response_json(content) if thinking.is_thinking(record) else json.loads(content)


def main():
    out = {}
    arms = {}
    for arm in ("gold_only", "clean_hybrid"):
        config = load_config(ROOT / f"training/configs/qwen3_8b_p0_sft001_{arm}.yaml", "sft")
        rows = [json.loads(x) for x in (ROOT / config["data"]["train"]).read_text(encoding="utf-8").splitlines() if x.strip()]
        bad = []
        for r in rows:
            q, full = r["messages"][1]["content"], r["metadata"]["target_full"]
            a, b = assess_t2pc(answer(r), q), assess_t2pc(full, q)
            if BT.exec_view(a) != BT.exec_view(b) or BT.strip_events(a.get("signature")) != BT.strip_events(b.get("signature")):
                bad.append(r["metadata"]["source_record_id"])
        rendered = render_records(tokenizer_for(config), rows, config, "sft")
        arms[arm] = {"rows": rows, "rendered": rendered}
        out[arm] = {"records": len(rows), "pipeline_equal_to_full_gold": len(rows) - len(bad), "mismatch": bad,
                    "reasoning_in_prompt": sum("<think>" in x["prompt"] for x in rendered),
                    "think_in_completion": sum("<think>" in x["completion"] for x in rendered)}
    g, h = arms["gold_only"], arms["clean_hybrid"]
    out["same_final_answer"] = sum(answer(a) == answer(b) for a, b in zip(g["rows"], h["rows"]))
    out["same_completion_text"] = sum(a["completion"] == b["completion"] for a, b in zip(g["rendered"], h["rendered"]))
    (HERE / "integrity.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
