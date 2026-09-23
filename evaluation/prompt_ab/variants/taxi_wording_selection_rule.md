# 후보 선택 규칙 (selection 결과를 보기 전에 작성)

작성 시각: selection run 진행 중, 결과 미확인 상태.
입력: selection run(68 paraphrase x D_PRE/T0/T1/T2)의 재채점 결과.

지표 (arm별)
  S   strict 정답 수 /68
  TC  첫 응답의 taxi_type_as_concept 수 (택시 유형 개념 node)
  RA  첫 응답의 relation_attribute_as_factor 수
  B24 b24 intent strict 정답 수 /6
  B11 b11 intent의 relation_attribute_as_factor 수

T2 채택 조건 (§8 "T2 우세")
  TC(T2) = min(TC) 이고, B11(T2) = 0 이고, B24(T2) >= B24(D_PRE) 이고, S(T2) >= S(D_PRE)

T1 채택 조건 (§8 "T1 우세")
  TC(T1) < TC(T0) 이고, B24(T1) >= B24(D_PRE) 이고, RA(T1) <= RA(D_PRE) 이고, S(T1) >= S(D_PRE)

순서
  1. T2 조건을 만족하면 T2.
  2. 아니면 T1 조건을 만족하면 T1.
  3. 둘 다 아니면 "D_PRE 우세". rollback 후보가 강해진다.
     이때도 holdout은 돌린다. 후보는 S가 큰 쪽, 같으면 TC가 작은 쪽,
     그래도 같으면 T2(긍정문만 있어 알려진 위험 둘을 모두 피한다).
     holdout 결과로 Case B(동등) / Case C(악화)를 가른다.

T1과 T2가 둘 다 조건을 만족하면 1번 순서대로 T2를 고른다.
가설 판정은 후보 선택과 별개로 보고한다.
  가설 A(부정 literal): T1이 T0보다 b24에서 회복하면 지지.
  가설 B(일반 분류어의 번짐): b11 od_role 오배치가 T1에 남고 T2에서 사라지면 지지.
