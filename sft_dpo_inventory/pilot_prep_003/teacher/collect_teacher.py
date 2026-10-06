# -*- coding: utf-8 -*-
"""정답 표본이 없는 질문에 대해 teacher trace를 모은다(결정 21). 첫 pilot 데이터에는 넣지 않는다.

    python sft_dpo_inventory/pilot_prep_003/teacher/collect_teacher.py --targets TARGETS.json \
        --out training/generated/thinking_traces/teacher_qwen3.8_27b/<run> --summary sft_dpo_inventory/pilot_prep_003/teacher/<run>

- 모델: Ollama ``qwen3.8:27b``(GPU 3 컨테이너). prompt 87048d0c(``GeoFlowPlanner.messages``, 학습 레코드 입력과 같은지 확인).
- 생성: ``think: true``(켬을 명시), temperature 0.6, 질문마다 표본 8개. 표본마다 고정 seed
  ``SEED_BASE + 1000 × 질문 순번 + 표본 번호``. 그 밖의 option(top_p, top_k, num_predict)은 지정하지 않는다(Modelfile 기본).
  요청마다 대화 상태 없이 보낸다.
- 저장: ``message.thinking``(추론 본문)과 ``message.content``(최종 응답)를 나눠 원문 그대로 ``--out``(ignore 경로)에 둔다.
  ``source: teacher``로 표시한다.
- 판정: 2번(HF trace)과 같은 ``thinking_prep_001/collect_traces.judge``(조건 계층 전 원 출력의 JSON을 reviewed gold와
  ``grounding_check``로 비교, 조건 계층 뒤 일치는 따로 기록).
- 요약(``--summary``)에는 질문별 정답 표본 수만 남기고 원문은 넣지 않는다.
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
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

MODEL = "qwen3.8:27b"
HOST = "http://localhost:11434"
SAMPLES = 8
TEMPERATURE = 0.6
SEED_BASE = 20261006


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, help="JSON list of {corpus_file, source_record_id}")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    out_dir, summary_dir = Path(args.out), Path(args.summary)
    if ROOT in out_dir.resolve().parents and "generated" not in out_dir.parts:
        raise SystemExit("--out은 저장소 밖이나 ignore 경로(generated)여야 한다")
    if out_dir.exists():
        raise SystemExit("--out이 이미 있다")

    import collect_traces as CT
    import httpx
    from geoflow.planner import GeoFlowPlanner
    from ollama_client import OllamaClient
    from training.data.common import check_expected_prompt, read_jsonl

    prompt_hash = check_expected_prompt()
    targets = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    records = []
    for target in targets:
        rows = {r["metadata"]["source_record_id"]: r for r in read_jsonl(ROOT / target["corpus_file"])}
        records.append(rows[target["source_record_id"]])
    tags = httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]
    info = next(m for m in tags if m["name"] == MODEL)
    version = httpx.get(f"{HOST}/api/version", timeout=10).json()["version"]
    planner = GeoFlowPlanner(client=None)
    out_dir.mkdir(parents=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    questions = []
    started = time.perf_counter()
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as stream:
        for qi, record in enumerate(records):
            messages = record["messages"][:2]
            question = messages[1]["content"]
            if planner.messages(question) != messages:
                raise SystemExit("레코드 입력이 현재 planner messages와 다르다")
            gold = json.loads(record["messages"][-1]["content"])
            sid = record["metadata"]["source_record_id"]
            judged = []
            t0 = time.perf_counter()
            for k in range(1, SAMPLES + 1):
                seed = SEED_BASE + 1000 * qi + k
                client = OllamaClient(HOST, MODEL, {"temperature": TEMPERATURE, "seed": seed},
                                      chat_timeout=1800.0, think=True)
                t1 = time.perf_counter()
                response = client.chat(messages)
                message = response.get("message") or {}
                content, thinking = message.get("content") or "", message.get("thinking") or ""
                verdict, payload = CT.judge(content, question, gold)
                row = {"trace_id": f"{sid}:teacher:{k}", "source": "teacher", "model": MODEL,
                       "model_digest": info["digest"], "ollama_version": version, "source_record_id": sid,
                       "question_index": qi, "sample_index": k, "seed": seed,
                       "options": {"temperature": TEMPERATURE, "seed": seed}, "think": True,
                       "thinking": thinking, "content": content,
                       "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                       "thinking_sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
                       "prompt_eval_count": response.get("prompt_eval_count"), "eval_count": response.get("eval_count"),
                       "done_reason": response.get("done_reason"), "seconds": round(time.perf_counter() - t1, 1),
                       "parsed": payload, "verdict": verdict}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                judged.append(row)
            q = {"question_index": qi, "source_record_id": sid, "corpus_file": targets[qi]["corpus_file"],
                 "correct_samples_of_8": sum(r["verdict"]["raw_match"] for r in judged),
                 "correct_after_condition_layer_only": sum(bool(r["verdict"].get("after_condition_match"))
                                                           for r in judged if not r["verdict"]["raw_match"]),
                 "parse_states": dict(__import__("collections").Counter(r["verdict"]["parse"] for r in judged)),
                 "done_reasons": dict(__import__("collections").Counter(str(r["done_reason"]) for r in judged)),
                 "eval_count": [r["eval_count"] for r in judged], "seconds": round(time.perf_counter() - t0, 1)}
            questions.append(q)
            print(json.dumps(q, ensure_ascii=False), flush=True)
    summary = {"model": MODEL, "model_digest": info["digest"], "quantization": info["details"].get("quantization_level"),
               "ollama_version": version, "prompt_sha256": prompt_hash, "think": True,
               "options": {"temperature": TEMPERATURE, "seed": "SEED_BASE + 1000*question_index + sample_index",
                           "seed_base": SEED_BASE, "other": "Modelfile defaults (not specified)"},
               "samples_per_question": SAMPLES, "judgment": "collect_traces.judge (raw output before condition layer)",
               "use": "not in first pilot data (decision 21)", "questions": questions,
               "questions_with_correct_sample": sum(q["correct_samples_of_8"] > 0 for q in questions),
               "traces_path": str((out_dir / "traces.jsonl").resolve()),
               "traces_sha256": hashlib.sha256((out_dir / "traces.jsonl").read_bytes()).hexdigest(),
               "seconds": round(time.perf_counter() - started, 1),
               "finished_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat()}
    (summary_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("questions_with_correct_sample", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
