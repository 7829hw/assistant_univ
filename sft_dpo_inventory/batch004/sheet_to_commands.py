# -*- coding: utf-8 -*-
"""검토자가 채운 batch004_review.xlsx의 batch004·hf_outputs 시트를 읽어 ``workflow decide`` 명령을 출력한다(실행하지 않는다).

    python sft_dpo_inventory/batch004/sheet_to_commands.py FILLED.xlsx --decisions DECISIONS.jsonl

- 결정 대응: 승인 → accepted, 수정 → accepted + --corrected-grounding(JSON 파일을 만든다), 보류 → needs_fix, 제외 → rejected.
- 승인·수정은 검토자가 의미 점검을 했다는 뜻이므로 --semantic-checks-confirmed를 붙인다. hf_outputs 쌍의 승인은 모델 출력이
  틀렸다는 판단이므로 --negative-is-wrong도 붙인다.
- 출력된 명령을 검토자가 확인한 뒤 직접 실행한다. 이 스크립트는 decisions 파일을 쓰지 않는다.
- v003_flags·결정요청 시트는 workflow 대상이 아니다. 그 결정은 REPORT의 다음 단계에서 따로 반영한다.
"""
import argparse
import json
import re
import shlex
import zipfile
from pathlib import Path
from xml.etree import ElementTree

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
STATUS = {"승인": "accepted", "수정": "accepted", "보류": "needs_fix", "제외": "rejected"}


def read_sheets(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in root.findall("m:si", NS)]
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in workbook.find("m:sheets", NS)]
        sheets = {}
        for index, name in enumerate(names, 1):
            root = ElementTree.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
            rows = []
            for row in root.iter(f"{{{NS['m']}}}row"):
                cells = {}
                for cell in row.findall("m:c", NS):
                    column = re.match(r"[A-Z]+", cell.get("r")).group(0)
                    if cell.get("t") == "s":
                        value = shared[int(cell.find("m:v", NS).text)]
                    elif cell.get("t") == "inlineStr":
                        value = "".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t"))
                    else:
                        node = cell.find("m:v", NS)
                        value = node.text if node is not None else ""
                    cells[column] = value
                rows.append(cells)
            header = rows[0] if rows else {}
            sheets[name] = [{header[c]: r.get(c, "") for c in header} for r in rows[1:]]
    return sheets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx")
    parser.add_argument("--decisions", required=True)
    parser.add_argument("--queue", default="sft_dpo_inventory/batch004/review")
    parser.add_argument("--corrections-dir", default="sft_dpo_inventory/batch004/review/corrections")
    args = parser.parse_args()
    sheets = read_sheets(args.xlsx)
    commands, problems = [], []
    for sheet, id_column in (("batch004", "후보 id"), ("hf_outputs", "쌍 id")):
        for row in sheets.get(sheet, []):
            choice = (row.get("결정(승인/수정/보류/제외)") or "").strip()
            if not choice:
                continue
            reviewer, memo = (row.get("검토자") or "").strip(), (row.get("메모") or "").strip()
            if choice not in STATUS or not reviewer or not memo:
                problems.append(f"{row[id_column]}: 결정·검토자·메모가 모두 필요하다({choice!r})")
                continue
            command = ["python", "-m", "training.annotations.workflow", "decide", "--queue", args.queue,
                       "--decisions", args.decisions, "--id", row[id_column], "--status", STATUS[choice],
                       "--reviewer", reviewer, "--reason", memo]
            if choice == "수정":
                corrected = (row.get("수정 grounding(JSON)") or "").strip()
                try:
                    json.loads(corrected)
                except ValueError:
                    problems.append(f"{row[id_column]}: 수정 grounding이 JSON이 아니다")
                    continue
                target = Path(args.corrections_dir) / f"{row[id_column]}.json"
                commands.append(f"mkdir -p {shlex.quote(str(target.parent))} && printf %s {shlex.quote(corrected)} > {shlex.quote(str(target))}")
                command += ["--corrected-grounding", str(target)]
            if STATUS[choice] == "accepted":
                command.append("--semantic-checks-confirmed")
                if sheet == "hf_outputs":
                    command.append("--negative-is-wrong")
            commands.append(" ".join(shlex.quote(part) for part in command))
    print("\n".join(commands))
    if problems:
        print("\n# 확인 필요:\n" + "\n".join(f"# {p}" for p in problems))


if __name__ == "__main__":
    main()
