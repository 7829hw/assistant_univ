"""X4 데이터안: V4 teacher 풀이에 "범위" 칸을 넣은 변형(PREREGISTRATION 6.1). CPU 전용, 모델 호출 없음.

    python build_x4.py REPO OUT_DIR [--relabel narrow|none]

규칙
1. 대상: loss_scope = full_response 이고 최종 JSON이 거부가 아닌 기록. 그 밖의 기록은 바이트 그대로.
2. 소속 표현 고치기(--relabel narrow, 기본): 질문에 "소속"이 있는 teacher 기록의 풀이에서 소속 지역을 택시 유형이라 부른 구절만 바꾼다(RELABEL).
   진짜 택시 유형(개인·법인) 구절과 "날짜·택시 유형:" 소제목은 바꾸지 않는다.
3. 칸 넣기(풀이 = 첫 </think> 앞)
   - 번호 항목: 첫 "N. 주변" 항목 문단 뒤에 "N+1. 범위: …" 문단. 그 뒤에 오는 번호 항목 머리(M > N)는 M+1로 미룬다.
     문단 끝 = 그 항목 뒤 첫 빈 줄, 또는 그 전에 요약 줄("측정:")이 시작되면 그 앞.
   - 요약 줄: 줄 머리가 "주변:"인 줄마다 그 줄 뒤에 같은 들여쓰기·글머리표로 "범위: …" 줄.
   - 내용은 기록의 최종 JSON(gold 계획)의 LOCATION concept에서 만든다. 장소 표시 = region이 있고 name이 region으로 시작하지 않으면
     "region name", 아니면 name(value가 없으면 text). 여러 개면 계획 순서로 ", ".
     번호 문단: `N+1. 범위: 장소 조건은 "<장소1>", "<장소2>"다.` / 없으면 `N+1. 범위: 장소 조건이 없다. 따라서 "지정 없음".`
     요약 줄: `범위: <장소1>, <장소2>` / 없으면 `범위: 지정 없음`
4. 바뀐 기록의 metadata에는 `x4_scope_slot`(규칙 버전, 원래 content sha256, 적용한 편집 목록)만 더한다. 나머지 metadata는 그대로.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

RULE_VERSION = "x4-scope-slot-v1"
NUM = re.compile(r"(?m)^([ \t]*(?:[-*] )?(?:\*\*)?)(\d+)\.(\s*(?:\*\*)?\s*)주변")
SUMMARY = re.compile(r"(?m)^([ \t]*(?:[-*] )?)(?:\*\*)?주변(?:\*\*)?\s*[:：][^\n]*")
ITEM = re.compile(r"(?m)^([ \t]*(?:[-*] )?(?:\*\*)?)(\d+)\.")
SUMMARY_START = re.compile(r"(?m)^[ \t]*(?:[-*] )?(?:\*\*)?측정(?:\*\*)?\s*[:：]")

RELABEL = [
    ("R1", re.compile(r"택시 유형\(소속 지역\) 조건"), "소속 지역 조건"),
    ("R2", re.compile(r"택시 유형(?:이나|과|·|/) ?(?:등록 지역|지역|소속) 조건"), "소속 지역 조건"),
    ("R3", re.compile(r"택시 유형에 가까운 조건\(개인·법인과 같은 분류\)"), "소속 지역 조건"),
    ("R4", re.compile(r"(?m)^([ \t]*(?:- )?)택시 유형: (\"[^\"\n]*소속\")"), r"\1소속 지역: \2"),
    ("R5", re.compile(r"택시 유형은 \"소속\"\(법인택시\)"), None),          # 장소로 채움(아래)
    ("R6", re.compile(r"\"소속\"은 법인택시를 뜻하는 조건으로 남는다"), "\"소속\"은 그 지역에 등록된 택시라는 조건으로 남는다"),
]


def places(plan):
    out = []
    for c in plan.get("concepts", []):
        if c.get("concept") != "LOCATION":
            continue
        v = c.get("value")
        if isinstance(v, str):          # scope id 값(예: "scope:district:2600000000")
            v = {"name": v}
        v = v or {}
        name, region = (v.get("name") or c.get("text") or "").strip(), (v.get("region") or "").strip()
        out.append(f"{region} {name}" if region and not name.startswith(region) else name)
    return out


def relabel(think, plist):
    edits = []
    for code, pat, rep in RELABEL:
        if code == "R5":
            rep = "소속 지역은 " + ", ".join(f'"{p}"' for p in plist) if plist else None
            if rep is None:
                continue
        think, n = pat.subn(rep, think)
        if n:
            edits.append({"rule": code, "count": n})
    return think, edits


def insert_slot(think, plist):
    edits = []
    numbered = (f'장소 조건은 {", ".join(chr(34) + p + chr(34) for p in plist)}다.' if plist
                else '장소 조건이 없다. 따라서 "지정 없음".')
    line = "범위: " + (", ".join(plist) if plist else "지정 없음")
    m = NUM.search(think)
    if m:
        n = int(m.group(2))
        start = m.end()
        blank = think.find("\n\n", start)
        summ = SUMMARY_START.search(think, start)
        ends = [x for x in (blank, summ.start() - 1 if summ else -1) if x >= 0]
        end = min(ends) if ends else len(think.rstrip())
        head, tail = think[:end], think[end:]
        renum = []

        def bump(mm):
            k = int(mm.group(2))
            if k > n:
                renum.append(k)
                return f"{mm.group(1)}{k + 1}."
            return mm.group(0)
        tail = ITEM.sub(bump, tail)
        think = f"{head}\n\n{m.group(1)}{n + 1}.{m.group(3) if m.group(3).strip() else ' '}범위: {numbered}{tail}"
        edits.append({"slot": "numbered", "after_item": n, "renumbered": renum})
    k = 0
    out, pos = [], 0
    for mm in SUMMARY.finditer(think):
        out.append(think[pos:mm.end()])
        out.append("\n" + mm.group(1) + line)
        pos = mm.end()
        k += 1
    out.append(think[pos:])
    think = "".join(out)
    if k:
        edits.append({"slot": "summary", "count": k})
    return think, edits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("out_dir")
    ap.add_argument("--relabel", choices=("narrow", "none"), default="narrow")
    args = ap.parse_args()
    repo, out = Path(args.repo).resolve(), Path(args.out_dir)
    src = repo / "sft_dpo_inventory/pilot_010/build/V4/full"
    lines = (src / "sft_train.jsonl").read_bytes().split(b"\n")
    assert lines[-1] == b""
    lines = lines[:-1]
    (out / "full").mkdir(parents=True, exist_ok=True)
    new_lines, changes = [], []
    counts = {"records": len(lines), "full_response": 0, "refusal_kept": 0, "slot_numbered": 0, "slot_summary": 0,
              "no_structure": 0, "relabel_records": 0, "changed": 0, "unchanged": 0, "relabel_rule_counts": {}}
    for idx, raw in enumerate(lines):
        r = json.loads(raw)
        meta = r["metadata"]
        if meta.get("loss_scope") != "full_response":
            new_lines.append(raw)
            counts["unchanged"] += 1
            continue
        counts["full_response"] += 1
        content = r["messages"][2]["content"]
        think, sep, rest = content.partition("</think>")
        plan = json.loads(rest.strip())
        if plan.get("unsupported"):
            new_lines.append(raw)
            counts["refusal_kept"] += 1
            counts["unchanged"] += 1
            continue
        plist = places(plan)
        edits = []
        if args.relabel == "narrow" and "소속" in r["messages"][1]["content"]:
            think, e = relabel(think, plist)
            if e:
                counts["relabel_records"] += 1
                for x in e:
                    counts["relabel_rule_counts"][x["rule"]] = counts["relabel_rule_counts"].get(x["rule"], 0) + x["count"]
            edits += e
        think, e = insert_slot(think, plist)
        edits += e
        kinds = {x.get("slot") for x in e}
        counts["slot_numbered"] += "numbered" in kinds
        counts["slot_summary"] += "summary" in kinds
        if not e:
            counts["no_structure"] += 1
        new_content = think + sep + rest
        if new_content == content:
            new_lines.append(raw)
            counts["unchanged"] += 1
            continue
        r["messages"][2]["content"] = new_content
        r["metadata"] = {**meta, "x4_scope_slot": {"rule": RULE_VERSION, "relabel": args.relabel,
                                                   "original_content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                                                   "places": plist, "edits": edits}}
        new_lines.append(json.dumps(r, ensure_ascii=False).encode("utf-8"))
        counts["changed"] += 1
        changes.append({"index": idx, "source_record_id": meta.get("source_record_id"), "trace_id": meta.get("trace_id"),
                        "places": plist, "edits": edits, "before": content, "after": new_content})
    data = b"\n".join(new_lines) + b"\n"
    (out / "full/sft_train.jsonl").write_bytes(data)
    (out / "full/sft_valid.jsonl").write_bytes((src / "sft_valid.jsonl").read_bytes())
    man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    man["sft"]["release_candidate"] = "V4S"
    man["sft"]["note"] = (man["sft"]["note"] + f" || V4S = V4 + teacher 풀이 범위 칸({RULE_VERSION}, relabel={args.relabel}), "
                          "topic2_semantic_order/dissociation/build_x4.py. 기록 수·순서·질문 목록은 V4와 같다.")
    man["sft"]["derived_from"] = {"path": str((src / "sft_train.jsonl").relative_to(repo)),
                                  "sha256": hashlib.sha256((src / "sft_train.jsonl").read_bytes()).hexdigest()}
    man["sft"]["output_hashes"] = {"sft_train.jsonl": hashlib.sha256(data).hexdigest(),
                                   "sft_valid.jsonl": hashlib.sha256((out / "full/sft_valid.jsonl").read_bytes()).hexdigest()}
    (out / "full/manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(out / "changes.jsonl", "w", encoding="utf-8") as f:
        for c in changes:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    (out / "build_counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
