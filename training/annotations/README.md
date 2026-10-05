# Pilot 이후 annotation 준비 (CPU only)

이 도구는 학습을 실행하지 않는다. LLM은 grounding JSON만 생성하며 production
prompt, planner contract, MacroComposer, Validator 및 compiler는 바꾸지 않는다.
자동 제안은 **pending**이며 validator PASS는 의미 정답의 증거가 아니다.

## 준비와 coverage

저장소 루트에서 실행한다. Runtime requirements로 실행 가능하며 torch/openpyxl은
필요하지 않다. XLSX는 표준 라이브러리로 생성하고 모든 cell을 문자열로 저장한다.

```bash
python -m training.annotations.workflow prepare \
  --gold-dir training/generated \
  --source geoflow_examples/question_graph_examples.yaml \
  --pilot training/experiments/thor_pilot_001 \
  --output training/annotations/generated/expansion_001
```

Output directory는 새 버전이어야 한다. 기존 파일을 덮어쓰지 않는다.

- `coverage.json`: ontology/registry의 모든 MEASURE(0건 포함), source/role/value,
  factors, 집계 단계, OD scope/dimension, SFT/DPO split, reviewer 상태와 gap.
  DPO category/negative_type별 pilot preference 관측도 포함한다.
- `review_queue.jsonl`: authoritative 불변 후보. 제안 target/rejected, 실제 parse →
  compose → G1~G7 결과, 실패 코드, parent/family, 모델 오답 원문과 provenance.
- `review_queue.xlsx`: filter/frozen header가 있는 **검토용 보기**.
  XLSX에서 편집한 상태는 자동 import하지 않는다. 판정은 아래 decision audit에 남긴다.
- `manifest.json`: seed, git SHA/branch, source/code/dataset/queue hash,
  production prompt와 ontology/factor definition hash, 보호 corpus hash 및 통계.

Generator는 pilot 오답의 필드 차이와 coverage gap이 있는 capability에만 작은
curated blueprint를 제안한다. 평가 질문의 지역명/날짜만 바꾼 문장을 training에
넣지 않는다. 새 질문은 definition 근거까지 독립적으로 검토한다.
집계 stage swap과 OD 방향/target swap도 **별도 검토 후보**이며 즉시 DPO가 아니다.
Raw diff/failure_hints는 오류 분류 제안일 뿐 의미 오류의 확정 라벨이 아니다.

## 사람이 판정하는 방법

XLSX의 `candidate_type`, `eligibility`, `quality`, `failure_hints`를 filter한다.
각 question의 source/role/value, factor 근거, inner/outer 집계, OD 방향,
지원/ambiguity 경계, parent/paraphrase lineage를 모두 확인한다. 기존 gold도
`사용자 검토 전` 표시가 있으므로 다시 검토한다.

아래 `ann-...`을 queue의 실제 ID로 바꾼다. 검토하지 않은 항목에 확인 flag를 쓰지 않는다.

```bash
# 보류: 무엇을 고쳐야 하는지 남긴다.
python -m training.annotations.workflow decide \
  --queue training/annotations/generated/expansion_001 \
  --decisions training/annotations/generated/expansion_001/decisions.jsonl \
  --id ann-... --status needs_fix --reviewer YOUR_NAME \
  --reason '장소와 taxi_type factor 근거를 다시 확인해야 함'

# 사람이 의미와 leakage lineage를 실제 확인한 annotation만 수락한다.
python -m training.annotations.workflow decide \
  --queue training/annotations/generated/expansion_001 \
  --decisions training/annotations/generated/expansion_001/decisions.jsonl \
  --id ann-... --status accepted --reviewer YOUR_NAME \
  --reason '원문 의미, subtype 정의, source/value, factor, family 분리 확인' \
  --semantic-checks-confirmed
```

`rejected`는 버릴 제안, `needs_fix`는 수정/재검토할 제안이다. 판정은 append-only이며
다시 판정하면 이전 decision hash를 supersedes로 연결한다. 수락 전에 수정이 필요하면
`--corrected-grounding corrected.json`을 함께 지정한다. 정해진 flat planner JSON만
허용한다. 질문/lineage/outcome을 바꾸려면 새 queue를 만들어야 한다.

`hard_negative` / `semantic_negative`의 수락에는 chosen이 맞고 rejected가 틀린
이유를 반드시 적고 `--negative-is-wrong`도 지정한다. 필요하면
`--corrected-rejected corrected_negative.json`을 사용한다. 동일/동등 pair는 거부된다.
Constraint failure뿐 아니라 **valid graph를 만드는 의미 오답**도 DPO에 포함할 수 있다.
개별 gold와 pair 후보는 따로 검토하므로 gold만 먼저 수락해도 된다.

## 보호 정책과 reviewed import

Evaluation registry 및 evaluation YAML, 부모/intent/paraphrase ID, 기존 SFT validation,
이전 reviewed corpus 버전의 validation, 동결된 pilot의 non-train items를
보호한다. 기존 evaluator의 집계 expansion과 training serializer/splitter를 재사용한다.
질문 exact, template, conservative semantic family(조건명/날짜/source 변경에도 유지),
declared parent/family가 겹치면 수락해도 **학습 export에서 제외**된다.
원래 보호된 제안의 target을 수정해서 보호를 우회할 수 없다.

Actual Base/SFT/DPO 오답을 question + chosen + rejected로 deduplicate한다. Frozen
SFT train에 ID/질문/gold가 일치하는 것만 train-origin으로 인정한다. Validation/dev
오답은 permanently diagnostic-only다. Syntax 손상은 mining 제외 사유로 report한다.

현재 unsupported에는 사람이 검토한 하위 taxonomy가 없다. 따라서 모든 unsupported를
하나의 보호 family로 보는 보수적 정책이다. 새 refusal 제안은 진단/경계 정의용이고
현재 export하지 않는다. 후속 데이터 구성에서는 독립 taxonomy와 split을 먼저 설계해야
한다. 자동 보호 검사만으로 모든 자연어 paraphrase를 탐지할 수 없으므로 **사람의
lineage 확인도 필수**다. 집계가 불명확한 질문은 clarification JSON 계약이 없어서
review-only이며 unsupported로 바꾸지 않는다.

```bash
python -m training.annotations.workflow import-reviewed \
  --queue training/annotations/generated/expansion_001 \
  --decisions training/annotations/generated/expansion_001/decisions.jsonl \
  --version annotation_v001 \
  --output training/annotations/generated/corpora/annotation_v001 \
  --seed 42 --valid-fraction 0.2
```

Pending/rejected/needs_fix는 export하지 않는다. 수락한 gold는 기존 `sft_record`의
schema, normalize=False parser, canonical serializer, composer/validator 검사까지
통과해야 한다. Critical error 또는 train/valid 독립 group 부족이면 nonzero 종료하고
corpus를 만들지 않는다. Prompt/schema/source/protection drift도 재검토가 필요하다.

Output은 `reviewed_annotations.yaml`, decision audit, `sft_train/valid.jsonl`,
**검토 완료 pair만** 포함한 `dpo_train/valid.jsonl`, corpus/training manifests다.
Family/contrast/template를 연결하여 group split하고 DPO는 SFT split을 상속한다.
같은 질문은 gold를 한 번만 저장하고, 다른 gold/lineage는 충돌 오류로 처리한다.
동일 family의 장소/날짜 paraphrase로 validation 수를 늘릴 수 없다.

다음 학습에서는 export directory를 training config의 dataset path로 지정한다.
기존 `training/generated`는 동결된 pilot 데이터이므로 덮어쓰거나 자동 merge하지 않는다.
Legacy build_sft/build_dpo는 기존 실험 재현용으로 유지한다. 이 단계의 새 corpus는
반드시 이 importer 결과를 사용하며, 미검토 synthetic mutation을 다시 더하지 않는다.
DPO pair가 한 split에만 있으면 DPO validation 조건을 충족하지 않는다.

## 다음 bounded pilot의 최소 조건

1. 기존 gold 재검토와 신규 gold/pair의 의미 판정을 실제 사람이 완료한다.
2. Gap 중 aggregation-stage / source-value-factor / rare subtype / OD를 독립 family로
   보강하고, train/valid 양쪽에 서로 다른 family가 있어야 한다. 단순 총량 목표는 없다.
3. DPO train/valid에 검토된 pair가 있으며 semantic/constraint와 negative_type coverage를
   확인한다. 평가/dev의 actual 오답은 분석에만 쓴다.
4. Gold 전체의 parser/composer/G1~G7 검사, group/semantic-family/exact leakage 검사,
   manifest hash 검사를 통과한다. Unsupported/ambiguity는 먼저 taxonomy/계약 경계를 정한다.
5. 다음 pilot 전에 새 corpus/config/prompt/decoding/seed를 동결하고 Base를 같은 조건으로
   다시 평가한다. 이미 본 dev 결과로 최종 품질을 주장하지 않는다. 최종 판단에는 새로
   사람 검토하고 사용 이력이 없는 holdout이 필요하다.

Tests: `python -m unittest tests.test_training_annotations -q` (GPU 불필요).
