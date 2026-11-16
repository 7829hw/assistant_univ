"""접두 재토큰화 일관성 검사(CPU): tok(prefix_text) == tok(raw_text)[:len] 인 비율과 경계 후보 token 목록."""
import contextlib, importlib.util, io, json, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "sft_dpo_inventory/thinking_prep_001"))
import hf_thinking as H
import x12_score as X
from transformers import AutoTokenizer
tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
spec = importlib.util.spec_from_file_location("fdc", root / "topic2_semantic_order/dissociation/fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec); argv, sys.argv = sys.argv, ["x", str(root)]
with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(fdc)
sys.argv = argv
raws = {}
for run in fdc.RUNS:
    raws[f"{run[0]}-{run[1]}-r{run[2]}"] = fdc.load_raw(fdc.raw_path(*run))
n = ok = 0; bad = []
for line in open(sys.argv[2], encoding="utf-8"):
    w = json.loads(line); full = raws[w["writer"]][w["id"]]
    p = tok(w["prefix_text"], add_special_tokens=False)["input_ids"]; f = tok(full, add_special_tokens=False)["input_ids"]
    n += 1
    if f[:len(p)] == p: ok += 1
    else: bad.append([w["writer"], w["id"]])
c = X.Candidates(X.token_bytes_table(tok))
cand = {s: [[tok.convert_ids_to_tokens(i) for i, _ in c(s.encode())[0]], [tok.convert_ids_to_tokens(i) for i in c(s.encode())[1]]] for s in ('"},', '"}]')}
res = {"prefixes": n, "prefix_consistent": ok, "inconsistent": bad, "boundary_candidates": cand}
Path(sys.argv[3]).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: (v if k != "inconsistent" else len(v)) for k, v in res.items()}, ensure_ascii=False)[:1500])
