"""1단계: 풀이 분류 검토용 층화 표본 100건 시트(PREREGISTRATION 4절). CPU 전용, 기존 기록만 읽는다.

    python make_review_sheet.py REPO OUT.xlsx OUT_index.json
층: 양식(분석·거절·기타) × 계획의 LOCATION(방출·누락) 6칸. seed 20261116. 칸마다 같은 수(100/6, 앞 칸부터 17)를 배정하고
모자란 칸의 몫은 남은 칸에 남은 크기 비례로 다시 나눈다(정수는 큰 나머지 순). 같은 문항 id는 최대 3건.
지표 정의는 fare_dissociation_check.py의 features()를 그대로 쓴다(모듈을 실행해 함수를 가져옴).
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import random
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
out_xlsx, out_index = sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("fdc", repo / "topic2_semantic_order/dissociation/fare_dissociation_check.py")
fdc = importlib.util.module_from_spec(spec)
argv, sys.argv = sys.argv, ["fare_dissociation_check.py", str(repo)]
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(fdc)
sys.argv = argv

gold = {it["id"]: it for it in fdc.gold["items"]}
pool = {}
for run in fdc.RUNS:
    raw = fdc.load_raw(fdc.raw_path(*run))
    label = f"{run[0]}-{run[1]}-r{run[2]}"
    for i in fdc.need:
        f = fdc.features(raw[i], fdc.T1[i])
        key = (f["template"], "방출" if f["location"] else "누락")
        pool.setdefault(key, []).append({"run": label, "id": i, "text": raw[i], "features": f})

CELLS = [(t, l) for t in ("analysis", "refusal", "other") for l in ("방출", "누락")]
sizes = {c: len(pool.get(c, [])) for c in CELLS}
N = 100
base = [N // len(CELLS) + (1 if k < N % len(CELLS) else 0) for k in range(len(CELLS))]  # 17,17,17,17,16,16
quota = {c: min(q, sizes[c]) for c, q in zip(CELLS, base)}
shortfall = N - sum(quota.values())
while shortfall > 0:
    open_cells = [c for c in CELLS if sizes[c] > quota[c]]
    if not open_cells:
        raise SystemExit("표본 100건을 채울 수 없음")
    cap = {c: sizes[c] - quota[c] for c in open_cells}
    share = {c: shortfall * cap[c] / sum(cap.values()) for c in open_cells}
    add = {c: min(int(share[c]), cap[c]) for c in open_cells}
    left = shortfall - sum(add.values())
    for c in sorted(open_cells, key=lambda c: -(share[c] - int(share[c]))):
        if left == 0:
            break
        if add[c] < cap[c]:
            add[c] += 1
            left -= 1
    for c in open_cells:
        quota[c] += add[c]
    shortfall = N - sum(quota.values())

rng = random.Random(20261116)
per_id = {}
chosen = []
for c in CELLS:
    cand = sorted(pool.get(c, []), key=lambda r: (r["run"], r["id"]))
    rng.shuffle(cand)
    got = 0
    for r in cand:
        if got == quota[c]:
            break
        if per_id.get(r["id"], 0) >= 3:
            continue
        per_id[r["id"]] = per_id.get(r["id"], 0) + 1
        chosen.append((c, r))
        got += 1
    if got < quota[c]:
        raise SystemExit(f"칸 {c}: 문항당 3건 제한으로 {quota[c]}건을 채우지 못함")

from xml.sax.saxutils import escape
import zipfile
import re as _re

_BAD = _re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _cell(ref, v):
    if isinstance(v, bool):
        v = "예" if v else "아니오"
    if isinstance(v, int):
        return f'<c r="{ref}"><v>{v}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(_BAD.sub("", str(v)))}</t></is></c>'


def _colname(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _sheet(rows, widths):
    cols = "".join(f'<col min="{k+1}" max="{k+1}" width="{w}" customWidth="1"/>' for k, w in enumerate(widths))
    body = "".join(f'<row r="{n}">' + "".join(_cell(f"{_colname(k)}{n}", v) for k, v in enumerate(r)) + "</row>"
                   for n, r in enumerate(rows, 1))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<cols>{cols}</cols><sheetData>{body}</sheetData></worksheet>')


def write_xlsx(path, sheets):
    names = [n for n, _, _ in sheets]
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                  for i in range(1, len(sheets) + 1)) + "</Types>",
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)) + "</sheets></workbook>",
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                  for i in range(1, len(sheets) + 1)) + "</Relationships>",
    }
    for i, (_, rows, widths) in enumerate(sheets, 1):
        files[f"xl/worksheets/sheet{i}.xml"] = _sheet(rows, widths)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)


head = ["번호", "층(자동 양식)", "층(자동 LOCATION)", "run", "문항 id", "질문", "gold 장소", "자동: 장소 언급", "자동: 지역 조건 서술",
        "자동: 계획 taxi_type", "풀이(<think>)", "계획(JSON)",
        "사람: 양식(분석/거절/기타)", "사람: 풀이가 지역 조건을 맞게 적었나(예/아니오/불명)", "사람: 메모"]
rows = [head]
index = []
for n, (c, r) in enumerate(chosen, 1):
    text = r["text"]
    think, plan = text.split("</think>", 1) if "</think>" in text else (text, "")
    f = r["features"]
    rows.append([n, c[0], c[1], r["run"], r["id"], gold[r["id"]]["question"], fdc.T1[r["id"]], f["mentions_place"],
                 f["states_region_condition"], f["taxi_type"], think[:32000], plan.strip()[:32000], "", "", ""])
    index.append({"no": n, "cell": list(c), "run": r["run"], "id": r["id"], "raw_sha256": hashlib.sha256(text.encode()).hexdigest(),
                  "think_truncated": len(think) > 32000})
info = [[line] for line in [
    "풀이 분류 검토용 층화 표본(PREREGISTRATION 4절). 기존 A/B 18 run × 대상 147문항의 첫 계획 호출 출력에서 뽑음.",
    "자동 열은 fare_dissociation_check.py features() 값. 사람 열을 채워 자동 분류(양식·지역 조건 서술)가 맞는지 확인한다.",
    "이 시트는 분류 규칙 검토용이며 등록된 지표 정의를 바꾸지 않는다. 바꿔야 하면 '사후 변경'으로 따로 기록한다.",
    "칸 크기 " + json.dumps({f"{a}/{b}": sizes[(a, b)] for a, b in CELLS}, ensure_ascii=False),
    "칸 배정 " + json.dumps({f"{a}/{b}": quota[(a, b)] for a, b in CELLS}, ensure_ascii=False) + ", seed 20261116, 문항당 최대 3건",
]]
write_xlsx(out_xlsx, [("검토", rows, (6, 10, 10, 16, 14, 40, 8, 8, 8, 8, 90, 60, 14, 18, 30)), ("설명", info, (150,))])
Path(out_index).write_text(json.dumps({"seed": 20261116, "sizes": {f"{a}/{b}": sizes[(a, b)] for a, b in CELLS},
                                       "quota": {f"{a}/{b}": quota[(a, b)] for a, b in CELLS}, "rows": index},
                                      ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({"sizes": {f"{a}/{b}": sizes[(a, b)] for a, b in CELLS}, "quota": {f"{a}/{b}": quota[(a, b)] for a, b in CELLS}},
                 ensure_ascii=False))
