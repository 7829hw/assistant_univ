# sampling 보정 실험 계획 (calibration_001) — 결정 64–67

작성·고정: 2026-10-09. **이 문서를 커밋한 뒤 측정을 시작하고, 그 뒤로는 고치지 않는다.** 계획과 다르게 된 것은 `PLAN_DEVIATIONS.md`에 따로 적는다.

## 0. 목적

pilot_002 진단(`pilot_002_diag/REPORT.md`)에서 greedy 한 번의 결과가 작은 조건 차이에도 크게 흔들렸다. 조건 하나만 바꿔도 21–31문항이 뒤바뀌어 학습 효과를 가릴 수 없었다. 이 실험은 다음을 확인한다.

1. 측정 잡음의 크기.
2. sampling으로 재도 HF와 Ollama의 차이가 남는지.
3. sampling 기준의 학습 효과와 양자화 효과.
4. PROTOCOL_v3 판정 규칙의 근거.

범위와 금지 사항:
- 학습하지 않는다. prompt `87048d0c`와 `SEMANTIC_CODE` 파일을 바꾸지 않는다(지문 `791c4a68…`).
- 업체 100과 aux_test_v1은 쓰지 않는다. 같은 셀을 greedy로 다시 재지 않는다(결정 64).
- 이 결과는 진단과 PROTOCOL_v3 선택지의 근거로만 쓴다. 학습 입력, checkpoint 선택, annotation 후보로 쓰지 않는다.

## 1. 문항 셋과 채점

- 문항 셋은 selection_v1 100문항이다(`conversion_diag/selection_gold.yaml`, sha256 `2ed1db62…`, 문항 순서 file).
- 결과는 두 기준으로 모두 낸다.
  - selection_v1(100문항).
  - selection_v2(98문항): n10과 k32를 뺀다(`selection_v2_items.json`, id 목록 sha256 `5b1d4d80…`, 결정 65).
- 채점은 최종 grounding을 `evaluate_vendor100.grounding_check`로 gold와 비교한다(지금 코드로 다시 채점).
  - 질문에 없는 aggregation 추가는 X다(결정 65, 현재 채점 규칙과 같음).
- U와 조용한 오답은 `baseline_conditions_001/compare_cells.py`의 분류를 쓴다. pilot_002·conversion_diag와 같은 코드다.
  - 함수: `axes_rows`, `grounding_v13/report.unacceptable`의 U1–U4, `report_class`.
  - HF 셀도 이번에는 `hf_eval_thinking.py`로 재서 기록 형식이 Ollama와 같으므로 U를 센다.

## 2. 셀(8개 × 문항마다 k = 4 표본)

| 순서 | 셀 | 경로 | 모델 | Ollama digest / adapter |
|---|---|---|---|---|
| 1 | HF-base | HF BF16, `hf_eval_thinking.py` | `Qwen/Qwen3-8B@b968826d` | – |
| 2 | HF-final | 같음 | base + pilot_002 최종 adapter(DPO step 144) | `/home/hwkim/sftdpo_work/pilot_002/checkpoints/dpo/checkpoint-144/policy`(adapter sha256 `60cf9ffe…`) |
| 3 | E | Ollama 0.35.1 | `qwen3:8b`(공식 Q4_K_M, 공식 TEMPLATE) | `500a1f06…` |
| 4 | c | Ollama | `geoflow-diag-qwen3-8b-official-hftmpl:q4km`(공식 가중치 + HF 형식 TEMPLATE) | `f83b28a9…` |
| 5 | B-conv | Ollama | `geoflow-qwen3-8b-b968826d-base:q4km-hfthink`(직접 변환 Q4_K_M) | `ab29de19…` |
| 6 | d | Ollama | `geoflow-diag-qwen3-8b-b968826d-base:q8_0-hfthink`(직접 변환 Q8_0) | `3c3843ae…` |
| 7 | Ollama-final | Ollama | `geoflow-qwen3-8b-pilot002-final:q4km-hfthink`(최종 Q4_K_M) | `c2d10cb2…` |
| 8 | e | Ollama | `geoflow-diag-qwen3-8b-pilot002-final:q8_0-hfthink`(최종 Q8_0) | `b608abf0…` |

- HF 셀을 먼저 재고 Ollama 셀을 잰다. 두 측정은 동시에 돌리지 않는다(CLAUDE.md 7번).
- 실행 스크립트는 `run_cal.sh`다. 표본 하나가 한 번의 실행(100문항)이고, 셀마다 표본 1–4를 차례로 잰다. 셀이 끝나면 커밋하고 push한다.
- 출력이 이미 있으면 멈춘다. 결과가 예상과 달라도 다시 재지 않는다.
  - 결정 55로 멈춘 표본은 원인이 해소되면 그 표본을 처음부터 다시 잴 수 있다. 다시 잰 사실과 이유는 `PLAN_DEVIATIONS.md`에 적는다.
  - 그 밖의 장애(crash, OOM)도 같은 방식으로 `PLAN_DEVIATIONS.md`에 적는다.

## 3. 생성 설정(두 경로 같게, 명시)

| 값 | HF(`generate` 인자) | Ollama(요청 `options`) |
|---|---|---|
| temperature | 0.6 | 0.6 |
| top_p | 0.95 | 0.95 |
| top_k | 20 | 20 |
| min_p | 0 | 0 |
| repeat / repetition penalty | `repetition_penalty=1` | `repeat_penalty: 1` |
| presence·frequency penalty | HF `generate`에 해당 인자가 없음. 적용되지 않으므로 0과 같다 | `presence_penalty: 0`, `frequency_penalty: 0` |
| seed | 호출마다 `torch.manual_seed`·`cuda.manual_seed_all` | 호출마다 `options.seed` |
| thinking | `enable_thinking=True` | think 미지정. 공식·HF 형식 TEMPLATE 모두 thinking 켬 |
| 생성 상한 | `max_new_tokens 8192` | `num_predict` 미지정(context 40960) |

- 그 밖의 조건은 각 경로의 기존 평가와 같다.
  - pipeline: flat 집계 grounding, 조건 계층(`--condition-check`) 켬, condition_notes 끔, 재질의 정책은 코드 기본.
  - provider mock, tims legacy, 기준일 2026-09-25.
  - Ollama는 문항마다 모델을 내린다(`OllamaStateReset`).
  - HF는 표본마다 새 프로세스를 띄우고, 모델을 올린 채 대화 상태 없이 문항을 돈다.
- 실제 적용 값의 확인:
  - Ollama:
    - 요청 options는 기록(`run_spec.options`, 호출별 `sampling_seed`)에 남는다.
    - 서버 로그에는 요청마다 `sampler params`(top_k, top_p, min_p, temp, penalties)가 찍힌다. 표본마다 그 줄을 세어 `runs/*_sampler_params.txt`에 남긴다.
    - Modelfile 파라미터는 `/api/show`로 확인한다(`model_runtime`).
  - HF: `meta.hf.decoding`에 generate 인자를 남긴다.
- HF 경로가 기존 selection 측정(`pilot_prep_005/sets/eval_set.py`)과 다른 점은 harness뿐이다.
  - pipeline 구성(`provider_eval.make_pipeline`)은 같은 인자다: flat, condition_check, condition_notes False, mock·legacy, 기준일 2026-09-25.
  - 이번에 `hf_eval_thinking.py`를 쓰는 이유는 기록 형식을 Ollama와 같게 해 U를 세기 위해서다.

## 4. seed 규칙(실행 전에 고정)

- 표본 번호 k = 1…4의 seed는 `S_k = 20261100 + k`(20261101–20261104)다.
- 호출 seed = `call_seed(S_k, 문항 id, c) = int.from_bytes(sha256(f"{S_k}:{id}:{c}").digest()[:4], "big") & 0x7FFFFFFF`
  - `evaluate_vendor100.SEED_RULE`, 커밋 `ce2235d`의 규칙이다.
  - c는 그 문항 안에서 모델을 부른 순번이다. 0은 첫 plan이고, 1부터는 재질의(장소 repair 등)를 부른 순서다. 실패한 호출도 순번을 쓴다.
  - 사용자 지시의 "호출 종류"는 이 순번으로 구분한다. 첫 plan은 늘 0번이고, 재질의는 그 뒤 순서로 번호가 붙는다.
- 두 경로가 같은 규칙을 쓴다. 다만 HF와 llama.cpp의 난수열은 달라, 같은 seed라도 표본끼리 짝지어지지 않는다. 비교 단위는 문항별 정답률이다.
- 같은 seed와 같은 셀의 표본 번호는 모든 셀에서 같다.

## 5. 재현성 확인(측정 전, `repro/`, 분석에 쓰지 않음)

- 대상: selection_v1의 5문항(old44/g02, contrast/c03c, indepv2/n06, indepv3/m09, indepv4/k08), seed `S_1`.
- 각 경로에서 두 번 생성한다. HF는 HF-base, Ollama는 E(`qwen3:8b`)다.
- 호출별 원문을 바이트 단위로 비교한다. HF는 `raw_text`, Ollama는 thinking과 content다.
- 결과는 6절에 적는다. 다르면 다른 정도를 적고 실험은 계속한다. 그때는 "seed 재현성 없음"을 결과 해석에 반영한다.

## 6. 재현성 결과(측정 전 확인)

2026-10-09 측정. 결과는 `repro/repro_compare.json`, 기록은 `repro/*.json`·`runs.log`에 있다.

| 경로 | 호출 바이트 일치 | 첫 plan 호출 일치 | 비고 |
|---|---|---|---|
| HF-base(GPU 3) | 8/8 | 5/5 | `meta.hf.decoding`: temperature 0.6, top_p 0.95, top_k 20, min_p 0.0, repetition_penalty 1.0, max_new_tokens 8192 |
| Ollama E(`qwen3:8b`, GPU 2) | 9/9 | 5/5 | 결정 55 확인 통과(100% GPU, 최저 98.4 tok/s) |

- 두 경로 모두 같은 seed에서 바이트 단위로 같은 출력이 나왔다. **seed 재현성이 있다.**
- Ollama에 실제로 적용된 값은 서버 로그의 `sampler params`로 확인했다. 9개 요청 모두 같다
  (`repro/ollama_E_{a,b}_sampler_params.txt`).
  - temp 0.600, top_k 20, top_p 0.950, min_p 0.000.
  - repeat_penalty 1.000, presence_penalty 0.000, frequency_penalty 0.000.
- 요청 options에도 같은 값이 들어갔다(`run_spec.options.sampling.extra_options`, 호출별 `sampling_seed`).

## 7. GPU와 결정 55

- HF: GPU 3에 다른 프로세스가 없으면 GPU 3을 쓰고, 있으면 Ollama 모델이 없는 GPU 2를 쓴다.
  - 시작 전에 nvidia-smi와 torch UUID를 확인한다(`run_cal.sh hf_gpu`).
  - HF 표본은 Ollama 모델이 내려간 상태에서 시작한다.
- Ollama: 모든 표본(셀의 각 실행)에 결정 55 확인을 붙인다(`pilot_002/ollama_gpu_guard.py`).
  - 시작 전: 컨테이너가 GPU 2를 보고, Ollama 0.35.1이고, 적재된 모델이 없는지 본다.
  - 첫 문항: 100% GPU인지 본다.
  - 모든 호출: 생성 속도가 30 tok/s 이상인지 본다(`pilot_002/PLAN_DEVIATIONS.md`, conversion_diag와 같은 기준).
  - 멈추면 출력을 `ABORTED_gpu_*`로 옮기고 멈춘다. 그 출력은 쓰지 않는다.
- 컨테이너는 옮기거나 재시작하지 않는다. 모델을 새로 등록하거나 지우지 않는다. 진단 모델 (c)·(d)·(e)는 남긴다(결정 67).

## 8. 기록(표본마다)

- 커밋하는 결과:
  - `runs/<셀>_s<k>.json`(Ollama는 `.jsonl`·`.spec.json`·guard·precheck·sampler_params도).
  - 문항별 최종 grounding, 결과 코드, 호출별 content·token 수·done_reason·seed·지연.
- 원문(thinking 포함): `training/generated/calibration_001/raw/<셀>_s<k>_raw.jsonl`(ignore 경로, 커밋하지 않음). 결과 meta에 sha256을 남긴다.
- 분석이 표본마다 만드는 것(`samples.jsonl`, 커밋):
  - grounding_ok, 결과 분류, U 종류(u_flags), 지연.
  - 생성 상한 도달(`done_reason == "length"`).
  - 루프(결정 40-D, `pilot_prep_004/loop_filter/apply_filter.py`의 `is_loop`, 원문 thinking 기준).
  - 오류 유형 4개(9.4절).

## 9. 분석(모델 호출 없음, `analyze.py` → `analysis.json`, `REPORT.md`)

모든 수치는 selection_v1(100)과 selection_v2(98) 두 기준으로 낸다. 난수는 numpy `default_rng(20261109)`이고, 계산마다 별도 stream을 쓴다.

### 9.1 문항별 지표

- 문항 i, 셀 X의 정답률 `p_Xi = (4표본 중 grounding_ok 수)/4`. U 비율 `u_Xi`, 조용한 오답 비율도 같은 방식으로 낸다.
- 셀 지표는 문항 평균(%)이다. 표본별 grounding_ok 개수(4개)의 평균·최소·최대도 함께 적는다.

### 9.2 측정 잡음

- 반쪽 차이: 같은 셀의 4표본을 두 쌍으로 나누는 세 가지 방법((1·2 | 3·4), (1·3 | 2·4), (1·4 | 2·3)) 각각에서, 두 반쪽(k = 2)의 셀 평균 차이를 낸다.
  - 잡음 분포는 세 나눔 × 문항 bootstrap 2,000회로 만든다. 문항 단위로 복원 추출하고 같은 추출을 두 반쪽에 쓴다.
  - 95% 구간과 표준편차를 셀마다 적는다.
- 한 번 측정(k = 1)끼리의 차이: 같은 셀의 표본 6쌍의 grounding_ok 개수 차이와 뒤바뀐 문항 수를 적는다. greedy 쌍의 21–31문항 뒤바뀜과 비교한다.
- 분산 성분:
  - 문항 안 표본 분산 `v_i = p_i(1−p_i)·k/(k−1)`(불편 추정).
  - k표본 셀 평균의 잡음 표준편차 `sd_k = sqrt(Σ_i v_i / k) / N`. 반쪽 차이의 실측 분포와 대조한다.
- greedy 위치: 기존 greedy 값을 셀의 sampling 분포에 둔다.
  - 기존 값: HF-base 82, HF-final 80, E 71, c 70, B-conv 69, d 70, Ollama-final 75, e 75(selection_v1 기준, 지금 채점으로 다시 셈).
  - 표본 4개(k = 1)의 최소·최대 안에 드는지 본다.
  - `z = (greedy − 100·mean p) / (100·sd_1)`을 적는다. |z| ≤ 2면 "분포 안"으로 쓴다.

### 9.3 조건 비교(문항 단위 쌍)

| 비교 | 쌍 |
|---|---|
| HF와 Ollama | HF-base 대 c, HF-base 대 d, HF-final 대 e |
| TEMPLATE | E 대 c |
| 변환 | c 대 B-conv |
| 양자화 | B-conv 대 d, Ollama-final 대 e |
| 학습 효과 | HF-base 대 HF-final, B-conv 대 Ollama-final, d 대 e |

- `d_i = p_Bi − p_Ai`의 평균(%p)을 낸다.
- 95% 신뢰구간은 문항 단위 bootstrap 10,000회의 percentile 2.5와 97.5다.
- paired sign-flip permutation 10,000회의 양측 p를 참고로 적는다.
- U 비율도 같은 방식으로 비교한다.
- 잡음과의 비교: 같은 조건의 두 셀(각 k = 4)이 보일 차이의 95% 폭 `1.96·sqrt(sd_4,A² + sd_4,B²)`과 나란히 적는다.
- 결론 문구:
  - 신뢰구간이 0을 포함하면 "차이를 확인하지 못함"이다.
  - 0을 포함하지 않으면 방향과 크기를 적는다.

### 9.4 오류 유형(문항×표본 비율, 셀마다)

`conversion_diag/compare_selection.py`와 같은 판별을 쓴다.

1. 질문에 없는 집계 추가: `factor:aggregation_spec` 차이에서 gold가 None.
2. dimension_target 누락.
3. 출발·도착 역할 추가·변경. 옛 표기 gold에 both를 쓴 표기 차이는 따로 센다.
4. 실차 통행량 오독.

### 9.5 검정력

- 쌍 비교의 분산을 `Var(mean d) = [σ²_δ + (v̄_A + v̄_B)/k] / N`으로 둔다.
  - `σ²_δ`는 문항별 참 차이의 분산이다. 관측된 `var(d_i)`에서 `(v̄_A + v̄_B)/4`를 빼서 추정하고, 0보다 작으면 0으로 둔다.
  - `v̄`는 9.2의 문항 안 분산 평균이다.
- 최소 검출 차이 `MDD = (1.96 + 0.84)·sqrt(Var)`(양측 α 0.05, 검정력 0.8)를 계산한다.
  - 대상 쌍: 학습 효과 세 쌍, 양자화 두 쌍, 그리고 모든 쌍을 모은 값.
  - 조합: N = 100, 98 × k = 1, 4, 8.
  - k = 1은 sampling 한 번을 뜻하고, greedy 한 번과 같지 않다(greedy는 문항 안 분산이 0인 대신 조건 변화에 따른 뒤바뀜이 있다).
- U 비율 차이도 같은 방식으로 계산한다.

### 9.6 결론 표지

결론마다 표지를 붙인다.
- **확인됨**: 이 측정에서 직접 확인.
- **가능성 있음**: 근거는 있으나 분리하지 못함.
- **미확인**.

반드시 답할 질문:
- HF와 Ollama의 greedy 차이(82 대 70)가 sampling에서도 남는가?
- pilot_002의 학습 효과는 sampling 기준으로 어느 방향인가?
- Q4_K_M과 Q8_0의 차이는 잡음보다 큰가?

## 10. 예상 시간

| 셀 | 표본 하나 | 셀(k = 4) |
|---|---|---|
| HF 2개 | 약 40–45분(greedy 중앙 22–26초/문항) | 약 3시간 |
| Ollama 6개 | 약 25–35분(conversion_diag greedy 기준) | 약 2–2.5시간 |
| 합계 | | 약 18–21시간(순서대로) |

## 11. 한계(보고서에 적는다)

- sampling 결과는 운영 조건(greedy)과 다르다.
- HF와 llama.cpp는 같은 seed라도 난수열이 다르다. sampler 구현(순서, min_p 처리)도 완전히 같지 않다. Ollama 체인은 top-k → top-p → min-p → temp다.
- k = 4라 문항별 정답률의 해상도는 0.25다.
- 한 장비, 한 Ollama 판(0.35.1)에서 잰다.
