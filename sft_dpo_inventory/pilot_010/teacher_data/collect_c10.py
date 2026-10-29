# -*- coding: utf-8 -*-
"""pilot_010 teacher 수집기(T-C·TEACH-C, 결정 242). ``pilot_009/teacher/collect_r9.py``의 사본에서 지시·검사만 ``teacher_contrast10``으로 바꿈(원본은 그대로).

    hfvenv/bin/python collect_c10.py --targets T.json --out /abs/dir --summary /abs/summary.json --seed-base N [--samples 8] [--label T-C]

- 모델: Ollama ``qwen3.8:27b``(digest가 ``DIGEST``와 다르면 모델 호출 전에 멈춤, exit 4), ``think: true``, temperature 0.6,
  seed ``seed_base + 1000 × 질문 순번 + 표본 번호``, 연속 방식(결정 79).
- 모든 문항 ``variant: contrast_v1``(teacher_contrast_v1 지시). 행마다 ``teacher_contrast10.evaluate``(원본 검사·c2·c2 뒤 검사, pass; 금지 절 이름은 실행 시작 때 한 번 계산).
- 원문 ``--out/traces.jsonl``(학습에 바로 쓰지 않음 — 거르기는 승인 뒤).
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
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

MODEL = "qwen3.8:27b"
DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"
HOST = "http://localhost:11434"
TEMPERATURE = 0.6


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--targets", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--samples", type=int, default=8)
    p.add_argument("--seed-base", type=int, required=True)
    p.add_argument("--label", default="T-C")
    a = p.parse_args()
    out_dir = Path(a.out)
    if out_dir.exists():
        raise SystemExit("--out exists")
    import httpx
    import teacher_contrast10 as T
    from ollama_client import OllamaClient
    from training.data.common import check_expected_prompt
    check_expected_prompt()
    targets = json.loads(Path(a.targets).read_text(encoding="utf-8"))
    info = next(m for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"] if m["name"] == MODEL)
    if info["digest"] != DIGEST:
        print(json.dumps({"error": "model digest differs", "digest": info["digest"], "expected": DIGEST}))
        raise SystemExit(4)
    version = httpx.get(f"{HOST}/api/version", timeout=10).json()["version"]
    out_dir.mkdir(parents=True)
    sha_c = T.instruction_sha256()
    forbidden = T.forbidden_sections()
    questions, started = [], time.perf_counter()
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as stream:
        for qi, t in enumerate(targets):
            msgs = T.messages(t)
            assert t["variant"] == "contrast_v1", t["id"]
            tag = T.TAG
            rows, t0 = [], time.perf_counter()
            for k in range(1, a.samples + 1):
                seed = a.seed_base + 1000 * qi + k
                client = OllamaClient(HOST, MODEL, {"temperature": TEMPERATURE, "seed": seed}, chat_timeout=1800.0, think=True)
                t1 = time.perf_counter()
                r = client.chat(msgs)
                m = r.get("message") or {}
                content, thinking = m.get("content") or "", m.get("thinking") or ""
                ev = T.evaluate(t, thinking, content, forbidden)
                row = {"trace_id": f"{t['id']}:{a.label}:{tag}:{k}", "source": "teacher", "model": MODEL, "model_digest": info["digest"],
                       "ollama_version": version, "id": t["id"], "variant": t["variant"], "gap": t.get("gap"), "question_index": qi, "sample_index": k,
                       "seed": seed, "options": {"temperature": TEMPERATURE, "seed": seed}, "think": True,
                       "teacher_instruction": tag, "teacher_instruction_sha256": sha_c,
                       "use_for_training": False, "thinking": thinking, "content": content,
                       "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                       "thinking_sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
                       "prompt_eval_count": r.get("prompt_eval_count"), "eval_count": r.get("eval_count"),
                       **{f"{x}_ms": round(r[x] / 1e6, 1) for x in ("eval_duration", "load_duration", "prompt_eval_duration", "total_duration")
                          if isinstance(r.get(x), (int, float))},
                       "done_reason": r.get("done_reason"), "seconds": round(time.perf_counter() - t1, 1),
                       "checks_raw": ev["raw"], "c2": ev["c2"], "checks_after_c2": ev["after"], "pass": ev["pass"]}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                rows.append(row)
            questions.append({"id": t["id"], "variant": t["variant"], "gap": t.get("gap"), "samples": len(rows), "pass": sum(r["pass"] for r in rows),
                              "raw_pass": sum(r["checks_raw"]["pass"] for r in rows), "c2_edited": sum(bool(r["c2"]["removed_lines"]) for r in rows),
                              "seconds": round(time.perf_counter() - t0, 1)})
            print(json.dumps(questions[-1], ensure_ascii=False), flush=True)
    summary = {"label": a.label, "model": MODEL, "model_digest": info["digest"], "ollama_version": version,
               "teacher_instruction_sha256": {T.TAG: sha_c}, "forbidden_sections": forbidden,
               "targets": str(Path(a.targets).resolve()), "targets_sha256": hashlib.sha256(Path(a.targets).read_bytes()).hexdigest(),
               "samples_per_question": a.samples, "options": {"temperature": TEMPERATURE, "seed_base": a.seed_base}, "pipeline": {"isolation": "continuous", "start_unload": False},
               "questions": questions, "traces_path": str((out_dir / "traces.jsonl").resolve()),
               "traces_sha256": hashlib.sha256((out_dir / "traces.jsonl").read_bytes()).hexdigest(),
               "seconds": round(time.perf_counter() - started, 1), "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(a.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"questions": len(questions), "pass": sum(q["pass"] for q in questions)}))


if __name__ == "__main__":
    main()
