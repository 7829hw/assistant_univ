# -*- coding: utf-8 -*-
"""평가 Query YAML을 읽고 최소 계약을 검증한다."""

import re
from pathlib import Path

import yaml


DEFAULT_QUERY_FILE = Path(__file__).resolve().parent / "stub_query.yaml"


class QueryValidationError(ValueError):
    """Query YAML의 구조나 id/question 계약이 올바르지 않음."""


class QuerySelectionError(ValueError):
    """요청한 Query ID를 유일하게 선택할 수 없음."""


def load_queries(path=DEFAULT_QUERY_FILE):
    """YAML에서 중복 없는 id/question 목록을 읽어 반환한다."""
    query_path = Path(path).expanduser().resolve()
    try:
        document = yaml.safe_load(query_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise QueryValidationError(
            f"Query YAML을 읽을 수 없습니다: {query_path}\n{error}"
        ) from error

    if not isinstance(document, list) or not document:
        raise QueryValidationError("Query YAML 최상위는 비어 있지 않은 list여야 합니다.")

    queries = []
    seen_ids = set()
    seen_questions = set()
    for index, item in enumerate(document, start=1):
        if not isinstance(item, dict):
            raise QueryValidationError(f"Query {index}는 object여야 합니다.")
        query_id = str(item.get("id", "")).strip()
        question = item.get("question")
        question = question.strip() if isinstance(question, str) else ""
        if not query_id or not question:
            raise QueryValidationError(
                f"Query {index}의 id와 question은 비어 있지 않아야 합니다."
            )
        if query_id in seen_ids:
            raise QueryValidationError(f"Query id가 중복되었습니다: {query_id}")
        if question in seen_questions:
            raise QueryValidationError(f"Query question이 중복되었습니다: {question}")
        seen_ids.add(query_id)
        seen_questions.add(question)
        queries.append({**item, "id": query_id, "question": question})

    return queries


_SHORT_QUERY_ID_PATTERN = re.compile(r"q\d{2}")


def select_queries(queries, query_ids=None):
    """전체 ID 또는 유일한 qNN 단축 ID를 입력 순서대로 선택한다."""
    if not query_ids:
        return list(queries)

    by_id = {item["id"]: item for item in queries}
    selected = []
    selected_ids = set()
    for requested_value in query_ids:
        requested = str(requested_value).strip()
        matched = by_id.get(requested)
        if matched is None and _SHORT_QUERY_ID_PATTERN.fullmatch(requested):
            matches = [
                item
                for item in queries
                if item["id"].startswith(requested)
            ]
            if len(matches) > 1:
                candidates = "\n".join(f"- {item['id']}" for item in matches)
                raise QuerySelectionError(
                    f"Ambiguous query id: {requested}\nMatches:\n{candidates}"
                )
            if matches:
                matched = matches[0]

        if matched is None:
            raise QuerySelectionError(f"Unknown query id: {requested}")
        if matched["id"] not in selected_ids:
            selected.append(matched)
            selected_ids.add(matched["id"])

    return selected
