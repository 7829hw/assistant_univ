# -*- coding: utf-8 -*-
"""표준 라이브러리만으로 xlsx 시트를 읽는다(openpyxl 없음). 셀 값(공유 문자열·inline·숫자)과 셀 메모를 돌려준다."""
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _col(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _text(node):
    if node is None:  # 값 없는 inlineStr 셀(<is> 없음, 세션 2c 2차 검토 파일)
        return ""
    return "".join(t.text or "" for t in node.iter(f"{{{NS['m']}}}t"))


def read_workbook(path):
    """{sheet_name: {"rows": [[...]], "comments": {ref: text}}}"""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        shared = [_text(si) for si in root.findall("m:si", NS)]
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    target = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", NS)}
    out = {}
    for s in wb.find("m:sheets", NS):
        rid = s.get(f"{{{NS['r']}}}id")
        part = target[rid].lstrip("/")
        part = part if part.startswith("xl/") else "xl/" + part
        root = ET.fromstring(z.read(part))
        rows = []
        for row in root.iter(f"{{{NS['m']}}}row"):
            vals = {}
            for c in row.findall("m:c", NS):
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "s":
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = _text(c.find("m:is", NS))
                elif v is None:
                    val = None
                elif t in ("str", "b", "e"):
                    val = v.text
                else:
                    val = float(v.text)
                    if val.is_integer():
                        val = int(val)
                vals[_col(c.get("r"))] = val
            r_idx = int(row.get("r")) - 1
            while len(rows) < r_idx:
                rows.append([])
            rows.append([vals.get(i) for i in range(max(vals) + 1)] if vals else [])
        comments = {}
        rel_part = part.replace("worksheets/", "worksheets/_rels/") + ".rels"
        if rel_part in z.namelist():
            for r in ET.fromstring(z.read(rel_part)).findall("pr:Relationship", NS):
                if r.get("Type", "").endswith("/comments"):
                    cpart = "xl/" + r.get("Target").replace("../", "")
                    croot = ET.fromstring(z.read(cpart))
                    for cm in croot.iter(f"{{{NS['m']}}}comment"):
                        comments[cm.get("ref")] = _text(cm)
        out[s.get("name")] = {"rows": rows, "comments": comments}
    return out
