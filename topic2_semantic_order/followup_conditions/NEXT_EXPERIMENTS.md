# 남은 우선순위

1. 승인된 단일 UUID와 실행 한도를 받아 C/D 및 F0/F48을 사전등록 순서대로 실행한다. 첫 3 seed는 기술 검증이다. 성능에 근거해 뒤 2 seed를 바꾸지 않는다.
2. A/C와 B/D를 비교해 LR interaction을 추정한다. Fine 대조는 F0/B/F48을 직접 비교한다. 반복 간 T1 변동과 효과 크기를 함께 보고한다.
3. 독립적으로 고정한 추가 seed와 여러 동일 순서 run에서 학습·평가 변동을 분리한다. 기존 세 seed는 사후 선택되었다. 같은 adapter를 동일 backend에서 반복 평가하면 serving 변동 성분을 별도로 추정할 수 있다. 별도 계획·GPU 승인 필요.
4. 시간 간격, recency, switch frequency를 분리한 순서와 loss-token exposure를 맞춘 순서를 각각 별도 통제 실험으로 고정한다. 개발 정답이나 오류를 순서에 쓰지 않는다. TRAIN view 서명과 실행 의미의 동치 감사도 별도 과제로 둔다.
5. coverage는 사람의 대체 corpus 승인, C-1 예외, 보호 목록과 audit receipt 및 budget matching이 갖춰진 뒤 새로 동결한다. H-final은 계속 봉인한다.
