# grounding 정리 단계의 값 형식 예외 수정 (fix-condition-hoist)

작성: 2026-10-06. 브랜치 `geoflow/fix-condition-hoist`(시작 `a64eb50`). 모델 호출 없음. prompt·평가 라벨·기존 기록은 바꾸지 않았다.

## 1. 재현

- **보고된 경로.** `geoflow/sft-dpo-t2pc`의 `sft_dpo_inventory/baseline_conditions_001` B·C 셀(qwen3:8b, think off)에서 업체 100 057의 첫 응답이 문제였다.
  - 형태: subtype이 빈 OBJECT 개념에 `value: {"region": ...}`(dict)가 들어 있었다.
  - 결과: `hoist_condition_concepts`의 `raw.get("value") in _CONDITION_SUBTYPES`에서 `TypeError: unhashable type: 'dict'`로 끝났다.
- **현재 코드에서 다시 확인했다.** 기록 원문을 `git show`로 읽어 현재 dev-v2(`a64eb50`) planner 입구에 넣었다(기록 파일은 이 브랜치로 복사하지 않았다).
  - condition_check 켬과 끔 모두 같은 `TypeError`가 났다.
- **최소 형태 테스트**(`tests/test_grounding_value_shapes.py`):
  - subtype 없는 OBJECT에 dict 값
  - 조건 이름 subtype(`taxi_type`)에 dict·list 값
  - subtype 자체가 dict·list
  - 고치기 전에는 재현 테스트 15건이 오류였고, 형식 변이 테스트는 725건이 계약 오류가 아닌 예외로 끝났다.

## 2. 찾은 위치

형식 변이 검사는 다음 조합을 모두 돌린다.
- 정리 규칙별 출발 grounding 5개.
- 개념 필드: `concept`, `subtype`, `role`, `source`, `value`, `text`, `attributes`, `od_role`, `attributes.od_role`, `value.name`, `value.region`, `id`.
- factor 전부와 `concepts`·`factors` 자체.
- 넣는 값: dict, list, 정수, 실수, bool, null, 문자열.
- 입구 4가지: `parse_grounding`, `parse_grounding(normalize=False)`, planner `_validate_payload`(condition_check 켬·끔).
- 합계 6,972 경우다.

계약 오류(`PlannerError`)가 아닌 예외가 난 위치:

| 위치 | 원인 | 값 |
|---|---|---|
| `grounding._hoist_structural_factors` | `dict(attributes)` | attributes가 정수·list·문자열 등 |
| `grounding._unit_text` | `text.strip()` | text가 문자열이 아님 |
| `grounding.normalize_place_concepts` | `factors.get`, `name/region.strip()` | factors가 object가 아님, 장소 name·region이 문자열이 아님 |
| `grounding.hoist_condition_concepts` | `value in _CONDITION_SUBTYPES`, `subtype in …`, `value in FACTOR_SPECS[…].values`, `factors.get` | value·subtype이 dict·list(보고된 버그) |
| `grounding.parse_grounding` factor 병합 | `{**hoisted, **raw_factors}` | factors가 object가 아님 |
| `conditions._measure`, `check_places` | `for item in concepts`, `attributes.get` | concepts가 list가 아님, attributes가 object가 아님 |
| `conditions.consumable`·`fixed_by_measure` → `operator_registry.accepts` | `(concept, subtype) in allowed` | 측정값 subtype이 dict·list |
| `conditions.reconcile_payload` | `payload["factors"].items()` | factors가 object가 아님 |
| `grounding._parse_attributes` | `od_role not in OD_ROLES` | od_role이 dict·list |

- 마지막 줄은 요청한 범위(`_parse_concept` 이전 정리 단계) 밖인 형식 검증 안이다. 사용자 승인을 받아 같은 방식으로 고쳤다.
- 고친 뒤 6,972 경우 모두 성공하거나 `PlannerError`로 끝난다.

## 3. 수정

원칙: 형식이 맞지 않는 값은 "이 정리 규칙에 해당하지 않음"으로 보고 그대로 넘긴다. 그러면 기존 형식 검증이 계약 오류로 거부한다.

- **올바른 형식은 같은 분기를 지난다.**
  - 문자열이 아닌 hashable 값(정수 등)은 수정 전에도 포함 검사가 거짓이었다.
  - 빈 값(`None`, `""`, `[]`, `{}`)은 수정 전과 같이 빈 값으로 읽는다.
  - `dict(attributes)`가 성공하던 입력(쌍의 list 등)은 그대로 변환된다.
- **정리 규칙을 넓히거나 새 해석을 넣지 않았다.**
- **pipeline 전체를 감싸는 예외 처리는 넣지 않았다.**
- **조건 계층에서 factors가 object가 아닐 때.** 수정 전에는 `{}`로 바꾼 뒤 예외로 끝났다.
  - 수정 후에는 payload를 바꾸지 않고 넘겨 `INVALID_FACTORS`로 거부한다.
  - 비우고 계속하면 잘못된 출력이 조건 없는 유효한 grounding이 되기 때문이다.
- **`od_role`.** 문자열이 아니면 문자열 오답과 같은 `INVALID_OD_ROLE`로 거부한다.

**057 첫 응답의 수정 후 결과** (condition_check 켬·끔 같음):
- `INVALID_CONCEPT`("concepts[0]: subtype가 비어 있습니다")로 멈춘다.
- `repair.decide`는 재질의 대상이 아니라고 판정한다(NOT_REPAIRABLE). T2PC 운영에서는 계약 오류로 끝나고 재질의 호출은 생기지 않는다.
- 실제 모델 호출로는 확인하지 않았다.

## 4. 기존 기록 재적용(동작이 같은지)

`verify_rerun.py`, 결과 `rerun_verification.json`. 기록된 모델 응답(계획·재질의)을 순서대로 넣어 `evaluate_vendor100.py rerun`으로 다시 실행했다.

| 기록(지문 97efa866, 커밋 2f53c72·e07ddd4·ad96729) | 기록 수 | 문항 |
|---|---:|---:|
| grounding_v13 개발 428(v11 full t2pc 9셋, v11 heldout, v12 measure) | 11 | 428 |
| grounding_v13 최종 56 | 1 | 56 |
| grounding_v11 small t2pc | 8 | 65 |
| grounding_v13 q8_t2pc(qwen3:8b + T2PC 코드·prompt) | 10 | 136 |
| grounding_v14 운영(C1, W1–W3, eval_warm) | 5 | 230 |
| sft-dpo-t2pc E·F(qwen3:8b, think auto·off; `git show`로 저장소 밖에만 꺼냄) | 2 | 200 |
| **합계** | **37** | **1,115** |

- **새 코드(지문 791c4a68):** 1,115문항 모두 원 기록과 같았다. 비교한 항목은 v3 범주, v4 분류, `grounding_ok`, 오류 코드, outcome이다.
  - `request_match` 불일치 0, `needs_live` 0.
- **수정 전 코드(a64eb50) 대조:** 차이 0. 재적용 자체가 기록을 그대로 재현한다.
- **제외한 기록:** T2P 후보(aa57c88, 지문 e063ca30)의 기록과 그 재적용 기록은 지문이 달라 넣지 않았다.
- 재적용 결과 파일은 저장소 밖에 있고, 각 파일의 sha256은 `rerun_verification.json`에 있다.

## 5. 새 지문과 명세

- **실행 의미 코드 지문:** `97efa866…` → `791c4a68a59647131321e3efad2325e549a46bc522230b25b2954a88c42eac6e`.
- **갱신한 곳:** `assistant_cli.py` T2PC 명세의 `code_fingerprint`, README "실행 기본값" 표와 근거 문단.
  - 모델·prompt를 바꾸지 않았고 모델 재측정 없이 갱신했다. 근거는 4절이다.
- **B 명세(`7e99136d…`)의 코드에는 같은 버그가 남아 있다.**
  - 별도 worktree에서 `scripts/geoflow_rollback_to_b.sh`를 실행해 확인했다. 되돌림 자체는 B 명세와 일치했다.
  - 그 뒤 `tests/test_grounding_value_shapes.py`가 실패했다(변이 719건, 재현 15건). 되돌리기 스크립트는 이 테스트를 지우지 않는다.
