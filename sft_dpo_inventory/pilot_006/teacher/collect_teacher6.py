# -*- coding: utf-8 -*-
"""pilot_006 teacher 수집기(표현 중립 v1, C5). ``pilot_prep_003/teacher/collect_teacher.py``와 같은 설정에 요청 messages만 표현 중립 지시를 붙인다.

    hfvenv/bin/python collect_teacher6.py --targets TARGETS.json --out /abs/ignore/dir --summary /abs/summary.json [--samples 8]

- 모델: Ollama ``qwen3.8:27b``(Ollama GPU 48f798cc), ``think: true``, temperature 0.6, 질문당 표본 8개, seed ``SEED_BASE + 1000 × 질문 순번 + 표본 번호``.
  그 밖 option은 Modelfile 기본. 연속 방식(결정 79: 문항·표본마다 모델을 내리지 않음). 요청마다 대화 상태 없음.
- 요청 messages: ``teacher6.messages``(Full planner system + 표현 중립 지시).
- 저장: thinking과 content를 원문 그대로 ``--out/traces.jsonl``(ignore 경로)에. 행마다 eval_count·eval_duration_ms(결정 55 guard가 읽음).
- 행마다 자동 검사 (a)(b)를 붙인다(``teacher6``). 질문당 최대 4개 사용(결정 48)은 데이터 빌드에서 고른다.
- 요약(``--summary``): 질문별 통과 수, 검사 결과 요약(원문 없음).
"""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

MODEL = "qwen3.8:27b"
HOST = "http://localhost:11434"
TEMPERATURE = 0.6
SEED_BASE = 20261016


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--targets", required=True, help="JSON list of {id, question, semantics}")
    p.add_argument("--out", required=True)
    p.add_argument("--summary", required=True)
    p.add_argument("--samples", type=int, default=8)
    a = p.parse_args()
    out_dir = Path(a.out)
    if out_dir.exists():
        raise SystemExit("--out exists")
    import httpx
    import teacher6 as T
    from geoflow.planner import parse_planner_json
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
            msgs = T.messages(t["question"])
            rows, t0 = [], time.perf_counter()
            for k in range(1, a.samples + 1):
                seed = SEED_BASE + 1000 * qi + k
                client = OllamaClient(HOST, MODEL, {"temperature": TEMPERATURE, "seed": seed}, chat_timeout=1800.0, think=True)
                t1 = time.perf_counter()
                r = client.chat(msgs)
                m = r.get("message") or {}
                content, thinking = m.get("content") or "", m.get("thinking") or ""
                try:
                    payload = parse_planner_json(content)
                except Exception:  # noqa: BLE001 - JSON 없음
                    payload = None
                ca = T.check_field_names(thinking)
                cb = T.check_conclusion(thinking, payload, t["semantics"])
                row = {"trace_id": f"{t['id']}:teacher6:{k}", "source": "teacher", "model": MODEL, "model_digest": info["digest"],
                       "ollama_version": version, "id": t["id"], "question_index": qi, "sample_index": k, "seed": seed,
                       "options": {"temperature": TEMPERATURE, "seed": seed}, "think": True, "teacher_instruction_sha256": T.INSTRUCTION_SHA256,
                       "thinking": thinking, "content": content, "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                       "thinking_sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
                       "prompt_eval_count": r.get("prompt_eval_count"), "eval_count": r.get("eval_count"),
                       **{f"{x}_ms": round(r[x] / 1e6, 1) for x in ("eval_duration", "load_duration", "prompt_eval_duration", "total_duration")
                          if isinstance(r.get(x), (int, float))},
                       "done_reason": r.get("done_reason"), "seconds": round(time.perf_counter() - t1, 1),
                       "check_a": ca, "check_b": cb, "pass": ca["pass"] and cb["pass"]}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                rows.append(row)
            questions.append({"id": t["id"], "samples": len(rows), "pass": sum(r["pass"] for r in rows),
                              "check_a_pass": sum(r["check_a"]["pass"] for r in rows), "check_b_pass": sum(r["check_b"]["pass"] for r in rows),
                              "final_matches_canonical": sum(r["check_b"]["final_matches_canonical"] for r in rows),
                              "seconds": round(time.perf_counter() - t0, 1)})
            print(json.dumps(questions[-1], ensure_ascii=False), flush=True)
    summary = {"model": MODEL, "model_digest": info["digest"], "ollama_version": version, "teacher_instruction_sha256": T.INSTRUCTION_SHA256,
               "samples_per_question": a.samples, "options": {"temperature": TEMPERATURE, "seed_base": SEED_BASE}, "questions": questions,
               "traces_path": str((out_dir / "traces.jsonl").resolve()),
               "traces_sha256": hashlib.sha256((out_dir / "traces.jsonl").read_bytes()).hexdigest(),
               "seconds": round(time.perf_counter() - started, 1), "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    Path(a.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"questions": len(questions), "pass": sum(q["pass"] for q in questions)}))


if __name__ == "__main__":
    main()
