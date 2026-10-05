# Vendor 100 baseline 001

이 결과는 evaluation-only이며 training, annotation candidate 생성, DPO negative mining, checkpoint/hyperparameter 선택에 사용하지 않는다. pilot_003은 실행하지 않았고 설정을 변경하지 않았다.

## 원본과 동결

- 원본: `evaluation/vendor100/질문 결과 및 정답 설명_100문항.xlsx` (sheet `질문`, 100행). 수정하지 않았다.
- 질문/ID: `assistant_univ_questions_100_v3.yaml`, `001`–`100` 순서. 추출 gold: `evaluation/vendor100/gold.yaml`.
- XLSX SHA256: `2f84f6b1e7e1dae7071e94578bd0c1c88b7746b7b12705d53b25c95a04bf17a6`.
- 시작 commit: `2872c368734751bd9f0bb0ac13b33720506c6167`; prompt SHA256: `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
- Protocol SHA256: `04a1417c0d7309ef53594fe0ab05e980cc25a3f8bfb5d4d2093f44cf820a39d9`; ordered questions SHA256: `1a3a56a8957826ebb6a78fd8baed616e7a4b623508ded3fd15c4b9973154ee07`.
- 모델/tokenizer: `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`; seed `42`.
- pilot_002의 기존 validation 선택 영수증과 adapter hash를 먼저 동결했다. 두 adapter 모두 step 2이며 vendor 결과로 재선택하지 않았다.
- 100/100문항 동일 production flat prompt, thinking 비활성, greedy(`do_sample=false`, beams=1), max_new_tokens=1024, repetition_penalty=1.0, EOS=[151645,151643], pad=151643, KV cache 사용. sampling용 temperature/top_p/top_k는 greedy에서 사용하지 않는다.
- BF16/SDPA, 기존 HFClient, 기존 production GeoFlowPipeline 및 repair policy. 기준일 2026-09-25, retrieval/condition_check 비활성. 설정과 effective generation config는 manifest/runtime 영수증에 남겼다.

## Gold 범위와 채점 해석

- Vendor가 제공한 것은 정답 Tool 호출·인자 100건과 비고 100건이다. 직접 작성한 grounding gold는 0건, 비교 가능한 실제 수치 정답은 0건이다. 과거 `Tool 선택 결과`는 정답 수치로 취급하지 않는다.
- Native grounding exact/concept/subtype/role 지표는 **N/A**다. 아래 reference 지표는 기존 `evaluate_vendor100.gold_grounding`의 결정적 역산 100건을 이용한 **진단치**이며, 새 정답 annotation을 만들지 않았다.
- 역산은 장소/scope·measure·factor는 vendor 호출에서 가져오지만 EVENT/MEASURE의 implicit source 등은 평가 코드 관례다. 올바른 user source/value 출력을 strict reference exact가 틀렸다고 셀 수 있다. 이 값을 human-reviewed semantic gold 정확도로 해석하지 않는다.
- JSON/contract/factor/strict reference exact/concept recall은 첫 응답, compose/validator는 기존 repair 후 최종 graph, vendor grounding semantic match는 최종 grounding 기준이다. JSON 지표는 production의 tolerant JSON extractor를 사용한다.
- Vendor grounding semantic match는 기존 evaluator의 measure/place/scope/factor/aggregation IR 비교다. source/role/value의 완전한 정답 검증이 아니다. Validator PASS도 질문 의미가 맞다는 뜻이 아니다.
- 실행은 기존 mock+legacy 계약의 **호출·인자·scope 출처·mock 값 전달** 검사만 했다. 실제 TIMS provider/수치 execution accuracy는 **N/A(0건)**. provider 미확인 정의/달력 위임과 모델 오류를 혼동하지 않는다.

## 100문항 비교

| Metric | Base | Best SFT | Best SFT+DPO |
|---|---:|---:|---:|
| JSON parse (first response) | 100/100 | 100/100 | 100/100 |
| Contract pass (first response) | 71/100 | 72/100 | 75/100 |
| Native grounding exact | N/A | N/A | N/A |
| Vendor grounding semantic match (final) | 35/100 | 33/100 | 35/100 |
| Strict inverse reference exact (diagnostic) | 25/100 | 23/100 | 25/100 |
| Concept reference recall (diagnostic) | 213/301 | 214/301 | 224/301 |
| Subtype reference recall (diagnostic) | 211/301 | 212/301 | 222/301 |
| Role reference recall (diagnostic) | 207/301 | 208/301 | 219/301 |
| Factor exact (first response, vendor-call reference) | 39/100 | 37/100 | 40/100 |
| Compose (final) | 56/100 | 53/100 | 57/100 |
| Validator pass (final) | 56/100 | 53/100 | 57/100 |
| Each G1–G7 pass (checked graphs only) | 56/56 | 53/53 | 57/57 |
| Repair attempted | 16/100 | 15/100 | 17/100 |
| Mock execution success (not semantic accuracy) | 56/100 | 53/100 | 57/100 |
| Mock vendor-call/answer match | 34/100 | 32/100 | 34/100 |
| Mock vendor semantic axis (resolved scope) | 34/100 | 32/100 | 34/100 |
| Real execution / numeric accuracy | N/A | N/A | N/A |

Concept/subtype/role는 기존 scorer의 matched/expected micro-recall이며 class accuracy가 아니다. Factor precision/recall의 raw numerator/denominator와 모든 G1–G7 conditional 분모는 RESULTS.json에 있다.

## Category 결과 (중복 소속 허용)

| Category | Questions | Base semantic | SFT semantic | DPO semantic |
|---|---:|---:|---:|---:|
| date_factor | 76 | 20/76 | 18/76 | 20/76 |
| source_role_value | 100 | 35/100 | 33/100 | 35/100 |
| OD | 33 | 17/33 | 16/33 | 17/33 |
| aggregation | 73 | 25/73 | 23/73 | 25/73 |
| fare | 10 | 1/10 | 1/10 | 1/10 |
| speed | 9 | 5/9 | 5/9 | 5/9 |
| rpm | 4 | 1/4 | 1/4 | 1/4 |
| passage_count | 24 | 3/24 | 2/24 | 3/24 |
| vacant_ratio | 7 | 2/7 | 2/7 | 2/7 |
| unsupported | 0 | N/A | N/A | N/A |

`date_factor`는 vendor date 인자가 있는 문항, OD는 trip-count/OD 조건 문항, aggregation은 reducer/bucket/rollup/dimension/order 인자를 포함한 넓은 축이다. fare/speed/rpm 등은 vendor measure 기준이다. source_role_value=100은 모든 grounding의 구조 검사를 뜻하며 100건의 human source/role label이 있다는 뜻이 아니다. Unsupported gold는 0건이므로 unsupported precision/recall을 주장하지 않는다. 모델의 거부 빈도는 RESULTS.json outcomes에만 기록했다.

## 개선·회귀 및 오류 사례

비교의 성공 기준은 동일 문항의 **vendor grounding semantic match**다. strict inverse exact나 Validator PASS로 성공을 대체하지 않았다.

- base_to_sft_improvements: 0건 — 없음
- sft_to_dpo_improvements: 2건 — 008, 084
- sft_to_dpo_regressions: 0건 — 없음
- all_fail: 65건 — 001, 002, 004, 005, 007, 009, 011, 012, 013, 016, 017, 019, 020, 021, 022, 024, 025, 027, 028, 030, 032, 034, 037, 039, 040, 042, 045, 046, 047, 049, 050, 052, 054, 055, 056, 059, 060, 061, 062, 064, 065, 066, 070, 072, 074, 075, 076, 077, 078, 079, 080, 081, 083, 086, 087, 088, 091, 092, 093, 095, 096, 097, 098, 099, 100

기존 scorer의 별도 mock semantic axis(정답 장소도 resolver로 풀어 비교)에서도 같은 비교를 기록했다. Grounding 표기 차이와 실제 mock 호출 의미 차이는 같지 않을 수 있으므로 두 축을 합치지 않았다.
- mock semantic base_to_sft_improvements: 0건 — 없음
- mock semantic sft_to_dpo_improvements: 2건 — 008, 084
- mock semantic sft_to_dpo_regressions: 0건 — 없음
- mock semantic all_fail: 66건 — 001, 002, 004, 005, 007, 009, 011, 012, 013, 016, 017, 019, 020, 021, 022, 024, 025, 027, 028, 030, 032, 034, 036, 037, 039, 040, 042, 045, 046, 047, 049, 050, 052, 054, 055, 056, 059, 060, 061, 062, 064, 065, 066, 070, 072, 074, 075, 076, 077, 078, 079, 080, 081, 083, 086, 087, 088, 091, 092, 093, 095, 096, 097, 098, 099, 100

전체 사례는 ignored raw 디렉터리의 `paired_examples.json`, 대표 최대 3건씩은 tracked `paired_cases.json`에 질문/vendor 정답 호출/실제 원응답/최종 grounding/차이를 함께 보존했다. `category_error_summary.json`은 measure/place/scope/factor 차이 분포다. 이 사례는 진단·보고용이며 annotation 또는 DPO rejected로 재사용하지 않는다.

## 중복·lineage와 benchmark 적합성

- ID와 normalized question 중복 0건, vendor 정답 의미가 동일한 내부 그룹 0건. lexical similarity ≥0.82인 12쌍은 모두 정답 조건이 다른 contrast다. `duplicate_contrast_audit.json` 참고.
- 기존 train/validation과 normalized question 중복 0건. 보수적인 default-normalized family 겹침은 train 3문항(016,063,076), validation 3문항(012,077,093)이다. 전체 corpus 버전/원래 generated corpus를 합친 감사이며 같은 record의 버전 반복을 중복 문항으로 세지 않았다.
- 실제 pilot_002의 **v002 corpus만** 보면 exact overlap은 train/validation 모두 0건, train family 겹침 후보는 2건(016,076), validation family 겹침은 0건이다. `lineage_pilot_002_scope.json` 참고. 이는 corpus의 잠재 template 공유이며 bounded optimizer step에서 실제로 각 record를 방문했다는 증명은 아니다.
- 기존 dev/evaluation 질문과 exact overlap 1문항(047), default-normalized family overlap 51문항. review 문서의 vendor 질문 12건은 모두 lineage-review witness/참조이며 approved training sample이 아니다. 자세한 경로/context는 두 lineage audit에 있다.
- Family 기준은 wording/place/date/source를 무시하는 보수적인 template 비교다. 겹침은 실제 공통 parent의 증명이 아니며, 검사 미검출도 독립성 증명이 아니다.
- 과거 vendor 질문으로 runtime 평가·개발을 수행한 이력이 있다. **앞으로의 고정 protocol 회귀·종단 비교에는 적절하지만 fresh unseen/final holdout 또는 100개 독립 family로 주장할 수 없다.** 이번 결과로 데이터/설정을 변경하지 않았다.

## 재측정 protocol

Frozen runner의 원문/hash를 manifest에 보존했다. runtime/training 코드는 추가·변경하지 않았다. ignored raw가 없는 checkout에서도 다음으로 복구할 수 있다:

```bash
python - <<'PY'
import json, hashlib
from pathlib import Path
m = json.loads(Path('training/evaluations/vendor_100_baseline_001/manifest.json').read_text())
p = Path('training/runs/vendor_100_baseline_001/benchmark.py'); p.parent.mkdir(parents=True, exist_ok=True)
source = m['protocol_runner_source']
assert hashlib.sha256(source.encode()).hexdigest() == m['protocol']['runner_sha256']
p.write_text(source, encoding='utf-8')
PY
PYTHONPATH=. python training/runs/vendor_100_baseline_001/benchmark.py verify
```

GPU inference는 기존 검증 이미지/venv와 offline pinned model cache에서 실행한다. 패키지·CUDA·PyTorch를 교체하지 않는다:

```bash
docker run --pull=never -d --name geoflow-vendor100-baseline --runtime nvidia --gpus all --shm-size 2g -v /home/hwkim/assistant_univ:/workspace -v /home/hwkim/assistant_univ:/home/hwkim/assistant_univ -v /tmp/geoflow-hf-cache:/hf-cache -w /home/hwkim/assistant_univ --entrypoint /bin/sh sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f -c 'sleep infinity'
docker exec -e HF_HOME=/hf-cache -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e TOKENIZERS_PARALLELISM=false geoflow-vendor100-baseline training/runs/thor-env/bin/python training/runs/vendor_100_baseline_001/benchmark.py run --label base
# 같은 명령의 --label을 sft, sft_dpo로 바꿔 순차 실행한다.
PYTHONPATH=. python training/runs/vendor_100_baseline_001/benchmark.py report
```

보고서와 오류 taxonomy까지 재생성하려면 reporting_manifest.json의 reporting_source를 SHA256 확인 후 같은 ignored 디렉터리의 render_report.py로 복구하고, `PYTHONPATH=.:training/runs/vendor_100_baseline_001 python training/runs/vendor_100_baseline_001/render_report.py`를 실행한다. CPU protocol test의 원문/hash/명령도 reporting_manifest.json에 보존했다. 보고 단계는 기존 scorer가 돌려주는 문자열 `no_grounding`을 문자열 전체로 집계하며 inference나 score를 변경하지 않는다.

같은 이름의 본 작업 컨테이너가 이미 있으면 중복 생성하지 않고 사용한다. Manifest immutable_inputs에 기록된 ignored XLSX/adapter/동결 corpus snapshot과 model cache는 로컬에서 별도 보존해야 한다. Git에 weight/binary/cache를 넣거나 ignore를 우회하지 않는다. 환경 버전과 tokenizer bytes/chat-template hash는 environment.json 및 tokenizer_receipt.json과 대조한다.

위 baseline_001 명령은 동일 hash의 완료된 row를 재추론하지 않는다. **pilot_003 이후에는 baseline_002 등 새 디렉터리**를 사용하고 아래 follow-up 절차로 새 checkpoint를 측정한다. vendor 결과를 checkpoint 선택에 사용하면 안 된다. 먼저 v003 자체 validation으로 선택을 완료한다.

1. 원래 manifest/frozen_questions/lineage_audit를 새 평가 디렉터리로 복사한다. 원본 baseline_001은 수정하지 않는다.
2. 복사본 models.sft/sft_dpo의 adapter/선택 영수증/identity hash만 독립적으로 이미 선택된 pilot_003 모델로 교체하고 해당 adapter 파일 hash를 immutable_inputs에 추가한다. model/revision/seed/prompt/decoding/protocol_hash/frozen_questions_hash는 변경하지 않는다.
3. frozen runner를 import한 후 `B.DEST=Path(new_evaluation_directory)`와 `B.RAW=Path(new_ignored_raw_directory)`를 지정한다. `B.verify()` → `B.run_model("base")` → `B.run_model("sft")` → `B.run_model("sft_dpo")` → `B.report()`를 순차 실행한다. 동일 protocol/100문항을 강제하고 raw model hash도 검사한다.
4. source/prompt/decoding/환경이 달라져 기존 hash 검사를 통과하지 못하면 같은 benchmark protocol run으로 합치지 말고 별도 protocol version으로 보고한다. Token training limit 조정은 inference의 max_new_tokens/원문 prompt를 변경할 이유가 아니다.

새 adapter hash 계산은 기존 baseline과 동일하게 `identity_hash = sha256(json.dumps(adapter_hashes, sort_keys=True).encode())`; adapter_hashes는 저장소 상대 경로→파일 SHA256이고 adapter_config.json/adapter_model.safetensors를 포함한다. Manifest의 runner source를 그대로 import하므로 새로운 evaluator를 구현할 필요가 없다.

## 검증과 불변성

- 기존 관련 unit tests 92개 PASS; frozen protocol CPU tests 7개 PASS(100 vendor 역산 reference의 pipeline roundtrip 포함).
- 완료 후 ordered IDs 100×3, protocol/model/hash, 동일 effective generation config, 모든 동결 corpus/config/production source/hash를 재검사했다. 결과는 VALIDATION.json 참고.
- 결과/manifest/소규모 대표 사례만 커밋한다. Model weights, checkpoint, XLSX binary, 전체 raw prediction/log는 기존 ignore 규칙대로 제외한다.
- 이번 작업은 inference/evaluation만 수행했다. Training, annotation import/generation, negative mining, production 변경, pilot_003 실행/config 조정, 시스템 설정 변경을 하지 않았다.
