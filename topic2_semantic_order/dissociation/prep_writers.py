"""X1·X2 풀이 작성자 접두 만들기(PREREGISTRATION 3.1). CPU 전용, 기존 기록만 읽는다.

기존 A/B 18 run × 대상 147문항의 첫 계획 호출 원문에서, 결정 지점 적용 조건을 만족하는 출력마다
    prefix_text = raw_text[:cut], tail = EVENT 객체를 닫는 문자 구간, emitted = 지표 2의 LOCATION 유무
를 만든다. 적용 조건: 분석 양식(features) 그리고 계획 JSON 파싱 그리고 concept 열 ∈ {(AMOUNT, EVENT), (AMOUNT, EVENT, LOCATION)}.

    python prep_writers.py REPO OUT.jsonl SUMMARY.json
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

SHAPES = {("AMOUNT", "EVENT"), ("AMOUNT", "EVENT", "LOCATION")}


def array_objects(plan):
    """plan 문자열에서 최상위 객체의 "concepts" 배열 원소 객체들의 (시작, 끝) 문자 위치(끝 = 닫는 '}' 위치)."""
    i = plan.index("{")
    depth, in_str, esc = 0, False, False
    key_buf, last_key, spans, stack = [], None, [], []
    start = None
    concepts_depth = None
    for k in range(i, len(plan)):
        ch = plan[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
                if depth == 1:
                    last_key = "".join(key_buf)
            elif depth == 1:
                key_buf.append(ch)
            continue
        if ch == '"':
            in_str = True
            key_buf = []
        elif ch in "{[":
            depth += 1
            stack.append(ch)
            if ch == "[" and depth == 2 and last_key == "concepts":
                concepts_depth = depth
            elif ch == "{" and concepts_depth is not None and depth == concepts_depth + 1:
                start = k
        elif ch in "}]":
            if ch == "}" and concepts_depth is not None and depth == concepts_depth + 1:
                spans.append((start, k))
            if ch == "]" and concepts_depth is not None and depth == concepts_depth:
                return spans
            depth -= 1
            stack.pop()
            if depth == 0:
                break
    return spans


def cut_point(plan):
    spans = array_objects(plan)
    end = spans[1][1]          # 두 번째 객체(EVENT)의 닫는 '}'
    c = end
    while c > 0 and plan[c - 1] in '"}':
        c -= 1
    return c, end


if __name__ == "__main__":
    repo = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("fdc", repo / "topic2_semantic_order/dissociation/fare_dissociation_check.py")
    fdc = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, ["fare_dissociation_check.py", str(repo)]
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(fdc)
    sys.argv = argv
    out = open(sys.argv[2], "w", encoding="utf-8")
    summary = {}
    for run in fdc.RUNS:
        label = f"{run[0]}-{run[1]}-r{run[2]}"
        raw = fdc.load_raw(fdc.raw_path(*run))
        s = {"items": 0, "analysis": 0, "unparsable": 0, "other_shape": 0, "applicable": 0, "tail": {}}
        for i in fdc.need:
            text = raw[i]
            s["items"] += 1
            f = fdc.features(text, fdc.T1[i])
            if f["template"] != "analysis":
                continue
            s["analysis"] += 1
            if "</think>" not in text:
                s["unparsable"] += 1
                continue
            head, plan = text.split("</think>", 1)
            offset = len(head) + len("</think>")
            try:
                obj = json.loads(plan)
                shape = tuple(c.get("concept") for c in obj.get("concepts", []))
            except Exception:  # noqa: BLE001
                s["unparsable"] += 1
                continue
            if shape not in SHAPES:
                s["other_shape"] += 1
                continue
            c, end = cut_point(plan)
            tail = plan[c:end + 1]
            nxt = plan[end + 1:end + 2]
            assert (nxt == ",") == (shape == ("AMOUNT", "EVENT", "LOCATION")), (label, i, nxt, shape)
            assert nxt in ",]", (label, i, nxt)
            s["applicable"] += 1
            s["tail"][tail] = s["tail"].get(tail, 0) + 1
            out.write(json.dumps({"writer": label, "id": i, "prefix_text": text[:offset + c], "tail": tail,
                                  "emitted": f["location"], "next_char": nxt, "taxi_type": f["taxi_type"],
                                  "states_region_condition": f["states_region_condition"],
                                  "raw_sha256": hashlib.sha256(text.encode()).hexdigest()}, ensure_ascii=False) + "\n")
        summary[label] = s
    tot = {k: sum(v[k] for v in summary.values()) for k in ("items", "analysis", "unparsable", "other_shape", "applicable")}
    tot["applicable_of_analysis"] = tot["applicable"] / tot["analysis"]
    Path(sys.argv[3]).write_text(json.dumps({"total": tot, "per_run": summary}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(tot, ensure_ascii=False))
