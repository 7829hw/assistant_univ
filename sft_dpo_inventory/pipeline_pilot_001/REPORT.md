# thinking 파이프라인 pilot 보고서 (pipeline_pilot_001)

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`.

- 계획: `PLAN.md`(학습 전 고정, `0e9529d`).
- 결정: `../DECISIONS.md`.
- 지킨 것: 업체 100·Ollama 호출·`ollama create`·prompt 변경·SEMANTIC_CODE 변경은 없었다. 재학습·재평가·설정 탐색도 없었다.
- 실행 의미 코드 지문은 작업 시작, 모든 평가 결과(meta), 작업 끝 모두 `791c4a68`이다.

> **이 수치로 학습 효과를 판단할 수 없다.** valid는 16문항뿐이고, 학습 질문과 같은 분포(같은 주제·합성 장소·정책)다.
> checkpoint 사이의 차이(같은 SFT 학습 안에서 11–13)는 1–2문항 크기다. 아래 수치는 파이프라인이 끝까지 돌았다는 기록으로만 쓴다.
> 효과는 추정하지 않는다.

## 0. 요약

- **성공 기준 충족.** 데이터 → SFT → checkpoint 6개 평가 → 선택 → DPO(reference 미리 계산) → checkpoint 4개 평가 → 선택이
  멈춤 없이 끝났다(15:13–17:15, GPU 2). 계획의 산출물이 모두 남았다(10절).
- **valid grounding_ok(16문항).** base 11, 고른 SFT(step 4) 13, 고른 DPO(step 6) 12.
- **막히거나 고친 부분**(5절):
  1. mock provider가 합성 장소명을 몰라서, 장소 재질의가 맞았던 장소명을 바꾼다(가람구 → 가람). valid 1문항은 모든 셀에서 이 때문에 X다.
  2. 짧은 메모리 측정은 실제 학습의 GPU 점유를 과소평가했다. SFT·DPO 모두 실제 peak가 47–48GB(전체 49,140MiB)였다.
  3. 그 밖: 메모리 비교 측정의 실행 실패 1회(로그 폴더 없음, 측정 전), DPO rejected 재판정에서 장소 재질의 처리.
- **GPU·Ollama.** host GPU 3에서 Ollama 컨테이너의 `nvidia-smi -L`이 이번에는 성공했다(GPU-48f798cc). NVML 오류가 해소된 것으로 보이지만 Ollama는 부르지 않았다.

## 1. 결정 기록

- `05f7bef`
  - `CLAUDE.md` 5·6번: GPU 2가 기본이다. GPU 3은 Ollama 미사용일 때만 추가 작업에 쓰고, host `nvidia-smi`로 먼저 확인한다.
  - Ollama 모델을 내리거나 컨테이너를 건드리지 않는다. Ollama 일정이 있으면 GPU 3 작업을 먼저 끝낸다. NVML 해결 전에는 Ollama API를 부르지 않는다.
  - 대기 규칙 4의 `/api/ps` 예시에 예외를 적었다.
  - 결정 2–10은 `sft_dpo_inventory/DECISIONS.md`에 적었고, `CLAUDE.md` 10번이 이 파일을 가리킨다.

## 2. 데이터(`data/`, CPU, `5a5a225`)

- 입력: thinking_prep_001 후보 SFT 44, DPO 214. 기존 생성물은 고치지 않았다.

| 단계 | SFT | DPO |
|---|---:|---:|
| 결정 8: 정답 표본이 없는 7문항 | 0(이 문항에는 원래 후보가 없음) | 0 |
| 결정 4: tokenization 불일치 trace 사용 | −2 | −15 |
| 결정 6: 운영 경로 재판정 | — | 199쌍 판정(rejected 61개) |
| 　남김: 운영 경로에서도 gold와 다름 | | 54 |
| 　뺌: 조건 계층이 고침(gold와 같아짐, 조건 계층이 값을 바꿈) | | −135 |
| 　뺌: 기타(정규화만으로 gold와 같아짐) | | −10 |
| builder 계약 판정(chosen 계약 실패 표본 2개) | −2 | −6 |
| **최종** | **40(12문항)** | **48(9문항)** |

- **재판정 방식.**
  - rejected 응답 본문을 HF-E와 같은 운영 경로에 넣었다(정규화, 조건 계층, compose, validate, mock·legacy). 모델은 부르지 않았다.
  - 운영 경로가 두 번째 호출을 요청한 경우는 둘로 나눴다.
    - 장소 조회 재질의(mock이 합성 장소명을 모름): 이미 검증을 지난 grounding으로 판정했다.
    - 계약 재질의: 첫 응답이 운영 경로에서 실패한 것이므로 "다름"으로 남겼다.
  - 남긴 54쌍의 이유:
    - 최종 grounding 없음 28(INVALID_CONCEPT 16, VALUELESS_CONCEPT 12, 재질의 없이 멈춤).
    - 최종 grounding이 gold와 다름 14.
    - 계약 재질의 12.
  - gold를 같은 경로에 넣으면 train·valid 35문항 모두 gold와 같은 grounding이 나왔다.
- **thinking_prep_001 "조건 계층 후 일치" 표시와 비교.**
  - 표시가 True였던 130쌍 중 16쌍은 운영 경로에서도 달랐다.
  - 표시가 False였던 69쌍 중 21쌍은 운영 경로에서 고쳐졌다(정규화와 조건 계층의 조합).
- **최종 데이터.**
  - SFT: greedy 2, 표본 38.
  - DPO: constraint 38, semantic 10.
  - 남은 표시: `compile_stop:UNVERIFIED_TIMS_CONTRACT`가 SFT 19, DPO 25(결정 7로 포함).
  - v003의 다른 DPO 표시(`t2pc_rejected_equals_chosen` 20, `t2pc_constraint_rejected_passes_contract` 8)는 재판정에서 모두 빠졌다.
- **길이**(`data/token_lengths_*.json`): 한도를 넘는 레코드는 없다.
  - SFT total 최대 9,133 / 9,216.
  - DPO prompt 7,314 / 7,424, chosen 1,593·rejected 1,270 / 1,920, total 8,898 / 9,216.
- **산출물.** `training/generated/thinking_v003_t2pc_pilot/`(ignored). sha256: sft 98fe815a…, dpo 26f61ea0…, manifest d6c1bb74….

## 3. 학습 기록(GPU 2)

설정은 thor pilot_003 profile이다(`PLAN.md`). 두 단계 모두 warmup 1 step이라 첫 step의 learning rate가 0이다. 실제 갱신은 SFT 11 step, DPO 7 step이다.

**SFT**(`train_logs/sft.log`, `sft_profile.json`)
- 12 step. 6.19초/step, 총 87.7초(model load 4.3초). epoch 0.3(40레코드 중 12개).
- loss(step 1–12): 0.119, 0.148, 0.100, 0.151, 0.112, 0.090, 0.138, 0.122, 0.118, 0.129, 0.103, 0.143. mean token accuracy 0.94–0.97.
  - 학습 데이터가 base 모델 자신의 생성 원문이라 처음부터 loss가 낮다. 레코드마다 오르내리며 추세는 보이지 않는다.
- 메모리: torch max allocated 33.92 GiB, max reserved 46.24 GiB, **nvidia-smi peak 47,882 MiB**.

**DPO**(`train_logs/dpo.log`, `dpo_profile.json`)
- reference: 고른 SFT checkpoint-4 adapter. 48쌍의 reference log-prob을 학습 전에 계산했다(3분 42초, 4.63초/쌍).
  - 학습 뒤 "Fixed SFT reference hash verified".
  - 모든 DPO checkpoint의 reference adapter sha256이 SFT checkpoint-4와 같다(2e1aa5d6…).
- 8 step. 17.59초/step, 총 376.7초(precompute 포함).

| step | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| loss | 0.693 | 0.693 | 0.691 | 0.710 | 0.625 | 0.548 | 0.839 | 0.740 |
| reward margin | 0.000 | 0.000 | 0.004 | −0.033 | 0.142 | 0.314 | −0.272 | −0.092 |
| accuracy(1쌍) | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 |

batch 1이므로 step마다 다른 쌍 하나의 값이다. 추세로 읽지 않는다.

**메모리와 결정 9**(`memory_compare/`, `train_logs/*_nvidia_smi.txt`)

| 측정 | reference | 레코드 | torch allocated / reserved | nvidia-smi peak | step 시간 |
|---|---|---|---|---|---|
| thinking_prep_001 probe(3 step, LR 0) | shared_adapter | 가장 긴 쌍(7,281 / 1,851 / 918) | 42.12 / 46.55 GiB | 48,200 MiB | 23.3초 |
| 이번 probe(같은 레코드, GPU 3) | precompute | 같음 | 35.00 / 43.34 GiB | 44,914 MiB | 18.7초 |
| 본 DPO 학습(48쌍 중 8 step) | precompute | 여러 길이 | 33.0 / 45.76 GiB | 47,386 MiB | 17.6초 |
| (참고) 본 SFT 학습 | — | 여러 길이 | 33.92 / 46.24 GiB | 47,882 MiB | 6.2초 |

- 같은 레코드에서 precompute는 실제 tensor 사용량을 7.1 GiB 줄였다. nvidia-smi peak는 3,286 MiB 줄었고, 여유는 940 → 4,226 MiB가 됐다.
- **본 학습에서는 여유가 다시 1.3–1.8GB로 줄었다.**
  - 실제 tensor peak(33–34 GiB)는 probe보다 낮다.
  - 그러나 길이가 다른 레코드를 차례로 처리하면서 PyTorch caching allocator가 잡아 둔 메모리(reserved)가 46 GiB까지 늘었다.
  - 한 레코드를 반복하는 짧은 probe는 이 효과를 재지 못한다. SFT도 같은 현상이다(probe 39,982 → 본 학습 47,882MiB).
  - OOM은 없었다. allocator가 비운 뒤 다시 잡을 수 있는 부분이라 바로 OOM 위험을 뜻하지는 않지만, nvidia-smi 기준 여유는 작다.

## 4. valid 결과(HF-E 조건, GPU 2, `valid/`)

| 셀 | adapter sha256 | grounding_ok | 첫 응답 raw 일치 | 모델 호출 | 장소 재질의 / 기타 재질의 | 시간 |
|---|---|---:|---:|---:|---|---:|
| base | — | **11** | 6 | 21 | 3 / 2 | 504초 |
| SFT step 2 | 3c6214f4… | 11 | 8 | 21 | 2 / 3 | 622초 |
| **SFT step 4(선택)** | 2e1aa5d6… | **13** | 9 | 20 | 2 / 2 | 589초 |
| SFT step 6 | e5b3e862… | 11 | 8 | 23 | 3 / 4 | 636초 |
| SFT step 8 | 7d097399… | 12 | 10 | 19 | 2 / 1 | 579초 |
| SFT step 10 | cad1a2fd… | 13 | 8 | 19 | 2 / 1 | 592초 |
| SFT step 12 | a0d378d8… | 11 | 8 | 21 | 1 / 4 | 647초 |
| DPO step 2 | b5b3c721… | 11 | 8 | 23 | 2 / 5 | 647초 |
| DPO step 4 | b316abfe… | 10 | 9 | 20 | 3 / 1 | 590초 |
| **DPO step 6(선택)** | 1a843daa… | **12** | 9 | 20 | 1 / 3 | 603초 |
| DPO step 8 | 813d11a8… | 11 | 10 | 21 | 2 / 3 | 695초 |

- 모든 셀이 같은 조건이다: GPU-a644de12, prompt 87048d0c, 지문 791c4a68, 생성 상한에 걸린 호출 0, 평가 peak allocated 17.2–18.1 GiB.
- **선택**(`selection_*.json`).
  - SFT: step 4와 10이 13으로 동점이라 더 이른 step 4를 골랐다.
  - DPO: step 6(12) 단독 최고.
  - 경로: `/home/hwkim/sftdpo_work/pipeline_pilot_001/checkpoints/{sft/checkpoint-4, dpo/checkpoint-6/policy}`(저장소 밖, 커밋하지 않음).

**문항 단위**(O = grounding_ok). 칸 순서: base, SFT 2·4·6·8·10·12, DPO 2·4·6·8.

| 문항 | 11셀 | base | SFT step 4 | DPO step 6 |
|---|---|---|---|---|
| 9d8392a4 | OOOOOOO..OO | O 정지(UNVERIFIED) | O 정지 | O 정지 |
| 0e4edbda | ..O.OO.O... | X INVALID_CONCEPT | **O** 답변 | X 답변(dimension_target) |
| 0d51b49a | OOOOOOOOOOO | O 답변 | O | O |
| 2d254560 | OOOOOOOOOOO | O 답변 | O | O |
| 4cafcbdd | ........... | X 장소(가람구→가람, 재질의) | X 같음 | X 같음 |
| 56366f54 | OOOOOOOOOOO | O 정지 | O | O |
| 5c88583c | OOOOOOOOOOO | O 정지 | O | O |
| fb7938d6 | O.OOOOOOOO. | O 정지 | O | O |
| f2cd5753 | OOOOOOOOOOO | O 정지 | O | O |
| 0d74b317 | OOOOOOOOOOO | O 정지 | O | O |
| 206f99f9 | OOOOOOOOOOO | O 정지 | O | O |
| dbfd9d05 | OOO....O.O. | O 장소 조회 실패 | O | O |
| dd838f31 | ........... | X 장소(해온시→해온, 재질의) | X PLACE_NOT_IN_QUESTION | X PLACE_NOT_IN_QUESTION |
| 7fae41a3 | .....OO..OO | X aggregation_spec | X 장소(해온시→해온) | **O** |
| 3584f62a | OOOOOO..O.O | O 정지 | O 정지 | **X** UNCONSUMED_CONDITION(places, taxi_type) |
| 29dcb56f | .OOOOOOOOOO | X INVALID_CONCEPT | **O** 정지 | O 정지 |

| 전이 | O→O | O→X | X→O | X→X |
|---|---:|---:|---:|---:|
| base → SFT step 4 | 11 | 0 | 2(0e4edbda, 29dcb56f) | 3 |
| SFT step 4 → DPO step 6 | 11 | 2(0e4edbda, 3584f62a) | 1(7fae41a3) | 2 |

- 같은 학습 안의 checkpoint 사이에서도 0e4edbda, 7fae41a3, 3584f62a, dbfd9d05가 O/X를 오간다.
- 16문항 중 9문항은 gold도 compile에서 멈추는(`UNVERIFIED_TIMS_CONTRACT`) 문항이다. 이 문항은 grounding만 비교했다.

## 5. 파이프라인에서 막히거나 고친 부분

1. **mock provider와 합성 장소명(평가 왜곡, 고치지 않음).**
   - valid의 합성 장소(가람구, 해온시, 솔빛시)는 mock provider가 모른다. 조회가 실패하면 운영 경로대로 모델에 장소 재질의가 간다.
   - 재질의 지시("시/군/구/동 접미사를 떼어 다시 시도")에 따라 모델이 맞던 장소명을 "가람", "해온"으로 바꾸고, 최종 grounding은 gold와 달라진다.
   - 4cafcbdd는 11셀 모두 첫 응답이 맞았는데 이 경로로 X가 됐다.
   - 같은 이유로 X가 된 경우가 더 있다: SFT step 8의 7fae41a3, DPO step 4·8의 dbfd9d05(첫 응답이 맞은 경우만 셈).
   - 장소 재질의만으로 생긴 차이는 `valid/place_repair_only_mismatch.json`에 있다.
   - 진단 목적으로만 이 경우를 빼고 다시 세어 보면 두 선택(SFT step 4, DPO step 6)은 바뀌지 않는다. 선택 규칙과 결과는 기록대로 둔다.
   - 다음 평가 전에 정할 일(고르지 않음):
     - (a) 합성 장소를 아는 provider(reference는 가람구·나래구만 안다)를 쓴다.
     - (b) 장소 재질의 전 grounding도 함께 채점한다.
     - (c) valid를 mock이 아는 장소의 문항으로 만든다.
   - 같은 원인을 DPO 재판정에서는 장소 재질의를 grounding으로 판정해 처리했다(2절).
2. **메모리 측정 방법.** 짧은 단일 레코드 probe는 실제 학습의 reserved 증가를 재지 못했다(3절).
   - 다음 학습 전 선택지(측정하지 않음): `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, 실제 데이터 순서로 몇 step을 도는 probe.
3. **trainer 평가 꺼짐.** thinking valid 레코드가 없어(trace를 train split만 수집) valid split이 비어 있다. trainer의 eval loss는 없고 checkpoint 선택은 생성 평가로만 했다(계획대로).
4. **DPO checkpoint 형식.** DPO checkpoint는 adapter가 `policy/`·`reference/` 아래에 저장된다. `eval_valid.py`가 `policy/`를 고르도록 처음부터 만들었고, 그대로 동작했다.
5. **실행 실패 1회(측정 전).** GPU 3 메모리 비교 측정의 첫 실행이 로그 폴더(`memory_compare/`)가 없어 shell redirect 단계에서 끝났다. Python은 시작하지 않았다. 폴더를 만들고 처음으로 실행했다(`gpu3_check.txt`).
6. **GPU 확인**(`gpu_check.txt`, `gpu3_check.txt`).
   - torch `CUDA_VISIBLE_DEVICES=2` = GPU-a644de12(PCI 0xAB, host GPU 2). Ollama 컨테이너 = GPU-48f798cc(host GPU 3).
   - 이번에는 컨테이너 안 `nvidia-smi -L`이 성공해 UUID로 직접 확인했다(이전 NVML 오류가 해소된 것으로 보임).
   - GPU 3은 쓰기 전 host `nvidia-smi`로 2 MiB, 프로세스 없음을 두 번 확인했다.
   - Ollama API는 부르지 않았다.

## 6. 진짜 pilot 전에 남은 일

1. **batch004 검토와 import.** 검토 시트(`sft_dpo_inventory/batch004/`)를 사람이 결정하고, 승인분만 import해 corpus를 다시 만든다. 그 뒤 thinking trace를 다시 수집한다.
2. **추론 표본 10개 검토.** `thinking_prep_001/traces/summary.json`의 seed 7 표본이다. 모델이 쓴 추론 문장은 아직 아무도 읽지 않았다.
3. **정답 표본이 없는 7문항의 처리.** 표본 수 증가, teacher 모델, thinking SFT 제외 중에서 고른다.
4. **Ollama NVML 확인과 `ollama create` 승인.**
   - 컨테이너 `nvidia-smi -L`이 이번에는 성공했다. 사용자가 해소를 확인하면 Ollama 호출 금지(`CLAUDE.md` 5번)를 풀지 정할 수 있다.
   - 그 뒤 HF 형식(결정 5) TEMPLATE으로 등록할지 승인이 필요하다.
5. **업체 100을 한 번만 평가하는 절차.** 학습 쪽 valid로 checkpoint를 고정한 뒤 업체 100을 한 번만 잰다.
   - HF: HF-E 대 adapter.
   - Ollama: E 대 등록 모델.
   - 고정 순서와 기록 형식은 측정 전에 문서로 정한다. 결과를 보고 checkpoint를 바꾸지 않는다.
6. **평가 세트의 합성 장소 문제(5절 1).** valid 채점 방식을 정한다. 지금 방식은 16문항 중 1–3문항을 모델과 무관하게 X로 만든다.
7. **메모리 여유(5절 2).** 실제 데이터 순서로 메모리를 다시 잴지, allocator 설정을 바꿀지 정한다. batch004 trace가 더 길면 여유가 더 줄어든다.
8. **validation 크기.** 16문항으로는 checkpoint 사이 1–2문항 차이를 가를 수 없다. 진짜 pilot의 선택용 valid를 몇 문항으로 할지 정한다.

## 7. 산출물

| 경로 | 내용 |
|---|---|
| `PLAN.md`, `../DECISIONS.md` | 고정 계획, 결정 |
| `build_pilot_data.py`, `data/` | 데이터 생성·재판정(요약, 거른 후보, 쌍별 재판정, 길이) |
| `eval_valid.py`, `select_checkpoint.py`, `run_pilot.sh`, `runs.log` | 평가·선택·실행 기록 |
| `valid/` | 11셀 결과(원문 sha256만), 실행 로그, 장소 재질의 진단 |
| `selection_sft.json`, `selection_dpo.json`, `resolved/` | 선택 결과, adapter 경로를 채운 DPO config |
| `train_logs/` | SFT·DPO 로그, profile, nvidia-smi 표본 |
| `memory_probe_precompute.py`, `memory_compare/` | 결정 9 같은 레코드 비교 |
| `summarize.py`, `summary.json` | 셀·전이·문항·학습 기록 요약 |
| `gpu_check.txt`, `gpu3_check.txt` | GPU 확인 |
| `training/configs/qwen3_8b_t2pc_thinking_pilot_{sft,dpo}.yaml` | pilot config |

저장소 밖·ignored(커밋하지 않음):

- `/home/hwkim/sftdpo_work/pipeline_pilot_001/`(checkpoint·adapter·profile, 6.4GB). sha256은 4절 표와 `summary.json`.
- `training/generated/thinking_v003_t2pc_pilot/`(학습 데이터).
- `training/generated/pipeline_pilot_001/`(평가 원문).
- 메모리 비교 측정의 임시 adapter는 지웠다.
