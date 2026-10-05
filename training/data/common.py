"""IO, provenance, reserved evaluation sources and coverage reports."""
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from geoflow.planner import GeoFlowPlanner
from training.data.canonicalize import SCHEMA_VERSION, canonical_json
from training.data.split import question_key

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


#: 이 브랜치의 학습 자료가 기대하는 planner prompt(T2PC, 87048d0c). thor는 522aa3b1에서 만들었다.
EXPECTED_PROMPT_SHA256 = "87048d0c554c365e0e7994d09a4515c1cc646785708ce6dc9d1f120b4b5e8c2c"


def production_prompt():
    return GeoFlowPlanner(client=None).system_prompt()


def check_expected_prompt():
    """현재 production prompt가 학습 자료의 기대값과 같은지 확인한다. 다르면 자료를 다시 만들어야 한다."""
    current = hashlib.sha256(production_prompt().encode()).hexdigest()
    if current != EXPECTED_PROMPT_SHA256:
        raise ValueError(f"Production prompt {current[:8]} differs from expected {EXPECTED_PROMPT_SHA256[:8]}; "
                         "re-measure and update EXPECTED_PROMPT_SHA256 deliberately")
    return current


def provenance(paths, seed):
    def git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL, text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    definition_files = ["prompts/geoflow_planner.yaml", "geoflow/planner.py", "geoflow/grounding.py",
                        "geoflow/factors.py", "geoflow/types.py", "geoflow/operator_registry.py",
                        "geoflow/aggregation.py", "geoflow/composer.py", "geoflow/validator.py",
                        "geoflow/operator_mapping.py"]
    definition_files += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT / "geoflow_macros").glob("*.yaml"))]
    from geoflow.types import GEOFLOW_VERSION
    return dict(generated_at=datetime.now(timezone.utc).isoformat(), git_commit=git("rev-parse", "HEAD"),
                branch=git("branch", "--show-current"), seed=seed, output_schema_version=SCHEMA_VERSION,
                ontology_version=GEOFLOW_VERSION, planner_schema_hash=sha256(ROOT / "geoflow/grounding.py"),
                factor_schema_hash=sha256(ROOT / "geoflow/factors.py"),
                representation="flat", prompt_hash=hashlib.sha256(production_prompt().encode()).hexdigest(),
                definition_hashes={p: sha256(ROOT / p) for p in definition_files},
                source_files={str(p): sha256(p) for p in paths})


def read_jsonl(path):
    records = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("Record must be an object")
                records.append(value)
            except (ValueError, TypeError) as error:
                raise ValueError(f"{path}:{line_number}: {error}") from error
    return records


def write_jsonl(path, records):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(canonical_json(r) + "\n" for r in records), encoding="utf-8")


def reserved_sources():
    registry = yaml.safe_load((ROOT / "evaluation/corpus_registry.yaml").read_text(encoding="utf-8"))
    files = {ROOT / "evaluation/corpus_registry.yaml"}
    for entry in [*registry.get("corpora", []), *registry.get("question_sets", [])]:
        files.add(ROOT / entry["path"])
        files.update(ROOT / p for p in entry.get("parents", []))
    # Additional benchmark inputs not registered as paraphrase corpora.
    files.update(ROOT.glob("*questions*.yaml"))
    files.update(ROOT.glob("stub_query*.yaml"))
    files.update((ROOT / "evaluation").rglob("*.yaml"))
    return {p.resolve() for p in files if p.exists()}


def protected_questions():
    questions = set()
    def visit(item):
        if isinstance(item, dict):
            if isinstance(item.get("question"), str):
                questions.add(question_key(item["question"]))
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)
    for path in reserved_sources():
        visit(yaml.safe_load(path.read_text(encoding="utf-8")))
    return questions


def check_source(path):
    resolved = Path(path).resolve()
    if resolved in reserved_sources() or (ROOT / "evaluation").resolve() in resolved.parents:
        raise ValueError(f"Reserved evaluation source cannot be used for training: {path}")


def coverage(records):
    counts = {key: Counter() for key in ("concept", "subtype", "role", "measure", "factor", "aggregation",
                                         "negative_type", "negative_category")}
    unsupported = od = 0
    for record in records:
        payload = json.loads((record.get("messages") or record["chosen"])[-1]["content"])
        unsupported += int(payload.get("unsupported") is True)
        od += int(any((c.get("attributes") or {}).get("od_role") for c in payload.get("concepts", [])))
        for concept in payload.get("concepts", []):
            for key in ("concept", "subtype", "role"):
                counts[key][concept[key]] += 1
            if concept["role"] == "MEASURE":
                counts["measure"][concept["subtype"]] += 1
        for key, value in payload.get("factors", {}).items():
            counts["factor"][key] += 1
            if key in {"aggregation", "rollup", "bucket", "answer"}:
                counts["aggregation"][f"{key}:{value}"] += 1
        for key in ("negative_type", "negative_category"):
            if record["metadata"].get(key):
                counts[key][record["metadata"][key]] += 1
    warnings = [f"Sparse {key}: {name} ({n})" for key, dist in counts.items()
                for name, n in sorted(dist.items()) if n < 3]
    if records and not od:
        warnings.append("No OD samples; add reviewed pickup/dropoff/both families before OD experiments")
    if records and any(not r["metadata"].get("reviewed_by") or "사용자 검토 전" in r["metadata"].get("reviewed_by", "") for r in records):
        warnings.append("Annotations include missing/human-pending reviewer provenance; semantic correctness needs human review")
    return dict(sample_count=len(records), od_sample_count=od, unsupported_sample_count=unsupported,
                parent_intent_count=len({r["metadata"]["parent_intent"] for r in records}),
                distributions={k: dict(sorted(v.items())) for k, v in counts.items()},
                warnings=warnings)


def write_manifest(output, stage, train, valid, info, issues):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    manifest[stage] = {**info, "train_count": len(train), "validation_count": len(valid),
                       "coverage": coverage(train + valid), "split_coverage": {
                           "train": coverage(train), "validation": coverage(valid)}, "issues": issues,
                       "output_hashes": {p.name: sha256(p) for p in output.glob(f"{stage}_*.jsonl")}}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
