# -*- coding: utf-8 -*-
"""실행 명세의 공통 부품: 실행 의미 코드의 내용 지문과 명세 hash.

평가 harness(evaluate_vendor100.py)의 run 동일성 확인과 CLI(assistant_cli.py)의 검증 표시가 같은 정의를 쓴다.

실행 의미 코드(``SEMANTIC_CODE``): GeoFlow 질문 처리 결과에 영향을 주는 파일. geoflow/ 패키지와 그것이 읽는 매크로·
템플릿·예시·reference 데이터, planner·system prompt, Tool schema, Tool 실행·mock·reference provider, 모델 요청을 만드는 client와 runtime이다. 내용(바이트)으로 지문을
만들므로 커밋이 달라도 이 파일들이 같으면 같은 지문이다(README·평가 기록·테스트 변경은 지문을 바꾸지 않는다).
assistant_cli.py는 넣지 않는다. CLI가 pipeline에 넘기는 설정은 검증 명세의 settings로 따로 비교한다.
"""
import hashlib
import json
from pathlib import Path

#: 실행 의미 코드. 디렉터리는 그 아래의 모든 파일(``__pycache__`` 제외), 나머지는 파일 하나다.
SEMANTIC_CODE = (
    "geoflow",
    "geoflow_macros",
    "geoflow_templates",
    "geoflow_examples",
    "prompts",
    "schemas",
    "reference_data",
    "build.py",
    "tool_executor.py",
    "tool_handlers.py",
    "mock_responses.py",
    "mock_stub.yaml",
    "reference_provider.py",
    "ollama_client.py",
    "assistant_runtime.py",
)


def _files(root):
    root = Path(root)
    for entry in SEMANTIC_CODE:
        path = root / entry
        if path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc":
                    yield item.relative_to(root).as_posix(), item
        elif path.is_file():
            yield entry, path


def code_fingerprint(root):
    """실행 의미 코드의 내용 지문. 파일 경로와 내용 hash 목록의 hash다."""
    listing = [(name, hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in _files(root)]
    digest = hashlib.sha256(json.dumps(listing, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"sha256": digest, "files": len(listing), "scope": list(SEMANTIC_CODE)}


def spec_sha256(spec):
    """명세 dict의 정규화 hash(키 순서와 무관)."""
    return hashlib.sha256(json.dumps(spec, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def spec_differences(old, new, prefix=""):
    """두 명세에서 값이 다른 키 경로 목록."""
    keys = sorted(set(old or {}) | set(new or {}))
    out = []
    for key in keys:
        a, b = (old or {}).get(key), (new or {}).get(key)
        path = f"{prefix}{key}"
        if isinstance(a, dict) and isinstance(b, dict):
            out.extend(spec_differences(a, b, path + "."))
        elif a != b:
            out.append(path)
    return out
