#!/usr/bin/env bash
# ablation_013(pilot_010/gpu/check_ready.sh 사본, 위치만 바꿈): ready/<ID>.json의 "sha256" {경로: 값}을 MAIN 파일과 맞춰 본다(입력이 ready 파일을 만든 때와 같은지). 다르면 exit 1.
set -euo pipefail
MAIN=/home/hwkim/assistant_univ
R="$MAIN/sft_dpo_inventory/ablation_013/gpu/ready/$1.json"
python3 - "$R" "$MAIN" <<'PY'
import hashlib, json, sys
from pathlib import Path
r = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
bad = [p for p, h in r["sha256"].items() if hashlib.sha256((Path(sys.argv[2]) / p).read_bytes()).hexdigest() != h]
print(json.dumps({"ready": sys.argv[1], "checked": len(r["sha256"]), "mismatch": bad}, ensure_ascii=False))
sys.exit(1 if bad else 0)
PY
