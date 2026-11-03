# ablation_012 계획(학습 전 고정) — A3 효과 분리, V4 seed 일관성(넓은 셋), 판정 설계 초안

결정 262(2026-11-03, 사용자). **진단이며 판정이 아니다.** V4를 채택하거나 기각하지 않는다. 이 문서와 `FREEZE_A12.json`은 학습 시작 전에 커밋·푸시한다.
분석 도구(6절)는 학습 중에 기존 셀로 smoke한 뒤 `FREEZE_A12_tools.json`으로 고정한다. 그 커밋 뒤에만 평가 작업이 시작된다(`gpu/ready/A12_TOOLS.json`, ablation_011과 같은 방식).
도구와 이 문서의 정의가 다르면 이 문서를 따른다. 도구 고정 때 정의를 보충하면 `FREEZE_A12_tools.json`의 `amendments_to_plan`에 적는다(평가 셀이 하나도 없을 때만).

하지 않는 것은 다음과 같다.
- PLAN_J 학습·판정, PLAN_J seed(101·523·2029·31·20271027)
- protected_final_v2 열람·고정, 주 셋 151 측정
- Ollama 호출·컨테이너 조작·DPO·Partial·nonthinking
- adapter 삭제, 기존 스크립트·FREEZE 수정
- **H-final 측정·열람**

## 0. 지시와 다른 점·실행 기록

- 30k 원천은 있고 sha256이 맞는다(`63d445b8…5102def`). 그래서 E2를 진행한다.
- **겹침 판정 도구**: 지시는 "client_test_10000과 같은 도구"로 판정하라고 했다. 그런데 그 도구는 저장소에 없다. CT10K `qa_test_10000.yaml`은 사용자가 업로드한 파일이고, 그 안에는 결과(pool 값)만 들어 있다.
  그래서 규칙을 다시 만들었다(`e2/build_e2.py` `PoolRule`). 이 규칙이 CT10K 10,000문항의 pool 라벨을 **모두** 재현할 때만 쓰도록 했고, 실제로 10,000/10,000 재현했다(`e2/pool_rule_check.json`).
  짝인 vendor100 문항이 CT10K에 없어 train_skeleton 여부의 근거가 없는 360문항은 보수적으로 뺐다.
- **H-ref 없음**: 비-tool_call 12,000문항의 원천 라벨에는 '거부' 기대 결과가 없다. 정답으로 구조화·정의·설명 응답이 적혀 있다. 지시대로 기술 통계만 낸다(`e2/e2_summary.json` `h_ref`).
  그래서 H-dev에는 거부 문항이 없다. H-dev의 거부 지표는 과잉 거부율(답이 있는 문항을 거부한 비율)뿐이고, 올바른 거부율은 E1(refusal_dev v2)에서만 본다.
- **A3 제거 질문**: A3은 레코드 462개를 뺐고, 이 레코드는 149질문에 걸쳐 있다(통째로 빠진 질문 99 + 일부만 빠진 질문 50).
  지시의 "A3 제거 질문"은 이 149질문으로 정했다. 대상 풀에서 이 149질문을 모두 빼므로 A3R과 A3이 같은 질문을 건드리지 않는다. 뽑는 수는 지시대로 99다.
- **A3R의 근접 대조 비중**: A3R은 무작위 질문을 빼므로 근접 대조 teacher 레코드가 대부분 남는다(408 → 368·370). 손실 token에서 근접 대조 teacher 비중은 43.6%로 A0의 36.8%보다 높고, A3은 16.2%다.
  즉 A3R은 "데이터 양만 같은" 대조다. 구성 차이는 5절 표와 RESULTS에 함께 적는다.
- **E1 정답률과 H-dev·CT10K 정답률의 정의가 다르다.**
  - E1은 ablation_011과 같은 `compute_gates.load_arm`의 견고성 패치 grounding_ok를 쓴다.
  - H-dev·CT10K는 client_test_10000과 같은 `category == "match"`를 쓴다. 이 두 셋은 정답 호출 문자열만 있는 셋이다.
- soup 서버는 `max_lora_rank` 64를 쓰고, CT10K V4 기존 셀은 16을 썼다. ablation_011 E-soup과 같은 조건이다. 차이는 서빙 설정 하나뿐이고 결과에 적는다.

## 1. A3R — 무작위 제거 대조 arm(빌드 `build/build12.py`, 요약 `build/build_summary.json`, 손실 `build/mask_audit12.json`)

- 대상 풀 = V4 답하는 질문 420 − A3 제거 질문 149 − 거부 질문 74(답하는 질문과 겹치지 않음) = **271질문**(레코드 1,250). id로 정렬한다.
- 뽑기: `numpy.random.default_rng(seed).choice(271, 99, replace=False)`를 되풀이한다. 뽑은 질문의 V4 레코드 합이 462의 ±2%(453–471)에 처음 드는 뽑기를 쓴다. 1,000번 안에 못 하면 멈춘다.

| arm | 뽑기 seed | 뽑기 횟수 | 뺀 레코드(A3 대비) | 레코드 = step | 거부 레코드(비중) | 근접 대조 teacher 레코드 | 손실 비중 % 거부 / 근접 대조 teacher / 나머지 | 학습 파일 sha256 |
|---|---:|---:|---|---:|---|---:|---|---|
| A0 (V4) | – | – | 0 | 1,984 | 79 (3.98%) | 408 | 2.24 / 36.79 / 60.98 | `3575c7f0…` |
| A3 | – | – | 462 | 1,522 | 79 (5.19%) | 110 | 3.13 / 16.15 / 80.71 | `e8ca3fbf…` |
| A3R-d1 | 20261104 | 3 | 464 (+0.43%) | 1,520 | 79 (5.20%) | 368 | 2.97 / 43.62 / 53.42 | 아래 FREEZE |
| A3R-d2 | 20261105 | 1 | 459 (−0.65%) | 1,525 | 79 (5.18%) | 370 | 2.95 / 43.49 / 53.55 | 아래 FREEZE |

- d1과 d2가 함께 뺀 질문은 39개다. tool별 레코드·질문 구성은 `build/build_summary.json`의 `arms.*.records_by_tool`·`reference_arms`에 있다.
- 빌드 검사(결정 250 항목)
  - dry-run·tokenizer-check 6/6 exit 0(`train/configs/checks/`).
  - 손실 token·마스크 audit 문제 0, 12,288 초과 0(최대 10,704).
  - 질문 목록 sha256(build_summary).
- 순서: ablation_011 A0 O4' 레코드 열(`ablation_011/build/orders/record_order_A0_o<seed>.json`)에서 빠진 레코드만 지웠다(`build/orders/record_order_A3R-d*_o<seed>.json`). 같은 질문 연속 길이는 6개 모두 최대 1–2(≤ 4)다.
  학습 wrapper(`ablation_011/train/train_a11.py`, 그대로)가 순서 파일 재생성·"arm 열 = A0 열 거르기"·레코드 집합 일치를 다시 확인한다(dry-run 통과).
- 학습: `train/configs/A3R-d{1,2}-o{1102,211102,2026113}.yaml`. ablation_011 `A3-o<seed>.yaml`에서 data·레코드 순서 파일·출력만 바꿨다(`train/configs/DIFF.md`).
  R1''(1 epoch, lr 2e-4 → 0 linear, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05, 12,288), 모델 seed 43, epoch 끝 checkpoint, thinking ON, 87048d0c, `expandable_segments:True`.
  출력은 `/data/hwkim/sftdpo_work/ablation_012/train/<id>`이고, adapter 위치·sha256은 `/data/hwkim/sftdpo_work/ablation_012/adapters_sha256.txt`에만 적는다(커밋 안 함, 결정 255).
- OOM·NaN이면 scheduler14가 출력 디렉터리를 `<dir>.failed1`로 옮기고 한 번 다시 돌린다. 또 실패하면 그 작업을 빼고 보고한다. NaN은 학습 로그의 loss로 확인한다.

## 2. E2 — H-dev·H-final(`e2/`, README·`e2_summary.json`)

| 셋 | 문항 | template_group | pool | sha256 |
|---|---:|---:|---|---|
| H-dev | 2,000 | 160 | independent 897 · vendor100_date_variant 1,103 | `9c7a0078…` |
| H-final(**봉인**) | 3,000 | 160 | independent 1,332 · vendor100_date_variant 1,668 | `bbc42650…` |

- 모집단 5,237 = 6,206 − train_skeleton 606 − verbatim 3 − 짝 근거 없음 360. template_group 층화(seed 20261103)로 나눴다.
- 학습 corpus v6·E1·CT10K와 질문 문자열이 겹치는 문항은 0개다. gold_check(CPU)는 H-dev 2,000/2,000, H-final 3,000/3,000 match다.
- H-final은 측정하지 않는다. 파일·sha256·구성 통계만 커밋하고, 문항별 gold_check 출력은 저장소 밖에 둔다.

## 3. 측정(작업 표 `gpu/jobs_a12.json`, 만든 도구 `gpu/make_jobs_a12.py`)

| 묶음 | 셀 | 조건 |
|---|---|---|
| E1 | A3R 6 모델 × {rdevv2, valid98, aux} × k 1–4 | ablation_011 E 작업과 같은 명령(`run_cell6x.py`, 동시 8, seed-base 20261100, grounding full, 기준일 2026-09-25) |
| CT10K | A0-o1102·o211102·o2026113·soup × 묶음 c1–c5, k=1 | client_test_10000과 같은 client·인자(동시 32, seed 20261101, `gpu/chunks/c1–c5`) |
| H-dev | A0 3·A3 3·A3R 6·soup·V4 o43·o1016·o7·A1 3·A2 3 k=1, base k=1·2 | `e2/h_dev.yaml --all-items`, 동시 32, 회차 seed 20261101(base k=2는 20261102) |

- 셀 수: E1 72, CT10K 20, H-dev 24(모두 116). 기준 셀(있는 것): E1 = ablation_011 셀과 pilot_010 V4 셀, CT10K = client_test_10000 V4 o43·o1016·o7과 base k=1–3.
- 다시 돌리기 규칙은 PLAN_S 5절과 같다. scheduler14가 셀이 끝날 때마다 자동으로 검사한다.
  - rdev 셀: 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2.
  - 그 밖의 셀(valid98·aux·CT10K 묶음·H-dev): 잘림 또는 서버 오류 > 1%.
  - 같은 seed로 한 번만 다시 돌린다. 원본은 `cells/replaced/`에 두고, 결과와 무관하게 교체한다. 기록은 `RERUNS_A12.json`.

## 4. GPU·일정(결정 114)

- 스케줄러 `gpu/scheduler14.py`(scheduler13 사본)가 GPU 0·1·2(`2445b100`·`a5ce83d0`·`48f798cc`)를 쓴다. 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/timeline.jsonl`이다.
  - 학습 전에는 host UUID·메모리·다른 프로세스·torch UUID를 확인하고, 서버 기동 때는 `gpu_ok`를 확인한다.
  - Ollama 컨테이너가 돌고 있으면 `/api/ps`가 비어야 GPU 2에 작업을 준다. 지금은 컨테이너가 없어 server_down이다. 컨테이너에는 손대지 않는다.
- 우선순위는 다음과 같다.
  1. A3R 학습(d1 seed 3개 prio 1–3 → d2 prio 4–6)
  2. 학습이 끝난 모델의 E1(prio 10–15)
  3. CT10K(prio 20–23)
  4. H-dev(prio 30–53: A0·A3·A3R → soup·V4·base → A1·A2)
  - 다시 돌리기는 prio 0으로 넣는다.
- `--deadline` = 시작 + 22시간. 그 뒤에는 어떤 작업도 새로 시작하지 않는다. 큐가 비면 `gpu/DONE`에 요약 한 줄을 쓴다(죽으면 `status: crashed`).
- 대기 방법: 백그라운드 대기가 다음 중 하나에서 끝난다. 그때 상태를 보고 다시 대기한다(ablation_011의 70분 공백 방지).
  - `gpu/DONE`이 생김
  - 스케줄러 PID가 없어짐
  - scheduler 출력에 Traceback이 나옴
  - runs.log에 작업 끝 줄이 새로 생김
  - 15분 경과
- 예상 시간: 학습 2바퀴 약 5h + E1 약 4.5 GPU-h + CT10K 약 10 GPU-h + H-dev 약 14 GPU-h. 모두 약 15h(GPU 3장).

## 5. 분석(도구 `analysis/`, ablation_011 고정 도구를 새 파일로 복사; 모든 결과에 "진단, 판정 아님")

표본 값은 ablation_011 PLAN 6절과 같다.
- ok = `compute_gates.load_arm` 견고성 패치 grounding_ok(E1)
- match = `category == "match"`(H-dev·CT10K)
- refused·경로 M/P/C = `compute_p9.sample_values`
- U1–U4 = `report.unacceptable`
- 잘림 = finish_reason length
- wall = `finished_at − started_at`

| 셋 | 정답률 | 올바른 거부율 | 과잉 거부율 | U | 속도 |
|---|---|---|---|---|---|
| E1 | 개발 셋 149(valid98 + aux) ok | rdev v2 거부 90 | 거부 아닌 169 | 개발 셋 149, 모델당 표본 수 | 잘림 호출·wall p50·p95 |
| H-dev | 2,000 match | – (H-ref 없음) | 2,000(모두 답이 있는 문항) | 2,000, 모델당 표본 수 | 잘림 호출·wall p50·p95 |

### 5.1 A3 분리

- 세 비교를 같은 순서 seed끼리 짝지어 계산한다: (A3 − A0), (A3R − A0), (A3 − A3R). A3R은 seed마다 d1·d2 문항 값의 평균이다.
  - 따로 보는 것: (A3R-d1 − A3R-d2), (A3R-d1 − A0), (A3R-d2 − A0).
- 점 추정은 세 seed 평균의 차다.
- bootstrap
  - 반복마다 seed 짝 3개를 복원 재추출하고, 문항도 같은 번호로 복원 재추출한다.
  - 통계량 = 재추출 seed 짝의 (X − Y) 재추출 문항 평균 차의 평균.
  - 10,000회, 비교마다 새 `numpy.random.default_rng(20261109)`, 백분위 95% CI.
  - ablation_011 `analyze_a11`의 `paired_boot`와 같다.
- 지표: 정답률·올바른 거부율(E1)·과잉 거부율·U1–U4 표본 수(seed 평균)·잘림 호출 수, wall p50·p95(점 추정). 셋: E1·H-dev.
- **해석 규칙(미리 고정)**: 지표·셋마다 (A3 − A3R)의 95% CI가 0을 포함하지 않으면 "요금 대조 고유 효과"로 적는다. 0을 포함하면 "데이터 양 효과와 구별 안 됨"으로 적는다.
  어느 쪽이든 1절의 구성 차이(근접 대조 비중)를 함께 적는다.

### 5.2 V4 seed 일관성(CT10K 10,000, 6 seed)

- V4 6 seed = client_test_10000 o43·o1016·o7(기존 셀) + A0 o1102·o211102·o2026113(새 셀). base = client_test_10000 k=1–3의 문항별 평균.
- seed별 정답률(match), 평균·sd(ddof 1)·범위를 낸다.
- template_group(CT10K 30문항 이상 그룹)마다 seed별 정답률을 본다.
  - **붕괴** = seed 정답률 < base 3회 평균 − 20pp인 그룹. seed마다 붕괴 수를 센다.
- seed 간 sd가 큰 그룹 상위 20개(같으면 범위·그룹 이름 순)를 뽑는다. 각 그룹이 학습 데이터의 어떤 질문 유형과 관련되는지 레코드 수와 순서상 위치로 기술한다. 원인은 단정하지 않는다.
  - 유형 서명은 정답 분석 tool | 시간 단위 | 지역 유형(`xtab_a11.classify`)과 measure(metric·subtype) 칸이다.
  - 학습 쪽 서명은 corpus `execution`이 있으면 그 호출로, 없으면 `view.measure.subtype`→tool만으로 맞춘다.
  - 각 seed의 순서에서 그 서명 레코드의 위치를 본다: 평균 위치, 마지막 10%·25% 안 수.
- **o43형 붕괴**(client_test_10000 RESULTS 4절: 소속 택시 요금 유형 `…1c3cb876…`·`…449f5bf2…`·`…6c262dd5…`, OD 상위 `…cd5fe2f2…`)가 새 seed 3개에서도 나오는지 그룹별로 본다.
- H-dev에서도 같은 표(seed별 정답률, 30문항 이상 그룹이 있으면 그룹 표)를 보조로 낸다. base는 k=1·2 평균이다.

### 5.3 soup(CT10K, 진단만; D5 후보 아님)

- soup과 o43·o1016·o7 각각을 문항 짝으로 비교한다.
  - 정답률 차와 문항 재추출 bootstrap 95% CI(10,000, `default_rng(20261109)`)
  - 한쪽만 맞힌 문항 수
- o43 붕괴 그룹에서 soup·각 seed·base의 정답률을 본다.
- 참고로 soup − V4 6 seed 평균도 낸다(6 seed 복원 재추출 + 문항 재추출).

### 5.4 검정력·seed 수(모의)

- 바탕은 V4 6 seed의 문항별 값이다(E1 k=4 평균, CT10K·H-dev k=1).
- seed 수 n ∈ {3, 5, 8}이다.
- 참 차이는 다음과 같다.
  - 정답률 Δ ∈ {0, −2, −3}pp(E1 개발 셋·H-dev)
  - 과잉 거부 Δ ∈ {0, +1}pp(E1 169·H-dev)
  - 올바른 거부 Δ ∈ {0, −5}pp(E1 rdev 90)
- 모의 한 번은 다음과 같다.
  1. V4 쪽 n seed와 후보 쪽 n seed를 6 seed에서 따로 복원 추출한다(짝 상관 0으로 둠: 보수적).
  2. 후보 쪽에는 참 차이를 문항 단위 무작위 뒤집기로 넣는다.
     - 정답률이 Δ만큼 떨어지도록 맞힌 표본을 확률 |Δ|/정답률로 틀림으로 바꾼다.
     - 거부는 거부 아닌 표본을 확률 Δ/(1 − 거부율)로 거부로 바꾼다.
     - 올바른 거부는 거부 표본을 확률 |Δ|/거부율로 비거부로 바꾼다.
  3. 안 2 bootstrap(seed 짝·문항 재추출, 1,000회)으로 CI를 낸다.
  - 400회 되풀이한다. 기준은 안 2 초안 한계(정답률 하한 > −3, 올바른 거부 하한 > −5, 과잉 거부 상한 < +1.5)다.
  - 결과는 CI 반폭 평균과 통과 확률이다. rng는 `numpy.random.default_rng(20261110)`.
- 안 3 모의
  - 6 seed에서 n seed를 복원 추출하고, 위의 참 차이를 넣은 뒤 다음을 모두 만족하는 비율을 본다.
    - 모든 seed가 넓은 셋(CT10K·H-dev) 정답률 ≥ base + 5pp
    - 붕괴 그룹 0
    - E1 seed 평균 과잉 거부 ≤ 3.0·올바른 거부 ≥ 85.0
  - 400회, 같은 rng 계열(`default_rng(20261111)`)을 쓴다. 수치 기준은 CRITERIA_v2_DRAFT에서 2안까지 다시 계산한다(확정 안 함).

### 5.5 과잉 거부 대상 유형(D6)

- A0 3 seed와 V4 o43·o1016·o7의 거부 표본을 모은다. 셋은 E1 거부 아닌 169, CT10K, H-dev다.
- 이를 ablation_011 교차표 도구(`xtab_a11.classify`: 정답 tool × 시간 단위 × 지역 유형)로 정리한다.
- `get_trip_metrics`와 시도 단위 요금 지표를 중심으로 칸별 거부 표본 비율과 seed 일관성을 본다. 이를 바탕으로 근접 대조를 보강할 유형 후보와 예상 문항 수를 `CONTRAST_PLAN_DRAFT.md`에 낸다(문항은 쓰지 않음).

## 6. 도구 고정 순서

1. 학습 시작
2. 분석 도구 작성(`analysis/analyze_a12.py` 등, ablation_011 도구를 새 파일로 복사)
3. smoke
   - ablation_011 셀로 A3 − A0 E1 값이 `ablation_011/analysis/results_a11.json`과 같아야 한다.
   - client_test_10000 셀로 V4 3 seed 정답률 85.94·94.23·93.84와 base 82.73·83.00·83.13이 나와야 한다.
4. `FREEZE_A12_tools.json` 커밋·푸시
5. `gpu/ready/A12_TOOLS.json` 생성 — 이때부터 평가 작업이 시작된다.

고정 뒤에는 도구를 고치지 않는다(오류를 찾으면 새 파일과 기록).

## 7. 산출물

- `RESULTS.md`
- `CRITERIA_v2_DRAFT.md`(2안까지, 확정 안 함)
- `CONTRAST_PLAN_DRAFT.md`
- `QUESTIONS.md`
- `pilot_010/PLAN_J2_DRAFT.md`(PLAN_J_DRAFT 그대로 둠)

셀·원문·로그는 규칙 3대로 커밋한다.
