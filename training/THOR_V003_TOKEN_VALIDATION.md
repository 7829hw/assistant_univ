# V003 token-limit and Thor memory gate — 2026-10-05

승인된 v003 전체 SFT 35건 / DPO 32 pair를 보존하면서 새 pilot profile에만 limit을 올렸다. v001/v002/v003 corpus, 이전 experiment/config, production prompt/schema/runtime은 수정하지 않았다. Pilot_003 본 학습은 시작하지 않았다.

## 선택과 trainer semantics

- SFT YAML: `max_seq_length: 7040` → 기존 `train_sft`가 TRL `SFTConfig.max_length`로 전달한다.
- DPO: `max_length: 7040`, `max_prompt_length: 6816`, `max_completion_length: 256`.
- 기존 helper는 실제 generation prefix + JSON/EOS + 1-token guard를 검사한다. 새 limit에서 67/67 record 통과, overflow/truncation/drop 모두 0건.
- 실제 최소값은 SFT total6977 / DPO total6978, prompt6789 / completion188이다. 7040은 기존 analyzer의 128 단위 total 반올림과 일치하며, prompt6816은 최소값보다 27 큰 32 단위 ceiling이다. Prompt를 analyzer의 6912까지 늘릴 필요가 없다. Completion256은 그대로 유지한다.
- 7008 같은 더 작은 total ceiling도 이 고정 corpus를 수치상 수용하지만, 현재 trainer는 dynamic padding을 사용한다. Max limit을 낮춰도 같은 입력의 tensor를 줄이지 않으므로 검증한 7040 profile을 선택했다. 필수 kernel alignment가 128이라고 주장하지 않는다.
- 설치된 TRL0.23.1의 `DPOTrainer.tokenize_row`는 prompt/completion을 각각 제한하고 forward에서 total을 제한한다. 두 개별 상한의 합 6816+256=7072가 total7040보다 커도 config 오류가 아니다. **모든 실제 pair의 결합 길이를 별도로 검사**해 total을 보장했다. 실제 최장 prompt6789 + rejected188 + guard1 = 6978이다.
- SFT는 completion-only loss, DPO는 fixed shared-adapter reference를 유지했다. Packing, QLoRA, flash-attn, torch.compile, fused optimizer를 켜지 않았다.

## 실제 장비와 실행 방식

Host `hpclab-thor2`, Ubuntu24.04.5/aarch64, L4T38.4, NVIDIA Thor compute11.0, driver580/CUDA13.0, unified memory122.82GiB. 기존 local image `sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f`와 기존 venv를 재사용했다. Torch2.13.0+cu130 / transformers4.56.2 / TRL0.23.1 / PEFT0.17.1 / accelerate1.14.0. Model/tokenizer revision `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`를 offline cache에서 읽었다.

BF16 LoRA rank16/alpha32, 실제 target252 modules, SDPA, non-reentrant gradient checkpointing, AdamW torch, batch1/accumulation1, worker0/unpinned을 유지했다. Power120W는 조회만 했고 clocks/power/JetPack/CUDA/PyTorch/패키지를 변경하지 않았다. Optional extension 테스트/설치도 하지 않았다.

각 단계는 독립 process에서 2 optimizer step씩, 총 6개 probe를 **순차** 실행했다:

1. `control_old`: 기존 limit에 들어가는 가장 긴 train record.
2. `control_new`: 같은 record/seed/reference에 limit만 변경.
3. `long_new`: 전체 corpus의 최장 승인 record.

최장 SFT RB003-17과 DPO RB003-30은 validation에 있다. Corpus나 export split을 바꾸지 않고 **runtime-only LR0 stress fixture**로만 사용했다. 실제 forward/backward와 AdamW moment-state 생성/optimizer step을 실행했지만 초기/최종 policy tensor hash가 정확히 같았다. Optimizer state는 process 종료로 폐기했다. Bootstrap SFT도 LR0의 fresh Base LoRA이며 `SMOKE_ONLY.json`을 붙였다. 이전 pilot adapter는 사용하지 않았고, 이 bootstrap을 pilot_003에 사용해서는 안 된다. 이 probe에서 생성한 loss/reward는 품질 지표가 아니다.

첫 prepare 버전의 SFT 호출은 기존 config validator가 LR0 YAML을 거부해 GPU model load 이전에 중단됐다. 일반 positive-LR 검증은 유지하고, 새 probe 버전002에서 검증 후 실행 copy에만 LR0을 명시적으로 적용했다. 실패 trace도 보존했다. Production/trainer 계약을 완화하지 않았다.

## 실측 결과

| Probe | Peak allocated GiB | Peak reserved GiB | Min system available GiB | sec/step | policy tokens/s | GPU 최대 °C |
|---|---:|---:|---:|---:|---:|---:|
| SFT old 6912 control | 29.51 | 33.13 | 83.09 | 15.02 | 460.09 | 43.41 |
| SFT new7040 same control | 29.51 | 33.13 | 80.83 | 14.36 | 481.25 | 45.53 |
| SFT new7040 longest | **29.65** | **33.31** | **80.73** | **16.42** | **424.90** | **47.16** |
| DPO old6912/6784 control | 32.12 | 34.26 | 80.32 | 52.64 | 262.03 | 51.06 |
| DPO new7040/6816 same control | 32.12 | 34.26 | 79.47 | 52.77 | 261.40 | 52.63 |
| DPO new7040/6816 longest | **32.42** | **34.89** | **79.20** | **52.43** | **266.14** | **54.97** |

모든 probe에서 OOM 없이 finite gradient/AdamW state, optimizer 2 step, policy hash 불변을 확인했다. DPO trainer의 초기/종료 fixed-reference hash 검사도 통과했다.

같은 입력에서는 allocated/reserved 증가가 0이다. 속도는 SFT -4.40%, DPO +0.24%의 sec/step 변화지만 두 step만 측정했으므로 유의미한 성능 차이라고 해석하지 않는다. 최장 sample은 old-fitting control보다 allocated가 SFT +0.139GiB / DPO +0.297GiB 증가했다. 이 비교는 **입력 자체도 다르므로 limit만의 영향이 아니다**. Min system available에는 model preparation, filesystem cache 등 CPU/GPU shared memory 변동도 포함한다. 단일 CUDA allocation 수치를 전체 unified memory 사용량으로 해석하지 않는다. 실제 available은 reserve 약24.56GiB를 충분히 상회했다.

sec/step은 forward/backward/reference/optimizer와 profile snapshot을 포함하고 eval/save를 제외한다. Timer는 `RunProfile.on_optimizer_step`에서 CUDA synchronize 후 종료되며, 뒤에 실행되는 finite-state callback과 adapter hash 검사는 step timing에 포함되지 않는다. Token rate는 policy의 nonpadding 입력 기준이며 DPO는 chosen+rejected를 세고 reference는 제외한다. 최장 SFT의 실제 TRL sequence6976 및 supervised completion187, 최장 DPO의 prompt/chosen/rejected6789/187/188을 원래 token ID와 대조해 silent truncation이 없는 것을 확인했다. Thermal은 phase별 sysfs GPU reading의 최대이며 continuous peak sensor recording이 아니다. 두-step 검증으로 long-run 안정성이나 throttling 부재를 입증하지 않는다.

## Frozen pilot_003 profiles

- `training/configs/qwen3_8b_thor_pilot_003_sft.yaml`
- `training/configs/qwen3_8b_thor_pilot_003_dpo.yaml`

6개 probe의 PASS, OOM 없음, 실제 optimizer step 및 policy hash/record-level token proof를 확인한 뒤에만 위 파일을 생성했다. 기존 pilot002 template의 bounded 설정(LR5e-5 SFT / LR1e-5·beta0.1 DPO, max12/8 step)을 유지하고 새 corpus/path/limit만 연결했다. SFT는 Base에서 시작한다. DPO의 `SELECTED_V003_SFT_REQUIRED`는 의도된 sentinel이며, **이번 새 SFT의 best generation checkpoint를 선택한 뒤 별도 resolved config로 고정**해야 한다. Last checkpoint, 이전 pilot adapter 또는 smoke bootstrap으로 자동 대체하지 않는다.

SFT config SHA256: `b6a8b83bd7aaf34b6659209fa3eda8e066dde8f114ffbbe2cabc22f6957e0f9f`

DPO config SHA256: `4a88d6d9bf95e281d8a15190f5ac4441a5e550070dade2836a880590d9556cf0`

Source commit `d67d8c708c936cbd9294d34df2d31646a56ea10b`, 정확한 probe source hashes, seed42, production prompt hash, corpus/old config hashes, 새 config hashes와 GPU proof는 `training/records/validation/thor_v003_token_smoke_002/`에 보존했다. Operator graph나 provider는 변경하지 않았다.

## 재현/검증

기존 검증된 Thor container/venv에서 별도 새 디렉터리를 사용한다:

```bash
python -m training.v003_token_smoke --prepare \
  --directory training/experiments/thor_v003_token_smoke_NEXT
python -m training.v003_token_smoke \
  --directory training/experiments/thor_v003_token_smoke_NEXT \
  --stage sft --case control_old
```

이어서 SFT `control_new`, `long_new`, DPO `control_old`, `control_new`, `long_new`를 동일 CLI로 **하나씩** 실행한다. Prepare는 GPU model을 초기화하지 않는다. 전체 기존 corpus/hash를 검사하고 모든 token guard를 통과해야 한다. Probe는 Thor GPU가 없으면 명확히 실패한다. 새 probe/profile version에는 새 directory를 사용한다.

다음 본 pilot 실행 전에 data-only preflight:

```bash
python -m training.train_sft \
  --config training/configs/qwen3_8b_thor_pilot_003_sft.yaml --dry-run
python -m training.train_sft \
  --config training/configs/qwen3_8b_thor_pilot_003_sft.yaml --tokenizer-check
python -m training.train_dpo \
  --config training/configs/qwen3_8b_thor_pilot_003_dpo.yaml --dry-run
python -m training.train_dpo \
  --config training/configs/qwen3_8b_thor_pilot_003_dpo.yaml --tokenizer-check
```

이 작업에서는 위 preflight까지 검증했고 **pilot_003 본 학습은 실행하지 않았다**. Training dependency 또는 GPU 환경을 새로 설치하지 않았다. Container는 종료/제거했고 GPU compute process가 없음을 확인했다. Weight/cache/ignored experiment는 commit하지 않는다.

관련 training suite **126 tests OK (skip2)**, 전체 suite **1184 tests OK (skip2, expected failure1)**. 신규 CPU 회귀 테스트 6개를 포함한다. Corpus/config/production source guard와 archive hash 대조도 통과했다. 자세한 결과는 `records/validation/thor_v003_token_smoke_002/TEST_VALIDATION.json`에 있다.
