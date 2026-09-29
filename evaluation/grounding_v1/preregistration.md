# grounding 개선 평가 사전 등록 (grounding_v1)

작성: 2026-09-29, 후보 실행 전. 기준 커밋 `cfd1bd0`(위임·로컬 책임 분리 `e828ba9` + query_loader id 수정).

## 평가셋의 역할

| 셋 | 역할 | 이 작업에서의 사용 |
|---|---|---|
| 업체 100문항(`evaluation/vendor100/gold.yaml`) | **개발·회귀셋** | 실패 원인 분석과 후보 선택에 쓴다. 이 셋의 향상은 일반화 성능이 아니다 |
| `evaluation/grounding_v1/holdout_questions.yaml`(44문항) | **독립 평가셋** | 후보 선택에 쓰지 않는다. 기준(B0)과 최종 후보에서 각 1회만 실행한다 |
| holdout_v2(126문장) | 기존 development(이미 열람됨) | 쓰지 않는다 |

독립 평가셋은 Claude가 작성했고 사람이 검토하지 않았다. 업체 100문항과 문장 틀·조건 조합이 다르지만, 개발셋의
실패 유형(택시 상태, 요일 토큰, 출발·도착, 두 단계 집계, 구간 선택 등)을 알고 만든 것이므로 그 유형에 대한
일반화를 재는 셋이며 모든 표현에 대한 일반화를 뜻하지 않는다.

gold 라벨의 오류는 LLM 실행 전에만 고친다: 정답 grounding 실행(`evaluate_vendor100.py --gold … gold`)으로 라벨이
코드 계약과 맞는지 확인하고, 맞지 않으면 라벨을 고친 뒤 이 문서에 적는다. LLM 결과를 본 뒤에는 라벨을 고치지 않는다.
결과를 본 뒤 셋을 개선에 쓰면 development로 전환했다고 적는다.

## 고정 조건

- 모델 `qwen3:8b`, temperature 0, think=auto, 질문마다 모델 unload(격리), Ollama 0.34.4
- 기준일 2026-09-25(Asia/Seoul), mock provider, TIMS legacy 실행 프로필(위임 허용)
- 채점기: `evaluate_vendor100.score`(업체 100문항과 같은 규칙). 기본값(taxi_type=all, taxi_status=all,
  dimension_target=both, aggregation=avg, region="", include_vicinity=false)은 생략과 같다. scope는 조회 결과 출처로
  대조한다. 답변은 Tool 반환값이 그대로 있어야 한다. 채점 규칙은 이 문서 이후 바꾸지 않는다.
  바꿔야 하면 전후 모두 다시 채점하고 적는다.
- `expected_outcome`이 answered가 아닌 문항(g17, g32: unsupported, g44: needs_clarification)은 결과 종류가 같을 때만 맞음.

## 보고할 지표(두 셋 모두)

1. 정답 grounding 기반 실행 정확도(LLM 없음)
2. 실제 LLM grounding 정확도: 최종 grounding의 개념(측정값, 장소 이름·지역·od_role, 사용자 scope)과 factor가 정답
   grounding과 같은가(기본값 정규화 후)
3. 전체 실행: Tool·인자·답변 일치(match), 잘못된 답변(answered_mismatch), 거부(refused_*), 실행 실패(failed)
4. LLM 호출 수(계획/재질의), 관측 지연(중앙값·합계)

## 채택 규칙(최종 후보, 개발셋 기준으로 정하고 독립셋으로 확인)

1. 개발셋 match가 B0보다 늘어난다.
2. B0에서 match였던 개발셋 문항 중 match가 아닌 것이 2개 이하이고, 각각 원인을 설명한다.
3. 잘못된 답변(answered_mismatch)이 B0보다 늘지 않는다.
4. 독립셋에서 match + 기대한 거부가 B0보다 줄지 않는다. 줄면 채택하지 않고 그대로 보고한다.
5. 추가 모델 호출을 도입하면 호출 수와 지연 증가를 함께 보고한다.

## 고정 기록

- `holdout_questions.yaml` sha256 `fac171e6c97ef20aee9a824a1c20217825266970e81b7abdb66b090ee91456d7` (이 문서와 함께 커밋, LLM 실행 전).
- LLM 실행 전 라벨 점검(정답 grounding, 기준 코드): match 41, 기대한 거부 2(g17 UNCONSUMED_CONDITION,
  g44 AMBIGUOUS_INNER_AGGREGATION), 정답 grounding 없음 1(g32, flat 표현 불가). 고친 라벨 없음.
