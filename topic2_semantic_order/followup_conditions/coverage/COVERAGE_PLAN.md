# Experiment 4 — Coverage × ordering, 준비 전용

**BLOCKED.** 행은 동결 V4 vs 승인된 대체 V4, 열은 O4′ vs semantic fine_weight=0.24. 기존 V4 두 셀은 재사용한다. 대체 corpus를 먼저 동결하고 양쪽 순서가 동일한 레코드를 정확히 한 번 소비한다. 향후 대조는 (대체 semantic−대체 O4′)−(V4 semantic−V4 O4′)이다. seed는 기존 5개를 공유할 수 있다. 별도의 신규 GPU 승인과 새로운 분석 동결 후에만 실행할 수 있다.

44개 approved fare 질문의 C-1 cap 예외 결정과 batch014 승인 여부는 별개다. 현재 어느 자료도 추가 학습에 사용하지 않는다. 새 질문의 human approval, 레코드별 teacher/self trace 승인과 content SHA, 교체/제거 목록을 받는다. 별도 권한이 있는 데이터 관리자가 생성한 protected ID 및 family blocklist와 exact/verbatim/skeleton 겹침 검사 영수증이 필요하다. 저장소 `ablation_012/e2/build_e2.py`의 `PoolRule`은 재사용 기준이다. CT10K, H-dev, E1, 기타 protected/dev/diagnostic은 격리한다. 봉인 자료 원문을 이 작업으로 가져오지 않는다. 서명·정규화의 차이 때문에 ID만으로 통과시키지 않는다.

1,984 records, 1,984 steps, 1,079 teacher full_response 및 905 json_only 정확히 일치. pinned tokenizer와 TRL mask로 총 loss token ±1%, teacher loss-token share ±1pp. 질문 수와 교체 및 그룹별 토큰 변화도 보고한다. 승인된 두 군의 optimizer·LR·LoRA·thinking ON·prompt는 동일하게 유지한다. 구조적으로 밀접한 승인된 대체 후보가 없으면 중단한다. 이 검증이 사람의 데이터 승인을 대신하지 않는다.

기존 `audit_coverage_arm.py`는 승인된 질문과 blocklist, ledger를 소비하며, `coverage_o4prime.py`는 성공 보고서와 candidate hash를 확인한 다음 NumPy O4′ 순서를 생성한다. 새 검증은 기존 검증 함수에 레코드 내용 해시, 독립 PoolRule 검사 영수증, teacher 할당량, 기존 레코드 내용 변경 금지를 추가했다. 승인 후 `python topic2_semantic_order/followup_conditions/coverage/validate.py --bundle <reviewed-dir> --approval <signed-decision-json>`로 시작한다. JSON은 `decision: APPROVED_COVERAGE_REPLACEMENT`, `review_reference`와 requirements.yaml의 모든 파일에 대한 `sha256` 매핑을 포함한다. 감사 통과 이후에만 별도 order output을 생성할 수 있다. 현 브랜치에 coverage config/launcher를 활성화하지 않았다.
