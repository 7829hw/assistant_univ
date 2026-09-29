# -*- coding: utf-8 -*-
"""평가 Query YAML을 읽고 최소 계약을 검증한다."""

from pathlib import Path

import yaml


DEFAULT_QUERY_FILE = Path(__file__).resolve().parent / "stub_query.yaml"


class QueryValidationError(ValueError):
    """Query YAML의 구조나 id/question 계약이 올바르지 않음."""


class QuerySelectionError(ValueError):
    """요청한 Query ID 또는 Family를 선택할 수 없음."""


def load_queries(path=DEFAULT_QUERY_FILE):
    """YAML에서 고유 id와 normalized eval_id/question을 읽어 반환한다."""
    query_path = Path(path).expanduser().resolve()
    try:
        text = query_path.read_text(encoding="utf-8")
        document = yaml.safe_load(text)
        # id는 YAML 원문 그대로 쓴다. safe_load(YAML 1.1)는 "010"을 8진수 8로, "001"을 1로
        # 읽어 id가 원문과 달라진다(업체 100문항에서 63개). 같은 문서를 BaseLoader로 다시 읽어
        # 원문 문자열을 얻는다.
        raw_document = yaml.load(text, Loader=yaml.BaseLoader)
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
        raw_item = raw_document[index - 1] if isinstance(raw_document, list) else {}
        raw_id = raw_item.get("id") if isinstance(raw_item, dict) else None
        query_id = str(raw_id if isinstance(raw_id, str) else item.get("id", "")).strip()
        question = item.get("question")
        question = question.strip() if isinstance(question, str) else ""
        if not query_id or not question:
            raise QueryValidationError(
                f"Query {index}의 id와 question은 비어 있지 않아야 합니다."
            )
        raw_eval_id = item.get("eval_id", query_id)
        if not isinstance(raw_eval_id, str) or not raw_eval_id.strip():
            raise QueryValidationError(
                f"Query {index}의 eval_id는 비어 있지 않은 string이어야 합니다."
            )
        eval_id = raw_eval_id.strip()
        if query_id in seen_ids:
            raise QueryValidationError(f"Query id가 중복되었습니다: {query_id}")
        if question in seen_questions:
            raise QueryValidationError(f"Query question이 중복되었습니다: {question}")
        seen_ids.add(query_id)
        seen_questions.add(question)
        queries.append({
            **item, "id": query_id, "eval_id": eval_id, "question": question
        })

    return queries


def select_queries(queries, query_ids=None):
    """query_ids가 있으면 접두사가 일치하는 Query를 YAML 순서대로 선택한다."""
    if not query_ids:
        return list(queries)

    selected = []
    for item in queries:
        item_id = str(item.get("id", ""))
        if any(
            item_id.startswith(str(query_id).strip())
            for query_id in query_ids
        ):
            selected.append(item)

    return selected
