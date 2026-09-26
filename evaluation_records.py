# -*- coding: utf-8 -*-
"""평가 기록 보호. 원자료와 이미 쓴 채점 파일을 덮어쓰지 않는다.

``cond_v1_4arms``에서 재채점이 첫 채점 파일을 덮어쓸 뻔한 일(수치가 같아 드러나지
않았다)을 다시 겪지 않기 위한 최소 장치다.

- 채점 결과는 ``RUN_DIR/analyses/<analysis_id>/``에 쓴다. 같은 id가 있으면 ``-2``,
  ``-3``을 붙인 새 id를 쓴다. 파일은 ``"x"`` 모드로만 연다.
- ``manifest.json``에 채점기 이름·버전·소스 hash, 설정, 원자료 hash, 출력 파일 hash를
  남긴다. 사후 정정이면 ``corrects``에 이전 결과 경로와 변경 이유를 적는다.
- 원자료(observations.jsonl)의 hash가 manifest와 다르면 비교를 거부할 수 있도록
  ``verify_inputs``를 둔다. 없는 원본을 추정해 다시 만들지 않는다.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ANALYSES = "analyses"


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _free_directory(base, analysis_id):
    candidate, index = base / analysis_id, 1
    while candidate.exists():
        index += 1
        candidate = base / f"{analysis_id}-{index}"
    return candidate


def write_analysis(run_dir, *, analysis_id, outputs, scorer, config, inputs, corrects=None):
    """채점 결과를 새 디렉터리에 쓴다. 쓴 디렉터리를 돌려준다.

    ``outputs``: {파일 이름: JSON으로 쓸 객체}. ``scorer``: {name, version, source}.
    ``inputs``: 원자료 경로 목록(hash를 적는다). ``corrects``: {"previous": 경로 목록,
    "reason": 변경 이유} 또는 None.
    """
    run_dir = Path(run_dir)
    base = run_dir / ANALYSES
    base.mkdir(exist_ok=True)
    target = _free_directory(base, analysis_id)
    target.mkdir(exist_ok=False)
    written = {}
    for name, payload in outputs.items():
        path = target / name
        with open(path, "x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        written[name] = sha256_file(path)
    source = scorer.get("source")
    manifest = {
        "analysis_id": target.name,
        "created_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "scorer": {**scorer, "source_sha256": sha256_file(source) if source else None},
        "config": config,
        "inputs": {str(Path(path)): sha256_file(path) for path in inputs},
        "outputs": written,
        "corrects": corrects,
    }
    with open(target / "manifest.json", "x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    return target


def verify_inputs(analysis_dir):
    """manifest에 적힌 원자료 hash가 지금 파일과 같은지. 다른 경로 목록(비어야 정상)."""
    manifest = json.loads((Path(analysis_dir) / "manifest.json").read_text(encoding="utf-8"))
    changed = []
    for path, digest in manifest["inputs"].items():
        if not Path(path).is_file() or sha256_file(path) != digest:
            changed.append(path)
    return changed


def write_new(path, payload):
    """새 파일에만 쓴다. 이미 있으면 FileExistsError."""
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    return Path(path)
