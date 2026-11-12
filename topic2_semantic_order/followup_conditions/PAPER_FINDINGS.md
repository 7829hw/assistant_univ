# 논문용 발견과 주장 범위

**새 분석으로 추가할 수 있는 결과:** 같은 1,984 레코드에서 coarse record window TV는 9.16%→1.21%, loss-masked TV는 10.37%→9.83%, LR×loss TV는 10.70%→10.51%였다. 실제 renderer와 completion-only collator로 계산한 908,705 supervised tokens 및 10개 원래 step 로그로 근거를 제시할 수 있다. 데이터 수를 보존하는 순서 개입의 **기계적** 효과를 설명한다. 새 순서의 CPU ablation은 0.24→0.48이 fine record TV를 단조롭게 개선하지 않음을 보여준다.

**기존 실험의 재현 및 추가 분해:** 기존 CT10K/T1 평균을 재현했다. T1의 base→SFT 전이와 오류 구성은 이 세션의 추가 분석이다. A→B silent wrong 10.3%→37.5%, unsupported refusal 11.4%→13.8%. 전체 CT10K의 −5.93pp 추정은 CI가 0을 포함한다. 세 seed × 세 run H-dev 반복 결과는 이미 완료된 기존 연구를 재분석한 것이며, 독립 재현이 아니다. 이 조건에서 관찰된 매우 큰 T1 반복 변동을 보고할 수 있다.

**사용할 수 없는 주장:** 균형이 모든 환경에서 해롭다, 내부 capability를 잃었다, LR이나 감독량 부족 때문에 요금이 무너졌다, 최적 fine weight가 존재하거나 coverage가 성능을 회복한다, H-dev가 이 분석의 독립 검증을 제공한다. 원래 S1–S4와 새 실험의 예정 지표는 별도다. 모든 성능 결론은 하나의 모델·recipe·도메인 및 개발 평가에 한정한다.
