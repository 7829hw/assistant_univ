# ablation_012 E2 — 새 holdout(결정 262)

원천 `/data/hwkim/sftdpo_work/sources/llm-finetuning-30000.jsonl`(sha256 `63d445b86bfb4a3444ba9eea632ba1ff03e51263f125ae4b35587b0c85102def`). 빌드 `build_e2.py`(모델 호출 없음), 요약 `e2_summary.json`.

**두 파일 모두 평가 전용이다. 학습·checkpoint 선택·annotation 후보에 쓰지 않는다.**

| 파일 | 문항 | 용도 | sha256 |
|---|---:|---|---|
| `h_dev.yaml` | 2,000 | ablation_012 개발 비교(H-dev) | `9c7a00784fb5da69c01037d9536e0f1099377aee3c4a9647b70745717f45d3df` |
| `h_final.yaml` | 3,000 | **봉인 — PLAN_J 판정 전용, 측정은 사용자 지시 뒤** | `bbc4265071be36f99630bfcc00fa832950c07a131e2007ba63a0274aa0697ddb` |

- 모집단: CT10K 모집단 16,206(tool_call 18,000 − 정답 날짜 > 20260925 1,794, 재현 확인) − CT10K 10,000 = 6,206.
  여기서 train_skeleton 606·verbatim_vendor100 3·짝 근거 없음 360을 빼 5,237(template_group 160).
- 겹침 판정: client_test_10000의 겹침 도구는 저장소에 없다(CT10K 파일에 pool 값만 있음). `build_e2.py`의 규칙을 다시 만들었다. 이 규칙은 CT10K 10,000문항의 pool 라벨을 모두 그대로 재현한다(`pool_rule_check.json`).
  규칙: verbatim은 질문 문자열이 같은 것, 날짜 변형은 date 인자를 뺀 정답 뼈대가 같은 것이다(vendor date last_year·weekday 제외). train_skeleton은 CT10K에서 train_skeleton으로 라벨된 vendor100 id 13개와 짝인 것이다.
  짝인 vendor100 문항이 CT10K에 없어 train_skeleton인지 알 수 없는 360문항은 보수적으로 뺐다.
- 참고 겹침: 남은 5,237문항 중 학습 corpus v6·E1(valid98·aux·refusal_dev v2)·CT10K와 질문 문자열이 같은 문항은 0개다.
- 나눔: template_group 비례 층화(`numpy.random.default_rng(20261103)`, 최대 잉여 배분). H-dev를 먼저 뽑고, 남은 것에서 H-final을 뽑았다. 둘 다 template_group 160개다.
  - H-dev pool: independent 897 · vendor100_date_variant 1,103.
  - H-final pool: independent 1,332 · vendor100_date_variant 1,668.
- gold_check(CPU, 정답 호출을 그대로 pipeline에 넣음): H-dev 2,000/2,000 match(`gold_check_h_dev.json`), H-final 3,000/3,000 match(`gold_check_h_final_summary.json`, 개수만).
- H-ref는 만들지 않았다. 비-tool_call 12,000문항(public_qa: trip_information_extraction 5,000 · term_definition 4,000 · schema_explanation 1,500 · condition_extraction 1,500)의 원천 라벨에는 구조화·정의·설명 응답만 있다.
  '거부' 기대 결과가 없어 원천 라벨만으로 거부가 확정되지 않는다. 기술 통계는 `e2_summary.json` `h_ref`에 있다.
- H-final은 이번 작업에서 측정하지 않는다. 문항 내용·결과는 보고에 쓰지 않는다.
