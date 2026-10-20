# -*- coding: utf-8 -*-
"""결정 200(R7) protected_final_v1 고정 확인. 판정 계산 전에 실행한다. 모델 호출 없음, 셋 내용은 출력하지 않는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/results/check_r7.py   # -> results/r7_check.json(추가 기록)

조건(셋 다):
1. ``sft_dpo_inventory/pilot_006/protected_final/manifest_v1.json``이 원격 브랜치(``git fetch`` 뒤 ``origin/geoflow/sft-dpo-t2pc``)에 커밋됨. manifest는 원격 것을 ``git show``로 읽는다.
2. 그 manifest의 ``file_sha256`` = 서버 파일(``/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx``) sha256. ``set`` = protected_final_v1, ``test`` 아님.
3. ``validate.py --xlsx <서버 파일> --report <저장소 밖>`` 결과 ``ok: true``. 표준 출력은 버리고 보고 JSON의 ``ok``만 읽는다(PROCEDURE.md 2단계, 문장을 옮기지 않음).
``pin_hash.py``는 실행하지 않는다(고정은 사람이 함).
"""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BR = "origin/geoflow/sft-dpo-t2pc"
MAN = "sft_dpo_inventory/pilot_006/protected_final/manifest_v1.json"
XLSX = Path("/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx")
REPORT = Path("/home/hwkim/sftdpo_work/protected_final_v1/r7_validate_report.json")
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True)


def main():
    rec = {"checked_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")}
    rec["fetch_rc"] = git("fetch", "-q", "origin").returncode
    rec["remote_head"] = git("rev-parse", BR).stdout.strip()
    show = git("show", f"{BR}:{MAN}")
    rec["1_manifest_on_remote"] = show.returncode == 0
    if rec["1_manifest_on_remote"]:
        man = json.loads(show.stdout)
        rec["manifest_commit"] = git("log", "-1", "--format=%H", BR, "--", MAN).stdout.strip()
        rec["manifest_set"], rec["manifest_test"] = man.get("set"), man.get("test")
        rec["manifest_file_sha256"] = man.get("file_sha256")
        rec["server_file_sha256"] = hashlib.sha256(XLSX.read_bytes()).hexdigest() if XLSX.exists() else None
        rec["2_sha_match"] = (man.get("set") == "protected_final_v1" and man.get("test") is False
                              and rec["server_file_sha256"] is not None and man.get("file_sha256") == rec["server_file_sha256"])
    else:
        rec["2_sha_match"] = False
    if rec["2_sha_match"]:
        REPORT.unlink(missing_ok=True)
        v = subprocess.run([PY, str(ROOT / "sft_dpo_inventory/pilot_006/protected_final/validate.py"), "--xlsx", str(XLSX), "--report", str(REPORT)],
                           cwd=str(ROOT), capture_output=True, text=True)
        rec["validate_exit"] = v.returncode
        rec["3_validate_ok"] = REPORT.exists() and json.loads(REPORT.read_text(encoding="utf-8")).get("ok") is True
    else:
        rec["3_validate_ok"] = None
    rec["pinned"] = bool(rec["1_manifest_on_remote"] and rec["2_sha_match"] and rec["3_validate_ok"])
    with open(HERE / "r7_check.json", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False))
    raise SystemExit(0 if rec["pinned"] else 3)


if __name__ == "__main__":
    main()
