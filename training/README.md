# GeoFlow Planner grounding SFT + DPO

이 패키지는 LLM의 **semantic grounding 정확도**를 개선하는 offline 학습 파이프라인이다.
production planner, prompt 기본값, deterministic composition, validation, compiler와 executor의
책임은 바꾸지 않는다. 분석 근거와 구현 순서는 [ARCHITECTURE.md](ARCHITECTURE.md)에 있다.

```text
Question -> fine-tuned GeoFlowPlanner -> grounding JSON -> parse_grounding
         -> MacroComposer -> GeoFlowPlan -> Validator G1-G7 -> Compiler -> Executor

Base -> SFT(correct grounding) -> DPO(chosen/rejected grounding preferences)
```

[Spatial-Agent, ACL 2026 §3.5 / Appendix D](https://aclanthology.org/2026.acl-long.679.pdf)는
SFT로 concept/type/functional role을, DPO로 graph well-formedness를 학습한다. 여기서는 두
단계 모두 **production grounding JSON**을 출력한다. Graph construction을 LLM으로 옮기면
현재 port/type 규칙, 유일한 operator 선택, deterministic macro composition의 장점이
사라진다. Graph/macro/operator/tool/실행 순서는 training completion에 없다. 품질 평가에
쓰이는 macro/operator 이름은 metadata에만 있으며 trainer가 학습 입력에서 제거한다.

## 설치와 의존성 경계

**Jetson AGX Thor에서는 [THOR.md](THOR.md)의 BF16 LoRA 절차를 사용한다.** Generic
`qwen_*.yaml`은 기존 x86 QLoRA 설정을 유지한다. Thor에서 아래 generic requirements로
PyTorch를 교체하지 말고, 이미 CUDA 연산이 성공하는 PyTorch + `requirements-thor.txt`를
사용한다. 실제 장비에서의 짧은 학습 결과는 [THOR_VALIDATION.md](THOR_VALIDATION.md)에 있다.

저장소 root에서 아래 명령을 실행한다. Python 3.10+를 사용한다. GPU와 모델 다운로드 없이
dataset builder, unit test, dry-run을 실행할 때는 runtime requirements만 필요하다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# GPU 학습 환경에서만 추가 설치. CUDA에 맞는 torch 설치를 먼저 확인한다.
pip install -r training/requirements.txt
```

학습 코드는 torch/transformers/PEFT/TRL을 lazy import한다. runtime requirements와 runtime
import graph는 training 패키지에 의존하지 않는다. API는 **TRL 0.23.1**, transformers
4.56.x, PEFT 0.17.x에 맞췄다. 임의의 최신 TRL로 교체하면 Config/Trainer API를 다시 확인한다.
[SFT API](https://huggingface.co/docs/trl/v0.23.1/en/sft_trainer)와
[DPO API](https://huggingface.co/docs/trl/v0.23.1/en/dpo_trainer)를 기준으로 구현했다.
bitsandbytes 지원 GPU/OS 및 bf16 가능 여부는 사용하는 머신에서 확인한다.

## 출력 계약과 source representation

실제 소규모 Thor pilot의 고정 조건과 재실행 방법은 [PILOT.md](PILOT.md),
Base/SFT/SFT+DPO 실측 비교는 [PILOT_REPORT.md](PILOT_REPORT.md)를 참고한다.
Pilot은 tiny-data 관측 실험이며 production 최종 모델 학습이 아니다.

Pilot 이후의 다음 단계는 추가 학습이 아니라 annotation 품질/coverage 보강이다.
[Annotation review workflow](annotations/README.md)는 coverage 분석, bounded 후보,
실제 오답 mining, JSONL/XLSX review queue와 reviewed-only corpus import를 제공한다.
자동 후보 및 evaluation/dev 오답은 다음 training corpus에 바로 넣지 않는다.

production 기본값은 `aggregation_grounding="flat"`이다. 지원 가능한 출력의 최상위 key는
`concepts`, `factors`이고, 지원 불가능한 출력은 정확히 `{"unsupported":true}`다.
`training.data.canonicalize.serialize_planner_target`는 다음을 보장한다.

- UTF-8, 정렬된 key, 최소 공백, JSON만 출력한다. 설명과 markdown fence가 없다.
- concept list를 의미 필드로 정렬하고 local ID를 `c1`, `c2`, …로 바꾼다.
  ID는 참조가 없는 출력 안의 local 이름이다. 중복 ID는 이름을 바꾸기 전에 거부한다.
- `text`, `value`, `attributes.od_role`, `source` 등 계약 필드는 보존한다.
- 내부 `Grounding`에서는 계약 필드만 명시적으로 꺼낸다. `Grounding.to_dict()` 전체를
  target으로 쓰지 않는다. 내부 aggregation/calendar/audit/normalization 값은 출력하지 않는다.
- raw dict의 unknown top/concept fields와 non-JSON 값은 오류다. rejected의 잘못된 subtype,
  role, factor 등은 JSON으로 보존한 뒤 **production parser**에서 오류를 기록한다.

예시 저장소 `geoflow_examples/question_graph_examples.yaml`은 structured annotation이다.
기본 builder는 `--source-representation structured`로 읽고 기존 `geoflow.aggregation`
parser와 명시적 `to_flat` projection으로 변환한다. bucket/inner/outer/select의 왕복 의미가
같아야 한다. 한 corpus에서 flat/structured source를 섞지 않는다. 생성 completion은 항상
flat이고, structured corpus 학습 실험은 이후 별도의 dataset/schema/prompt ablation으로 분리한다.
Clarification은 production에서 오류/사용자 확인 경로이며, 정답 assistant JSON이 정해져
있지 않다. 현재 구현에서는 이를 unsupported로 재라벨하지 않고 제외 사유를 기록한다.

## 데이터 출처와 검증

기본 source는 위 question-graph store다. 먼저 `load_store`/`verify_example`로 source schema,
grounding↔graph↔macro annotation을 확인한다. 이후 flat canonical target을 생성하고
`parse_grounding -> MacroComposer.compose -> validator.validate`를 실행한다. G1~G7 logic은
production 모듈을 import하며 training 아래에 복사하지 않는다.

Gold는 normalize=False로도 통과해야 하며, production normalization/drop-invented-region이
grounding 의미를 바꾸는 annotation은 수정 요청 오류로 보고한다. 데이터 생성 중 조용한
자동 정답 보정은 하지 않는다. Unsupported는 production planner가 parser 이전에 인식하므로
`parse_ok=true, compose_ok=null, validation_ok=null, outcome=unsupported`로 기록한다.
이것은 graph validation 통과를 뜻하지 않는다.

현재 store에는 16개 예시가 있다. 최초 strict build에서는 answered 13개 + unsupported 2개를
사용하고 clarification 1개를 제외한다. Annotation의 `reviewed_by`에는 사용자 검토 전 표시가
포함되어 있다. 등록 검증은 질문 의미에 대한 사람의 정답 검토를 대신하지 않는다. Reviewer,
source version과 tags를 metadata에 남기고 manifest에 관련 warning을 기록한다.

독립 annotation을 추가하려면 아래 YAML list 형식을 사용한다. `parent_intent` 또는 `family`에
모든 paraphrase의 동일한 부모를 적는다. `reviewed_by`에는 실제 검토자를 기록한다.

```yaml
- id: new_intent_01_p0
  parent_intent: new_intent_01
  question: "..."
  grounding: {concepts: [...], factors: {...}}
  tags: [overall_average]
  reviewed_by: "검토자/검토일"
```

이 데이터는 `--source-representation flat`로 생성한다. 서로 다른 source를 하나로 합칠 때도
부모 family를 유지해야 한다. 현재 CLI의 input은 한 source document다.

## Leakage 정책과 split

`evaluation/corpus_registry.yaml`의 development 표시가 학습 허용을 의미하지 않는다. 기존에
본 holdout, v2 benchmark, question set, 그 부모와 evaluation/ 아래 데이터는 모두 학습 입력에서
차단한다. root의 vendor questions/stub query도 보존한다. Reserved YAML 안의 질문과 공백/
문장부호/Unicode를 정규화한 중복도 차단한다. **자연어 paraphrase의 의미 중복을 완전히
자동 탐지할 수는 없다.** 신규 annotation은 평가 family에서 파생시키지 말고 사람이 확인한다.

Split은 question random split이 아니다. 명시적 parent/family, abstract semantic template
(concept/subtype/role/OD, factor presence, 집계·dimension·order 값), `contrast_pair:<id>`를
연결한 component 단위다. 장소/날짜/택시 유형 조건 값은 template에서 추상화해 조건값만 바꾼
질문도 함께 둔다. Unsupported는 별도 reviewed taxonomy가 없어 모두 한 family로 묶는다.
그룹을 정렬한 후 seed로 섞고 validation group을 고른다. Train/validation parent 및 질문
중복을 검사한다. 새 source가 추가되면 component ID/split이 달라질 수 있으므로 dataset 판을
다시 고정한다. DPO는 **SFT split을 상속**하며 재분할하지 않는다.

## SFT dataset 생성

```bash
python -m training.data.build_sft \
  --input geoflow_examples/question_graph_examples.yaml \
  --source-representation structured \
  --output training/generated --seed 42 --valid-fraction 0.2 --strict
```

`sft_train.jsonl`, `sft_valid.jsonl`, `manifest.json`을 생성한다. 다음은 record 형식 예시다.
system content는 생략 표기이며 실제 파일에는 `GeoFlowPlanner.system_prompt()` 전체가 들어간다.

```json
{
  "messages": [
    {"role":"system","content":"<production system prompt 전체>"},
    {"role":"user","content":"지난달 중구 법인택시의 운행일수 평균은?"},
    {"role":"assistant","content":"{\"concepts\":[{\"concept\":\"AMOUNT\",\"id\":\"c1\",\"role\":\"MEASURE\",\"source\":\"implicit\",\"subtype\":\"operating_days\"},{\"concept\":\"EVENT\",\"id\":\"c2\",\"role\":\"SUPPORT\",\"source\":\"implicit\",\"subtype\":\"operation\"},{\"concept\":\"LOCATION\",\"id\":\"c3\",\"role\":\"SUBCOND\",\"source\":\"user\",\"subtype\":\"place\",\"text\":\"중구\",\"value\":{\"name\":\"중구\",\"region\":\"\"}}],\"factors\":{\"aggregation\":\"avg\",\"date\":\"last_month\",\"taxi_type\":\"corporate\"}}"}
  ],
  "metadata": {"source":"geoflow_examples/question_graph_examples.yaml","source_record_id":"ex01","parent_intent":"<component id>","tags":["overall_average"]}
}
```

## DPO dataset 생성과 negative 종류

```bash
python -m training.data.build_dpo \
  --gold training/generated --output training/generated \
  --seed 42 --max-negatives 8 --strict
```

`dpo_train.jsonl`, `dpo_valid.jsonl`을 추가하고 manifest의 `dpo` section을 갱신한다.
각 prompt/chosen/rejected는 TRL conversational preference 형식이다.

```json
{
  "prompt":[{"role":"system","content":"<production system prompt 전체>"},{"role":"user","content":"2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?"}],
  "chosen":[{"role":"assistant","content":"<canonical concepts + factors: aggregation=sum, bucket=week, rollup=min>"}],
  "rejected":[{"role":"assistant","content":"<동일 concepts + factors: aggregation=min, bucket=week, rollup=sum>"}],
  "metadata":{
    "negative_type":"aggregation_stage_swap","negative_category":"semantic","mutation_source":"synthetic",
    "chosen_quality":{"parse_ok":true,"compose_ok":true,"validation_ok":true,"validation_codes":[]},
    "rejected_quality":{"parse_ok":true,"compose_ok":true,"validation_ok":true,"validation_codes":[]}
  }
}
```

위 예시는 JSON 필드 구조를 줄여 표시한 것이다. 실제 content는 SFT와 동일한 완전한 JSON
문자열이다. 두 graph가 valid이어도 질문은 sum→min을 요구하므로 min→sum은 semantic error다.
Constraint negative는 parser/composer/validator 실패이며 별도 `error_code`/detail을 기록한다.
Validator가 실제로 실행되었을 때만 실패 G-code를 기록한다. 파싱/합성 실패는 G-code를
만들어내지 않는다. Unsupported/refusal은 constraint failure가 아니라 semantic preference다.

Mutation은 다음 실제 필드를 편집한다.

- measure subtype와 core concept confusion, EVENT subtype confusion
- MEASURE 제거, MEASURE↔SUPPORT와 SUBCOND→COND role 오류
- factor hallucination/omission, 날짜 범위 오류, vicinity 제거
- pickup/dropoff 동시 swap 및 개별 pickup/dropoff/both 변경, od_role 및 장소 제거, 잘못된 장소/상위 region
- avg↔sum, min↔max, med→avg, bucket 변경, aggregation↔rollup stage swap, rollup/bucket 제거
- 지원 가능한 질문의 false refusal와 unsupported 질문의 generic revenue grounding
- implicit↔user source 오류(이 저장소에서는 값과 scope provenance에 실제 의미가 있음)

`count`는 현 factor aggregation enum이 아니다. Count 의미는 passage_count/trip_count 등의
measure subtype으로 표현하므로 `aggregation=count`를 gold처럼 취급하지 않는다. LOCATION은
factor가 아니라 concept value다. 날짜/유형/집계는 factors이고 장소 오류는 concepts를 편집한다.
Implicit EVENT가 없더라도 registry가 올바르게 추론하는 것은 허용된 동작이다. 이를 synthetic
negative로 만들지 않고, mining에서도 ID/text/order와 유일하게 추론 가능한 EVENT 차이만 있는
prediction은 제외한다. `negative_details`에 편집 path/이전값/이후값을 기록한다.

## SFT checkpoint로 hard negative 수집

```bash
python -m training.predict_groundings \
  --gold training/generated/sft_train.jsonl \
  --model Qwen/Qwen3-8B --adapter training/checkpoints/sft \
  --output training/generated/predictions.jsonl --seed 42

python -m training.data.build_dpo \
  --gold training/generated --predictions training/generated/predictions.jsonl \
  --output training/generated/mined --max-negatives 0 --seed 42 --strict
```

`--max-negatives 0`은 mining만, 8 등은 synthetic+mined를 섞는다. Validation source로도 별도
추론할 수 있지만 train으로 옮기지 않는다. `--gold`에 없는 prediction id, 질문/prompt hash
불일치는 오류다. Benchmark inference 결과를 DPO로 옮길 수 없다.
Mined dataset을 학습하려면 DPO config의 data.train/valid/manifest도 생성한 mined 디렉터리로 바꾼다.

Prediction JSONL은 record별 다음 필드를 갖는다. `grounding` object 또는 `raw_text` JSON
문자열을 제공한다. Raw syntax 실패는 critical report 대상으로, syntax-only negative로
학습하지 않는다. Supported alternate grounding은 gold와 다르다는 사실만으로 자동 정답 판정이
되지는 않는다. Mined semantic pair의 `semantic_judgment=differs_from_gold_requires_review`를
확인해 사람이 검토한 dataset 판을 고정한다.

```json
{"source_record_id":"ex01","question":"지난달 중구 법인택시의 운행일수 평균은?","raw_text":"<model JSON response>","prompt_hash":"<현재 SFT manifest prompt_hash>","model":"Qwen/Qwen3-8B+SFT","seed":42}
```

## 학습과 loss

```bash
python -m training.train_sft --config training/configs/qwen_sft.yaml --dry-run
python -m training.train_dpo --config training/configs/qwen_dpo.yaml --dry-run
# tokenizer만 다운로드. GPU/model weight 없이 실제 template·길이·경계를 검사한다.
python -m training.train_sft --config training/configs/qwen_sft.yaml --tokenizer-check
python -m training.train_dpo --config training/configs/qwen_dpo.yaml --tokenizer-check
# GPU에서 실행
python -m training.train_sft --config training/configs/qwen_sft.yaml
python -m training.train_dpo --config training/configs/qwen_dpo.yaml
# 재시작 예시 (실제로 생성된 checkpoint 경로를 지정)
python -m training.train_sft --config training/configs/qwen_sft.yaml \
  --resume-from-checkpoint training/checkpoints/sft/checkpoint-10
```

Config에서 model name, dtype, quantization, LoRA rank/alpha/dropout/target_modules, batch,
gradient accumulation, epochs, LR, warmup, checkpoint/log/evaluation/seed를 바꿀 수 있다.
Generic config 기본값은 Qwen3-8B QLoRA, bf16, rank 16, accumulation 16이다. Thor 전용 config는
BF16 LoRA/accumulation8이며 별도 smoke는 accumulation1이다. Target module 이름은 모델의
실제 named_modules에 있는지 검사한다. Full tuning은 lora.enabled=false와
model.load_in_4bit=false를 함께 지정한다. fp16 머신에서는 bf16=false, fp16=true로 바꾼다.
DDP의 QLoRA device는 LOCAL_RANK를 따른다. 멀티 GPU/FSDP 성능은 별도 검증이 필요하다.

SFT 저장 파일은 chat `messages`지만 trainer가 tokenizer의 generation prompt를 렌더링해
**standard prompt/completion strings**로 변환한다. TRL의 `completion_only_loss=True`,
`assistant_only_loss=False`, `packing=False`를 명시한다. Qwen non-thinking prefix(빈 think
block 포함)는 prompt에만 들어가며, supervision은 JSON+EOS다. 이 경로는 tokenizer template의
`{% generation %}` mask 지원을 요구하지 않는다. 실제 TRL completion_mask가 없는 경우
학습 전에 실패한다. JSON이나 system prompt를 잘라 학습하지 않도록 token limit 초과와
prefix tokenization mismatch는 오류다. 다른 모델은 `chat_template_kwargs`를 맞추고 tokenizer
check를 먼저 실행한다. Training과 HF evaluation은 같은 renderer를 사용한다.

DPO 기본값은 `model.adapter_path`의 SFT adapter를 `policy`(trainable)와 `reference`(frozen)로
두 번 로드한다. Base adapter를 disable해서 reference를 잘못 Base로 되돌리지 않는다.
기존 adapter를 이어 학습할 때 rank/alpha/target_modules는 저장된 SFT adapter 설정을 따른다.
Config의 LoRA 설정은 fresh adapter 생성에 적용된다. `model.revision`은 base/tokenizer에
동시에 전달된다. 연구 실행에서는 main 대신 고정 SHA를 쓰며 HF 평가/추론의 `--revision`도 맞춘다.
Merged SFT full checkpoint를 쓸 때는 `adapter_path`를 제거하고 `sft_merged: true`를 명시한다.
그 위 fresh LoRA에서는 adapter-disabled initial checkpoint가 reference다. Full tuning에서는
TRL이 frozen initial-policy copy를 만든다. `reference.mode: explicit`와 `name_or_path`는 merged
policy/full reference checkpoint 비교용이며 dual-adapter 경로와 함께 쓰지 않는다.
beta, max_prompt_length, max_completion_length, max_length 등은 DPO config에서 조절한다.
최종 DPO 저장 디렉터리 root에는 policy adapter를 표준 PEFT 형식으로 export한다. Checkpoint
재시작을 위해 저장된 policy/reference subdirectory도 보존한다.

## 동일 corpus의 네 baseline 비교

| 실험 | Policy 초기값 | DPO reference |
|---|---|---|
| Base | config의 원본 Qwen checkpoint (학습 전) | 해당 없음 |
| SFT only | Base → SFT adapter | 해당 없음 |
| DPO only | **같은 Base checkpoint**, SFT adapter 없음 | frozen Base |
| SFT → DPO | SFT policy | frozen SFT policy |

`DPO only`는 config의 별도 복사에서 `initial_mode: dpo_only`, `adapter_path` 제거,
`training.output_dir: training/checkpoints/dpo_only`로 설정하고 동일 DPO data를 사용한다.
SFT+DPO와 LR/beta/epoch 비교 조건을 기록한다. 원본 Qwen checkpoint는 Qwen3-8B 배포 모델이며
이 프로젝트의 SFT 이전이라는 뜻이다. Pretraining-only 모델이라는 뜻은 아니다.

```bash
python -m training.evaluate_checkpoint --dry-run \
  --query-file evaluation/v2/paraphrases_holdout_v2.yaml

python -m training.evaluate_checkpoint --model Qwen/Qwen3-8B \
  --label Base --execute --output training/runs/base.json
python -m training.evaluate_checkpoint --model Qwen/Qwen3-8B \
  --adapter training/checkpoints/sft --label SFT --execute --output training/runs/sft.json
python -m training.evaluate_checkpoint --model Qwen/Qwen3-8B \
  --adapter training/checkpoints/dpo_only --label DPO --execute --output training/runs/dpo.json
python -m training.evaluate_checkpoint --model Qwen/Qwen3-8B \
  --adapter training/checkpoints/dpo --label SFT+DPO --execute --output training/runs/sft_dpo.json
python -m training.evaluate_checkpoint --compare \
  training/runs/base.json training/runs/sft.json training/runs/dpo.json training/runs/sft_dpo.json \
  --output training/runs/comparison.json
```

Wrapper는 `evaluate_planner.evaluate_once`/`summarize`를 호출한다. Registry corpus는 기존
`paraphrase_corpus` loader로 읽고 parent gold를 각 item에 붙인다. Query YAML list도 지원하며,
완전한 grounding/factor 지표를 얻으려면 `golden` 또는 `grounding`을 넣는다. 기존 concept/
subtype/role accuracy, macro_exact/recall, operator_accuracy, validation, execution, repair를
그대로 재사용한다. 추가 지표는 JSON parse rate(기존 tolerant JSON extractor 기준), planner
contract rate, grounding exact match(local ID/text/order 무시), factor precision/recall/exact,
**explicit unsupported** precision/recall, composition 성공, G1~G7별 pass rate, repair rates다.

Grounding/factor 정확도는 최초 응답, downstream 지표는 기존 evaluator의 계획 단계 repair 후
결과다. 전체 validation_pass_rate denominator는 전체 질문이고, G별 rate는 **validator가 실제
실행된 질문**만이다(`validation_checked_count` 참조). Execution success는 검증 후 실제
실행한 질문에 한정하며 미실행이면 null이다. Runtime execution repair는 기존 evaluator가
실행하지 않는다. `repair_success_rate`는 성공한 planning repair / 시도한 planning repair다.
Complete gold가 없는 지표는 null/labeled_count=0이고 invalid gold도 model miss로 세지 않는다.
학습 validation split과 최종 평가 corpus는 서로 다른 용도다.

결과에는 `by_intent`, `by_task_group`이 포함된다. 전체 평균과 함께 그룹별 regression을 확인한다.
비교 명령은 corpus/prompt hash, item 순서, provider/execute/inference mode와 generation limit가
같은지 확인한다. Comparison artifact에 모든 그룹별 결과도 포함된다. Generation은 HF에서
동일 non-thinking, greedy mode를 사용한다. 실제 모델 품질/개선 수치는 실행 전에는 없다.

CPU에서는 `--predictions file.jsonl`로 위 prediction 형식의 benchmark 결과를 replay할 수 있다.
Replay에는 첫 응답만 있으므로 repair inference는 `REPLAY_REPAIR_UNAVAILABLE`이며 실모델
repair 성능을 의미하지 않는다. `--provider mock` 또는 `reference`의 실행은 합성 데이터 계산
검증이다. 실제 TIMS 성공률이라는 주장을 할 수 없다. 기존 Ollama 평가는
`python evaluate_planner.py --model <ollama-model> --execute`로 유지된다.

## 저장, merge, Ollama 연결

Trainer는 adapter/full model과 tokenizer를 `save_pretrained` 형식으로 저장하고
`training_provenance.json`에 config/manifest/prompt hash를 남긴다. Checkpoint prompt hash가
production과 달라지면 HF evaluation과 DPO continuation에서 탐지한다. HF Hub upload는 별도
명시적 작업이다. 로컬 저장만 수행하고 자동 upload하지 않는다.

```bash
python -m training.merge_adapter --base Qwen/Qwen3-8B \
  --adapter training/checkpoints/dpo --output training/checkpoints/merged_dpo --dry-run
python -m training.merge_adapter --base Qwen/Qwen3-8B \
  --adapter training/checkpoints/dpo --output training/checkpoints/merged_dpo --dtype bfloat16
```

Merge는 4-bit base에서 하지 않고 비양자화 full base를 CPU 메모리에 로드한다. 해당 RAM과
디스크 공간이 필요하다. Root policy adapter만 merge하며 frozen reference는 merge하지 않는다.
Merged model/tokenizer/provenance를 Hugging Face checkpoint 디렉터리로 저장한다.

Ollama 연결은 별도 deployment 단계다. 지원 architecture/adapter import 경로를
[Ollama import 문서](https://docs.ollama.com/import)에서 확인한다. 일반적인 full model 경로는
merged HF 모델 → 호환 llama.cpp의 `convert_hf_to_gguf.py` → GGUF → 선택적 quantization →
Modelfile의 `FROM /absolute/path/model.gguf` → `ollama create <model-name> -f Modelfile`이다.
llama.cpp 설치/변환, Ollama model 생성은 이 패키지가 자동 수행하지 않는다. 변환 도구와
Ollama가 Qwen3를 지원하는지 확인하고 chat template/non-thinking 설정 및 production prompt
동일성을 점검한 후 기존 evaluator로 재측정한다. HF↔GGUF quantization 효과도 분리한다.

## 재현성, coverage, strict errors

Manifest에는 생성 시각 UTC, git SHA/branch(graceful null fallback), seed, source hashes,
output schema version, prompt hash, planner/factor/ontology/operator definition file hashes,
output hashes, split별/전체 counts와 분포를 기록한다. Concept/subtype/role/measure/factor/
aggregation, OD/unsupported/parent counts, negative_type 및 semantic/constraint 분포, 희소 class와
OD 부재/reviewer warning을 포함한다. Trainer와 DPO builder는 data checksum 및 prompt drift를
검사한다. 모든 생성물/weights/log는 .gitignore의 training/generated, checkpoints, runs에 있다.

Non-JSON structure, unknown vocabulary, invalid factor, duplicate id/question, runtime normalization을
필요로 하는 gold, 불가능한 합성/검증, 동일 pair, split leakage, source 혼용은 명시적 오류다.
Record별 문제는 manifest issues에 기록하고 `--strict`는 nonzero로 종료한다. 알려진 clarification
exclusion/equivalent mining prediction은 exclusion으로 구분한다. Source 파일 자체가 읽히지
않거나 store header/schema가 잘못되면 CLI가 즉시 nonzero 오류를 출력한다. Critical issue가
있는 manifest로는 trainer를 실행할 수 없다.

```bash
python -m unittest tests.test_training_data tests.test_training_trainers tests.test_training_evaluation -q
python -m unittest discover -s tests -t . -q
python -m training.predict_groundings --gold training/generated/sft_train.jsonl \
  --model Qwen/Qwen3-8B --dry-run
```

## 알려진 제약과 GPU 실행 전 결정

현재 기본 corpus는 15 sample/13 parent component의 smoke dataset이며 OD는 없다. 속도/RPM,
scope, OD, 더 많은 unsupported subtype 등은 독립적이고 사람이 검토한 annotation을 추가해야
한다. Synthetic library가 지원하는 오류라도 해당 source 필드가 없으면 생성되지 않는다.
작은 validation split의 loss/accuracy는 연구 결론을 내릴 근거가 아니다. 기존 평가셋도 결과를
이미 본 development가 대부분이므로 최종 비교에는 새 benchmark family가 필요하다.

Qwen3-8B 실제 tokenizer의 SFT/DPO prefix·길이 검사는 CPU에서 통과했다. Thor BF16 LoRA의
SFT/DPO backward·optimizer smoke 결과는 THOR_VALIDATION.md를 참고한다. 다른 모델의 tokenizer
preflight, 장시간 학습, dual-adapter GPU resume, multi-GPU, merge 및 GGUF
변환은 사용 환경에서 검증해야 한다. CPU 테스트는 데이터 계약과 production downstream,
config/dry-run/prefix guard를 검증한다. 오래된 전체 suite 중 업체 원본 XLSX가 필요한 테스트는
파일이 저장소에 없어 실패할 수 있고 localhost HTTP 테스트는 socket 허용 환경이 필요하다.

GPU 실행 전 고정할 항목: 모델/정확한 revision, GPU VRAM·dtype·4-bit 여부, sequence/prompt/
completion limits(실제 tokenizer-check 결과 기준), rank/alpha/target modules, effective batch,
SFT LR/epochs·DPO LR/epochs/beta, semantic/constraint 및 synthetic/mined 비율, 검토한 annotation
판, split seed, 동일 평가 corpus/provider/prompt/generation 설정이다. 실행 후 환경의 dependency
lock, 모델 revision과 GPU 정보를 experiment 기록에 추가한다.

## 작업 브랜치와 보존 기록

후속 작업 브랜치는 `geoflow/sft-dpo-thor`이다. 작업 단위마다 테스트/검증, diff 확인,
커밋, SHA 보고를 수행하며 `geoflow/dev-v2`에는 커밋하지 않는다. Push는 별도 요청이 필요하다.

[records/README.md](records/README.md)에 bounded pilot 001/002 보고서, reviewed v001/v002/v003
승인·coverage·manifest와 batch003의 원래 pending queue, 별도 최종 decision을 보존했다.
V003의 compact index는 같은 production prompt hash에서 정확한 export 재구성을 지원한다.
원본 ignored 산출물과 weights/checkpoints/XLSX는 추적하지 않는다.

## V003 token/memory gate

Reviewed v003는 기존 6912 limit을 초과하는 승인 record 7건을 보존한다. Thor GPU smoke가
통과한 새 bounded profile은 `configs/qwen3_8b_thor_pilot_003_sft.yaml`과
`configs/qwen3_8b_thor_pilot_003_dpo.yaml`이다. SFT total7040, DPO total7040/prompt6816/
completion256이며 기존 generic/Thor/pilot001/002 config는 변경하지 않았다.
전체67 record의 token preflight와 최장 SFT/DPO 실제 backward/optimizer proof, memory/time
비교, config hashes는 [THOR_V003_TOKEN_VALIDATION.md](THOR_V003_TOKEN_VALIDATION.md)에 있다.
본 pilot003은 아직 실행하지 않았다. SFT는 Base에서 시작하고 DPO는 새 SFT의 best generation
checkpoint를 선택한 뒤 `SELECTED_V003_SFT_REQUIRED`를 별도 resolved config에서 지정한다.
LR0 memory-smoke bootstrap adapter는 품질 학습에 사용하지 않는다.
