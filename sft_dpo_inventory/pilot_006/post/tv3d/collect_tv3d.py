# -*- coding: utf-8 -*-
"""T-v3d 수집기(``teacher/collect_teacher6v3.py``의 사본에서 요청·검사만 v3d로 바꿈; 원본은 그대로).

    hfvenv/bin/python collect_tv3d.py --targets tv3d_targets.json --out /abs/dir --summary /abs/summary.json [--samples 8] [--seed-base 20261916]

- 모델: Ollama ``qwen3.8:27b``, ``think: true``, temperature 0.6, seed ``seed_base + 1000 × 질문 순번 + 표본 번호``, 연속 방식(결정 79).
- 행마다 (a)(b)(c) 검사와 A2 유형. pass = (a) ∧ (b) ∧ ¬(c). 원문은 ``--out/traces.jsonl``(학습에 쓰지 않음).
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

MODEL = "qwen3.8:27b"
HOST = "http://localhost:11434"
TEMPERATURE = 0.6


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--targets", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--seed-base", type=int, default=20261916)
    a = p.parse_args()
    out_dir = Path(a.out)
    if out_dir.exists():
        raise SystemExit("--out exists")
    import httpx
    import teacher_v3d as T
    from ollama_client import OllamaClient
    from training.data.common import check_expected_prompt
    check_expected_prompt()
    targets = json.loads(Path(a.targets).read_text(encoding="utf-8"))
    info = next(m for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"] if m["name"] == MODEL)
    version = httpx.get(f"{HOST}/api/version", timeout=10).json()["version"]
    out_dir.mkdir(parents=True)
    questions, started = [], time.perf_counter()
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as stream:
        for qi, t in enumerate(targets):
            msgs = T.messages(t["question"], t["semantics"])
            rows, t0 = [], time.perf_counter()
            for k in range(1, a.samples + 1):
                seed = a.seed_base + 1000 * qi + k
                client = OllamaClient(HOST, MODEL, {"temperature": TEMPERATURE, "seed": seed}, chat_timeout=1800.0, think=True)
                t1 = time.perf_counter()
                r = client.chat(msgs)
                m = r.get("message") or {}
                content, thinking = m.get("content") or "", m.get("thinking") or ""
                ca = T.check_field_names(thinking, content)
                cb = T.check_conclusion(content, t["semantics"])
                cc = T.check_exposure(thinking, content)
                row = {"trace_id": f"{t['id']}:teacher_v3d:{k}", "source": "teacher", "model": MODEL, "model_digest": info["digest"],
                       "ollama_version": version, "id": t["id"], "question_index": qi, "sample_index": k, "seed": seed,
                       "options": {"temperature": TEMPERATURE, "seed": seed}, "think": True, "teacher_instruction_sha256": T.instruction_sha256(),
                       "teacher_instruction": "teacher_neutral_v3d", "use_for_training": False,
                       "thinking": thinking, "content": content, "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                       "thinking_sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
                       "prompt_eval_count": r.get("prompt_eval_count"), "eval_count": r.get("eval_count"),
                       **{f"{x}_ms": round(r[x] / 1e6, 1) for x in ("eval_duration", "load_duration", "prompt_eval_duration", "total_duration")
                          if isinstance(r.get(x), (int, float))},
                       "done_reason": r.get("done_reason"), "seconds": round(time.perf_counter() - t1, 1),
                       "check_a": ca, "check_b": cb, "check_c": cc, "a2_types": T.a2_types(thinking), "pass": ca["pass"] and cb["pass"] and not cc["exposed"]}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                rows.append(row)
            questions.append({"id": t["id"], "samples": len(rows), "pass": sum(r["pass"] for r in rows),
                              "check_a_pass": sum(r["check_a"]["pass"] for r in rows), "check_b_pass": sum(r["check_b"]["pass"] for r in rows),
                              "exposed": sum(r["check_c"]["exposed"] for r in rows), "a2_any": sum(bool(r["a2_types"]) for r in rows),
                              "seconds": round(time.perf_counter() - t0, 1)})
            print(json.dumps(questions[-1], ensure_ascii=False), flush=True)
    summary = {"model": MODEL, "model_digest": info["digest"], "ollama_version": version, "variant": "v3d", "teacher_instruction_sha256": T.instruction_sha256(),
               "samples_per_question": a.samples, "options": {"temperature": TEMPERATURE, "seed_base": a.seed_base}, "questions": questions,
               "traces_path": str((out_dir / "traces.jsonl").resolve()),
               "traces_sha256": hashlib.sha256((out_dir / "traces.jsonl").read_bytes()).hexdigest(),
               "seconds": round(time.perf_counter() - started, 1), "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(a.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"questions": len(questions), "pass": sum(q["pass"] for q in questions)}))


if __name__ == "__main__":
    main()
