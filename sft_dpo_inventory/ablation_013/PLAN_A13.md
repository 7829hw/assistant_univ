# ablation_013 계획(학습 전 고정) — 근접 대조 비중 대조(A3T), V4 짝 seed 5개, batch014 초안·진단

결정 263(2026-11-06, 사용자). **진단이며 판정이 아니다.** V4를 채택·기각하지 않는다. batch014는 초안이고 이번 세션에서 학습에 쓰지 않는다.
이 문서와 `FREEZE_A13.json`은 학습 시작 전에 커밋·푸시한다. 분석 도구(6절)는 학습 중에 기존 셀로 smoke한 뒤 `FREEZE_A13_tools.json`으로 고정하고,
그 커밋 뒤에만 평가 작업이 시작된다(`gpu/ready/A13_TOOLS.json`, ablation_011·012와 같은 방식). 도구와 이 문서의 정의가 다르면 이 문서를 따른다.
도구 고정 때 정의를 보충하면 `FREEZE_A13_tools.json`의 `amendments_to_plan`에 적는다(평가 셀이 하나도 없을 때만).

하지 않는 것: PLAN_J 학습·판정과 PLAN_J seed(101·523·2029·31·20271027), H-final 측정·문항 열람(그룹 크기 분포만 염), protected_final_v2 열람·고정, 주 셋 151 측정,
Ollama 컨테이너 조작, DPO·Partial·nonthinking, adapter 삭제, 기존 스크립트·FREEZE 수정, batch014·미승인 데이터로 학습, CT10K·H-dev 문항 원문을 batch014 작성에 쓰기, CT10K·H-final 측정.

## 0. 지시와 다른 점·실행 기록

- **D5b(Ollama)**: 지시문은 두 칸 중 어느 것도 고르지 않은 채 왔다. 실제 상태를 따랐다 — `docker ps -a` 컨테이너 0개, `localhost:11434` 응답 없음.
  그래서 **teacher 수집(T-C3·TEACH-C14)을 하지 않고** 자체 표본 진단(J-b014)만 한다. 컨테이너에는 손대지 않았다(결정 263 실행 기록).
- **A3T 목표 비중에 닿지 않음**: 요금 지표가 아닌 근접 대조 풀은 55질문(batch011 r2 14, batch012 r2 12, batch013 c2 29)·198레코드이고, 근접 대조 teacher 레코드는 110개다.
  풀 전체를 빼도 근접 대조 teacher 손실 비중은 **29.60%**(A0 36.79%)로, 목표 A3 16.15% ± 2pp(14.15–18.15)에 못 미친다.
  지시 2.1의 규칙("다 빼도 못 미치면 가능한 만큼만 빼고 실제 비중 보고")대로 **풀 전체(55질문·198레코드)를 뺀 A3T**를 쓴다.
  남은 근접 대조 teacher 298레코드는 모두 요금 지표(A3이 뺀 것)라 더 뺄 수 없다(빼면 A3이 된다).
  - 결과: A3T의 근접 대조 비중(29.6%)은 A3(16.2%)과 같지 않고 A0(36.8%)에 가깝다. 데이터 양도 A3T −198레코드, A3 −462레코드로 다르다.
  - 그래서 (A3 − A3T)는 "근접 대조 비중을 맞춘" 비교가 아니다. 5.1 해석 규칙은 고정한 문구 그대로 적되, 이 구성 차이(비중 16.2 vs 29.6, 레코드 1,522 vs 1,786)를 같은 줄에 적는다.
- **A0 새 순서 seed**: 후보 7102·311102·41102·511102는 저장소에 이미 있어 버렸고, 단어 grep 0건인 **2026117·2026131**로 확정했다(결정 263 실행 기록, 확정 전 기록).
- **H-final 그룹 크기 분포**(D2, `e2/h_final_group_sizes.json`, 그룹 이름 없이 크기만): 3,000문항·160그룹, 20문항 이상 78그룹, **30문항 이상 59그룹**, 50문항 이상 3그룹(최대 63, 중앙값 14).
  H-dev(비교)는 20문항 이상 54, 30문항 이상 3, 50문항 이상 0이다.

## 1. A3T(빌드 `build/build13.py`, 요약 `build/build_summary.json`, 손실 `build/mask_audit13.json`)

- 대상 풀 = V4 질문 중 (corpus v6 `provenance.kind == "r2_contrast"` ∪ 근접 대조 teacher 레코드가 있는 질문) − 요금 지표(`view.measure.subtype` ∈ {revenue, active_taxi_count, active_taxi_ratio, operating_days}, build11과 같은 정의).
  batch013 c1이 모두 요금 지표인지, 풀에 거부 질문이 없는지 확인했다.
- 뽑기: `default_rng(20261106).permutation(55)` 순서로 질문을 통째로 하나씩 빼며 비중을 다시 계산. 55번째까지 목표 범위에 들지 않음(`removed_A3T.json` `trace`).
- 손실 token = 학습 코드 렌더(`train_a11.install_override` + `render_records`, A0-o1102 config)의 completion token 수. 이 값으로 A0·A3·A3R의 비중이 mask_audit12와 같게 나온다(빌드에서 A0 일치 검사).

| arm | 레코드 = step | 질문 | 거부 레코드 | 근접 대조 teacher 레코드(요금) | 손실 비중 % 거부 / 근접 대조 teacher / 나머지 | 손실 token |
|---|---:|---:|---:|---|---|---:|
| A0 (V4) | 1,984 | 494 | 79 | 408 (298) | 2.24 / 36.79 / 60.98 | 908,705 |
| A3 | 1,522 | 395 | 79 | 110 (0) | 3.13 / 16.15 / 80.71 | 648,868 |
| A3R-d1 | 1,520 | 395 | 79 | 368 | 2.97 / 43.62 / 53.42 | 685,255 |
| A3R-d2 | 1,525 | 395 | 79 | 370 | 2.95 / 43.49 / 53.55 | 688,920 |
| **A3T** | **1,786** | **439** | 79 | **298 (298)** | **2.62 / 29.60 / 67.78** | 775,202 |

- tool별 레코드·질문 수는 `build/build_summary.json` `composition`(A0·A3·A3R-d1·d2·A3T·A3T_removed). A3T가 뺀 레코드의 tool: 실차 건수 142·통과량 건수 36·RPM 20.
- 빌드 검사(결정 250): mask audit 문제 0, 12,288 초과 0(최대 10,704); dry-run·tokenizer-check 5/5 exit 0(`train/configs/checks/`); 질문 목록 sha256(build_summary).
- 순서: ablation_011 A0 레코드 열에서 빠진 레코드만 지움(`build/orders/record_order_A3T_o<seed>.json`), 같은 질문 연속 최대 2(≤ 4).

## 2. A0 짝 seed 추가

- V4 데이터 그대로. `order7b.order_file({"full": V4}, seed)`(build11과 같은 호출; seed 1102로 돌려 ablation_011 `order_b2_o1102.json`과 바이트 단위로 같음을 먼저 확인)
  → `build/orders/order_b2_o{2026117,2026131}.json`, `record_order_A0_o{…}.json`. 연속 최대 2. 학습 wrapper가 "A0 열 = order7b O4' 순서"를 다시 확인한다(dry-run 통과).
- A0 순서 seed 5개 = 1102·211102·2026113(ablation_011) + 2026117·2026131(이번).

## 3. 학습(config `train/configs/`, 차이 `train/configs/DIFF.md`)

- A3T-o{1102,211102,2026113}: ablation_011 `A3-o<seed>.yaml`에서 data·레코드 순서 파일·출력만 바꿈.
- A0-o{2026117,2026131}: ablation_011 `A0-o1102.yaml`에서 순서 seed·O4' 순서 파일·레코드 순서 파일·출력만 바꿈.
- 공통: R1''(1 epoch, lr 2e-4 → 0 linear, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05, 12,288), 모델 seed 43, epoch 끝 checkpoint(checkpoint-1786·1984), thinking ON, 87048d0c,
  `expandable_segments:True`, wrapper `ablation_011/train/train_a11.py` 그대로. 출력 `/data/hwkim/sftdpo_work/ablation_013/train/<id>`; adapter 위치·sha256은 `/data/hwkim/sftdpo_work/ablation_013/adapters_sha256.txt`에만(결정 255).
- OOM·NaN이면 scheduler15가 출력 디렉터리를 `<dir>.failed1`로 옮기고 한 번 다시 돌린다. 또 실패하면 빼고 보고.

## 4. 측정(작업 표 `gpu/jobs_a13.json`, 만든 도구 `gpu/make_jobs_a13.py`, seed `gpu/seeds_a13.json`)

| 묶음 | 셀·출력 | 조건 |
|---|---|---|
| E1 | A3T 3·A0 새 2 × {rdevv2, valid98, aux} × k 1–4 = 60셀 | ablation_012 E 작업과 같은 명령(`run_cell6x.py`, 동시 8, seed-base 20261100, grounding full, 기준일 2026-09-25) |
| H-dev | A3T 3·A0 새 2 × k=1 = 5셀 | `ablation_012/e2/h_dev.yaml --all-items`, 동시 32, seed 20261101 |
| J-b014-base | `batch014/base_first_response.jsonl`, `training/generated/ablation_013/self/` | base, `collect6b --mode first`(greedy) → `--mode self`(greedy 1 + 표본 8, round seed 20261015, 표본 seed = EV.call_seed) — pilot_010 J-b013과 같은 명령 |
| J-b014-v4-* | `batch014/v4_first_response_<이름>.jsonl` | V4 o1016·o7·o43 + A0 o1102·o211102·o2026113 첫 응답(greedy, `collect8 --mode first`) |

- 기준 셀(기존): E1 = ablation_011 A0·A3 셀, ablation_012 A3R 셀; H-dev = ablation_012 A0·A3·A3R·V4·base 셀.
- 다시 돌리기 규칙은 PLAN_S 5절(ablation_012와 같음): rdev 셀 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2, 그 밖 > 1% → 같은 seed 한 번, 원본 `cells/replaced/`, 결과와 무관하게 교체. 기록 `RERUNS_A13.json`.
- J-b014 작업은 `gpu/ready/J-b014.json`(batch014 초안 검사·커밋 뒤, 입력 sha256)이 있어야 시작하고, 명령 첫머리 `check_ready13.sh`로 sha256을 다시 맞춘다. 진단 열은 학습 데이터로 쓰지 않는다. base 표본 원문은 보존한다.

## 5. 분석(도구 `analysis/`, ablation_012 고정 도구 사본; 모든 결과에 "진단, 판정 아님")

표본 값·지표 정의는 PLAN_A12 5절과 같다(ok = `compute_gates.load_arm` 견고성 패치 grounding_ok(E1), match(H-dev), refused = `compute_p9.sample_values`, U1–U4 = `report.unacceptable`(H-dev gold 주입은 ablation_012 amendments와 같음), 잘림 = finish_reason length, wall).
짝 bootstrap = `core_a11copy.boot_paired`(seed 짝·문항 공유 재추출, 10,000회, 비교마다 새 `default_rng(20261109)`, 백분위 95%).

### 5.1 A3 분리 2판

- 같은 순서 seed 짝(1102·211102·2026113, 3개)으로 (A3 − A3T), (A3T − A0), (A3 − A3R)을 계산한다. A3R은 seed마다 d1·d2 문항 값의 평균(ablation_012와 같음). 셋은 E1·H-dev.
- 지표: 정답률·올바른 거부율(E1)·과잉 거부율·U1–U4 표본 수·잘림 호출 수(점 추정·CI), wall p50·p95(점 추정).
- **해석 규칙(미리 고정)**, 지표·셋마다:
  - (A3 − A3T)의 95% CI가 0을 포함하지 않으면 "근접 대조 비중을 맞춰도 남는 요금 대조 고유 효과", 포함하면 "근접 대조 비중 효과와 구별 안 됨"으로 적는다.
  - (A3T − A0)의 **과잉 거부** CI 하한이 0보다 크면(A3T가 과잉 거부를 늘림) "요금 외 근접 대조도 과잉 거부를 막음"으로 적는다. 그렇지 않으면 "요금 외 근접 대조의 과잉 거부 효과는 보이지 않음".
  - 위 문구 옆에 반드시 0절의 구성 차이(A3T 근접 대조 비중 29.6% — 목표 16.2%에 닿지 않음, 레코드 1,786 vs A3 1,522)를 적는다.
- 서술용 그림(`analysis/fig_share_a13.png`): x = 근접 대조 teacher 손실 비중(%), y = 과잉 거부율·정답률(E1·H-dev 각각). 점 = A0(순서 seed 5개)·A3·A3R-d1·A3R-d2·A3T × 순서 seed. 회귀선은 그리지 않는다.

### 5.2 대상 서명 / 그 밖 분리

- 모든 비교(5.1과 5.3)를 H-dev·E1에서 "T1–T5 서명 문항"과 "그 밖"으로 나눠 함께 보고한다(같은 bootstrap, 문항 재추출은 각 부분 안에서).
- 분류는 정답 호출로 한다(xtab 도구의 `classify` = (tool, 시간 단위, 지역 유형) + 정답 분석 호출의 인자):
  - T1: tool `get_trip_metrics`, aggregation(없으면 avg) ∈ {avg, med, min, max}, 시간 단위 ∈ {일, 기간, 주}, 지역 ∈ {시도, 없음}.
  - T2: tool `get_trip_metrics`이고 T1이 아니며 (지역 = 시군구 또는 시간 단위 = 요일유형).
  - T3: tool `get_billing_metrics`, metric ∈ {revenue, active_taxi_count, active_taxi_ratio}, ((지역 = 시도이고 시간 단위 ∈ {일, 월}) 또는 dimension ∈ {sido, dayofweek}).
  - T4: tool `get_trip_count`, dimension 없음, 시간 단위 = 일, 지역 ∈ {없음, POI}.
  - T5: tool `get_trip_count`, dimension 있음, limit 있음(OD 상위 N).
  - 여러 칸에 들면 앞 번호. 어느 것에도 안 들면 "그 밖". 거부 기대 문항(E1 rdev 거부 90)은 서명 분리에서 뺀다(올바른 거부는 전체로만).

### 5.3 A0 5 seed 바탕 분포와 CRITERIA_DEV_v1 검정력(보고만)

- A0 순서 seed 5개(ablation_011 3 + 이번 2)의 E1·H-dev 정답률·올바른 거부·과잉 거부 seed 평균·sd(ddof 1)·범위. V4 o43·o1016·o7(H-dev)은 참고로 따로.
- `CRITERIA_DEV_v1.json`(2-가, 이 계획과 함께 고정)의 검정력을 5 seed 실측 값으로 다시 계산한다. **기준은 바꾸지 않는다.**
  - 모의: A0 5 seed의 문항 값에서 V4 쪽 5 seed와 후보 쪽 5 seed를 따로 복원 추출(짝 상관 0, 보수적), 후보 쪽에 참 차이를 문항 단위 무작위 뒤집기로 넣고(PLAN_A12 5.4와 같은 방법),
    `boot_paired` 1,000회로 CI. 400회 되풀이, `default_rng(20261113)`.
  - 참 차이: 정답률 {0, −2, −3, −4}pp(H-dev), 올바른 거부 {0, −5, −7}pp(E1 rdev), 과잉 거부 {0, +1, +1.5}pp(E1·H-dev). 출력: CI 반폭 평균, 지표별 통과 확률, Δ=0 네 조건 모두 통과 비율(같은 모의 회차에서).
- 이 절의 A3T·A3R은 3 seed라 CRITERIA_DEV_v1(5 seed)을 적용하지 않는다(수치만).

### 5.4 batch014 진단(J-b014)

- T유형별: base greedy 첫 응답과 표본(greedy 1 + 8)의 "초안과 같음"(gold 파이프라인 결과 일치, batch013 `build_review13`과 같은 정의)·거부로 끝남 비율.
  V4 6 seed 첫 응답의 거부율·오답률(거부 아님 & 초안과 다름).
- V4가 실제로 약한 유형인지: T유형별 V4 6 seed 거부율을 base와 나란히, seed마다 적는다.
- T5: 정답 `dimension_target`과 응답 `dimension_target`이 다른 수(출발 역할 오류: pickup vs both 등), `scope_pickup`/`scope_dropoff` 자리가 바뀐 수.

## 6. GPU·일정(결정 114)

- 스케줄러 `gpu/scheduler15.py`(scheduler14 사본, 위치·이름만 바꿈)가 GPU 0·1·2(`2445b100`·`a5ce83d0`·`48f798cc`)를 쓴다. 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/timeline.jsonl`.
  학습 전 host UUID·메모리·다른 프로세스·torch UUID 확인, 서버 기동 때 `gpu_ok`. Ollama 컨테이너가 없으면 server_down(빈 것)으로 본다. 컨테이너에는 손대지 않는다.
- 우선순위: (1) 학습 A3T 3(prio 1–3) → A0 2(prio 4–5) (2) 끝난 모델의 E1(prio 10–14)·H-dev(prio 20–24) (3) J-b014(prio 30–36). 다시 돌리기 prio 0.
- `--deadline` = 시작 + 22시간(그 뒤 새 작업 없음). 큐가 비면 `gpu/DONE` 요약 한 줄. 대기는 백그라운드 대기(DONE·PID 없어짐·Traceback·runs.log 새 끝 줄·15분 경과 중 하나에서 끝남).
- 예상: 학습 2바퀴 약 5.5h(A3T 176분, A0 195분), E1 약 4 GPU-h, H-dev 약 3 GPU-h, J-b014 약 2 GPU-h → 약 9–10h.

## 7. 도구 고정 순서

1. 학습 시작
2. 분석 도구 작성(`analysis/analyze_a13.py` 등, ablation_012 고정 도구를 새 파일로 복사)
3. smoke: ablation_011·012 기존 셀로 (A3 − A3R)·(A3 − A0) E1·H-dev 값이 `ablation_012/analysis/results_a12.json`과 같아야 한다.
4. `FREEZE_A13_tools.json` 커밋·푸시 → 5. `gpu/ready/A13_TOOLS.json` 생성(이때부터 평가 작업 시작).

고정 뒤에는 도구를 고치지 않는다(오류를 찾으면 새 파일과 기록).

## 8. 산출물

`RESULTS.md`, `CRITERIA_DEV_v1.json`(이 계획과 함께 고정), `e2/h_final_group_sizes.json`, `PLAN_A14_DRAFT.md`, `QUESTIONS.md`, `sft_dpo_inventory/batch014/`(초안·검토 시트, 승인 아님).
셀·원문·로그·초안은 규칙 3대로 커밋한다.
