# Partial Grounding 실현 가능성 검증 (2026-10-09)

설계안: `geoflow_partial_grounding_design.md`(LLM은 subtype·value 등 의미 판단만 출력하고, 구조 필드는
`parse_grounding()`이 ontology에서 채운다). branch `geoflow/partial-grounding`.
모델 호출과 GPU는 쓰지 않았다. 기록된 LLM 응답을 현재 코드로 다시 실행해 확인했다.

## 결론

실현 가능하다. 다만 설계안 그대로가 아니라 아래 네 가지를 고쳐서 적용해야 한다.

| 설계안 | 검증 결과 | 구현에서 택한 것 |
|---|---|---|
| 6.1 subtype → concept | subtype 이름이 concept 사이에 겹치지 않아 하나로 정해진다 | `CONCEPT_SUBTYPES` 역방향 표 |
| 6.2 role | 대부분 정해진다. 예외: 값 있는 장소의 `EXTENT`(정상 경로, 테스트 있음), 답이 장소인 질문(값 없는 place = MEASURE), 그룹 단위 말을 적은 값 없는 SUBCOND 장소(정리 규칙이 뺌) | 비었을 때만 채운다. place는 값이 있으면 SUBCOND, 없으면 MEASURE |
| 6.3 source (measure = user) | **설계안과 다르다.** 현재 계약에서 MEASURE와 EVENT의 source는 `implicit`이다(gold 111건, 기록 4만여 건 모두) | SUBCOND·COND = user, SUPPORT·MEASURE = implicit |
| 6.4 id | parser가 붙여도 된다. 재질의는 `Grounding.to_dict()`(채워진 id) 위에서 돌므로 일관된다 | `{subtype}_{순번}` |
| 6.5 support EVENT | **이미 composer가 한다**(`MacroComposer._infer_port`, OD 질문 포함). parser가 더하면 중복이고 `inferred` 표시가 사라진다 | parser는 EVENT를 더하지 않는다 |
| 14 충돌하면 거부 | **하위 호환이 깨진다.** 시험 구현에서 기존 테스트 12건 실패(EXTENT 장소 거부, 오류 코드 변경, 정리 규칙 이전에 거부). concept 충돌은 기존 `INVALID_SUBTYPE`이 이미 거부한다 | 적힌 값은 고치지도 거부하지도 않고 기존 계약 검사에 맡긴다 |
| 9 completion은 `parse_grounding()` 안 | **부족하다.** 조건 대조(`conditions.reconcile_payload`)가 parse 전에 raw payload의 concept·role·source·id를 읽는다 | planner가 조건 대조 전에 한 번 더 부른다(멱등). 기록은 `normalizations`에 남긴다 |

추가로, 조건을 개념으로 적는 출력(`OBJECT/private`)을 factor로 옮기는 기존 정리 규칙이 `concept == "OBJECT"`에
기대고 있어서, concept이 비어 있으면 같은 규칙이 적용되도록 넓혔다(조건 값은 어느 concept의 subtype도 아님).
`text`는 생략 대상에서 뺐다. 장소 근거 확인(`check_places`)과 정리 규칙이 읽는다.

## 재실행 실험

`replay_partial.py`: vendor100 형식 run 35개(3,398문항, cell B–F, HF-E, pilot SFT/DPO, path_repeat
greedy/sampling)의 첫 계획 응답을 (full) 그대로, (partial) `id·concept·role·source`와 EVENT 개념을 지운 것으로
넣어 같은 코드로 실행했다. 재질의 응답은 기록 그대로 쓰되, 가리키는 id만 새 id로 바꿨다.

- full arm은 기록을 재현한다(cell E grounding_ok 79, match 84).
- 3,398문항 중 3,238건(95.3%)은 Tool 호출·오류 코드·채점 범주가 완전히 같다.
- 정답(match 또는 올바른 거부 `expected_refusal`) 기준으로 Full 정답 → Partial 오답은 **0건**,
  Full 오답 → Partial 정답은 46건이다. 나머지 114건은 오답끼리 바뀌었다.
- 현재 기준 조건(E, HF-E, pilot HF-sft/HF-final, ollama_greedy): 100/100 동일.
- 약한 조건일수록 이득이 크다: HF base match 50→58, cell F 55→59, HF-F 53→56.
  모델이 틀리게 적은 구조 필드(EVENT 잘못 선택, role/source 오기)가 partial에서는 생기지 않기 때문이다.

원인별(`analysis.txt`, 한 문항이 여러 원인에 들 수 있음. 개선/중립 = 정답 여부가 바뀜/그대로):

| 원인 | 개선 | 중립 |
|---|---:|---:|
| EVENT가 측정값의 사건과 다름 | 42 | 52 |
| role/source 오기 | 27 | 82 |
| 답이 장소인 MEASURE | 0 | 15 |
| ontology 밖 subtype | 7 | 10 |

**정정(2026-10-09).** 처음 판에는 "퇴행 6건"이라고 적었다. 분석 스크립트가 `refused_unsupported`를 올바른 거부로
셌기 때문이다. `score()`에서 그것은 답해야 할 문항을 거부한 오답이고, 올바른 거부는 `expected_refusal`이다.
6건(질문 5개)은 gold가 모두 answered다. full은 잘못된 EVENT 때문에 `NO_OPERATOR`로 틀리게 거부했고, partial은
답했으나 모델이 적은 다른 의미 값(장소 누락, 날짜 표기, dimension 등)으로 틀렸다. 거부되어야 할 이유가 없으므로
capability·검증 규칙을 더하지 않는다. 이 6건은 `regression_event_refusal.yaml`로 고정했고, 사건 추론으로 거부가
사라지는 동작은 `tests/test_partial_grounding.py`(`EventRefusalRegressionTest`)가 확인한다.

출력 길이: gold 111건의 최종 JSON은 Qwen3-8B tokenizer로 평균 125 → 68 토큰(−46%). thinking ON에서는
응답당 eval이 약 1,000토큰이라 전체 출력 기준 절감은 수 %다.

## 한계와 다음 단계

- 이 실험은 "모델이 같은 의미 판단을 하고 구조 필드만 생략한다"는 가정의 상한 확인이다. 실제로 partial을
  출력하도록 prompt를 줄였을 때(설계안 Phase 4) 모델의 의미 판단이 유지되는지는 LLM 측정이 필요하다
  (Phase 5: 같은 모델 Full vs Partial prompt, Ollama/HF 순차 측정).
- 실행 의미 코드가 바뀌어 fingerprint 고정 테스트 3건이 실패한다(`test_cli_run_settings` 2건,
  `test_path_repeat_sampling` 1건). 실제 모델 실험이 끝나 동작을 확정한 뒤 한 번만 갱신한다. 나머지는 통과한다.

## 파일

- `replay_partial.py`: 재실행. `analyze_replay.py`: 원인 분류.
- `replay_result.json`, `replay_log.txt`, `analysis.txt`: 결과. `regression_event_refusal.yaml`: regression set.
- 구현: `geoflow/grounding.py`(`complete_grounding_payload`, `hoist_condition_concepts`),
  `geoflow/planner.py`. 테스트: `tests/test_partial_grounding.py`.
