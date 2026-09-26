# 질문–의미 graph 예시 검색과 grounding 문맥

2026-09-26. 논문 §3.4 "Retrieval-augmented Orchestration"과 부록 E.1 "Example Retrieval Mechanism"의
첫 단계를 이 프로젝트 구조에 맞춰 붙인 기록이다. 결정적 macro 조합·검증·실행은 바꾸지 않았다.

## 1. 요약

| 구분 | 내용 |
|---|---|
| 구현한 것 | 검토된 질문–의미 graph 예시 저장소, 등록 검증, 질문 top-k 검색(cosine), 검색된 예시를 structured grounding prompt에 해석 문맥으로 붙이는 선택 기능, 검색 기록 |
| 유지한 것 | LLM 출력 계약(구조화 grounding), composer의 macro 조합, G1–G5 검증, 조건 보존·scope provenance, provider 계약, 실행과 답변. 예시 graph를 실행하지 않고 예시의 조건·값을 옮기는 경로가 없다 |
| 구현하지 않은 것 | 검색 결과로 LLM이 graph의 변환·port 연결을 drafting하는 단계(논문의 "guide parameter binding and edge instantiation"), 자유 graph 생성, SFT/DPO |
| 환경 제약 | **임베딩 실행 환경이 없다.** Ollama 서버(0.33.2, root 실행)가 embedding을 켜지 않았고(`This server does not support embeddings`), embedding 전용 모델·numpy·sentence-transformers도 없다. 모델을 내려받지 않았다. 그래서 평가는 **문자 n-gram TF-IDF lexical 검색**으로 했다. 이것은 임베딩 검색이 아니며 논문 방식을 구현했다고 부르지 않는다. 임베딩 경로(`OllamaEmbedder`)는 인터페이스·index 형식·가짜 서버 테스트까지만 있다 |
| 기본값 | 끔. production 기본값, TIMS 계약, provider, 모델은 바꾸지 않았다 |

## 2. 논문에서 확인한 내용

첨부 PDF(ACL 2026 long, pp. 14896–14911)의 본문을 직접 읽었다.

- §3.4: 반복되는 구조 패턴 때문에 검증된 macro-template 라이브러리로 조합한다. "Given a question q, the
  LLM additionally generates the GeoFlow Graph guided by retrieved examples E_q from a question-graph
  store."
- 부록 E.1: 예시 저장소 E = {(q_i, G_i)}. 각 graph G_i는 텍스트 설명으로 직렬화한다. 입력 질문 q의
  임베딩과 저장된 질문 q_i의 임베딩 사이 cosine 유사도로 top-k를 고른다. 검색된 예시는 template 기반
  조합에서 parameter binding과 edge instantiation을 안내한다.
- 논문은 임베딩 모델, k, 입력 정규화, 직렬화 형식, 예시 수를 밝히지 않는다. 아래 선택은 모두 이
  프로젝트의 것이다.

## 3. 예시 저장소

`geoflow_examples/question_graph_examples.yaml`(v1, 16개), 코드 `geoflow/examples.py`.

필드: id, version, question, grounding(검토한 정답, 구조화 계약), graph(조건 값 없는 직렬화), macros,
result_kind(scalar / selected_groups / grouped_values / dimension_groups), aggregation(bucket·inner·
outer·select), expected_outcome(answered / needs_clarification / unsupported)와 expected_error,
note(의미 구분 한 줄), tags, source, split(`retrieval_store`만 허용), reviewed_by, reference(선택).

| id | 의미 | 결과 형태 | 측정값 | 비고 |
|---|---|---|---|---|
| ex01 | 전체 평균 | scalar | 운행 시간 | |
| ex02 | 전체 합계 | scalar | 매출 | reference 500,000 |
| ex03 | 주별 합계의 평균 | scalar | 운행 시간 | |
| ex04 | 월별 평균 중 가장 큰 값 | scalar | 영업 횟수 | 값이지 달이 아님 |
| ex05 | 주별 합계 중 가장 작은 값 | scalar | 매출 | reference 30,000 |
| ex06 | 합계가 가장 길었던 주 | selected_groups | 운행 시간 | |
| ex07 | 평균이 가장 낮았던 주 | selected_groups | 매출 | reference 20260831, 30,000 |
| ex08 | 합계가 가장 많았던 달 | selected_groups | 영업 횟수 | |
| ex09 / ex10 | 주별 평균 중 가장 짧은 값 / 평균이 가장 짧았던 주 | scalar / selected_groups | 운행 시간 | 최소 대조쌍 |
| ex11 | 주별 운행 시간의 최댓값(구간 안 집계 없음) | — | 운행 시간 | 확인 필요(AMBIGUOUS_INNER_AGGREGATION) |
| ex12, ex13 | 주별·월별 값을 모두 나열 | grouped_values | 매출, 운행 시간 | 지원 안 함(`{"unsupported": true}`) |
| ex14 | 월별 합계의 평균 | scalar | 매출 | reference 1,119,500 |
| ex15 | 주별 평균들의 평균 | scalar | 운행 시간 | 전체 평균과 다름 |
| ex16 | 구·군별 평균 상위 3곳 | dimension_groups | 매출 | order·limit은 dimension에만 |

출처: 모두 2026-09-26에 새로 쓴 학습용 문장이다. 평가 질문·그 paraphrase·지역명만 바꾼 변형과
기능 확인 6문항을 넣지 않았고, 모델 출력을 예시로 옮기지 않았다. 질문 의미에 대한 검토는 작성자(Claude)가
했고 사용자 검토 전이다(`reviewed_by`).

"구간별 값 목록"은 현재 grounding 계약(result는 reducer 또는 select 하나)으로 표현할 수 없다. 그래서
정답 응답을 `{"unsupported": true}`로 둔 경계 예시로 넣었다. 계약을 넓히지 않았다.

### 등록 검증(`python example_retrieval.py verify`)

형식·실행 검증이다. 질문 의미의 정답 여부는 사람이 검토한다.

1. grounding이 구조화 계약으로 파싱된다(unsupported 예시는 기대 오류가 UNSUPPORTED_QUESTION).
2. grounding의 집계 spec이 `aggregation`과 같고, 유도한 결과 형태가 `result_kind`와 같다.
3. composer가 grounding에서 만든 graph의 직렬화와 macro 목록이 저장된 것과 같다. 확인 필요 예시는
   기대한 조합 오류 코드가 난다.
4. G1–G5 검증을 통과한다.
5. reference 예시 4개는 reference provider에서 끝까지 실행해 기대 결과와 같다. 기대값은 손으로 센
   값이고 테스트가 독립 SQL로 다시 센다.

graph 직렬화는 transformation마다 한 줄이며 조건 parameter(date·time·taxi_type·taxi_status)의 값과
장소 이름은 적지 않는다.

    operation(EVENT/operation, SUPPORT) + place_scope --OPERATION_METRIC[aggregation=avg; metric=hours; 조건: date, taxi_type]--> hours_groups(AMOUNT/hours, SUPPORT, 구간=week)
    hours_groups --REDUCE_GROUPS[reducer=min]--> hours(AMOUNT/hours, MEASURE)

## 4. 검색

코드 `geoflow/retrieval.py`, 명령 `example_retrieval.py`.

| 항목 | 값 |
|---|---|
| 입력 | 질문 원문 하나. gold·기대 macro·정답 result kind는 입력으로도 filter로도 쓰지 않는다(`select(question)`만 있다) |
| 정규화 | `nfkc+casefold+strip-punct+collapse-ws/v1` |
| embedder | `LexicalEmbedder`(kind=lexical, char-ngram-tfidf v1, n=2–3, smooth idf를 저장소로 맞춤) / `OllamaEmbedder`(kind=embedding, `/api/embed`, version=모델 digest) |
| 유사도 | L2 정규화 벡터의 내적(cosine) |
| 순서 | 점수(소수 12자리 반올림) 내림차순, 같으면 예시 id 오름차순 |
| 설정 | top_k 3(상한 5), max_chars 3000, min_score 없음 |
| index | `geoflow_examples/index_lexical.json`: 형식 판, 정규화 판, 저장소 이름·판·sha256·예시 수, embedder 정체(종류·이름·판·설정)와 상태(idf), 예시별 id·version·질문 hash·벡터 |

재현

    python example_retrieval.py verify
    python example_retrieval.py build            # 같은 저장소면 byte 단위로 같은 index(테스트)
    python example_retrieval.py query "지난달 가람구 개인택시 주별 매출 평균 중 가장 큰 값은?" --show-section

오래된 index: 불러올 때 저장소 sha256, 예시 id 집합, 예시별 (version, 정규화 질문 hash)를 대조한다.
어긋나면 `RETRIEVAL_INDEX_STALE`로 거부하고 retriever를 만들지 않는다. 형식·정규화 판이 다르면
`RETRIEVAL_INDEX_INVALID`, 파일이 없으면 `RETRIEVAL_INDEX_MISSING`이다. 임베딩 index는 현재 모델
digest가 index와 다르면 `RETRIEVAL_EMBEDDER_MISMATCH`다.

## 5. grounding에 연결되는 구조

    질문 ──> planner.messages(question)
               ├─ system_prompt()            # 검색을 끄면 이것만(byte 단위로 기존과 같음)
               └─ + [검토된 해석 예시] 절      # 검색을 켜면 질문마다 한 번 골라 붙임
           ──> LLM ──> 구조화 grounding(현재 질문) ──> composer ──> G1–G5 ──> compile ──> 실행 ──> 답변

- 옵션: `GeoFlowPipeline.create(..., example_selector=ExampleRetriever.load())`. structured 계약에서만
  받는다(flat이면 ValueError).
- 예시 절: 안내 4줄(구조 판단에만 참고, 예시의 날짜·장소·택시 유형·숫자를 옮기지 않음, 현재 질문을
  따름, 출력 형식은 기존 계약) + 예시마다 질문, aggregation_plan, dimension·order·limit 유무, 결과 형태,
  의미 graph, 구분 한 줄. 예시 grounding의 조건 값은 절에 넣지 않는다(질문 문장 자체에 있는 것만
  보인다).
- composer는 현재 질문의 LLM grounding만 받는다. 예시 graph나 예시 grounding은 어떤 단계에도
  전달되지 않는다. 검증·조건 보존·provider 계약은 검색과 무관하게 그대로 적용된다.
- 기록: `run.retrieval`(mode, status, 정규화 질문, 후보 id·판·점수·순위, 넣은/뺀 예시와 이유, 설정,
  index·저장소 hash, embedder 정체, 절 글자 수·sha256). 평가 관측은 실제 system prompt의 hash와 글자
  수도 남긴다.
- 실패 동작: index 문제는 pipeline을 만들 때 오류다. 질문마다 검색이 실패하면 `RETRIEVAL_FAILED`로
  실패하고 예시 없이 계속하지 않는다. min_score를 둔 설정에서 넘는 예시가 없으면 status `no_match`로
  기록하고 예시 절 없이 진행한다.
- 같은 질문의 재질의(patch)는 처음 고른 예시를 그대로 쓴다.

## 6. 대표 질문의 흐름

development 확인(run `20260926_212959_dev_retrieval_v1`)의 r3 "지난달 가람구 개인택시 주별 매출 평균 중
가장 큰 값은?", arm `structured+cc+rx`.

1. **검색(lexical)**: ex09 0.465(주별 평균 중 가장 짧은 값 → 값), ex04 0.437(월별 평균 중 가장 큰 값
   → 값), ex05 0.407(주별 합계 중 가장 작은 값 → 값). 절 2,243자, system prompt 13,676 → 15,921자.
2. **grounding(LLM 원문)**: `aggregation_plan = {bucket: {unit: week, reducer: avg}, result: {reducer:
   max}}`, date `last_month`, 장소 가람구. taxi_type은 빠졌고 condition_check가 질문 표현으로 private을
   채웠다. 검색 없는 같은 모델은 `result: {select: max}`(그 값을 가진 주)로 적어 조용한 오답을 냈다.
3. **의미 graph(composer)**: `RESOLVE_PLACE_SCOPE → OPERATION_METRIC[aggregation=avg, 구간=week] →
   REDUCE_GROUPS[reducer=max]`, macro PLACE_TO_SCOPE + EVENT_TO_GROUPED_MEASURE.
4. **실행 계획**: range_partition(주 6개, 양 끝 포함 범위 호출 6회, 조건 date·taxi_type·scope 모두
   보존) → COLLECT_GROUPS → REDUCE_GROUPS(max). fused bucket/rollup은 reference 계약에 없는 항목
   때문에 거부됐다.
5. **결과(reference 합성 데이터 계산)**: 주별 평균 100,000 / 100,000 / 150,000 / 70,000 / 200,000 /
   60,000 → 200,000. 손 계산·독립 SQL과 같다. 답변에 합성 데이터, 적용 기간, 계산 의미가 표시된다.

예시(나래구·운행 시간·영업 횟수)의 장소·측정값·값은 grounding에도 실행 인자에도 나타나지 않았다.

## 7. 검증

### A. 결정적 테스트(`tests/test_example_retrieval.py`)

- 예시 등록: 16개 전부 통과. 변조(graph 한 줄 삭제, macro, 집계 칸, 결과 형태, reference 기대값,
  기대 결과 종류, 파싱 안 되는 grounding) 모두 거부. reference 예시 4개의 기대값을 독립 SQL로 다시 셈.
- 저장소 분리: evaluation/ 아래 모든 질문 YAML(runs 제외)의 질문이 저장소에 없다. 검색 평가 셋의
  의미 서명이 저장소 예시와 겹치지 않는다. 저장소 split은 `retrieval_store`만 허용.
- index: 커밋된 index를 다시 만들면 byte 단위로 같다. 질문·판 변경, 예시 삭제는 STALE, 없는 파일은
  MISSING, 정규화 판이 다르면 INVALID. retriever 생성 자체가 실패한다.
- 순서: 같은 입력·같은 index에서 같은 결과, top-k 1/3/5가 전체 순위의 앞부분, 동률은 id 순, top_k 범위
  밖 거부, min_score no_match, 글자 수 제한으로 뺀 예시 기록, 고정 예시는 질문과 무관.
- 임베딩 인터페이스(가짜 Ollama): index 왕복, 모델 digest가 바뀌면 거부, embedding을 켜지 않은 서버는
  RETRIEVAL_EMBEDDER_UNAVAILABLE.
- 연결: 검색을 끄면 system prompt가 기존과 같고 run.retrieval은 None. flat 계약에는 붙일 수 없다.
  예시(나래구·8월 전체)가 붙어도 실행 인자는 현재 질문의 가람구·20260801-20260815뿐이고 값은
  reference 계산(SQL과 같음). `dimension=week` grounding과 질문에 없는 scope id는 예시가 있어도 거부.
  선택기 오류는 RETRIEVAL_FAILED. 한 질문에 한 번만 고른다. CLI 기본은 끔.
- 평가 셋 gold: 답할 수 있는 13문항의 값을 독립 SQL로 다시 세고, 17문항의 gold grounding이
  reference에서 gold 결과(답/확인 필요/지원 안 함)와 값에 닿는다(condition_check on/off 모두).

### B. development 확인(기능 확인 6문항, 1회)

qwen3:8b, reference, 기준일 2026-09-25, condition_check on. 결정에 쓴 development다.

| 문항 | structured+cc | +rx | +fx | 검색이 바꾼 것 |
|---|---|---|---|---|
| r1 전체 평균 | 맞음 | 맞음 | 맞음 | — |
| r2 주별 합계의 평균 | 거부(`dimension=week`) | 맞음 | 맞음 | 불필요한 dimension 제거(고정 예시도 같음) |
| r3 주별 평균의 최댓값 | 조용한 오답(주 선택) | 맞음 | 조용한 오답 | 값 반환/구간 선택 |
| r4, r5 합계가 가장 큰 주 | 맞음 | 맞음 | 맞음 | — |
| r6 법인 전체 평균 | 맞음 | 맞음 | 맞음 | — |

bucket·내부 집계는 세 arm 모두 맞았다. 이 결과를 보고 저장소·prompt를 고치지 않고 후보를 고정했다.

### C. 비교 평가(`retrieval_eval_v1`, 측정 전 고정: `evaluation/retrieval/preregistration_v1.md`)

run `20260926_214029_retrieval_eval_v1`, 채점 `analyses/v2.7-eval`. 17문항 × 3 arm × 2회, 무효 관측 0.
temperature 0에서 두 반복의 원문이 모두 같았다. 사실상 문항당 관측 1개이므로 아래 수는 모두 짝수다.

| 지표(34 관측) | A structured+cc | B +rx(검색) | C +fx(고정) |
|---|---|---|---|
| 의미 계획·조건·결과 종류 모두 맞음(correct) | 18 | 18 | **24** |
| reference 계산 정답(26 중) | 18 | 20 | **24** |
| 조용한 오답 | 12 | 12 | 10 |
| 부당한 거부 | 2 | **4** | 0 |
| bucket 맞음 / 판정 | 26/28 | 26/26 | 30/30 |
| 구간 안 집계(inner) 맞음 | 22/28 | **18/26** | 26/30 |
| 구간 밖 집계(outer) 맞음 | 24/28 | 26/26 | 28/30 |
| 결과 종류(값/구간) 맞음 | 24/28 | 26/26 | 28/30 |
| dimension·order·limit 오류(최종 grounding) | 0 | 0 | 0 |
| 조건 누락·추가(최종 grounding) | 0 | 0 | 0 |
| condition_check가 고친 LLM 조건 | 8 | 4 | 10 |
| 필요한 의미 구분을 설명하는 예시 포함(문항) | — | 15/17 | 10/17 |
| system prompt 글자 수(중앙값) | 13,676 | 15,878 | 15,875 |
| 입력 token(중앙값) | 6,116 | 6,983 | 6,989 |
| 지연 중앙값(ms) | 7,128 | 7,843 | 7,137 |
| LLM 호출 | 34 | 34 | 34 |

문항별 변화(A → B)
- 좋아짐: e01(월별 합계 중 가장 큰 값을 달 선택으로 적던 것 → 값), e03(월별 평균을 합계로 적던 것
  → 평균), e12(`dimension=week` 거부 → 맞음).
- 나빠짐: e05·e08(내부 집계를 질문의 "최고/최저 매출"(max/min) 대신 sum으로 적음. 1순위 예시 ex05·
  ex06/ex07의 sum/avg를 옮긴 것으로 보인다), e07(`dimension=week`가 새로 나와 거부), e04(장소 값을
  `{name: "", region: 가람구}`로 적어 거부. 집계와 무관한 형식 오류).
- 그대로 틀림: 목록 질문 e14·e15(세 arm 모두 목록 대신 값 하나를 지어냄. B는 e14에 목록 예시 ex12를
  붙였는데도 그랬다), 모호 질문 e16·e17(세 arm 모두 구간 안 집계를 sum으로 짐작).

A → C: e01·e03·e12가 좋아졌고 나빠진 문항이 없다. e07은 A와 다른 이유로 여전히 틀린다.

후처리와 모델 출력의 분리(`analyses/replay-v1`): 102개 관측의 원문을 현재 코드로 다시 돌리면 모두
기록과 같고, 같은 원문을 예시 on/off로 돌린 결과도 102/102 같다. 즉 arm 사이의 차이는 모두 예시가
모델 출력을 바꾼 영향이다. condition_check를 끄고 같은 원문을 돌리면 A 12, B 8, C 14 관측의 결과가
달라진다(주로 LLM이 지어낸 기간을 질문 표현으로 되돌린 것. 예: C의 e08 원문 `20240401-20240430`).

판정(측정 전 규칙)
- **B(검색)는 A보다 낫다는 조건을 만족하지 못했다.** correct 18 = 18, 조용한 오답 12 = 12, 부당한 거부
  4 > 2 + 1. "이 규모에서 개선을 보이지 못함"이며 부당한 거부는 늘었다.
- 검색 효과(B − C ≥ 2)도 성립하지 않는다. 오히려 고정 예시 C가 A보다 correct +6, 조용한 오답 −2,
  부당한 거부 −2였다. C는 판정 대상이 아니었으므로 이것을 결론으로 쓰지 않는다. 이 셋은 이제
  development이며, 고정 예시의 효과를 주장하려면 새 셋이 필요하다.
- 기본값은 끔으로 유지한다.

## 8. 개선된 오류와 남은 오류

| 오류 | development(6문항) | 비교 평가(17문항) |
|---|---|---|
| "평균 중 가장 큰 값"을 "그 값을 가진 구간"으로 해석(값/구간) | 검색으로 고쳐짐(r3). 고정 예시로는 안 고쳐짐 | A는 결과 종류 4/28 틀림 → B·C 0~2. B의 결과 종류·outer는 판정된 것 전부 맞음 |
| "가장 큰 주"를 order·limit으로 적음 | structured 계약에서는 관측되지 않음(flat에서만) | 세 arm 모두 0 |
| 시간 구간을 `dimension=week`로 적음 | 검색·고정 예시 모두 고침(r2) | A e12 → B e12는 고침, e07은 새로 생김. C는 0 |
| 내부·외부 집계 혼동 | — | B에서 내부 집계 오류가 늘었다(e05·e08). 가장 비슷한 예시의 reducer를 옮기는 것으로 보인다 |
| 목록 질문을 값 하나로 답함 | — | 세 arm 모두 남음(e14·e15) |
| 모호한 구간 안 집계를 짐작 | — | 세 arm 모두 남음(e16·e17) |

원인 기록
- lexical 유사도는 조건 표현(가람구·개인택시·매출·7월부터 8월까지)이 겹치는 예시를 위로 올린다.
  e01–e04는 모두 ex14(가람구 개인택시 7–8월 월별 매출 합계 평균)가 1순위였다. 검색 입력에서 조건
  표현을 빼지 않았기 때문에 집계 구조가 아니라 조건이 닮은 예시가 붙는다.
- 1순위 예시의 구간 안 reducer가 현재 질문과 다르면 모델이 그 reducer를 옮기는 경우가 있었다(e05: ex05의
  sum, e08: ex06·ex07). 고정 예시 C에는 이 형태의 충돌(현재 질문과 표면이 닮고 reducer만 다른 예시)이 적다.
- 고정 예시 C는 최소 대조쌍(ex09·ex10, 같은 문장에서 값/구간만 다름)을 항상 보여 준다. B는 문항에 따라
  대조쌍의 한쪽만 붙는 경우가 많았다(e05: ex05·ex09·ex07).

## 9. 논문과의 대응과 차이

| 논문(§3.4, 부록 E.1) | 이 프로젝트 | 차이 |
|---|---|---|
| 예시 저장소 E = {(q_i, G_i)} | 16개 예시, 질문 + 검토한 grounding + graph 직렬화 | grounding(개념·역할·factor·aggregation_plan)을 함께 둔다. 이 프로젝트의 LLM 출력이 graph가 아니라 grounding이기 때문 |
| G_i를 텍스트 설명으로 직렬화 | transformation마다 한 줄, 조건 값 제외 | 조건 값이 prompt로 새지 않게 값을 뺐다 |
| q의 임베딩과 q_i 임베딩의 cosine top-k | 인터페이스·index·결정적 순서 구현. 평가는 lexical(문자 n-gram TF-IDF) cosine top-3 | **임베딩 검색을 실행하지 못했다**(환경 제약). lexical 결과를 임베딩 검색 결과로 해석하면 안 된다 |
| 검색 예시가 template 조합의 parameter binding·edge instantiation을 안내 | 검색 예시는 grounding(질문 해석) 문맥일 뿐. 조합은 composer가 결정적으로 한다 | LLM이 예시를 보고 변환·port 연결을 drafting하는 단계는 없다 |
| 예시 수·선택 기준 비공개 | top_k 3(상한 5), max_chars 3000, 등록 검증 통과 예시만 | 예시 수와 prompt 크기를 제한하고 넘치면 뺀 이유를 기록 |
| — | 저장소 hash·예시 판으로 오래된 index 거부, 검색 기록 저장, 고정 예시 비교군 | 재현성과 평가를 위해 더한 것 |

논문의 retrieval 전체를 재현했다고 보지 않는다. 구현한 것은 질문–graph 예시 검색과 grounding 문맥
제공이고, 유지한 것은 결정적 macro 조합·검증·실행이며, 검색을 이용한 LLM의 변환·port 연결 drafting은
구현하지 않았다.

## 10. 다음 최소 작업

1. 검색 입력에서 조건 표현(장소·기간·택시 유형)을 가리고 집계 표현만으로 유사도를 재는 정규화 v2와,
   고른 예시와 함께 그 예시의 대조쌍을 항상 붙이는 선택 규칙을 만든다. 둘 다 이 평가를 본 뒤의 변경이므로
   새 평가 셋(fresh)으로 A/B/C를 다시 잰다.
2. 임베딩 실행 환경을 쓸 수 있게 되면(Ollama embedding 활성화와 embedding 모델 설치는 사용자 승인이
   필요하다) `python example_retrieval.py build --ollama-model MODEL --out ...`로 index를 만들어 같은 셋에서
   lexical과 비교한다.
3. 목록 질문과 모호한 구간 안 집계는 예시만으로 고쳐지지 않았다. 계약 쪽 대안(목록 결과 형태를 grounding
   계약에 넣을지, 모호성 판정을 코드로 할지)을 따로 설계한다.
4. 예시 저장소의 질문 의미 검토를 사용자가 확인한다(현재 `reviewed_by`는 작성자 검토만).
