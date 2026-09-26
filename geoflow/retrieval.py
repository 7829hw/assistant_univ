# -*- coding: utf-8 -*-
"""질문–graph 예시 검색(논문 §3.4, 부록 E.1의 top-k cosine 검색)과 grounding 문맥 만들기.

검색은 grounding을 돕는 **문맥**만 만든다. 검색된 예시의 graph를 실행하거나, 예시의 조건
값·계산 값을 현재 질문의 grounding이나 실행 인자로 옮기는 경로는 없다. 현재 질문의 graph는
현재 질문의 LLM grounding을 composer가 조합한 것뿐이고, 검증·조건 보존·provider 계약은
검색과 무관하게 그대로 적용된다.

구성
- ``normalize``: 검색 입력 정규화(NORMALIZATION에 판을 적는다). 입력은 질문 원문 하나다.
  평가 gold, 기대 macro, 정답 result kind는 입력으로도 filter로도 쓰지 않는다.
- embedder: ``OllamaEmbedder``(질문 임베딩, Ollama ``/api/embed``)와 ``LexicalEmbedder``
  (문자 n-gram TF-IDF). 둘 다 L2 정규화 벡터를 내고 cosine은 내적이다.
  **LexicalEmbedder는 임베딩이 아니다.** 이 환경에 임베딩 실행 환경이 없어 둔 임시 lexical
  검색이며, 기록에 ``kind: lexical``로 남는다. 논문의 임베딩 검색을 구현했다고 부르지 않는다.
- index: 저장소 hash, 예시별 (id, version, 질문 hash), embedder 정체(이름·판·설정),
  정규화 판을 적은 JSON. 불러올 때 현재 저장소와 다르면 ``RETRIEVAL_INDEX_STALE``로 거부한다.
- ``ExampleRetriever``: top-k. 순서는 (점수 내림차순, 예시 id 오름차순)이다. 점수는 소수 12자리에서
  반올림해 비교하므로 부동소수 잡음이 순서를 바꾸지 않는다.
- ``FixedExamples``: 질문과 무관하게 같은 예시를 붙이는 비교군(검색 효과와 예시 자체의 효과를
  나누기 위한 것).
- ``render_section``: prompt 절. 예시 수(top_k ≤ MAX_TOP_K)와 글자 수(max_chars)를 제한한다.
  넘치는 예시는 빼고 뺀 이유를 기록한다.

실패 동작(조용히 숨기지 않는다)
- index 파일이 없거나, 형식이 다르거나, 저장소와 어긋나거나, embedder가 다르면 retriever를
  만들 때 ``RetrievalError``를 낸다. pipeline은 만들어지지 않는다.
- 질문마다 embedder 호출이 실패하면 planner가 ``RETRIEVAL_FAILED``로 실패시킨다. 예시 없이
  계속 진행하지 않는다.
- ``min_score``를 두었는데 넘는 예시가 없으면 status ``no_match``로 기록하고 예시 절 없이
  (검색을 끈 것과 같은 prompt로) 진행한다. 이것은 오류가 아니라 기록되는 결과다.
"""

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from geoflow.errors import GeoFlowError
from geoflow.examples import STORE_PATH, load_store

INDEX_FORMAT = "geoflow-example-index/1"
NORMALIZATION = "nfkc+casefold+strip-punct+collapse-ws/v1"
LEXICAL_INDEX_PATH = STORE_PATH.parent / "index_lexical.json"
#: 붙일 수 있는 예시 수의 상한. 설정값(top_k)이 이보다 크면 거부한다.
MAX_TOP_K = 5
DEFAULT_TOP_K = 3
DEFAULT_MAX_CHARS = 3000
#: 점수 비교 전 반올림 자릿수. 같은 입력·같은 index에서 순서가 흔들리지 않게 한다.
SCORE_DIGITS = 12
SECTION_HEADING = "[검토된 해석 예시]"

_PUNCT = re.compile(r"[?!.,~·…\"'“”‘’()\[\]{}:;]")
_SPACE = re.compile(r"\s+")


class RetrievalError(GeoFlowError):
    stage = "retrieval"
    default_user_message = "질문 해석 예시를 검색하지 못했습니다."


def normalize(text):
    """검색 입력 정규화. 판은 ``NORMALIZATION``."""
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = _PUNCT.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _l2(vector):
    if isinstance(vector, dict):
        norm = math.sqrt(sum(value * value for value in vector.values()))
        return {key: value / norm for key, value in sorted(vector.items())} if norm else {}
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else [0.0 for _ in vector]


def cosine(a, b):
    """L2 정규화된 두 벡터의 cosine(=내적). 희소(dict)와 밀집(list)을 받는다."""
    if isinstance(a, dict) and isinstance(b, dict):
        if len(b) < len(a):
            a, b = b, a
        return sum(value * b.get(key, 0.0) for key, value in a.items())
    if isinstance(a, dict) or isinstance(b, dict) or len(a) != len(b):
        raise RetrievalError("벡터 형식이 서로 다릅니다.", code="RETRIEVAL_VECTOR_MISMATCH")
    return sum(x * y for x, y in zip(a, b))


# -- embedder ----------------------------------------------------------------------


class LexicalEmbedder:
    """문자 n-gram TF-IDF. **임베딩이 아닌 임시 lexical 검색**이다.

    n-gram은 공백을 ``_``로 바꾼 정규화 문자열에서 뽑는다. IDF는 저장소 질문으로 정하고
    index에 저장한다(smooth idf: ln((1+N)/(1+df))+1). 저장소에 없는 n-gram은 무시한다.
    """

    kind = "lexical"
    name = "char-ngram-tfidf"
    version = "1"

    def __init__(self, idf, ngram=(2, 3)):
        self.idf = dict(sorted(idf.items()))
        self.ngram = tuple(ngram)

    @classmethod
    def fit(cls, texts, ngram=(2, 3)):
        documents = [set(cls._grams(text, ngram)) for text in texts]
        df = Counter(gram for grams in documents for gram in grams)
        n = len(documents)
        return cls({gram: math.log((1 + n) / (1 + count)) + 1 for gram, count in df.items()},
                   ngram)

    @staticmethod
    def _grams(text, ngram):
        text = normalize(text).replace(" ", "_")
        return [text[i:i + size] for size in range(ngram[0], ngram[1] + 1)
                for i in range(len(text) - size + 1)]

    def identity(self):
        return {"kind": self.kind, "name": self.name, "version": self.version,
                "params": {"ngram": list(self.ngram)}}

    def state(self):
        return {"idf": self.idf}

    def embed(self, texts):
        vectors = []
        for text in texts:
            counts = Counter(gram for gram in self._grams(text, self.ngram) if gram in self.idf)
            vectors.append(_l2({gram: count * self.idf[gram] for gram, count in counts.items()}))
        return vectors


class OllamaEmbedder:
    """Ollama ``/api/embed``로 질문 임베딩을 얻는다.

    정체(identity)에 model 이름과 ``/api/tags``의 digest를 적는다. 모델 파일이 바뀌면 index와
    어긋나 거부된다. HTTP 함수는 테스트에서 바꿔 끼운다. 이 저장소의 실행 환경(2026-09-26)은
    Ollama 서버가 embedding을 켜지 않았고 embedding 전용 모델도 없어 실제로 돌려 보지 못했다.
    """

    kind = "embedding"

    def __init__(self, model, host="http://localhost:11434", *, post=None, get=None,
                 timeout=60.0):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout
        self._post = post or self._http_post
        self._get = get or self._http_get
        self._digest = None

    @property
    def name(self):
        return f"ollama:{self.model}"

    def _http_post(self, url, payload):
        import httpx
        response = httpx.post(url, json=payload, timeout=self.timeout)
        return response.status_code, response.json()

    def _http_get(self, url):
        import httpx
        response = httpx.get(url, timeout=self.timeout)
        return response.status_code, response.json()

    @property
    def version(self):
        if self._digest is None:
            try:
                status, body = self._get(f"{self.host}/api/tags")
            except Exception as error:  # noqa: BLE001 - 검색 오류로 바꾼다
                raise RetrievalError(f"Ollama에 연결하지 못했습니다: {error}",
                                     code="RETRIEVAL_EMBEDDER_UNAVAILABLE") from error
            models = {item.get("name"): item.get("digest") for item in (body or {}).get("models", [])}
            if status != 200 or self.model not in models:
                raise RetrievalError(f"Ollama에 embedding 모델 {self.model}이 없습니다.",
                                     code="RETRIEVAL_EMBEDDER_UNAVAILABLE")
            self._digest = models[self.model]
        return self._digest

    def identity(self):
        return {"kind": self.kind, "name": self.name, "version": self.version,
                "params": {"endpoint": "/api/embed"}}

    def state(self):
        return {}

    def embed(self, texts):
        inputs = [normalize(text) for text in texts]
        try:
            status, body = self._post(f"{self.host}/api/embed",
                                      {"model": self.model, "input": inputs})
        except Exception as error:  # noqa: BLE001
            raise RetrievalError(f"Ollama embedding 호출이 실패했습니다: {error}",
                                 code="RETRIEVAL_EMBEDDER_UNAVAILABLE") from error
        vectors = (body or {}).get("embeddings")
        if status != 200 or not isinstance(vectors, list) or len(vectors) != len(inputs):
            raise RetrievalError(
                f"Ollama embedding 응답을 쓸 수 없습니다: {(body or {}).get('error', status)}",
                code="RETRIEVAL_EMBEDDER_UNAVAILABLE")
        return [_l2([float(value) for value in vector]) for vector in vectors]


# -- index -------------------------------------------------------------------------


def _entries(store):
    return [{"id": example.id, "version": example.version,
             "text_sha256": _sha(normalize(example.question))} for example in store.examples]


def build_index(store, embedder=None):
    """저장소 전체를 임베딩한 index(dict). embedder가 없으면 lexical을 저장소로 맞춘다."""
    texts = [example.question for example in store.examples]
    embedder = embedder or LexicalEmbedder.fit(texts)
    vectors = embedder.embed(texts)
    entries = _entries(store)
    for entry, vector in zip(entries, vectors):
        entry["vector"] = vector
    return {
        "format": INDEX_FORMAT,
        "normalization": NORMALIZATION,
        "store": {"path": Path(store.path).name, "version": store.version,
                  "sha256": store.sha256, "examples": len(store.examples)},
        "embedder": {**embedder.identity(), "state": embedder.state()},
        "examples": entries,
    }


def save_index(index, path):
    Path(path).write_text(json.dumps(index, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")


@dataclass(frozen=True)
class LoadedIndex:
    data: dict
    path: str
    sha256: str
    embedder: object

    @property
    def identity(self):
        return {key: self.data["embedder"][key] for key in ("kind", "name", "version", "params")}


def load_index(path, store, embedder=None):
    """index를 읽고 현재 저장소·embedder와 맞는지 확인한다. 어긋나면 RetrievalError."""
    path = Path(path)
    if not path.exists():
        raise RetrievalError(f"검색 index가 없습니다: {path}", code="RETRIEVAL_INDEX_MISSING")
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise RetrievalError(f"검색 index를 읽을 수 없습니다: {error}",
                             code="RETRIEVAL_INDEX_INVALID") from error
    if data.get("format") != INDEX_FORMAT or data.get("normalization") != NORMALIZATION:
        raise RetrievalError(
            f"검색 index 형식이 다릅니다: {data.get('format')}/{data.get('normalization')}",
            code="RETRIEVAL_INDEX_INVALID")
    stale = []
    if data["store"].get("sha256") != store.sha256:
        stale.append("저장소 hash")
    current = {entry["id"]: entry for entry in _entries(store)}
    recorded = {entry["id"]: entry for entry in data.get("examples") or []}
    if set(current) != set(recorded):
        stale.append(f"예시 id 차이 {sorted(set(current) ^ set(recorded))}")
    for example_id in sorted(set(current) & set(recorded)):
        if (current[example_id]["version"], current[example_id]["text_sha256"]) != (
                recorded[example_id]["version"], recorded[example_id]["text_sha256"]):
            stale.append(f"{example_id} 내용")
    if stale:
        raise RetrievalError(
            f"검색 index가 현재 예시 저장소와 다릅니다({', '.join(stale)}). "
            "python example_retrieval.py build로 다시 만드세요.",
            code="RETRIEVAL_INDEX_STALE", context={"index": str(path), "stale": stale})
    recorded_identity = data["embedder"]
    if recorded_identity.get("kind") == LexicalEmbedder.kind:
        if embedder is not None and embedder.identity()["name"] != recorded_identity["name"]:
            raise RetrievalError("index와 embedder가 다릅니다.", code="RETRIEVAL_EMBEDDER_MISMATCH")
        embedder = LexicalEmbedder(recorded_identity["state"]["idf"],
                                   tuple(recorded_identity["params"]["ngram"]))
        if embedder.identity() != {key: recorded_identity[key]
                                   for key in ("kind", "name", "version", "params")}:
            raise RetrievalError("lexical index 판이 코드와 다릅니다.",
                                 code="RETRIEVAL_EMBEDDER_MISMATCH")
    else:
        if embedder is None:
            raise RetrievalError("임베딩 index에는 embedder가 필요합니다.",
                                 code="RETRIEVAL_EMBEDDER_MISMATCH")
        live = embedder.identity()
        if {key: live[key] for key in ("kind", "name", "version")} != {
                key: recorded_identity.get(key) for key in ("kind", "name", "version")}:
            raise RetrievalError(
                f"index embedder({recorded_identity.get('name')}@{recorded_identity.get('version')})와 "
                f"현재 embedder({live['name']}@{live['version']})가 다릅니다.",
                code="RETRIEVAL_EMBEDDER_MISMATCH")
    return LoadedIndex(data=data, path=str(path), sha256=_sha(text), embedder=embedder)


# -- 선택과 prompt 절 ---------------------------------------------------------------


@dataclass(frozen=True)
class RetrievalSettings:
    top_k: int = DEFAULT_TOP_K
    max_chars: int = DEFAULT_MAX_CHARS
    min_score: float | None = None

    def __post_init__(self):
        if not 1 <= self.top_k <= MAX_TOP_K:
            raise ValueError(f"top_k는 1~{MAX_TOP_K}이어야 합니다: {self.top_k}")
        if self.max_chars < 200:
            raise ValueError(f"max_chars가 너무 작습니다: {self.max_chars}")

    def to_dict(self):
        return {"top_k": self.top_k, "max_chars": self.max_chars, "min_score": self.min_score,
                "order": "score desc, id asc", "score_digits": SCORE_DIGITS}


@dataclass
class RetrievalResult:
    mode: str
    query: str
    candidates: list = field(default_factory=list)
    included: list = field(default_factory=list)
    dropped: list = field(default_factory=list)
    section: str = ""
    settings: dict = field(default_factory=dict)
    index: dict | None = None

    @property
    def status(self):
        return "ok" if self.included else "no_match"

    def to_dict(self):
        return {"mode": self.mode, "status": self.status, "query": self.query,
                "candidates": list(self.candidates), "included": list(self.included),
                "dropped": list(self.dropped), "settings": dict(self.settings),
                "index": self.index, "section_chars": len(self.section),
                "section_sha256": _sha(self.section) if self.section else None}


_KIND_LABELS = {
    "scalar": "값 하나",
    "selected_groups": "값이 가장 큰/작은 구간(그 구간과 값)",
    "grouped_values": "구간별 값 목록 — 현재 계약으로 표현할 수 없음",
    "dimension_groups": "지역·요일 등 dimension 그룹별 값",
}
_OUTCOME_LABELS = {"needs_clarification": "사용자 확인 필요", "unsupported": "지원하지 않음"}
_STRUCTURE_FACTORS = ("dimension", "order", "limit")

SECTION_GUIDE = f"""{SECTION_HEADING}
예시 저장소에서 현재 질문과 비슷한 질문을 골라 붙였다. 검토된 해석이지만 현재 질문의 답은 아니다.
- 집계 구조(구간 단위, 구간 안 집계, 구간별 값의 집계, 답이 값인지 구간인지, 목록 질문인지)를
  판단하는 데만 참고한다.
- 예시의 날짜·장소·택시 유형·숫자는 현재 질문과 무관하다. 현재 질문에 없는 조건이나 값을 예시에서
  옮기지 않는다.
- 현재 질문의 표현이 예시와 다르면 현재 질문을 따른다.
- 출력은 위 grounding 계약의 JSON 형식 그대로다."""


def render_example(example, position):
    lines = [f"예시 {position}", f"질문: {example.question}"]
    if example.grounding.get("unsupported"):
        lines.append('출력: {"unsupported": true}')
    else:
        plan = example.grounding["factors"].get("aggregation_plan")
        if plan is not None:
            lines.append("aggregation_plan: " + json.dumps(plan, ensure_ascii=False,
                                                           separators=(", ", ": ")))
        structure = [f"{key}={example.grounding['factors'][key]}" for key in _STRUCTURE_FACTORS
                     if key in example.grounding["factors"]]
        lines.append("dimension·order·limit: " + (", ".join(structure) if structure else "없음"))
    kind = _KIND_LABELS[example.result_kind]
    if example.expected_outcome != "answered":
        kind += f" / {_OUTCOME_LABELS[example.expected_outcome]}"
    lines.append(f"결과 형태: {kind}")
    if example.graph:
        lines.append("의미 graph:")
        lines.extend(f"  {line}" for line in example.graph)
    lines.append(f"구분: {example.note}")
    return "\n".join(lines)


def render_section(examples, max_chars):
    """(절 문자열, 넣은 예시, 뺀 예시와 이유). 예시가 하나도 없으면 빈 문자열."""
    section, included, dropped = SECTION_GUIDE, [], []
    for example in examples:
        block = render_example(example, len(included) + 1)
        if len(section) + 2 + len(block) > max_chars:
            dropped.append({"id": example.id, "reason": "max_chars"})
            continue
        section += "\n\n" + block
        included.append(example)
    return (section if included else ""), included, dropped


class ExampleRetriever:
    """질문 원문 하나로 top-k 예시를 고른다."""

    mode = "retrieved"

    def __init__(self, store, index, settings=None):
        self.store = store
        self.index = index
        self.settings = settings or RetrievalSettings()
        self._vectors = [(entry["id"], entry["vector"]) for entry in index.data["examples"]]

    @classmethod
    def load(cls, *, store_path=STORE_PATH, index_path=LEXICAL_INDEX_PATH, embedder=None,
             settings=None):
        store = load_store(store_path)
        return cls(store, load_index(index_path, store, embedder), settings)

    def describe(self):
        return {"mode": self.mode, "index": Path(self.index.path).name,
                "index_sha256": self.index.sha256, "store_sha256": self.store.sha256,
                "embedder": self.index.identity, "normalization": NORMALIZATION,
                "settings": self.settings.to_dict()}

    def rank(self, question):
        [query] = self.index.embedder.embed([question])
        scored = [(round(cosine(query, vector), SCORE_DIGITS), example_id)
                  for example_id, vector in self._vectors]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored

    def select(self, question):
        ranked = self.rank(question)
        chosen = [(score, example_id) for score, example_id in ranked
                  if self.settings.min_score is None or score >= self.settings.min_score]
        chosen = chosen[:self.settings.top_k]
        examples = [self.store.get(example_id) for _score, example_id in chosen]
        section, included, dropped = render_section(examples, self.settings.max_chars)
        return RetrievalResult(
            mode=self.mode, query=normalize(question),
            candidates=[{"rank": rank, "id": example_id,
                         "version": self.store.get(example_id).version,
                         "score": round(score, 6)}
                        for rank, (score, example_id) in enumerate(chosen, start=1)],
            included=[example.id for example in included], dropped=dropped, section=section,
            settings=self.settings.to_dict(), index=self.describe())


class FixedExamples:
    """질문과 무관하게 같은 예시를 붙인다(비교군). 검색하지 않는다."""

    mode = "fixed"

    def __init__(self, store, example_ids, settings=None):
        self.store = store
        self.settings = settings or RetrievalSettings(top_k=len(example_ids))
        if len(example_ids) > self.settings.top_k:
            raise ValueError("고정 예시 수가 top_k를 넘습니다.")
        self.examples = [store.get(example_id) for example_id in example_ids]

    def describe(self):
        return {"mode": self.mode, "store_sha256": self.store.sha256,
                "fixed_ids": [example.id for example in self.examples],
                "settings": self.settings.to_dict()}

    def select(self, question):
        section, included, dropped = render_section(self.examples, self.settings.max_chars)
        return RetrievalResult(
            mode=self.mode, query=normalize(question),
            candidates=[{"rank": rank, "id": example.id, "version": example.version,
                         "score": None} for rank, example in enumerate(self.examples, start=1)],
            included=[example.id for example in included], dropped=dropped, section=section,
            settings=self.settings.to_dict(), index=self.describe())
