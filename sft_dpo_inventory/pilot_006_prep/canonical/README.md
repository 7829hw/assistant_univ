# canonical 계층과 기존 데이터 변환(W5)

작성: 2026-10-15(pilot_006 준비 세션 1). **승인이 아니다.** 초안(batch007)은 초안 표시를 유지했다. 모델 호출 없음.

## 코드(`grounding/`, SEMANTIC_CODE 밖, Full 지문 `791c4a68` 그대로)

| 파일 | 내용 |
|---|---|
| `canonical.py` | 레코드 = execution 층(vendor Tool 호출 열) + semantics 층(nodes: subtype·value·text span·attributes(od_role)·override, event, factors, unsupported). `view`는 measure·conditions(subtype, span, value, od_role)·dimension·dimension_target·bucket/rollup·aggregation·order/limit·vicinity·refusal 요약 |
| `full_renderer.py` | semantics → Full target(id·concept·role·source를 ontology로, override 우선, EVENT는 있던 경우만) |
| `partial_renderer.py` | semantics → Partial target(P0: subtype·value·text·attributes, EVENT 없음. partial-grounding `build_targets.convert`와 같은 규칙) |
| `completion.py` | Partial → 구조 필드 채움(W3 이식) |
| `validation.py` | 검증 사슬(계획서 v2 5.2): render_full과 completion 뒤 render_partial을 T2PC 경로(`assess_t2pc`)와 mock 실행에 각각 넣어 판정·서명(EVENT 제외)·Tool 호출·결과가 같은지 |

## 변환 결과(`build_canonical.py` → `canonical_records.jsonl`, `conflicts.json`, `validation_summary.json`)

| 출처 | 레코드 | 검증 사슬 통과 | Full 경로가 mock에서 답함 |
|---|---:|---:|---:|
| trunk `reviewed_gold_v006_t2pc`(pilot_004 판 131질문) | 131 | 131 | 83 |
| pg `reviewed_gold_v006_p0` | 154 | 154 | 115 |
| pg `reviewed_reasoning_v001` | 154 | 154 | 115 |
| batch007 초안 | 27 | 27 | 11 |
| 합계(질문 205) | 466 | **466** | 324 |

- 통과 = Full과 Partial 표현이 같은 판정(parse·outcome·오류 코드·validation·operators·compile), 같은 grounding 서명(EVENT 제외), 같은 mock Tool 호출·결과.
- Full 경로가 mock에서 답하지 못한 142건(두 표현 모두 같음): mock 실행 UNSUPPORTED_COMBINATION 56, mock 장소 NOT_FOUND 51, T2PC 조건 계층 UNCONSUMED_CONDITION 30,
  MISSING_REQUIRED_INPUT 5. 승인된 trunk 레코드에도 있으므로 mock 환경의 한계로 본다(이 레코드들은 실행 확인이 약하다).
- **conflicts: 0.** 여러 출처에 있는 질문 154개(trunk와 pg가 함께 가진 v005 111질문 포함)에서 semantic_key(text span 제외)가 모두 같다. text span만 다른 경우도 0.
- pg `target_p0` 308개가 `render_partial`과 모두 같다(변환 규칙이 pg와 같음).
- id: trunk `t2pc:<id>`, pg `pg:<id>`, pg batch006은 `pg:pg-b006-NN`(trunk `b006-NN` 24개와 이름만 같고 내용이 다르다, 결정 111), batch007 `b007:<id>`.
