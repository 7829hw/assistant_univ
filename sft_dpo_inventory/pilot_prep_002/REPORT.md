# 진짜 pilot 전 준비 (pilot_prep_002)

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`. 결정 11·12는 `../DECISIONS.md`에 있다(`49782e1`).

- 하지 않은 것: 업체 100 사용, Ollama 호출, `ollama create`, prompt 변경, SEMANTIC_CODE 변경, 학습 설정 탐색.
- 다시 학습한 것: 메모리 확인용 학습만(2절, 평가 없음, adapter 삭제).
- 고치지 않은 것: `pipeline_pilot_001` 결과, 기존 라벨·검토 시트.
- 실행 의미 코드 지문은 작업 시작과 끝 모두 `791c4a68`이다.

## 0. 요약

1. **valid 채점 왜곡: 일부만 고쳐졌다.**
   - 결정 11의 provider 선택을 평가 경로에 넣고, 11셀을 기록된 첫 응답으로 다시 채점했다(모델 호출 0).
   - 모든 셀이 +1이다. 4cafcbdd(가람구)가 reference로 풀려 X→O가 됐다. `needs_live`는 0이다.
   - 선택은 바뀌지 않는다(SFT step 4, DPO step 6).
   - **남은 왜곡:** 솔빛시·해온시 문항 3개(dbfd9d05, dd838f31, 7fae41a3)는 어느 provider도 모른다. 이 문항들은 여전히 mock 장소 재질의로 왜곡될 수 있다.
2. **메모리: expandable_segments로 nvidia-smi peak가 크게 줄었다.**
   - SFT 47,882 → 38,696MiB, DPO 47,386 → 35,128MiB.
   - 실제 tensor 사용(max allocated)과 step 시간은 그대로다.
   - step별 loss는 SFT 최대 0.003, DPO 최대 0.10 달랐다. 원인은 정하지 못했다(2.3).
   - 추정 최대 길이: SFT total 약 12,900–13,700, DPO 문장당 약 13,800–14,200 token.
3. **valid 제안**(채택 안 함): (a) 16, (b) batch004 일부, (c) 보호 개발 셋 stage_v7·heldout_v8·heldout_v9.
   - pilot의 같은 학습 안 checkpoint 쌍 불일치율로 보면, 16문항에서는 평균적인 차이를 우연과 구분할 수 없다.
4. **업체 100 절차 초안:** `../vendor100_protocol/PROTOCOL.md`.
   - Ollama E(79)는 이전 코드 지문(97efa866)에서 잰 값이다. 운영 비교 전에 현재 코드로 한 번 다시 재야 한다는 점을 적었다.

## 1. valid 채점 왜곡 수정

### 1.1 provider 분류

- 표: `provider/provider_classification.md`, 상세: `.json`.
- 방법: gold(batch004는 초안) grounding의 장소를 pipeline과 같은 인자로 조회했다(`get_place_scope(name, region, include_vicinity)`).
  - mock: `mock_get_place_scope`, fixture 37개 이름.
  - reference: `ReferenceProvider.place_scope`. 가람구·나래구만 안다.
  - literal scope(`scope:edge:2607` 등)는 조회하지 않는다.

| 출처 | 문항 | 조회 없음 | mock | reference만 | 둘 다 안 됨 |
|---|---:|---:|---:|---:|---:|
| v003_t2pc train | 19 | 2 | 5 | 4(가람구·나래구) | 8(솔빛동·솔빛시·해온시·하늘구·하늘동) |
| v003_t2pc valid | 16 | 4 | 1 | 1(4cafcbdd 가람구) | 10(솔빛시·해온시 3, 하늘구·하늘동 7) |
| batch004 후보 | 18 | 8 | 3 | 0 | **7**(부산 강서구, 성남 판교역, 대전역, 서울 강남역) |

**둘 다 안 풀리는 문항(보고만 한다. gold·질문은 고치지 않았다).**

- **v003 valid 10.**
  - 하늘구·하늘동 7개는 mock 경로에서 compile 정지(UNVERIFIED_TIMS_CONTRACT)가 장소 조회보다 먼저 일어난다. 그래서 채점에는 영향이 없었다.
  - **솔빛시·해온시 3개(dbfd9d05, dd838f31, 7fae41a3)는 장소 조회까지 가서 왜곡이 남는다.**
  - pilot 11셀 가운데 이 3문항이 장소 재질의 뒤 places만 gold와 달라 X가 된 셀이 8개다(`pipeline_pilot_001/valid/place_repair_only_mismatch.json`).
  - 그중 첫 응답이 맞았던 경우는 3건이다(SFT step 8의 7fae41a3, DPO step 4·8의 dbfd9d05). 나머지는 첫 응답도 틀렸던 경우다.
- **v003 train 8.** 학습에는 영향이 없다(trace 판정은 원 JSON 비교). DPO 운영 재판정에서는 장소 재질의를 grounding으로 판정했다.
- **batch004 7.** 실제 지명이지만 mock fixture에 없다. valid로 쓰면(3절 b) 같은 왜곡이 생긴다.

### 1.2 평가 경로

- `valid_eval/eval_valid_v2.py`: `pipeline_pilot_001/eval_valid.py`에서 provider 선택만 바꿨다.
- 공통 구성: `valid_eval/provider_eval.py`.
  - reference: `ToolExecutor(handlers=reference, provider=reference)` + `profile_for(REFERENCE)`.
  - mock: 기존과 같음.
  - pipeline 구성과 채점 코드는 같다.
- 문항마다 `provider`, `provider_class`를 결과에 남긴다.
- CPU에서 gold를 넣어 확인했다(fake client): 16/16 grounding_ok, 4cafcbdd만 reference(UNSUPPORTED_BY_PROVIDER로 정지).

### 1.3 pilot 11셀 다시 채점(`valid_rescore/rescore.json`, `valid_eval/rescore.py`)

- 기록된 첫 응답을 새 경로에 다시 넣었다. 두 번째 모델 호출이 필요한 문항은 부르지 않고 `needs_live`로 표시해 세기로 했다. 해당 문항은 없었다.
- **재적용 검증.** provider가 mock인 문항 중 첫 응답만으로 끝났던 124건을 다시 돌렸다. 기존 판정·결과 종류와 124/124 같았다.

| 셀 | 기존 | 새 점수 | needs_live | 바뀐 문항 |
|---|---:|---:|---:|---|
| base | 11 | 12 | 0 | 4cafcbdd X→O |
| SFT step 2 / 4 / 6 / 8 / 10 / 12 | 11 / 13 / 11 / 12 / 13 / 11 | 12 / 14 / 12 / 13 / 14 / 12 | 0 | 각 셀 4cafcbdd X→O |
| DPO step 2 / 4 / 6 / 8 | 11 / 10 / 12 / 11 | 12 / 11 / 13 / 12 | 0 | 각 셀 4cafcbdd X→O |

- 4cafcbdd는 모든 셀에서 첫 응답이 "가람구"를 맞게 썼다. reference에서는 장소가 풀리고 RPM 도구가 지원되지 않아 정지했으며, grounding이 gold와 같다.
- **선택 규칙을 새 점수에 적용해도** SFT step 4(step 10과 동점, 이른 쪽), DPO step 6이다. 고른 checkpoint는 바꾸지 않았다.

## 2. 메모리 대책(결정 12)

### 2.1 실행

- GPU 2, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(`memory/`).
- GPU 확인: 컨테이너 `nvidia-smi -L` = GPU-48f798cc, torch = GPU-a644de12, GPU 2 사용 2MiB(`memory/gpu_check.txt`).
- GPU 3은 쓰지 않았다(GPU 2로 충분).
- `pipeline_pilot_001`과 같은 데이터·순서·seed·설정이다. config 사본에서 바꾼 것은 출력 경로뿐이다(`config_diff_*.txt`).
  - SFT 12 step.
  - DPO 8 step: reference 미리 계산, pilot DPO와 같은 시작 adapter인 pilot SFT checkpoint-4(2e1aa5d6…).
- 평가는 하지 않았다. 임시 checkpoint는 지웠고, sha256만 남겼다(`*_adapter_sha256.txt`).

### 2.2 비교

| | 본 학습(pilot) | expandable_segments | 차이 |
|---|---|---|---|
| SFT nvidia-smi peak | 47,882 MiB | **38,696 MiB** | −9,186 |
| SFT torch max allocated / reserved | 33.92 / 46.24 GiB | 33.92 / 37.27 GiB | allocated 같음 |
| SFT step 시간 | 6.19초 | 5.76초 | |
| DPO nvidia-smi peak | 47,386 MiB | **35,128 MiB** | −12,258 |
| DPO torch max allocated / reserved | 33.00 / 45.76 GiB | 32.99 / 33.79 GiB | allocated 같음 |
| DPO step 시간(precompute 제외) | 17.59초 | 17.55초 | |
| DPO reference 미리 계산 | 3분 42초 | 3분 45초 | |

- 여유(49,140MiB 기준): SFT 1.3 → 10.4GB, DPO 1.8 → 14.0GB.

### 2.3 loss

- **SFT:** step 1–2는 같다. 이후 차이는 최대 0.0031(step 8: 0.1216 → 0.1185). 최종 adapter sha256이 다르다.
- **DPO:** step 1–2(0.6931)는 같다. 이후 차이는 최대 0.101(step 7: 0.8386 → 0.9395).
  - reward margin도 다르다. step 3: 0.004 → 0.093, step 8: −0.092 → 0.055.
  - batch 1 DPO의 margin은 작아서 작은 수치 차이에도 loss가 크게 움직인다.
- **원인은 정하지 못했다.** pilot 설정(expandable_segments 끔)을 두 번 돌린 적이 없다. 그래서 allocator 설정의 영향인지, GPU 연산의 비결정성인지 구분할 수 없다.
  - 그 구분이 필요하면 같은 설정을 두 번 돌려 비교하는 측정이 하나 더 필요하다. 하지 않았다.

### 2.4 batch004 trace가 더해졌을 때의 최대 길이(추정, `memory/length_estimate.json`)

계산식(길이에 선형이라고 가정):

```
L_max = L_meas + (budget − peak_meas) / k
budget = 49,140 − 1,024(안전 여유) = 48,116 MiB
k(A, 보수적) = (peak_meas − base) / L_meas
k(B)         = (allocated_meas − base) / L_meas
```

| 단계 | 측정점 | 추정 최대 길이 | prompt 7,314일 때의 응답(thinking+JSON) 최대 |
|---|---|---|---|
| SFT | 9,132 token, nvidia 38,696MiB, base 15,789MiB | total **12,887(A) – 13,673(B)** | 약 5,570 – 6,360 |
| DPO | 가장 긴 쌍(문장당 9,132 패딩)을 precompute probe allocated(35.00 GiB) + expandable 본 학습의 slack·context로 환산: nvidia 약 37,186MiB, base 15,956MiB | 문장당(prompt + max(chosen, rejected)) **13,833(A) – 14,152(B)** | 약 6,520 – 6,840 |

- **추정의 한계.**
  - 9,133 token을 넘는 길이는 재지 않았다.
  - DPO 측정점은 두 측정(expandable 없이 잰 가장 긴 쌍 + expandable 본 학습의 slack)을 합친 값이다.
- **참고.**
  - HF-E 생성 길이는 중앙값 767, 최대 8,192 token이다(상한 도달 1문항).
  - 지금 config 한도(SFT 9,216, DPO 9,216 / 7,424 / 1,920)는 응답 약 1,900 token까지만 받는다. batch004 trace가 길면 한도를 올려야 한다. 그것은 학습 설정 변경이라 사용자 결정이다.

## 3. 진짜 pilot의 checkpoint 선택용 valid 제안(채택 안 함)

출처: `valid_proposal/valid_options.json`. 학습 데이터 = v003_t2pc train 19 + batch004 후보 18.

- 겹침 기준:
  - 질문 겹침: 정규화 질문이 같음.
  - family 겹침: thor `family_key`와 같은 거친 의미 기준(측정값·OD·집계/그룹 factor)이 같음.

| | (a) v003_t2pc valid | (b) batch004 승인분 일부 | (c1) stage_v7 | (c2) heldout_v8 | (c3) heldout_v9 |
|---|---|---|---|---|---|
| 문항 | 16 | 계약 통과 후보 14 중 일부(전체 18, 4개는 target 결정 대기) | 16(다른 셋과 중복 1, 고유 15) | 40 | 48 |
| 출처 | reviewed gold v001–v003 | batch004 후보(Claude 초안) | grounding_v7 대조 셋 | grounding_v8 held-out | grounding_v9 held-out |
| 사람 검토 | 있음(hwkim 확정·import 승인) | 검토 대기 | 없음(Claude 작성, 기대 결과 사전 고정) | 없음(하위 에이전트 작성) | 없음(하위 에이전트 작성) |
| 학습과 질문 겹침 | 0 | 0 | 0 | 0 | 0 |
| 학습과 family 겹침(거친 의미) | 0 | 2(v003 train과) | 0 | 4 | 2 |
| provider | mock 1, reference 1, 조회 없음 4, 둘 다 안 됨 10 | 조회 없음 6, mock 1, 둘 다 안 됨 7 | mock 11, 조회 없음 5 | mock 35, 조회 없음 5 | mock 36, 조회 없음 9, gold 없음 3 |
| 정책·모호 제외 | 감사 대상 아님 | 검토에서 정함 | 0(v13 감사 대상 아님 = 감사되지 않음) | 0(같음) | 0(같음) |
| 제외 뒤 규모 | 16(이 중 3문항은 mock 왜곡 남음) | 승인분 중 배정한 수 | 15 | 40 | 45(gold 없음 3 제외) |
| 조건 | 학습 질문과 같은 주제 분포 | valid로 보낸 만큼 학습이 준다(family 단위로 나눠야 함). 7개는 mock이 장소를 모름 | **학습에 계속 쓰지 않는다.** 보호 정책은 학습 입력만 막으므로 선택 전용으로는 쓸 수 있다 | 같음 | 같음 |

- **(c)를 쓸 때의 조건.**
  - 그 셋을 학습 입력·annotation 후보로 계속 쓰지 않는다.
  - 선택에 쓴 뒤에는 그 셋을 최종 평가로 내세우지 않는다.
  - v8·v9는 과거 prompt 후보 선택에 쓰였다. 새 held-out이 아니라 기존 기록이다.
  - c1+c2+c3 = 100문항(정책 제외 0, gold 없음 3 제외). mock으로 장소가 모두 풀리거나 조회가 없다.

**검정력**(같은 셋에서 checkpoint 둘 비교, McNemar 정확 검정 양측 0.05)

- pilot의 같은 학습 안 checkpoint 쌍 21개에서 관측한 문항 불일치율: 평균 17%, 최대 37.5%. base 대 checkpoint는 평균 19%.
- 불일치가 6문항 미만이면 어떤 차이도 유의하지 않다.

| 문항 수 | 불일치(평균 17%) | 유의한 최소 순차이 | 불일치(최대 37.5%) | 유의한 최소 순차이 | checkpoint 하나 평가(30초/문항) | (관측 38초/문항) |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 3 | 불가 | 6 | 6(전부 한쪽) | 8분 | 10분 |
| 30 | 5 | 불가 | 11 | 9 | 15분 | 19분 |
| 45 | 8 | 8 | 17 | 9 | 23분 | 29분 |
| 60 | 10 | 8 | 22 | 12 | 30분 | 38분 |
| 100 | 17 | 9 | 38 | 14 | 50분 | 64분 |

- 이 계산은 checkpoint 사이의 불일치가 pilot과 비슷하다는 가정에 기댄다. pilot은 16문항이라 불일치율 추정 자체가 거칠다.
- 평가 시간은 checkpoint 수에 비례한다. pilot 구성(SFT 6 + DPO 4)이면 100문항일 때 약 8.3–10.6시간이다.

## 4. 업체 100 한 번 평가 절차 초안

`../vendor100_protocol/PROTOCOL.md`(**초안, 사용자 확인 전**). 담은 것:

- 평가 시점: checkpoint 고정·커밋 뒤, 문서 확정 뒤. 운영 셀은 Ollama 해제·`ollama create` 승인 뒤.
- 셀:
  - 학습 효과: HF-E(84) 대 adapter.
  - 운영: Ollama E 대 등록 모델.
  - **기준값 재사용 조건:** 실행 명세가 같아야 한다. E(79)는 지문 97efa866에서 쟀으므로 현재 코드로 한 번 다시 재야 한다.
- 실행 조건: 기준일 2026-09-25, max_new_tokens 8192, mock·legacy, 조건 계층 켬, GPU 배정, 명세 기록.
- 재실행 금지. 예외는 기반 장애뿐이고, 이어 재기·이탈 기록 절차를 적었다.
- 쌍 비교와 McNemar, U1–U4와 조용한 오답의 분리 판정.
  - 참고값: HF-E 대 E(84 대 79, b 11 c 6)는 p = 0.33이다.
- 해석 규칙(개선·차이 없음·악화)과, 사용자가 정할 값 7개를 빈칸과 선택지로 두었다.

## 5. 진짜 pilot 전에 남은 일

**사용자**

1. batch004 검토(검토 시트 55항목). 지원 불가 target 형식 결정 4건(b004-34·35·40·41) 포함.
2. 추론 표본 10개 검토(`thinking_prep_001/traces/summary.json` seed 7).
3. 정답 표본이 없는 7문항의 처리.
4. checkpoint 선택용 valid 선택(3절 a/b/c 또는 조합)과 크기.
5. 솔빛시·해온시 3문항의 채점 방식(1.1).
   - 선택지: valid에서 제외, 장소 재질의 전 grounding으로 채점, 평가 전용 gazetteer 추가.
   - 평가 전용 gazetteer는 SEMANTIC_CODE 밖이어야 한다.
   - batch004를 valid로 쓰면 그 7문항도 같은 문제다.
6. 학습 한도 상향 여부(batch004 trace 길이를 본 뒤, 2.4).
7. `PROTOCOL.md` 확인과 빈칸 결정.
8. Ollama 금지 해제(컨테이너 NVML 확인. 이번 두 작업에서 `nvidia-smi -L`은 성공했다)와 `ollama create` 승인.
9. expandable_segments를 학습 기본 환경으로 쓸지 결정. loss 차이의 원인을 가리려면 반복 측정 1회가 필요하다(2.3).

**Claude Code**(사용자 결정 뒤)

1. batch004 승인분 import와 v004 corpus 생성. 승인분만 쓰고, valid 배정은 사용자 결정대로 family 단위로 한다.
2. 새 corpus 학습 split의 thinking trace 수집(greedy 1 + 표본 8), 후보·DPO 쌍 생성(결정 4·6·7·8 적용), 길이 측정.
3. 정한 valid로 평가 경로 준비(`eval_valid_v2.py`, 필요하면 보호 셋 읽기 경로 추가). 기대 결과는 실행 전에 고정한다.
4. 진짜 pilot의 PLAN.md 고정. 학습은 expandable_segments(결정 시)로 한다.
5. 학습 → checkpoint 평가 → 선택 → 고정·커밋.
6. 업체 100 한 번 평가: HF 셀, 그리고 승인 뒤 Ollama 셀. 프로토콜 확정판을 따른다.

## 6. 산출물

| 경로 | 내용 |
|---|---|
| `provider/classify_providers.py`, `provider_classification.{md,json}` | 문항별 provider 분류 |
| `valid_eval/provider_eval.py`, `eval_valid_v2.py`, `rescore.py` | provider 선택 평가 경로, 재채점 |
| `valid_rescore/rescore.json` | 11셀 기존·새 점수, 문항별 재적용 결과, 선택 비교 |
| `memory/` | 실행 스크립트, GPU 확인, 로그, profile, trainer_state, adapter sha256, 길이 추정 |
| `valid_proposal/propose_valid.py`, `valid_options.json` | valid 선택지 규모·겹침·검정력(보호 셋 질문 문장 없음) |
| `../vendor100_protocol/PROTOCOL.md` | 업체 100 절차 초안 |

메모리 확인 학습의 checkpoint는 지웠다(`/home/hwkim/sftdpo_work/pilot_prep_002_memcheck` 없음). pilot의 checkpoint(`/home/hwkim/sftdpo_work/pipeline_pilot_001/`)는 그대로다.
