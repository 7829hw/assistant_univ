"""X4 변형 검사와 승인 자료(PREREGISTRATION 6.1 4단계 보고). CPU 전용.

    python verify_x4.py REPO X4_DIR
검사: (1) 바뀌지 않은 기록은 바이트 같음, (2) 바뀐 기록의 system·user 메시지·최종 JSON·metadata(x4_scope_slot 제외) 같음,
(3) 바뀐 풀이 = (원래 풀이 + 표현 고치기) 에 "범위" 칸 삽입과 번호 미루기만 더한 것(문자 단위 diff),
(4) 기록 수·질문 목록 같음. 보고: token 수 변화(assistant content, 학습 tokenizer), 남은 "택시 유형" 구절, 표본 20건 diff.
"""
import difflib
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import build_x4 as B

repo, x4 = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
sys.path.insert(0, str(repo / "sft_dpo_inventory/thinking_prep_001"))
import hf_thinking as H  # noqa: E402
from transformers import AutoTokenizer  # noqa: E402

tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
orig = (repo / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl").read_bytes().split(b"\n")[:-1]
new = (x4 / "full/sft_train.jsonl").read_bytes().split(b"\n")[:-1]
assert len(orig) == len(new) == 1984
res = {"records": len(new), "byte_identical": 0, "changed": 0, "errors": [], "tokens": {}, "residual_taxi_type_lines": []}
tok_before = tok_after = 0
by_kind = {}
changed_idx = []
for i, (a, b) in enumerate(zip(orig, new)):
    if a == b:
        res["byte_identical"] += 1
        ra = json.loads(a)
        if ra["metadata"].get("loss_scope") == "json_only":
            by_kind["json_only_identical"] = by_kind.get("json_only_identical", 0) + 1
        continue
    res["changed"] += 1
    changed_idx.append(i)
    ra, rb = json.loads(a), json.loads(b)
    if ra["messages"][:2] != rb["messages"][:2]:
        res["errors"].append([i, "system/user 다름"])
    ma = dict(rb["metadata"])
    slot = ma.pop("x4_scope_slot", None)
    if ma != ra["metadata"] or slot is None:
        res["errors"].append([i, "metadata 다름"])
    ca, cb = ra["messages"][2]["content"], rb["messages"][2]["content"]
    if slot["original_content_sha256"] != hashlib.sha256(ca.encode()).hexdigest():
        res["errors"].append([i, "원래 sha 다름"])
    ta, _, pa = ca.partition("</think>")
    tb, _, pb = cb.partition("</think>")
    if pa != pb:
        res["errors"].append([i, "최종 JSON 다름"])
    if ra["metadata"].get("loss_scope") != "full_response":
        res["errors"].append([i, "full_response가 아닌 기록이 바뀜"])
    ref = ta
    if "소속" in ra["messages"][1]["content"]:
        ref, _ = B.relabel(ta, slot["places"])
    # 역연산: 넣은 문단·줄을 정확히 빼고 번호를 되돌리면 ref와 같아야 한다
    plist = slot["places"]
    numbered = (f'장소 조건은 {", ".join(chr(34) + p + chr(34) for p in plist)}다.' if plist
                else '장소 조건이 없다. 따라서 "지정 없음".')
    line = "\n범위: " + (", ".join(plist) if plist else "지정 없음")
    inv = tb
    num_edit = [e for e in slot["edits"] if e.get("slot") == "numbered"]
    if num_edit:
        n = num_edit[0]["after_item"]
        pat = re.compile(r"\n\n[ \t]*(?:[-*] )?(?:\*\*)?" + str(n + 1) + r"\.\s*(?:\*\*)?\s*범위: " + re.escape(numbered))
        m = pat.search(inv)
        if not m:
            res["errors"].append([i, "번호 범위 문단 없음"])
            continue
        head, tail = inv[:m.start()], inv[m.end():]
        tail = B.ITEM.sub(lambda mm: f"{mm.group(1)}{int(mm.group(2)) - 1}." if int(mm.group(2)) > n + 1 else mm.group(0), tail)
        inv = head + tail
    sum_edit = [e for e in slot["edits"] if e.get("slot") == "summary"]
    if sum_edit:
        # 요약 줄은 "주변:" 줄 바로 뒤에 같은 머리(들여쓰기·글머리표)로만 넣었다
        body = line[1:]
        inv, cnt = re.subn(r"(?m)(^([ \t]*(?:[-*] )?)(?:\*\*)?주변(?:\*\*)?\s*[:：][^\n]*)\n\2" + re.escape(body) + r"(?=\n|$)", r"\1", inv)
        if cnt != sum_edit[0]["count"]:
            res["errors"].append([i, f"요약 범위 줄 수 다름 {cnt}"])
            continue
    if inv != ref:
        sm = difflib.SequenceMatcher(None, ref, inv, autojunk=False)
        op = next(o for o in sm.get_opcodes() if o[0] != "equal")
        res["errors"].append([i, f"역연산 불일치 {op[0]} {ref[op[1]:op[2]][:60]!r} -> {inv[op[3]:op[4]][:60]!r}"])
    na, nb = len(tok(ca, add_special_tokens=False)["input_ids"]), len(tok(cb, add_special_tokens=False)["input_ids"])
    tok_before += na
    tok_after += nb
    by_kind.setdefault("delta_per_record", []).append(nb - na)
d = by_kind.pop("delta_per_record")
d.sort()
all_fr = 0
for a in orig:
    r = json.loads(a)
    if r["metadata"].get("loss_scope") == "full_response":
        all_fr += len(tok(r["messages"][2]["content"], add_special_tokens=False)["input_ids"])
res["tokens"] = {"changed_records_before": tok_before, "changed_records_after": tok_after, "added": tok_after - tok_before,
                 "per_record_added_min_median_max": [d[0], d[len(d) // 2], d[-1]],
                 "all_full_response_content_before": all_fr, "relative_increase_full_response": (tok_after - tok_before) / all_fr}
res.update(by_kind)
# 남은 "택시 유형" 구절(소속 teacher 기록)
for a, b in zip(orig, new):
    r = json.loads(b)
    if "소속" in r["messages"][1]["content"] and r["metadata"].get("loss_scope") == "full_response":
        for line in r["messages"][2]["content"].split("</think>")[0].split("\n"):
            if "택시 유형" in line:
                res["residual_taxi_type_lines"].append([r["metadata"].get("source_record_id"), line.strip()[:200]])
man_a = json.loads((repo / "sft_dpo_inventory/pilot_010/build/V4/full/manifest.json").read_text())["sft"]
man_b = json.loads((x4 / "full/manifest.json").read_text())["sft"]
res["manifest_same_questions"] = (man_a["question_list_sha256"] == man_b["question_list_sha256"] and man_a["train_count"] == man_b["train_count"])
res["sft_train_sha256"] = hashlib.sha256((x4 / "full/sft_train.jsonl").read_bytes()).hexdigest()
res["ok"] = not res["errors"] and res["byte_identical"] + res["changed"] == 1984 and res["manifest_same_questions"]
(x4 / "verify.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# 표본 20건 diff: 표현 고치기 기록 5 + 번호 미루기 3 + 나머지 12(seed 20261116)
changes = [json.loads(line) for line in open(x4 / "changes.jsonl", encoding="utf-8")]
rng = random.Random(20261116)
rel = [c for c in changes if any("rule" in e for e in c["edits"])]
ren = [c for c in changes if c not in rel and any(e.get("renumbered") for e in c["edits"])]
rest = [c for c in changes if c not in rel and c not in ren]
pick = rng.sample(rel, 5) + rng.sample(ren, 3) + rng.sample(rest, 12)
md = ["# X4 표본 20건 diff (풀이 부분, unified diff)", "",
      "seed 20261116. 표현 고치기 기록 5, 번호 미루기 기록 3, 나머지 12. `-` 원래 V4, `+` V4S.", ""]
for n, c in enumerate(pick, 1):
    a = c["before"].split("</think>")[0].split("\n")
    b = c["after"].split("</think>")[0].split("\n")
    diff = list(difflib.unified_diff(a, b, lineterm="", n=1))[2:]
    md += [f"## {n}. 기록 {c['index']} `{c['source_record_id']}` 장소 {c['places'] or '없음'}", "",
           f"편집: `{json.dumps(c['edits'], ensure_ascii=False)}`", "", "```diff", *diff, "```", ""]
(x4 / "SAMPLE20_DIFF.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("residual_taxi_type_lines",)}, ensure_ascii=False)[:1500])
print("residual lines", len(res["residual_taxi_type_lines"]))
