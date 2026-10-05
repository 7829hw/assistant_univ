# Thor bounded pilot 001 — 실측 보고서

이 결과는 최종 production 모델 검증이 아니다. 동결된 작은 데이터와 세 validation 질문을 이용한 pilot이다. 원본 JSON, trainer state, config, SHA, telemetry는 `training/experiments/thor_pilot_001/`에 보존했다. LLM grounding 이후의 deterministic production 경계는 변경하지 않았다.

## 1. 실험 고정 정보

- Branch / commit: `geoflow/dev-v2` / `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`. 시작 시 dirty 상태이므로 `git.diff`, `git.status`, source snapshots와 수정 이력을 함께 사용해야 한다.
- Model/tokenizer: `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`; BF16, SDPA, nonthinking chat template.
- Prompt SHA256: `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`. Production prompt 및 runtime 정의의 SHA가 실험 내내 동일한지 검사했다.
- Seed: 42; greedy `do_sample=false`, `max_new_tokens=1024`, inference cache=true. 각 모델의 generation 설정은 동일하다.
- SFT train/valid 12/3; DPO train/valid 82/24. Rank 16, alpha 32, dropout .05, projection 252개, batch 1 / accumulation 1. Generic Thor accumulation 8 설정은 유지했다.
- SFT max length 6912; DPO prompt 6784 / completion 256 / total 6912. Prompt compression이나 truncation을 사용하지 않았다.

| Dataset | SHA256 |
| --- | --- |
| training/generated/sft_train.jsonl | a0dffc70b023402098e430591a1bd59cdcbc1d429f94ed481a7688ac49a6edfd |
| training/generated/sft_valid.jsonl | c38308e04c5623baa4e13bb3eb4a39fdcdb2cde2b7aeea07e9dab31d467a5354 |
| training/generated/dpo_train.jsonl | be1eef829f6fc75409bf9f1f849e5a84248b8f416caa1e18de8563f714b2975d |
| training/generated/dpo_valid.jsonl | 67527d4b95d43187c94de9b4f95de2d6d71634b355ed2efd772d0e5330758090 |

부모 intent·semantic template·정규화 질문의 train/validation 교집합, DPO split 상속, 동일 pair/chosen-rejected를 검사했다. 보호된 evaluation registry 질문 1,116개와 SFT train의 정규화 exact overlap은 0이었다. 선택 전 동결한 외부 개발 질문 20개는 train과 exact/template overlap이 없으며, 최종 benchmark가 아니다. Unsupported 진단 2개는 broad training family와 겹치므로 별도 보고한다.

## 2. Base 성능

동일한 37개 질문을 실제 generation으로 측정했다: train 12, checkpoint 선택용 validation 3, 외부 개발 질문 20, unsupported 진단 2. 아래 최종 비교 표의 Base 열이 동결된 기준점이다.

| Split | Grounding exact | JSON | Contract | Compose |
| --- | --- | --- | --- | --- |
| train | 1/12 (8.3%) | 12/12 (100.0%) | 4/12 (33.3%) | 3/12 (25.0%) |
| valid | 0/3 (0.0%) | 3/3 (100.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| external | 7/20 (35.0%) | 20/20 (100.0%) | 11/20 (55.0%) | 10/20 (50.0%) |
| external_refusal_diagnostic | 0/2 (0.0%) | 2/2 (100.0%) | 2/2 (100.0%) | 1/2 (50.0%) |

평가 harness에서 parser 오류 시 raw JSON을 잃고 gold denominator를 제외하는 관측 오류를 발견해 최소 수정 후 Base generation 전체를 다시 측정했다. 수정 전 결과는 `base_pre_evaluator_fix.json`으로 보존했다. 별도로 reference handler에 default TIMS compiler contract를 적용하던 wrapper 설정을 기존 `profile_for("reference")`로 맞췄다. 최종 모델 모두에서 compilation에 도달한 저장 응답을 동일 profile로 replay했고 semantic/composition/validation 값이 바뀌지 않음을 assert했다. Base/DPO w36의 실패한 실제 repair는 원본 record를 유지했다. 원본은 `*_before_profile_correction.json`에 보존했다. Runtime/compiler/validator rule을 수정하지 않았다.

## 3. SFT pilot

| Experiment | LR | Steps | Local best | Last train loss | Val grounding | Peak GiB | sec/step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sft_1 | 5e-05 | 12 | sft_1_step2 | 1.6742 | 1/3 (33.3%) | 29.46 | 12.63 |
| sft_2 | 0.0001 | 6 | sft_2_step6 | 0.2283 | 0/3 (0.0%) | 29.44 | 12.60 |
| sft_3 | 0.0002 | 6 | sft_3_step6 | 0.0775 | 0/3 (0.0%) | 29.44 | 12.59 |

최종 선택: `sft_1_step2`. Generation validation 1/3을 얻은 checkpoint이며 train loss로 선택하지 않았다. 외부 개발 질문은 선택에 사용하지 않았다. SFT-1은 6에서 process를 종료한 뒤 같은 12-step scheduler horizon으로 resume했다. 전체 SFT optimizer step은 24이다. SFT 후보는 12-step linear scheduler horizon과 warmup 1을 공유하며, 후보 2/3은 6에서 중단했다. SFT-1은 1 epoch, 후보 2/3은 0.5 epoch를 관찰했다.

| Experiment | Step | Val loss | Generation exact | JSON |
| --- | --- | --- | --- | --- |
| sft_1 | 2 | 0.782854 | 1/3 | 3/3 |
| sft_1 | 4 | 0.67547 | 0/3 | 3/3 |
| sft_1 | 6 | 0.537572 | 0/3 | 3/3 |
| sft_1 | 8 | 0.418676 | 0/3 | 3/3 |
| sft_1 | 12 | 0.318907 | 0/3 | 3/3 |
| sft_2 | 2 | 0.744883 | 0/3 | 3/3 |
| sft_2 | 4 | 0.466729 | 0/3 | 3/3 |
| sft_2 | 6 | 0.24486 | 0/3 | 3/3 |
| sft_3 | 2 | 0.671926 | 0/3 | 3/3 |
| sft_3 | 4 | 0.235247 | 0/3 | 3/3 |
| sft_3 | 6 | 0.088859 | 0/3 | 3/3 |

모든 step의 train/eval loss와 generation 관찰 시점은 `metrics/learning_curves.csv`와 JSON에 보존했다. step 10은 loss/resume용 저장점이며 사전 정의한 generation 후보는 2/4/6/8/12였다.

## 4. DPO pilot

정책 초기값은 선택된 `sft_1_step2`이며 같은 base model의 policy/reference adapter를 사용했다. Reference-free DPO나 full reference duplication으로 변경하지 않았다. 기존 FP32 adapter reload correction 및 reference hash 확인을 유지했고 학습과 최종 preference 평가 후 reference 불변성을 검증했다. 전체 DPO optimizer step은 18이다. 각 후보는 6/82 epoch(약 0.073)를 실행했으며 warmup 1/linear schedule을 사용했다. DPO에서는 TRL 기본 disable_dropout=True가 적용된다.

| Experiment | LR | Beta | Step | DPO val loss | Observed pref | Chosen reward | Rejected reward | Margin | Generation | sec/step |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dpo_1 | 5e-06 | 0.1 | 2 | 0.67337 | 3/6 | 0.05237 | 0.01081 | 0.04156 | 1/3 | 38.66 |
| dpo_1 | 5e-06 | 0.1 | 4 | 0.64472 | 5/6 | 0.0556 | -0.04501 | 0.10061 | 0/3 | 38.66 |
| dpo_1 | 5e-06 | 0.1 | 6 | 0.63862 | 5/6 | 0.0897 | -0.02406 | 0.11376 | 0/3 | 38.66 |
| dpo_2 | 5e-06 | 0.05 | 2 | 0.67139 | 4/6 | 0.0347 | -0.0103 | 0.045 | 0/3 | 38.68 |
| dpo_2 | 5e-06 | 0.05 | 4 | 0.68618 | 4/6 | 0.02185 | 0.00656 | 0.01529 | 0/3 | 38.68 |
| dpo_2 | 5e-06 | 0.05 | 6 | 0.67771 | 4/6 | 0.01997 | -0.0118 | 0.03177 | 0/3 | 38.68 |
| dpo_3 | 1e-05 | 0.1 | 2 | 0.68929 | 4/6 | 0.0629 | 0.05019 | 0.01271 | 0/3 | 38.65 |
| dpo_3 | 1e-05 | 0.1 | 4 | 0.66093 | 4/6 | 0.14009 | 0.07015 | 0.06994 | 0/3 | 38.65 |
| dpo_3 | 1e-05 | 0.1 | 6 | 0.64406 | 6/6 | 0.17336 | 0.07177 | 0.10159 | 1/3 | 38.65 |

최종 선택: `dpo_3_step6`. 선택용 generation 1/3과 관찰용 preference 6/6을 얻었다. 관찰 6쌍은 각 validation parent에서 semantic/constraint 하나씩 골랐으며, 아래 최종 preference 평가는 전체 24/82쌍이다. 서로 다른 beta의 reward margin은 동일 척도로 직접 비교하지 않는다.

| Split/category | Correct/total | Mean margin | Mean loss |
| --- | --- | --- | --- |
| train/overall | 62/82 | 0.05252 | 0.6683 |
| valid/overall | 16/24 | 0.04607 | 0.67165 |
| train/constraint | 28/35 | 0.06779 | 0.66094 |
| train/semantic | 34/47 | 0.04115 | 0.67378 |
| valid/constraint | 5/5 | 0.09985 | 0.6448 |
| valid/semantic | 11/19 | 0.03191 | 0.67872 |

| Validation negative_type | Correct/total | Mean margin |
| --- | --- | --- |
| aggregation_confusion | 0/2 | -0.03424 |
| aggregation_stage_swap | 0/1 | -0.15794 |
| event_subtype_confusion | 1/1 | 0.09192 |
| factor_omission | 4/6 | 0.04924 |
| location_omission | 1/2 | 0.06564 |
| measure_confusion | 1/2 | 0.00532 |
| region_hallucination | 1/2 | -0.00532 |
| role_measure_to_support | 1/1 | 0.15652 |
| role_support_to_measure | 1/1 | 0.00614 |
| source_confusion | 3/3 | 0.11629 |
| supported_false_refusal | 1/1 | 0.18462 |
| temporal_scope_confusion | 2/2 | 0.0586 |

관찰용 6쌍을 제외한 나머지 preference는 10/18이다. 관찰 subset은 parent/category 균형을 맞췄지만 negative_type 전체를 포함하지 않는다.

24 validation pairs는 세 질문의 다양한 mutation이므로 독립적인 24개 unseen 질문이 아니다. Pair별 chosen/rejected reward, margin, loss, reference/policy hash는 `dpo_best_preferences.json`에 있다. Preference accuracy는 TRL의 reference 대비 reward margin>0 판정이다. 최초 policy=reference에서 모든 margin은 0이므로 이를 SFT의 의미 정확도 0으로 해석하면 안 된다. Margin=0은 tie로 기록하며 정답으로 세지 않는다.

## 5. 최종 비교

### 외부 개발 질문 20개

| Metric | Base | Best SFT | Best SFT+DPO |
| --- | --- | --- | --- |
| JSON parse | 20/20 (100.0%) | 20/20 (100.0%) | 20/20 (100.0%) |
| Contract pass | 11/20 (55.0%) | 12/20 (60.0%) | 13/20 (65.0%) |
| Grounding exact | 7/20 (35.0%) | 8/20 (40.0%) | 8/20 (40.0%) |
| Concept | 23/43 (53.5%) | 26/43 (60.5%) | 28/43 (65.1%) |
| Subtype | 23/43 (53.5%) | 26/43 (60.5%) | 28/43 (65.1%) |
| Role | 23/43 (53.5%) | 26/43 (60.5%) | 28/43 (65.1%) |
| Factor exact | 8/20 (40.0%) | 9/20 (45.0%) | 9/20 (45.0%) |
| Factor precision | 30/33 (90.9%) | 30/34 (88.2%) | 35/39 (89.7%) |
| Factor recall | 30/69 (43.5%) | 30/69 (43.5%) | 35/69 (50.7%) |
| Compose success | 10/20 (50.0%) | 12/20 (60.0%) | 12/20 (60.0%) |
| Validation | 10/20 (50.0%) | 12/20 (60.0%) | 12/20 (60.0%) |
| Macro exact | 9/20 (45.0%) | 11/20 (55.0%) | 11/20 (55.0%) |
| Macro | 11/23 (47.8%) | 14/23 (60.9%) | 14/23 (60.9%) |
| Operator | 11/23 (47.8%) | 14/23 (60.9%) | 14/23 (60.9%) |
| Execution | 0/9 (0.0%) | 0/10 (0.0%) | 0/10 (0.0%) |
| Executed / all questions | 0/20 (0.0%) | 0/20 (0.0%) | 0/20 (0.0%) |
| Repair attempted | 1/20 (5.0%) | 0/20 (0.0%) | 1/20 (5.0%) |
| Repair success | 0/1 (0.0%) | N/A (0/0) | 0/1 (0.0%) |

Concept/subtype/role 분모는 gold concept instance, factor precision/recall은 factor 수다. Macro는 label recall이며 Macro exact는 질문 단위 완전 일치다. Execution은 실행 결과를 반환한 plan만 분모에 들어가는 기존 조건부 metric이다. Compiler에서 막힌 plan은 여기서 제외되므로 전체 질문 중 실행 성공 count도 따로 표시한다. JSON은 기존 tolerant extractor, contract는 production parser의 호환 정규화 포함 판정이다. Grounding exact는 ID/표면 text/순서를 제외한 정규화 의미 일치이며 원본 JSON byte 일치가 아니다.

| Rule | Base | SFT | SFT+DPO |
| --- | --- | --- | --- |
| G1_ACYCLICITY | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G2_ROLE_ORDERING | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G3_TYPE_COMPATIBILITY | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G4_EXECUTABILITY | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G5_CONNECTIVITY | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G6_SCOPE_PROVENANCE | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |
| G7_AGGREGATION_SEMANTICS | 10/10 (100.0%) | 12/12 (100.0%) | 12/12 (100.0%) |

G1~G7 조건부 pass는 실제 validator에 도달한 plan만 분모에 들어간다. 이를 전체 질문 100% pass로 읽으면 안 된다. `w22_p0`의 `needs_clarification` gold는 inner aggregation이 미지정되어 compose 실패가 의도된 결과다. 다른 19개 answerable gold는 compose/validate를 통과했다.

### Checkpoint 선택용 validation 3개

| Metric | Base | Best SFT | Best SFT+DPO |
| --- | --- | --- | --- |
| JSON parse | 3/3 (100.0%) | 3/3 (100.0%) | 3/3 (100.0%) |
| Contract pass | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Grounding exact | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Concept | 0/9 (0.0%) | 3/9 (33.3%) | 3/9 (33.3%) |
| Subtype | 0/9 (0.0%) | 3/9 (33.3%) | 3/9 (33.3%) |
| Role | 0/9 (0.0%) | 3/9 (33.3%) | 3/9 (33.3%) |
| Factor exact | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Factor precision | N/A (0/0) | 6/6 (100.0%) | 6/6 (100.0%) |
| Factor recall | 0/14 (0.0%) | 6/14 (42.9%) | 6/14 (42.9%) |
| Compose success | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Validation | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Macro exact | 0/3 (0.0%) | 1/3 (33.3%) | 1/3 (33.3%) |
| Macro | 0/6 (0.0%) | 2/6 (33.3%) | 2/6 (33.3%) |
| Operator | 0/7 (0.0%) | 3/7 (42.9%) | 3/7 (42.9%) |
| Execution | N/A (0/0) | 0/1 (0.0%) | 0/1 (0.0%) |
| Executed / all questions | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| Repair attempted | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| Repair success | N/A (0/0) | N/A (0/0) | N/A (0/0) |

### Unsupported 진단 및 MEASURE별 성능

| Metric | Base | SFT | SFT+DPO |
| --- | --- | --- | --- |
| Grounding exact | 0/2 (0.0%) | 0/2 (0.0%) | 0/2 (0.0%) |
| Unsupported precision | N/A (0/0) | N/A (0/0) | N/A (0/0) |
| Unsupported recall | 0/2 (0.0%) | 0/2 (0.0%) | 0/2 (0.0%) |

| Gold MEASURE | Base exact | SFT exact | SFT+DPO exact |
| --- | --- | --- | --- |
| fare | 4/8 (50.0%) | 4/8 (50.0%) | 4/8 (50.0%) |
| operating_days | 1/4 (25.0%) | 1/4 (25.0%) | 1/4 (25.0%) |
| vacant_ratio | 0/2 (0.0%) | 0/2 (0.0%) | 0/2 (0.0%) |
| active_taxi_ratio | 1/1 (100.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| trip_count | 0/3 (0.0%) | 0/3 (0.0%) | 0/3 (0.0%) |
| passage_count | 0/1 (0.0%) | 1/1 (100.0%) | 1/1 (100.0%) |
| speed | 1/1 (100.0%) | 1/1 (100.0%) | 1/1 (100.0%) |

`by_intent`도 각 generation report에 보존했다. 대부분 그룹은 1문항이므로 해당 비율을 일반 성능으로 해석하지 않는다. Gold reference replay의 외부 gold는 19/20이 compose/validate를 통과했고, 실행 결과를 반환한 18개는 모두 실패했다(0/18; 전체 0/20). Provider는 fare/trip/drive/operating_days/vicinity 등의 실행을 지원하지 않는다. Grounding 품질과 실행 backend coverage를 분리해서 해석해야 한다.

## 6. Overfitting 분석

| Checkpoint | Train exact | Validation exact |
| --- | --- | --- |
| base | 1/12 | 0/3 |
| sft_best | 1/12 | 1/3 |
| sft_last | 2/12 | 0/3 |
| dpo_best | 1/12 | 1/3 |
| dpo_last | 1/12 | 1/3 |

SFT-1의 validation loss는 .782854(step 2)에서 .318907(step 12)로 감소했지만 generation은 1/3→0/3이다. Step 4부터 관측된 generation regression이 있으며, higher LR에서는 supported 질문에 false refusal이 나타났다. Train exact가 100%가 되는 memorization onset은 이 bounded 구간에서 관측하지 못했다. 따라서 loss 감소를 semantic generalization이나 전형적 train-set memorization으로 단정할 수 없다.

DPO-1은 관찰 preference 3/6→5/6으로 증가하면서 generation 1/3→0/3으로 악화됐다. 선택된 DPO-3은 step 2/4에서 0/3, step 6에서 1/3으로 회복했다. Preference 정확도만으로 actual grounding 품질을 예측할 수 없었다. 각 DPO는 train 82쌍 중 6 optimizer step만 수행했으므로 full-epoch preference memorization onset 및 최적 epoch는 검증하지 않았다.

## 7. 대표 개선/회귀 사례

JSON은 표시를 위해 공백만 압축했다. 실제 원문은 model report와 error JSONL에 그대로 보존했다.

### Base가 틀리고 SFT가 고친 사례: ex06

지난달 달서구 개인택시의 운행일수 합계가 가장 많았던 주는?

Gold:

```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"달서구","value":{"name":"달서구","region":""}}],"factors":{"aggregation":"sum","answer":"bucket","bucket":"week","date":"last_month","rollup":"max","taxi_type":"private"}}
```

Base:

```json
{"concepts":[{"id":"date_range","text":"지난달","concept":"EVENT","subtype":"operation","role":"COND","source":"user"},{"id":"location","text":"달서구","concept":"LOCATION","subtype":"place","role":"COND","source":"user","value":{"name":"달서구","region":""}},{"id":"taxi_type","text":"개인택시","concept":"OBJECT","subtype":"taxi_type","role":"COND","source":"user"},{"id":"operating_days","concept":"AMOUNT","subtype":"operating_days","role":"MEASURE","source":"implicit"}],"factors":{"bucket":"week","aggregation":"sum","rollup":"max","answer":"bucket"}}
```

SFT:

```json
{"concepts":[{"id":"location_1","text":"달서구","concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"user","value":{"name":"달서구","region":""}},{"id":"taxi_type","text":"개인택시","concept":"OBJECT","subtype":"taxi_type","role":"COND","source":"user","value":"private"},{"id":"operation","concept":"EVENT","subtype":"operation","role":"SUPPORT","source":"implicit"},{"id":"operating_days","text":"운행일수","concept":"AMOUNT","subtype":"operating_days","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","aggregation":"sum","rollup":"max","answer":"bucket"}}
```

SFT+DPO:

```json
{"concepts":[{"id":"location_1","text":"달서구","concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"user","value":{"name":"달서구","region":""}},{"id":"taxi_type_1","text":"개인택시","concept":"OBJECT","subtype":"taxi_type","role":"COND","source":"user","value":"private"},{"id":"operation","concept":"EVENT","subtype":"operation","role":"SUPPORT","source":"implicit"},{"id":"operating_days","text":"운행일수","concept":"AMOUNT","subtype":"operating_days","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","aggregation":"sum","rollup":"max","answer":"bucket"}}
```

### SFT가 틀리고 DPO가 고친 사례

이번 최종 세 모델 비교에서는 해당 exact-match 사례가 0개였다. 없는 사례를 만들어 설명하지 않는다.

### 선택된 DPO에서 regression된 사례

이번 최종 세 모델 비교에서는 해당 exact-match 사례가 0개였다. 없는 사례를 만들어 설명하지 않는다.

### 모든 모델이 실패한 OD dimension 사례: w37_p0

지난달 승하차 건수가 가장 많은 읍면동 간 노선 상위 3개는?

Gold:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"count","concept":"AMOUNT","subtype":"trip_count","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","dimension":"emd","dimension_target":"both","order":"top","limit":3}}
```

Base:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"trip_count","concept":"AMOUNT","subtype":"trip_count","role":"MEASURE","source":"implicit"},{"id":"emd","concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"implicit"}],"factors":{"bucket":"month","dimension":"emd","dimension_target":"both","order":"top","limit":3}}
```

SFT:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"trip_count","concept":"AMOUNT","subtype":"trip_count","role":"MEASURE","source":"implicit"},{"id":"emd","concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"implicit"}],"factors":{"bucket":"month","dimension":"emd","dimension_target":"both","order":"top","limit":3}}
```

SFT+DPO:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"trip_count","concept":"AMOUNT","subtype":"trip_count","role":"MEASURE","source":"implicit"},{"id":"emd","concept":"LOCATION","subtype":"place","role":"SUBCOND","source":"implicit"}],"factors":{"bucket":"month","dimension":"emd","dimension_target":"both","order":"top","limit":3}}
```

### Exact 개선으로 세지 않은 DPO 부분 개선: w02_p0

지난달 매주 가장 낮았던 택시 요금의 평균은?

Gold:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"fare","concept":"AMOUNT","subtype":"fare","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","rollup":"avg","aggregation":"min"}}
```

Base:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"fare","concept":"AMOUNT","subtype":"fare","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","aggregation":"max","rollup":"avg","answer":"value"}}
```

SFT:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"fare","concept":"AMOUNT","subtype":"fare","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","aggregation":"avg","rollup":"min","answer":"value"}}
```

SFT+DPO:

```json
{"concepts":[{"id":"trip","concept":"EVENT","subtype":"trip","role":"SUPPORT","source":"implicit"},{"id":"fare","concept":"AMOUNT","subtype":"fare","role":"MEASURE","source":"implicit"}],"factors":{"date":"last_month","bucket":"week","aggregation":"max","rollup":"avg","answer":"value"}}
```

SFT는 inner=avg / outer=min, DPO는 inner=max / outer=avg였다. Gold inner=min / outer=avg이므로 outer만 고쳤고 exact는 여전히 실패다.

### 중간 DPO checkpoint의 실제 regression

선택된 최종 모델과 별개로 DPO-1 step 4에서는 SFT가 맞힌 ex06을 틀렸다. 해당 checkpoint의 validation preference는 5/6이지만 generation exact는 0/3이었다.

```json
{"concepts":[{"id":"date_range","text":"지난달","concept":"EVENT","subtype":"operation","role":"COND","source":"user"},{"id":"location","text":"달서구","concept":"LOCATION","subtype":"place","role":"COND","source":"user","value":{"name":"달서구","region":""}},{"id":"taxi_type","text":"개인택시","concept":"OBJECT","subtype":"taxi_type","role":"COND","source":"user"},{"id":"operating_days","text":"운행일수","concept":"AMOUNT","subtype":"operating_days","role":"MEASURE","source":"implicit"}],"factors":{"bucket":"week","aggregation":"sum","rollup":"max","answer":"bucket"}}
```

## 8. Thor 성능

Ubuntu 24.04.5 host / aarch64 / JetPack 7.1, Jetson Linux 38.4, CUDA 13.0, Thor capability 11.0, unified memory 122.82 GiB. 기존 immutable image/venv의 PyTorch 2.13.0+cu130, transformers 4.56.2, TRL .23.1, PEFT .17.1, accelerate 1.14.0을 유지했다. BNB/QLoRA/flash-attn 및 FP8/FP4는 설치·시험하지 않았다.

| Run | Steps | Peak allocated GiB | Peak reserved GiB | Min MemAvailable GiB | sec/step | Policy input tokens/sec |
| --- | --- | --- | --- | --- | --- | --- |
| sft_1 | 6 | 29.44 | 60.25 | 55.85 | 12.63 | 541.49 |
| sft_1_resume | 6 | 29.46 | 60.25 | 53.21 | 12.63 | 541.99 |
| sft_2 | 6 | 29.44 | 60.25 | 54.71 | 12.60 | 543.01 |
| sft_3 | 6 | 29.44 | 60.25 | 52.62 | 12.59 | 543.18 |
| dpo_1 | 6 | 32.09 | 40.52 | 75.48 | 38.66 | 354.52 |
| dpo_2 | 6 | 32.09 | 40.52 | 75.51 | 38.68 | 354.40 |
| dpo_3 | 6 | 32.09 | 40.52 | 72.45 | 38.65 | 354.60 |

실제 optimizer step 수행 구간의 합계는 16.65분이다. Eval/generation/save/load 시간은 포함하지 않는다. DPO throughput은 chosen+rejected policy input을 세며 reference token은 제외한다. SFT/DPO token rate를 completion throughput으로 비교하지 않는다.

| Phase | SFT allocated GiB | DPO allocated GiB |
| --- | --- | --- |
| trainer_ready | 15.42 | 15.58 |
| first_forward | 25.19 | 27.42 |
| first_backward | 15.60 | 15.76 |
| first_optimizer_step | 15.92 | 16.09 |

Weights를 CPU에 load한 다음 Trainer가 GPU로 옮기므로 `model_load`의 CUDA allocation=0이 load 미실행을 뜻하지 않는다. Load 시간, 각 phase의 system memory와 온도는 profile에 있다. Unified memory reserve는 실측 MemTotal의 20%(24.57 GiB)이고, 관측 최소 MemAvailable은 52.62 GiB였다. OOM은 발생하지 않았다.

Read-only telemetry: GPU 온도 40.16–83.31°C, tegrastats 최대 사용 RAM 70955 MiB. GPU clock/power-limit은 N/A이므로 throttling 여부를 확정할 수 없다. SFT run 평균은 12.59–12.63초, DPO는 38.65–38.68초로 run 사이 큰 지속 저하는 관측되지 않았다. 연속 10–20분 backward training이나 장시간 안정성은 이 짧은 run으로 검증할 수 없다. Nvpmodel/jetson_clocks는 변경하지 않았다.

## 9. Resume 검증 결과

| State | Before checkpoint-6 | After checkpoint-12 |
| --- | --- | --- |
| Global step | 6 | 12 |
| Epoch | 0.5 | 1 |
| Optimizer state tensors | 504 | 504 |
| Optimizer step | 6.0 | 12.0 |
| Scheduler last_epoch | 6 | 12 |

새 process의 실제 로그에서 global step 6으로 시작해 7–12의 forward/backward/optimizer step을 수행했다. Python/numpy/CPU/CUDA RNG state와 dataloader 진행 상태를 복원했고 adapter SHA도 달라졌다. 중단 없는 run과의 bitwise 일치 시험은 수행하지 않았다.

## 10. 데이터 부족 분석

SFT train의 supported 10문항은 operating_days 6 / revenue 4뿐이고, unsupported는 2문항이다. Fare/trip_count/speed/passage_count/ratio 및 pickup/dropoff/OD LOCATION gold는 train에 없다. 외부 OD dimension 3문항(w35/36/37)의 exact는 다음과 같다. Scope의 od_role과 dimension_target은 서로 다른 coverage로 확장해야 한다.

| Coverage | Base | SFT | SFT+DPO |
| --- | --- | --- | --- |
| OD dimension (3 questions) | 0/3 | 0/3 | 0/3 |

- Base: 주요 raw-field 오류 단서 = concept/subtype: 15, role_or_concept: 15, source_or_concept: 15, factor:missing:taxi_type: 12, factor:wrong:date: 11, factor:missing:date: 10.
- SFT: 주요 raw-field 오류 단서 = concept/subtype: 15, role_or_concept: 15, source_or_concept: 15, factor:missing:taxi_type: 10, factor:missing:date: 9, factor:wrong:date: 8.
- SFT+DPO: 주요 raw-field 오류 단서 = concept/subtype: 14, role_or_concept: 14, source_or_concept: 14, factor:missing:date: 10, factor:missing:taxi_type: 10, factor:wrong:date: 8.

Raw-field 단서는 annotation 검토용이며 독립적인 accuracy metric이 아니다. Generation report의 status/error에는 실제 schema failure code도 남겼다. Unsupported taxonomy와 지원 경계, source/role/value, temporal/factor coverage가 부족하다. DPO train은 semantic 47/constraint 35, valid는 semantic 19/constraint 5이며 질문 family가 적어 비율만으로 강한 결론을 낼 수 없다.

## 11. 다음 dataset annotation 우선순위

1. 기존 gold를 수동 검토하고 source/role/value 및 factor/date 정규화 대조 예제를 추가한다. MISSING_CONCEPT_VALUE, INVALID_SUBTYPE, INVALID_FACTOR의 실제 prediction을 확인한다.
2. Bucket/inner/outer/answer 대조 예제를 우선 확대한다. 전체 validation에서 aggregation confusion 0/2, stage swap 0/1이었고 실제 w02도 inner reducer를 잘못 선택했다. 작은 분모의 진단 신호로 해석하며 w22 같은 미지정 inner를 임의로 보완하지 않는 예제를 유지한다.
3. Fare/trip_count/passage_count/speed/ratio를 포함한 새 parent intent를 추가해 revenue/operating_days 편중을 줄인다.
4. Pickup/dropoff/both dimension과 실제 origin/destination LOCATION/od_role을 서로 다른 family로 추가한다. OD dimension 실패는 실측했지만 실제 OD scope grounding은 아직 평가하지 못했다.
5. Unsupported 이유 taxonomy, 지원 경계의 positive 예제, clarification 예제를 늘려 false refusal과 forced support를 함께 검토한다.
6. 실제 prediction에서 수동 검토한 hard negative를 구축한다. Semantic/constraint 분포와 source/measure/role/OD 난도를 검토하고 pair accuracy만으로 채택하지 않는다. 기존 holdout은 training으로 옮기지 않고 새 family를 annotation한다.


별도 후속 TODO: production prompt compression. System content 6698 tokens, user 평균 26.6, assistant 평균 107, total 평균 6850.6, system 비율 97.77%. Chat wrapper를 포함한 prompt는 약 6748이고 SFT p50/p95/p99/max는 6863/6884/6884/6884, DPO max는 6886이다. Token 비율은 FLOP 실측값이 아니지만 completion-only loss에서도 긴 prompt 계산이 필요하다. 이번에는 prompt를 축소하지 않았다.

## 12. Recommendation

**D: 본 학습 전에 annotation 확대를 우선한다.** SFT에 작은 개선 신호는 있지만 validation 3문항과 검토 전 개발 질문 20개로 일반화나 최종 hyperparameter를 결정할 수 없다. DPO preference 개선은 실제 generation 개선과 일치하지 않았고 중간 checkpoint의 회귀도 관측했다. 현 adapter를 production에 채택하지 않고 source/role/factor 및 부족한 MEASURE/OD/unsupported를 보완한 뒤, 수동 검토한 negative로 같은 bounded protocol을 다시 실행하는 것을 권한다. 선택 모델의 외부 exact는 7/20→8/20→8/20이었고 DPO exact 개선·회귀 사례는 모두 0개다. DPO는 concept/factor 부분 점수를 개선했으나 완전한 정답을 추가하지 못했다.

BF16 LoRA rank 16과 shared reference를 이번에 검증한 기준으로 유지한다. LR/beta/effective batch/epoch는 최종 권장값이 아니며 데이터 확대 후 다시 선택해야 한다. QLoRA 전환이나 runtime 경계 변경은 필요하지 않다.

### 재실행과 저장 파일

새 experiment directory에 host Git/data 환경에서 freeze한 뒤, 기존 Thor GPU 환경에서 실행한다. 자세한 환경 진입 방법은 PILOT.md와 THOR.md에 있다.

```bash
python -m training.pilot freeze --directory training/experiments/thor_pilot_002
python -m training.pilot configs --stage sft --directory training/experiments/thor_pilot_002
python -m training.pilot evaluate --label base --directory training/experiments/thor_pilot_002
python -m training.pilot_run --directory training/experiments/thor_pilot_002
python -m training.pilot_report --directory training/experiments/thor_pilot_002 --correct-execution-profile
```

변경 파일: `training/pilot.py`, `pilot_run.py`, `pilot_report.py`, `PILOT.md`, 본 보고서, 새 CPU pilot tests, 기존 trainer의 callback 주입, evaluator의 raw capture/denominator/provider-profile 보정, README, gitignore. 생성 artifact는 commit하지 않는다. 원본 commit만으로는 재현할 수 없으며 초기 snapshot, evaluator 수정 전후 snapshot, 실제 command SHA와 일치하는 helper 7개 버전(code_history), 최종 source snapshot을 함께 보존했다. 평가 corpus 재구성 SHA도 최초 items.json과 동일함을 확인했다. Production planner/composer/validator/compiler/operator mapping은 동결한 SHA를 유지했다.

검증: full suite 1,115 tests PASS(skip 2, expected failure 1), pilot/evaluation CPU tests 14 PASS, 6개 후보의 실제 forward/backward/optimizer, resume, live generation, reference hash 검사를 수행했다. Best/final checkpoint와 resume 증거를 adapter 중심으로 유지했고, 선택하지 않은 intermediate는 inventory를 남겨 정리했다. 오류 JSONL, paired 개선/회귀, 학습 곡선, config/환경/telemetry/원본 결과는 위 experiment directory에 있다.

실험 storage: 약 7.23 GiB(정리 후), 남은 디스크 약 547.01 GiB. `selected_models.json`에 실제 best/final adapter 경로와 SHA가 있다. Model cache는 `/tmp/geoflow-hf-cache`에 있으므로 후속 실행 전에 보존 상태를 확인해야 한다.
