#!/usr/bin/env python3
"""TIMS 도구 스키마 플래튼 + 시스템 프롬프트 조립.

사용법:
    python build.py            # 검증만 (파일 미생성)
    python build.py --dump     # build/ 에 산출물 기록
    python build.py -v         # 검증 상세 출력

런타임 로더로 사용:
    from build import build
    TOOLS, SYSTEM_PROMPT = build()
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

try:
    import jsonref
except ImportError:  # pragma: no cover
    sys.exit("jsonref가 필요합니다: pip install jsonref")

# --------------------------------------------------------------------------
# 설정
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"

# 도구 이름 접두어 규칙
#   resolve_ : 결정적 매핑,  get_ : 참조/메타데이터,  query_ : 동적 로그 집계
NAME_PREFIXES = ("resolve_", "get_", "query_")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

PLACEHOLDER_RE = re.compile(r"\{\{[^}]*\}\}")


class BuildError(Exception):
    """빌드 실패. 메시지에 파일/도구 위치를 반드시 포함한다."""


# --------------------------------------------------------------------------
# 1. 스키마 로드 및 $ref 인라인
# --------------------------------------------------------------------------


def _solidify(obj):
    """jsonref가 돌려주는 lazy proxy를 순수 dict/list로 변환."""
    if hasattr(obj, "keys"):
        return dict(obj)
    return list(obj)


def _load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise BuildError(f"{path.name}: YAML 파싱 실패\n{e}") from e


def load_tools(schema_dir: Path, verbose: bool = False) -> list[dict]:
    """schemas/*.yaml 을 읽어 $ref가 모두 인라인된 도구 목록을 반환."""
    common_file = schema_dir / "_common.yaml"
    if not common_file.exists():
        raise BuildError(f"{common_file} 없음")

    common = _load_yaml(common_file) or {}
    defs = common.get("$defs")
    if not defs:
        raise BuildError(f"{common_file.name}: $defs 키가 없거나 비어 있음")

    tools: list[dict] = []
    seen_names: dict[str, str] = {}

    files = sorted(p for p in schema_dir.glob("*.yaml") if not p.name.startswith("_"))
    if not files:
        raise BuildError(f"{schema_dir}: 도구 스키마 파일이 없음")

    for path in files:
        doc = _load_yaml(path)
        if not isinstance(doc, list):
            raise BuildError(f"{path.name}: 최상위는 도구 목록(list)이어야 함")

        for i, spec in enumerate(doc):
            where = f"{path.name}[{i}]"
            if not isinstance(spec, dict) or "function" not in spec:
                raise BuildError(f"{where}: 'function' 키가 없음")

            name = (spec.get("function") or {}).get("name", "<이름없음>")
            where = f"{path.name}::{name}"

            # $defs를 주입해 참조를 해소한 뒤 다시 제거한다.
            merged = {**spec, "$defs": defs}
            try:
                # merge_props=True: $ref 옆에 쓴 description 등 sibling 속성 보존
                resolved = jsonref.replace_refs(
                    merged, lazy_load=False, merge_props=True
                )
                flat = json.loads(json.dumps(resolved, default=_solidify))
            except Exception as e:  # noqa: BLE001
                raise BuildError(f"{where}: $ref 인라인 실패\n{e}") from e

            flat.pop("$defs", None)

            if name in seen_names:
                raise BuildError(
                    f"{where}: 도구 이름 중복 (이미 {seen_names[name]}에 정의됨)"
                )
            seen_names[name] = path.name

            flat["_source"] = path.name  # 검증 메시지용, 출력 직전 제거
            tools.append(flat)

            if verbose:
                print(f"  로드 {where}")

    return tools


# --------------------------------------------------------------------------
# 2. 도구 스키마 검증
# --------------------------------------------------------------------------


def validate_tools(tools: list[dict], verbose: bool = False) -> None:
    """도구별 6항목 검증. 첫 오류에서 멈추지 않고 전부 모아 보고한다."""
    errors: list[str] = []

    for tool in tools:
        fn = tool.get("function") or {}
        name = fn.get("name", "<이름없음>")
        src = tool.get("_source", "?")
        where = f"{src}::{name}"

        def err(msg: str, _w=where) -> None:
            errors.append(f"{_w}: {msg}")

        # (1) 이름 규칙
        if not NAME_RE.match(str(name)):
            err(f"이름이 snake_case가 아님 ({name!r})")
        elif not str(name).startswith(NAME_PREFIXES):
            err(f"이름 접두어가 {NAME_PREFIXES} 중 하나여야 함 ({name!r})")

        # (2) 도구 설명 존재
        if not str(fn.get("description", "")).strip():
            err("function.description 이 비어 있음")

        params = fn.get("parameters")
        if not isinstance(params, dict):
            err("parameters 가 객체가 아님")
            continue

        # (3) JSON Schema 자체 유효성
        try:
            Draft202012Validator.check_schema(params)
        except Exception as e:  # noqa: BLE001
            err(f"parameters가 유효한 JSON Schema가 아님\n    {e}")
            continue

        props = params.get("properties") or {}
        if not isinstance(props, dict):
            err("properties 가 객체가 아님")
            continue

        # (4) additionalProperties: false — 모델이 지어낸 파라미터 차단
        if params.get("additionalProperties") is not False:
            err("parameters.additionalProperties 가 false 로 지정되지 않음")

        # (5) required 항목이 실제 properties 에 존재하는지
        #     "- metric, scope" 처럼 YAML 오작성으로 문자열 1개가 되는 사고를 잡는다.
        req = params.get("required", [])
        if not isinstance(req, list):
            err(f"required 는 리스트여야 함 (현재 {type(req).__name__})")
        else:
            for r in req:
                if not isinstance(r, str):
                    err(f"required 원소가 문자열이 아님 ({r!r})")
                elif "," in r or " " in r:
                    err(f"required 원소에 구분자가 섞여 있음 ({r!r}) — 항목을 분리할 것")
                elif r not in props:
                    err(f"required 의 {r!r} 가 properties 에 없음")

        # (6) 파라미터별 설명 / scope 형식 검사
        for pname, pschema in props.items():
            pw = f"{where}.{pname}"
            if not isinstance(pschema, dict):
                errors.append(f"{pw}: 파라미터 정의가 객체가 아님")
                continue
            if not str(pschema.get("description", "")).strip():
                errors.append(f"{pw}: description 이 비어 있음")
            if "$ref" in pschema:
                errors.append(f"{pw}: $ref 가 해소되지 않고 남아 있음")
            # scope 계열은 pattern 으로 형식을 강제해 환각을 조기 차단
            if "scope" in pname and pschema.get("type") == "string":
                if "pattern" not in pschema:
                    errors.append(f"{pw}: scope 파라미터에 pattern 이 없음")
                elif "직접 생성 금지" not in str(pschema.get("description", "")):
                    errors.append(f"{pw}: description 에 '직접 생성 금지' 표기가 없음")

        if verbose:
            print(f"  검증 {where} — 파라미터 {len(props)}개")

    if errors:
        raise BuildError(
            f"도구 스키마 검증 실패 ({len(errors)}건)\n  - "
            + "\n  - ".join(errors)
        )


# --------------------------------------------------------------------------
# 3. 시스템 프롬프트 조립
# --------------------------------------------------------------------------


def build_prompt(prompt_file: Path, verbose: bool = False) -> str:
    """prompts/system.yaml 의 order 순서대로 섹션을 결합한다."""
    if not prompt_file.exists():
        raise BuildError(f"{prompt_file} 없음")

    doc = _load_yaml(prompt_file) or {}
    order = doc.get("order")
    sections = doc.get("sections")

    if not isinstance(order, list) or not order:
        raise BuildError(f"{prompt_file.name}: order 가 비어 있거나 리스트가 아님")
    if not isinstance(sections, dict):
        raise BuildError(f"{prompt_file.name}: sections 가 객체가 아님")

    missing = [k for k in order if k not in sections]
    if missing:
        raise BuildError(f"{prompt_file.name}: order 의 섹션이 정의되지 않음 → {missing}")

    unused = [k for k in sections if k not in order]
    if unused:
        # 오타로 섹션이 조용히 누락되는 사고를 막기 위해 오류로 처리한다.
        raise BuildError(
            f"{prompt_file.name}: sections 에 있으나 order 에 없는 섹션 → {unused}"
        )

    parts = []
    for key in order:
        body = str(sections[key]).strip()
        if not body:
            raise BuildError(f"{prompt_file.name}: 섹션 {key!r} 이 비어 있음")
        parts.append(body)
        if verbose:
            print(f"  섹션 {key} — {len(body)}자")

    prompt = "\n\n".join(parts) + "\n"

    leftover = PLACEHOLDER_RE.findall(prompt)
    if leftover:
        raise BuildError(
            f"{prompt_file.name}: 미해결 플레이스홀더 {sorted(set(leftover))}"
        )

    return prompt


# --------------------------------------------------------------------------
# 4. 교차 검증 — 스키마 enum 과 프롬프트 설명의 표류 감지
# --------------------------------------------------------------------------


def check_enum_drift(tools: list[dict], prompt: str) -> list[str]:
    """스키마 enum 값 중 시스템 프롬프트에 언급되지 않은 것을 찾는다.

    enum 은 수작업 동기화 대상이므로 강제하지 않고 경고만 낸다.
    (스키마에 값을 추가하고 프롬프트 갱신을 잊는 사고를 잡기 위함)
    """
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()

    for tool in tools:
        fn = tool.get("function") or {}
        name = fn.get("name", "?")
        props = ((fn.get("parameters") or {}).get("properties")) or {}
        for pname, pschema in props.items():
            if not isinstance(pschema, dict):
                continue
            for value in pschema.get("enum") or []:
                key = (pname, str(value))
                if key in seen:
                    continue
                seen.add(key)
                if str(value) not in prompt:
                    warnings.append(
                        f"{name}.{pname}: enum 값 {value!r} 이 시스템 프롬프트에 없음"
                    )
    return warnings


# --------------------------------------------------------------------------
# 5. 엔트리포인트
# --------------------------------------------------------------------------


def build(
    verbose: bool = False,
    strict_enum: bool = False,
    config_root: str | Path | None = None,
):
    """config root의 YAML에서 (tools, system_prompt)를 생성해 반환한다."""
    root = (
        ROOT
        if config_root is None
        else Path(config_root).expanduser().resolve()
    )
    schema_dir = root / "schemas"
    prompt_file = root / "prompts" / "system.yaml"

    tools = load_tools(schema_dir, verbose)
    validate_tools(tools, verbose)
    prompt = build_prompt(prompt_file, verbose)

    warnings = check_enum_drift(tools, prompt)
    if warnings:
        if strict_enum:
            raise BuildError(
                f"enum 표류 ({len(warnings)}건)\n  - " + "\n  - ".join(warnings)
            )
        for w in warnings:
            print(f"[경고] {w}", file=sys.stderr)

    for tool in tools:
        tool.pop("_source", None)

    return tools, prompt


def main() -> int:
    ap = argparse.ArgumentParser(description="TIMS 도구 스키마/프롬프트 빌드")
    ap.add_argument("--dump", action="store_true", help="build/ 에 산출물 기록")
    ap.add_argument("--strict-enum", action="store_true",
                    help="enum 표류를 경고가 아닌 오류로 처리")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    try:
        tools, prompt = build(verbose=args.verbose, strict_enum=args.strict_enum)
    except BuildError as e:
        print(f"\n[빌드 실패] {e}\n", file=sys.stderr)
        return 1

    payload = json.dumps(tools, ensure_ascii=False, indent=2)

    if args.dump:
        BUILD_DIR.mkdir(exist_ok=True)
        (BUILD_DIR / "tools.json").write_text(payload + "\n", encoding="utf-8")
        (BUILD_DIR / "system_prompt.txt").write_text(prompt, encoding="utf-8")
        print(f"기록: {BUILD_DIR/'tools.json'}, {BUILD_DIR/'system_prompt.txt'}")

    print(
        f"빌드 성공 — 도구 {len(tools)}개 / 스키마 {len(payload):,}자 "
        f"/ 프롬프트 {len(prompt):,}자"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
