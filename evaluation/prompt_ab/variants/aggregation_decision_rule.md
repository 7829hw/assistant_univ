# 두 단계 집계 grounding H0 vs H2 판정 규칙 (사전 등록)

holdout 측정 **전에** 고정했다. 구현은 `aggregation_ab.py`의 `decide()`이며, 이 문서와 같다.

- **측정:** `evaluation/paraphrases_aggregation_holdout.yaml` (fresh, 23 intent, 69 paraphrase)
- **arm:** `H0_AGG`(production, 64bbceb4) vs `H2_AGG`(04d7baed). 재질의 문구는 두 arm이 같다(5af4c744)
- **protocol:** isolated_state_v1, paraphrase마다 arm당 1회, 반복 없음. planner 재시도는 관측 전체를 다시 시작하고, 다시 생기면 무효다(f3b0eb0)
- **채점:** Tool 인자까지 보는 strict

## 정의

| 이름 | 뜻 |
|---|---|
| 조용한 오답 | 계획이 검증을 통과했는데 strict 오답이다. 지원 범위 밖 질의에 계획이 만들어진 경우도 포함 |
| strict 정답 intent | intent의 모든 paraphrase가 최종 strict 정답 |
| 조용한 오답 intent | paraphrase 하나라도 조용한 오답인 intent |
| 명시된 두 단계 | 의미 golden에 bucket이 있고 inner가 unspecified가 아닌 paraphrase |
| 안쪽 미지정 control | 의미 golden에 bucket이 있고 inner가 unspecified인 paraphrase |
| 안쪽 지어냄 | 안쪽 미지정 control에서 avg 아닌 inner를 적음 |
| 구간 없음 | D칸 |
| 파이프라인 실패 | lowering 뒤 합성·operator·검증 단계의 실패 code |

## 판정 (우선순위: 조용한 오답 intent → strict 정답 intent → 안전한 거부 → paraphrase strict → 재질의 → 복잡도)

| 검사 | 조건 |
|---|---|
| A | 명시된 두 단계의 조용한 오답: H2 < H0 |
| B | 안쪽 지어냄: H2 ≤ H0 |
| C | 구간 없음 strict 정답: H2 ≥ H0 |
| D | H2에만 있는 조용한 오답 intent가 없고, 조용한 오답 intent 수 H2 ≤ H0 |
| E | strict 정답 intent 수: H2 ≥ H0 |
| F | 파이프라인 실패 수: H2 ≤ H0 |

- **Case A:** A~F 모두 성립 → H2 production 구현을 다음 별도 단계로 추천. 이번 단계에서는 제품 commit을 하지 않는다.
- **Case A_TRADEOFF:** E만 실패 → 사람이 판단한다. 자동으로 채택하지 않는다.
- **Case C:** 조용한 오답 intent 수 H2 > H0, 또는 같으면서 strict 정답 intent 수 H2 < H0 → H2 폐기. 두 단계 집계는 현재 모델과 grounding의 한계로 기록. 추가 prompt 조정을 중단한다.
- **Case B:** 그 밖 → 채택하지 않는다. known limitation으로 유지.
- **Case D(development에서는 좋고 holdout에서 뒤집힘):** 이번에는 development 비교를 측정하지 않았으므로 해당하지 않는다. development 질의 3개로는 parse·lowering 실행만 확인했다.

결과를 본 뒤 H2 prompt를 고치고 다시 재지 않는다. 이 holdout은 측정 뒤 development로 바꾼다.
