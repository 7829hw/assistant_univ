"""X2(18×18 + base 행), 중간 체크포인트 54개, B안 어댑터의 x12 작업 목록(CPU). 계산은 x12_tree.py(트리 계산, 지표 정의 그대로).
먼저 GPU 2에서 트리 계산 검증(최종 18 어댑터 자기 풀이 앞 12건 = 216행)을 하고, tree_check.py로 X1(순차 계산)과 대조한다.
검사를 못 넘으면 그 레인은 멈춘다(X2는 순차 계산 안으로 돌아가 다시 정한다).
    python make_jobs_x2.py MAIN_REPO
출력: gpu/jobs_x2.json, x12/readers_final18_p1.json, x12/readers_final18_p2.json, x12/readers_B.json
B안: 2단계 시작 시점에 검증 영수증(results_B/execution/verified_*.json)이 있는 run = S0T0-o2026113-t43 하나(영수증은 commit d71bd8e3, 2026-11-16 18:31).
"""
import hashlib
import json
import sys
from pathlib import Path

main = Path(sys.argv[1]).resolve()
D = main / "topic2_semantic_order/dissociation"
finals = json.loads((D / "x12/readers_final18.json").read_text())
(D / "x12/readers_final18_p1.json").write_text(json.dumps(finals[:9], indent=1) + "\n")
(D / "x12/readers_final18_p2.json").write_text(json.dumps(finals[9:], indent=1) + "\n")
bpath = "/data/hwkim/sftdpo_work/topic2_semantic_order/followup_conditions/causal_controls/train/S0T0-o2026113-t43/checkpoint-1984"
bsha = hashlib.sha256(Path(bpath, "adapter_model.safetensors").read_bytes()).hexdigest()
assert bsha == "deecd3718f60a9f5309881889feec25f7040dd5a627edbccbf0e53653973540c", bsha   # server_full/server_s0t0_o2026113_t43_ck1984.json
(D / "x12/readers_B.json").write_text(json.dumps([{"name": "Bopt-S0T0-o2026113-t43", "path": bpath, "run": None, "sha256": bsha}], indent=1) + "\n")

WP = "{MAIN}/training/generated/topic2_dissociation/writer_prefixes.jsonl"
PI = "{MAIN}/training/generated/topic2_dissociation/prompt_ids_147.jsonl"
RAWX = "{MAIN}/training/generated/topic2_dissociation/x12"
R = "{MAIN}/topic2_semantic_order/dissociation/x12"
DONE = "topic2_semantic_order/dissociation/gpu/done"


def x(jid, lane, readers, pairs, out, limit=0):
    a = ["--readers", f"{R}/{readers}", "--writers", WP, "--prompt-ids", PI, "--pairs", pairs, "--out", f"{RAWX}/{out}"]
    if limit:
        a += ["--limit", str(limit)]
    return {"id": jid, "lane": lane, "kind": "x12tree", "done_marker": f"{DONE}/{jid}.json", "args": a}


def check(jid, lane):
    return {"id": jid, "lane": lane, "kind": "check", "script": "tree_check.py", "done_marker": f"{DONE}/{jid}.json",
            "args": [f"{RAWX}/tree_validate.jsonl", f"{RAWX}/x1_self_final18.jsonl", f"{R}/tree_check_{lane}.json"]}


jobs = [x("TREE-validate", "g2", "readers_final18.json", "self", "tree_validate.jsonl", limit=12), check("TREE-check-g2", "g2"),
        x("X2-final18-p1", "g2", "readers_final18_p1.json", "all", "x2_final18_p1.jsonl"),
        x("X2-base", "g2", "readers_base.json", "all", "x2_base.jsonl"),
        x("X2-Bopt", "g2", "readers_B.json", "all", "x2_bopt.jsonl"),
        check("TREE-check-g0", "g0"),
        x("X2-final18-p2", "g0", "readers_final18_p2.json", "all", "x2_final18_p2.jsonl"),
        x("X1-mid54", "g0", "readers_mid54.json", "same_run", "x1_mid54.jsonl")]
(D / "gpu/jobs_x2.json").write_text(json.dumps({"note": "X2·중간 체크포인트·B안 x12 작업(트리 계산). 끝나면 같은 GPU에서 X4 레인(jobs_x4.json)이 이어진다.",
                                                "jobs": jobs}, ensure_ascii=False, indent=1) + "\n")
print(len(jobs))
