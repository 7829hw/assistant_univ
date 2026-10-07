# 새 선택용 셋·보조 시험 셋 후보 조사 (결정 41·42, 작업 지시 2)

작성: 2026-10-07. 모델을 부르지 않았다. 산출물: `survey.json`(셋별 이력, 문항별 조건), `options.json`(선택지별 규모).
스크립트: `survey_sets.py`, `options.py`. 질문 문장은 산출물에 넣지 않았다(셋·id·수·라벨 값만).

## 결론: 작업 지시의 규칙대로면 남는 셋이 없다. 셋을 만들지 않고 멈췄다.

작업 지시 2의 규칙은 "문항 단위 결과를 데이터 설계나 분석에 쓴 셋은 후보에서 뺀다"이다.
이 규칙을 v13·v14 비교까지 포함해 셋 단위로 적용하면, 정답 grounding이 있는 보호 개발 셋 중 남는 셋은 없다.

- 업체 100·stage_v7·heldout_v8·heldout_v9는 지시대로 뺐다.
- 나머지 11개 셋은 모두 grounding_v13 개발 비교(428문항)나 최종 검증(56문항)에 들어 있다. 문항 단위 결과도 보고서에 적혀 있다.
  - 예: `grounding_v13/selection.md`가 at/t05b, old44/g44, indepv3/m40, indepv4/k25 등을 문항별로 논의한다.
  - `final_report.json`·`grounding_v14/runs/ops`도 final 문항을 문항별로 적는다.
- 이전 판의 선례도 같다: `pilot_prep_002/valid_proposal`은 "grounding_v13 비교에 쓰지 않은 셋"만 valid 후보로 삼았고, 그 셋이 지금의 valid98이다.
- 다른 형식의 보호 셋(structured_grounding 4개, reference, retrieval; 합계 129문항)에는 정답 grounding이 없다.
  - 기대 plan·조건만 있으므로 조건 3(정답 grounding이 현재 pipeline을 통과)을 적용할 수 없다.

규칙의 해석(v13·v14 비교를 "분석"으로 볼지, 제외를 셋 단위로 할지 문항 family 단위로 할지)은 사용자가 정할 일이다.
그래서 아래에 선택지와 규모를 적고, 셋 생성·기준값 측정(HF-E)·PROTOCOL_v2의 셋 항목은 보류했다.

## 1. 셋별 사용 이력

칸의 값은 "그 기록에 들어간 문항 수 / 그중 문항 id가 보고에 따로 적힌 수"다. "–"는 쓰이지 않았다는 뜻이다.

| 셋 | 문항 | 지시 | v13 개발 비교 | v13 최종 | v14 기록 | 오류 유형 분석 = 공백 유형 = batch004 근거 | valid98 | pilot_001 분석 | 조건 통과 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|
| vendor100 | 100 | 뺌 | 100/14 | – | 10 | 3 | – | 100 | (해당 없음) |
| old44 | 44 | | 44/15 | – | 13 | 2 | – | – | 38 |
| contrast | 31 | | 31/4 | – | 4 | 4 | – | – | 25 |
| indepv2 | 40 | | 40/9 | – | 8 | 4 | – | – | 35 |
| indepv3 | 40 | | 40/14 | – | 13 | 4 | – | – | 33 |
| indepv4 | 40 | | 40/9 | – | 13 | 2 | – | – | 31 |
| at | 16 | | 16/6 | – | 3 | – | – | – | 14 |
| stage_v7 | 16 | 뺌 | – | – | – | – | 15 | 15 | – |
| heldout_v8 | 40 | 뺌 | – | – | – | – | 39 | 39 | – |
| od_v8 | 16 | | 16/5 | – | 4 | 16 | – | – | 13 |
| heldout_v9 | 48 | 뺌 | – | – | – | – | 44 | 44 | – |
| heldout_v10 | 48 | | 48/19 | – | 20 | 48 | – | – | 35 |
| status_v10 | 33 | | 33/12 | – | 8 | 33 | – | – | 27 |
| measure_v12 | 20 | | 20/11 | – | 10 | 20 | – | – | 14 |
| final_v12 | 56 | | – | 56/27 | 50 | – | – | – | 37 |
| cli_check_v14 | 6 | 사본 | – | – | – | – | – | – | 0 |

이력의 출처:

- **v13:** `evaluation/grounding_v13/runs/dev_report.json`, `final_report.json`.
- **v14:** `evaluation/grounding_v14/runs/**.json`(ops·diag·check·retro).
- **오류 유형 분석:** `sft_dpo_inventory/generated/error_types_v13_model_name_only.json`(136문항).
  - 공백 유형 도출(`coverage_gap.py`)은 이 산출물을 입력으로 쓴다.
  - batch004는 그 공백 유형을 근거로 설계했다.
  - 그래서 세 이력의 문항이 같다.
- **valid98:** `pilot_001/valid98/valid98_items.json`.
- **pilot_001 분석:** `pilot_001_analysis/analysis.json`(valid98과 업체 100).

## 2. 문항 조건(작업 지시 2)

대상은 지시로 뺀 4개 셋과 사본을 제외한 11개 셋, 384문항이다. 조건을 모두 통과한 문항은 302개다.

조건과 판정 방법:

1. 앞 셋과 정규화 질문이 같지 않다.
2. 정책·모호 라벨이 아니다(`policy_scale.exclusion_keys`: v13 dev_report·label_audit, D1–D4).
3. 정답 grounding이 있다.
4. 장소가 mock으로 모두 풀린다(`classify_providers`: mock, mock_and_reference, no_lookup).
5. 정답 grounding을 현재 pipeline에 그대로 넣었을 때 기대 결과로 끝난다.
   - 넣는 방법: 모델 응답 자리에 정답 JSON을 돌려주는 client를 쓴다.
   - pipeline은 평가와 같은 구성이다(flat, 조건 계층 켬, mock+legacy, 기준일 2026-09-25).
   - 기대 결과: 답하는 문항은 v3 `match`이면서 `grounding_ok`, 정지 문항은 `expected_refusal`.
6. 학습 데이터(v004 reviewed gold 53문항; teacher 17문항 포함)와 겹치지 않는다.
   - 대조 항목: 정규화 질문, 거친 의미 family, thor `family_key`, thor `template_key`.

조건별로 빠진 문항:

| 이유 | 문항 |
|---|---:|
| 학습 데이터와 family 겹침 | 47 |
| 정답 grounding 없음 | 22 |
| 정책·모호 | 8 |
| pipeline에서 기대와 다르게 멈춤(확인 요청 3, 지원 불가 1) | 4 |
| 앞 셋과 중복 | 1 |

- 장소가 mock으로 풀리지 않아 빠진 문항은 0이다.
- batch005 후보와의 family 겹침은 아직 셀 수 없다(후보가 없음). 작업 지시 4의 겹침 검사에서 이 셋들과 겹치는 batch005 후보를 빼는 방식으로 막는다.

## 3. 선택지(사용자가 고른다)

| 선택지 | 규칙 | 선택용 셋 | 보조 시험 셋 | 남는 문제 |
|---|---|---|---|---|
| 0. 규칙대로 | v13·v14 비교도 분석으로 보고 셋 단위로 뺀다 | 0 | 0 | 셋을 새로 써야 한다(아래 3). |
| 1. 문항 family 단위 | v13·v14 비교는 GeoFlow 코드·prompt 선택용 평가로 보고 이력으로만 둔다. SFT 쪽(오류 유형 분석·공백 유형·batch004 근거 136문항)에 쓰인 문항은 그 family째 뺀다 | old44·contrast·indepv2–4에서 154문항 → 약 100 | at·final_v12 51문항 | 이 셋들은 v13에서 T2PC 코드 선택에 쓰였다. SFT 학습 전후 비교에는 영향이 없지만 "한 번도 보지 않은 셋"은 아니다. 같은 셋 안의 다른 family 문항은 SFT 분석에 쓰였다 |
| 2. 셋 단위(SFT 쪽만) | 선택지 1의 기준을 셋 단위로 적용 | 없음 | at·final_v12 51문항 | 선택용 셋은 valid98을 계속 써야 한다(결정 41과 어긋남). 또는 51문항을 선택용으로 쓰고 보조 시험 셋을 두지 않는다 |
| 3. 새 보호 셋 작성 | Claude가 새 질문과 gold를 쓰고 사용자가 검토 | 약 100 | 50 이상 | 질문·gold 약 150건의 사람 검토가 batch005(60건)에 더해진다. 작성자가 batch005와 같아 family 분리를 따로 지켜야 한다 |

선택지 1의 유형 분포(조건 통과 문항 기준, `options.json`):

| | 문항 | 집계 없음 | dimension 있음 | dimension_target 있음 | 정지 기대 |
|---|---:|---:|---:|---:|---:|
| 선택용 후보(old44·contrast·indepv2–4) | 154 | 0.448 | 0.338 | 0.130 | 10 |
| 보조 시험 후보(at·final_v12) | 51 | 0.627 | 0.333 | 0.216 | 5 |
| 참고: 보호 개발 셋 전체(업체 100 제외, 454) | 454 | 0.654 | 0.423 | 0.280 | 34 |

- 선택지 1·2에서 두 셋은 셋이 달라 id·contrast family가 겹치지 않는다.
- 거친 의미 family(측정값·OD·집계 구조)까지 서로 겹치지 않게 하려면 더 줄어든다. 이 기준을 쓸지도 정해야 한다.
- 선택지를 정하면 다음을 한다:
  1. 문항 목록·sha256을 고정한다.
  2. base를 HF-E 조건으로 두 셋에서 한 번씩 잰다.
  3. PROTOCOL_v2의 셋 항목을 채워 확정한다.
