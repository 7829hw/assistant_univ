# 실패 조건과 근거

| 연구 질문 | 상태 | 현재 답 |
|---|---|---|
| Q1. 균형이 그룹 회귀를 줄였는가? | NOT SUPPORTED | V4·Qwen3-8B·1 epoch·선형 LR·0.24에서 동결 S1–S4를 모두 통과하지 못했다. B에서 20pp 초과 회귀 그룹과 T1 회귀를 관측했다. 전체 효과 CI가 0을 포함한다. |
| Q2. LR이 interleaving 효과를 바꾸는가? | BLOCKED | 동일 nominal LR 합의 C/D 설계와 CPU 검증만 완료했다. 성능 interaction을 계산할 데이터가 없다. |
| Q3. Fine balance 강도에 따른 성능 차이는? | BLOCKED | F0에서 fine exposure 불균형이 커졌고 F48의 fine 레코드 균형은 0.24보다 개선되지 않았다. 이 결과는 순서의 기계적 성질이다. |
| Q4. 어떤 그룹이 회귀하는가? | EXPLORATORY | T1에서 base-correct→wrong 및 silent wrong이 늘었다. coarse의 record TV 개선은 loss/LR×loss TV 개선으로 거의 전달되지 않았다. Gap, recency, 전환, 감독량의 성능 연관은 작은 서명 일치 집합에 한정되며, 인과 설명을 지지하지 않는다. Coverage interaction은 BLOCKED. |
| Q5. 순서 효과와 재학습 변동을 구분할 수 있는가? | INCONCLUSIVE | 같은 순서에서 run 차이의 존재는 SUPPORTED. 세 seed H-dev 반복 평균의 전체·T1 대비 CI에 0이 포함된다. seed, train-run, serving variability를 모집단 수준에서 식별하기에는 부족하다. |

확인된 범위: 정해진 V4 recipe에서 의미 그룹의 **레코드 노출 균형만으로 관찰된 기능 회귀를 방지하기에 충분하지 않았다**. 특히 coarse record exposure가 크게 균일해진 조건에서 감독 토큰 노출은 거의 균일해지지 않았고, T1 정확도가 매우 낮은 run이 남았다. 이 둘 사이의 매개 관계는 검증되지 않았다. 기존 A와 B는 within-question 순서도 다르고 시간 간격·전환·LR 노출이 함께 바뀌므로, 그 중 한 변수를 원인으로 식별할 수 없다.
