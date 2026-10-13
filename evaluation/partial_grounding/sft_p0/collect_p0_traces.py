"""P0 thinking trace 수집기(준비만, 결정 66). 승인된 데이터셋과 수집 모델이 정해지기 전에는 실제로 돌리지 않는다.

    # 모델 호출 없이 입력·prompt만 확인
    python evaluation/partial_grounding/sft_p0/collect_p0_traces.py --dataset DATASET.jsonl --dry-run
    # 실제 수집(사용자 승인 뒤, run_collect.sh가 resident_begin 다음에 부른다)
    python ... --dataset DATASET.jsonl --model MODEL --out RAW.jsonl --samples 8 --round-seed 20261020

- 입력: 승인된 P0 데이터셋 레코드({id, question, target_p0, source, dataset_version}). 기존 Full trace(pilot_002)는 쓰지 않는다.
- prompt: P0(`evaluation/partial_grounding/prompts/partial_p0.yaml`, 결합 system prompt hash `d7f4c12a…`). 메시지는
  `GeoFlowPlanner.messages(question)`와 같다([system, user]). gold를 힌트로 주지 않는다.
- 실행: Ollama 상주·문항 격리(resident_isolated). 요청마다 앞에 `PrefixCacheReset`(evaluate_vendor100)을 보내 서버 KV cache를
  같은 상태로 만든다. 모델을 내리지 않는다. 대화 상태 없이 요청마다 messages를 새로 만든다.
- 표본: 질문마다 greedy 1개(temperature 0) + sampling `--samples`개(temperature 0.6, top_p 0.95, top_k 20). seed는
  `evaluate_vendor100.call_seed(round_seed, item_id, sample_index)`로 정한다(순서와 무관).
- 저장(원문 보존, 결정 66): question, item id, dataset version, source, system prompt hash, model, model digest, Ollama 버전,
  seed·옵션, thinking 원문, 최종 응답 원문, eval_count, prompt_eval_count, duration, load_duration, isolation reset 결과, 시각.
  isolation 요청은 표본 기록·점수·token 지표에 넣지 않는다(reset 결과만 남긴다).
- 판정(기존 `thinking_prep_001/collect_traces.judge`와 같은 취지, 조건 계층 전 원 출력 기준):
  - 응답 JSON을 P0 target과 평가 비교 정규형(`_grounding_view`, parser 완성 뒤)으로 비교 → `match_raw`.
  - T2PC 운영 경로(조건 계층 켬)의 결과·의미 서명(EVENT 제외)이 target과 같은가 → `match_after_conditions`(따로 센다).
  - 학습 후보 선별(필터·질문당 개수)은 수집 뒤 별도 결정으로 정한다.
- cell_guard watch가 읽을 수 있도록 표본마다 jsonl 한 줄에 `llm_calls`(duration_ms, load_duration_ms, eval_count)를 넣는다.
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

P0_PROMPT = ROOT / "evaluation/partial_grounding/prompts/partial_p0.yaml"
EXPECTED_P0_SHA = "d7f4c12a"
HOST = "http://localhost:11434"


def system_prompt_sha():
    from geoflow.planner import GeoFlowPlanner, load_planner_prompt
    planner = GeoFlowPlanner(client=None, prompt=load_planner_prompt(P0_PROMPT))
    return planner, hashlib.sha256(planner.system_prompt().encode("utf-8")).hexdigest()


def judge(question, text, target):
    import evaluate_vendor100 as V
    from geoflow.grounding import complete_grounding_payload
    from geoflow.planner import parse_planner_json
    import build_targets as BT
    from training.data.validation import assess_t2pc
    try:
        payload = parse_planner_json(text)
    except Exception as error:  # noqa: BLE001
        return {"parse_ok": False, "error": type(error).__name__}
    out = {"parse_ok": True}
    try:
        got = V._grounding_view(complete_grounding_payload(json.loads(json.dumps(payload))))
        want = V._grounding_view(complete_grounding_payload(json.loads(json.dumps(target))))
        out["match_raw"] = got == want
    except Exception as error:  # noqa: BLE001
        out["match_raw"], out["raw_error"] = False, type(error).__name__
    a, b = assess_t2pc(payload, question), assess_t2pc(target, question)
    out["match_after_conditions"] = (BT.exec_view(a) == BT.exec_view(b)
                                     and BT.strip_events(a.get("signature")) == BT.strip_events(b.get("signature")))
    out["outcome"], out["error_code"] = a.get("outcome"), a.get("error_code")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--model")
    ap.add_argument("--out")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--round-seed", type=int, default=20261020)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    planner, sha = system_prompt_sha()
    if not sha.startswith(EXPECTED_P0_SHA):
        raise SystemExit(f"P0 system prompt hash {sha[:8]} != {EXPECTED_P0_SHA}")
    records = [json.loads(line) for line in Path(a.dataset).read_text(encoding="utf-8").splitlines() if line.strip()]
    if a.dry_run:
        msgs = planner.messages(records[0]["question"])
        print(json.dumps({"records": len(records), "prompt_sha256": sha[:8], "messages": [m["role"] for m in msgs],
                          "system_chars": len(msgs[0]["content"]),
                          "requests_planned": len(records) * (1 + a.samples)}, ensure_ascii=False))
        return 0
    if not (a.model and a.out):
        raise SystemExit("--model과 --out이 필요하다(수집 모델은 사용자 결정, trace_collection_plan.md)")
    import httpx
    import evaluate_vendor100 as V
    version = httpx.get(f"{HOST}/api/version", timeout=10).json().get("version")
    digest = {m["name"]: m["digest"] for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}.get(a.model)
    reset = V.PrefixCacheReset(HOST, a.model)
    with open(a.out, "a", encoding="utf-8") as out:
        for record in records:
            messages = planner.messages(record["question"])
            for k in range(1 + a.samples):
                if k == 0:
                    options, seed = {"temperature": 0}, None
                else:
                    seed = V.call_seed(a.round_seed, record["id"], k)
                    options = {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "seed": seed}
                state = reset.reset()
                started = time.perf_counter()
                body = httpx.post(f"{HOST}/api/chat", timeout=600, json={
                    "model": a.model, "messages": messages, "stream": False, "options": options}).json()
                message = body.get("message") or {}
                row = {
                    "id": f"{record['id']}:{'greedy' if k == 0 else f'sample:{k}'}", "item_id": record["id"],
                    "question": record["question"], "dataset_version": record.get("dataset_version"),
                    "source": record.get("source"), "prompt_sha256": sha, "model": a.model, "model_digest": digest,
                    "ollama_version": version, "options": options, "seed": seed, "round_seed": a.round_seed,
                    "isolation_reset": {"succeeded": state.succeeded, "detail": state.detail},
                    "thinking": message.get("thinking") or "", "content": message.get("content") or "",
                    "llm_calls": [{"kind": "plan", "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                                   "load_duration_ms": round((body.get("load_duration") or 0) / 1e6, 1),
                                   "eval_count": body.get("eval_count"), "prompt_eval_count": body.get("prompt_eval_count"),
                                   "done_reason": body.get("done_reason")}],
                    "judge": judge(record["question"], message.get("content") or "", record["target_p0"]),
                    "collected_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
