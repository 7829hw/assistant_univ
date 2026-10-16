# -*- coding: utf-8 -*-
"""protected_final_v1 해시 고정(결정 135 G5, H5, SPEC 4.3). 파일 sha256과 행 수만 저장소에 남긴다. 원본은 저장소 밖에 둔다. 내용은 출력하지 않는다.

    hfvenv/bin/python pin_hash.py --xlsx /home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx --author "작성자" [--out manifest_v1.json] [--test]

- 먼저 ``validate.py``가 통과해야 한다(이 스크립트가 다시 부르고, 실패하면 고정하지 않음).
- 기록: 파일 sha256, 문항 행 수, 고정 시각, 작성자, validate 요약 sha256. 이 파일을 커밋한 SHA가 "고정 시점"이다.
- 이미 manifest가 있으면 덮어쓰지 않는다(다시 고정하려면 사용자 결정과 새 이름).
- 측정 전 확인: ``--verify``로 파일 sha256이 manifest와 같은지 본다(다르면 exit 2, 측정하지 않음).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    p.add_argument("--author", default="")
    p.add_argument("--out", default=str(HERE / "manifest_v1.json"))
    p.add_argument("--verify", action="store_true")
    p.add_argument("--test", action="store_true")
    a = p.parse_args()
    out = Path(a.out)
    digest = hashlib.sha256(Path(a.xlsx).read_bytes()).hexdigest()
    if a.verify:
        man = json.loads(out.read_text(encoding="utf-8"))
        same = man["file_sha256"] == digest
        print(json.dumps({"file_sha256_matches_manifest": same}))
        raise SystemExit(0 if same else 2)
    if out.exists():
        raise SystemExit(f"{out} exists; not overwriting")
    cmd = [sys.executable, str(HERE / "validate.py"), "--xlsx", a.xlsx] + (["--test"] if a.test else [])
    v = subprocess.run(cmd, capture_output=True, text=True)
    if v.returncode != 0:
        print("validate failed; not pinned")
        raise SystemExit(1)
    summary = json.loads(v.stdout)
    man = {"set": "protected_final_v1", "file_sha256": digest, "rows": summary["rows"], "author": a.author,
           "pinned_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
           "validate_summary_sha256": hashlib.sha256(v.stdout.encode("utf-8")).hexdigest(), "test": a.test,
           "rule": "원본은 저장소 밖. 고정 뒤 모델 출력 금지, 채택 후보 1개 대 base k=8 한 번(SPEC 1절)."}
    out.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("file_sha256", "rows", "pinned_at")}))


if __name__ == "__main__":
    main()
