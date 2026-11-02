# ablation_011 계획(학습 전 고정) — V4 한계 세 가지를 겨냥한 ablation

결정 261(2026-11-02, 사용자). **진단이며 판정이 아니다.** 결과로 V4를 채택·탈락시키지 않는다. 이 문서와 `FREEZE_A11.json`은 학습 시작 전에 커밋·푸시한다.
분석 도구(7절)는 학습 중에 기존 pilot_010 셀로 smoke한 뒤 `FREEZE_A11_tools.json`으로 고정하고, 그 커밋 뒤에만 평가 작업이 시작된다(`gpu/ready/A11_TOOLS.json`).
도구와 이 문서의 정의가 다르면 이 문서를 따른다.

하지 않는 것: PLAN_J 판정 단계 학습과 PLAN_J seed(101·523·2029·31·20271027), protected_final_v2 열람·고정, 주 셋 151 측정, Ollama 호출·DPO·Partial·nonthinking, 기존 adapter 삭제, 기존 스크립트 수정.

## 0. 지시와 다른 점(실행 기록, 결정 261에 적음)

- **E2(독립 holdout H-ans·H-ref) 없음.** 원천 `llm-finetuning-30000.jsonl`(sha256 `63d445b8…`)이 업로드 폴더(`/home/hwkim/.claude/uploads/`, `qa_test_10000.yaml`만 있음)·저장소·`/data/hwkim`·`/home/hwkim`·`/tmp`에 없다.
  지시 10절대로 E2와 E2 전용 기준 셀(base k=1·2, V4 o43·o1016·o7 k=1, B2 F)을 뺀다. E2에 기대던 분석(H-ans 정답률, H-ref 올바른 거부율, template_group 상위 20, base k=1·2 sampling 분산)은 6절의 대체 분석으로 바꾸고 결과에 "E2 없음"을 적는다.
- **순서 seed 1102 · 211102 · 2026113**(제안 3·1102·20261102에서 바꿈). 3은 기존 sampling seed(`pilot_006_prep/gpu/g0_speed.json`, `pilot_006/post/o1_speed.json`), 20261102는 회차 seed S_2(셀 460곳, 이번 E1 k=2와도 같음). 바꾼 값은 저장소 전체(`training/generated` jsonl 포함) seed 문맥 grep 0건.
- soup 서빙 `max_lora_rank` = 64: vLLM 0.30.0이 받는 값이 {1, 8, 16, 32, 64, 128, …}이라 48은 없다(48 이상 최소값).

## 1. arm과 데이터(빌드 `build/build11.py`, 검사 `build/mask_audit11.py`, 요약 `build/build_summary.json`·`build/mask_audit11.json`)

V4에서 한 가지만 바꾼다. 공통: R1''(1 epoch, lr 2e-4 → 0 linear, batch 1·accum 1, warmup 1 step, LoRA r16/α32/dropout 0.05, max_seq 12,288), 모델 seed 43, epoch 끝 checkpoint, thinking ON, 프롬프트 87048d0c, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.

| arm | 바꾼 것 | 레코드 = step | 질문 | 거부 레코드 | 근접 대조 teacher | 손실 비중 % 거부 / 근접 대조 teacher / 나머지 | 학습 파일 sha256 | 질문 목록 sha256 |
|---|---|---:|---:|---:|---:|---|---|---|
| A0 | 없음(`pilot_010/build/V4/full/sft_train.jsonl` 그대로) | 1,984 | 494 | 79 (S-1 10·teacher 69) | 408 | 2.24 / 36.79 / 60.98 | `3575c7f0…` | `d559b3e1…` |
| A1 | 근접 대조 teacher 408레코드 손실 범위 → json_only | 1,984 | 494 | 79 | 408(json_only) | 3.27 / 7.57 / 89.16 | `07a5622b…` | `d559b3e1…` |
| A2 | 거부 비중 ρ 0.02: R = round(0.02·1,905/0.98) = 39 | 1,944 | 454 | 39 (S-1 10·teacher 29) | 408 | 0.94 / 37.27 / 61.79 | `b017b340…` | `00031b7e…` |
| A3 | 요금 지표 근접 대조 뺌(462레코드) | 1,522 | 395 | 79 | 110 | 3.13 / 16.15 / 80.71 | `e8ca3fbf…` | `1d55c3ec…` |
| A0-soup | 학습 없음, S-V4-o43·o1016·o7 checkpoint-1984 정확한 평균 | – | – | – | – | – | – | – |

- **A1 json_only 정의 확인**(지시 3절 정지 조건): 저장소 정의(`training/data/thinking.py`)는 "추론(`</think>`와 뒤 공백까지)을 prompt에 붙이고 completion = 최종 JSON + EOS, prompt + completion token 경계가 바뀌면 거부"로 "같은 입력에서 최종 JSON에만 손실"과 같다.
  다만 `by_source`는 teacher 레코드의 json_only 표시를 거부하고 `order7.within_key`가 `loss_scope`로 질문 안 순서를 정하므로, `loss_scope`는 그대로 두고 `metadata.a11_loss_scope_override = "json_only"`를 더한 뒤
  학습 wrapper `train/train_a11.py`가 표시 레코드만 json_only로 렌더한다. mask audit: A1 1,984레코드 모두 prompt + completion 문자열·token 열이 A0와 같고, 표시 레코드 completion = canonical Full JSON + EOS, 나머지 렌더는 A0와 같다.
- **A2**: 거부 레코드는 V4 거부 79의 부분집합. build10w 4단계 채우기 규칙(S-1 먼저, 이어서 teacher 거부 trace를 (질문별 합, `Random("20261016:refusal_tie:V4")` 순위)로)을 R = 39로 다시 적용했다.
  같은 규칙을 R = 79로 돌리면 V4 거부 79를 그대로 다시 만든다(검사 통과); R = 39의 teacher 채움 29개는 V4 채움 순서의 앞 29개다. 빠진 40레코드 `build/removed_A2.json`.
- **A3**: (a) batch013 c1(corpus v6 `provenance.group == "c1"`, 승인 48문항) 질문의 모든 레코드 258(8b json_only 164·근접 대조 teacher 94)과 (b) 근접 대조 teacher 중 요금 지표 질문(pilot_010 `select_teachc10.py` 정의: 측정 subtype ∈ {revenue, active_taxi_count, active_taxi_ratio, operating_days}; corpus `execution`이 있는 181문항은 정답 호출 `get_billing_metrics`와 모두 일치)의 204(approved_billing 140·batch011 r2 34·batch012 r2 30)를 뺀다. 같은 질문의 RC7 레코드는 남는다. 질문 99개가 통째로 빠진다. 빠진 레코드 id `build/removed_A3.json`(학습 전 커밋).
  A3는 답하는 레코드가 줄어 거부 비중이 3.98% → 5.19%로 오른다(거부 레코드 수는 같음). 진단에서 이 동반 변화를 함께 적는다.
- 빌드 검사(결정 250과 같은 항목, arm마다): dry-run·tokenizer-check 12/12 exit 0(`train/configs/checks/`), 손실 token·마스크 audit 문제 0, 12,288 초과 0(최대 10,704), 질문 목록 sha256(위 표), 순서 연속 길이(2절).

## 2. 공유 순서(`build/orders/`)

- 순서 seed마다 A0(V4 1,984레코드)로 `order7b.order_file`(O4')을 만든다 → `order_b2_o<seed>.json`(train_b7b와 같은 형식·검사).
- 그 순서로 놓은 A0 레코드 키(`질문 id|trace id`) 열을 기준으로 arm 레코드 순서 파일 `record_order_<arm>_o<seed>.json`: A1 = A0와 같은 열, A2·A3 = A0 열에서 빠진 레코드만 지움(상대 순서 유지, 다시 섞지 않음).
- 같은 질문 연속 길이: 12개 모두 최대 2(≤ 4). 학습 wrapper가 매번 순서 파일 재생성·sha256·"arm 열 = A0 열 거르기"·레코드 집합 일치를 확인하고, A0·A1은 train_b7b 순서(`order7b.order_records`)와 같은지도 확인한다(dry-run 12/12 통과).

## 3. 학습(`train/configs/<arm>-o<seed>.yaml`, 바탕 pilot_010 `S-V4-o43.yaml`; 차이 `train/configs/DIFF.md`)

- 12개: {A0, A1, A2, A3} × 순서 seed {1102, 211102, 2026113}. wrapper `train/train_a11.py`(train_b7b의 lr 계획·저장 지점·profile 그대로). 출력 `/data/hwkim/sftdpo_work/ablation_011/train/<id>/checkpoint-<step>`.
- adapter는 지우지 않고 위치·sha256만 기록한다(커밋 안 함, 결정 255).
- OOM·NaN이면 한 번 다시 한다. 또 실패하면 그 작업을 빼고 보고한다. 시작 22시간 뒤에는 새 학습을 시작하지 않는다(scheduler `--train-deadline`); 블록이 덜 끝났으면 완료된 블록(같은 순서 seed의 네 arm이 모두 평가된 것)만 짝 비교에 쓴다.

## 4. soup(`soup/soup11.py`)

- S-V4-o43·o1016·o7 `checkpoint-1984`(`/data/hwkim/sftdpo_work/pilot_010/train_s10/`). 모듈마다 A' = concat(A1, A2, A3)(rank 48), B' = concat(B1, B2, B3)/3, `r = 48`, `lora_alpha = 96`(alpha/rank = 2 유지) → B'A'·2 = (1/3)Σ B_i A_i·2.
- CPU 검사: 임의 모듈 ≥ 5개(seed 고정)에서 B'A'·scale과 세 delta 평균의 최대 절대 차 / 세 delta 평균의 최대 절대값 < 1e-5(float64 계산과 저장 dtype 둘 다). 실패하면 soup만 빼고 보고한다.
- 서빙 `max_lora_rank` 64(`gpu/serve_a11.sh`, 그 밖은 같은 서버 설정). 출력 `/data/hwkim/sftdpo_work/ablation_011/soup/V4-soup3`(커밋 안 함, sha256 기록).

## 5. 평가와 GPU

- E1(개발·거부; **V4 선택에 이미 쓴 셋**임을 결과에 적는다): refusal_dev v2(거부 90 + 대조 30) + valid98 + aux, k = 4(회차 seed 20261100 + k), 동시 8, grounding_target full, 기준일 2026-09-25.
  client·채점 `pilot_006_prep/gpu_data/run_cell6x.py` → `pilot_005/vllm_eval_thinking5.py`, vLLM 0.30.0 BF16 17,408 flashinfer, rank 16(soup 64) — pilot_010 ES 셀과 같은 명령(이름·경로만 다름, `gpu/make_jobs_a11.py`).
- 기준 셀(있는 셀, 재측정 없음): V4 o43·o1016·o7 = `pilot_010/cells/s10_v4_*`, base = refusal_dev v2 k=12(`pilot_009/cells/base_rdevv2`)·valid98·aux k=4(pilot_006_prep), B2 F = pilot_007 B2 valid98·aux + pilot_009 `b2f_*_rdevv2`(`pilot_010/gates/spec_s10.json`과 같은 셀).
- 다시 돌리기(PLAN_S 5절과 같음): valid98·aux 셀은 잘림 또는 서버 오류 > 1%면 같은 seed로 한 번만; refusal_dev v2 셀은 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2일 때만. 원본은 `cells/replaced/`에 두고 결과와 무관하게 교체한다.
- GPU(결정 114): 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/timeline.jsonl`. 스케줄러 `gpu/scheduler13.py`(scheduler12 사본) 하나가 GPU 0·1·2(`2445b100`·`a5ce83d0`·`48f798cc`)를 쓴다.
  우선순위 (1) 학습이 끝난 모델의 평가 → (2) 학습(블록 1 = A0·A1·A2·A3 @1102 → 블록 2 @211102 → 블록 3 @2026113) → (3) soup 평가. 학습 전 host UUID·메모리·다른 프로세스·torch UUID 확인, 서버 기동 때 `gpu_ok`.
  Ollama GPU(`48f798cc`): 컨테이너가 돌고 있으면 `/api/ps`가 비어야 작업을 준다(지금은 컨테이너 없음 = server_down). 컨테이너에 손대지 않는다.

## 6. 분석(도구 `analysis/analyze_a11.py`·`analysis/xtab_a11.py`; 모든 결과에 "진단, 판정 아님")

표본 값: ok = `compute_gates.load_arm`(견고성 패치 grounding_ok), refused·경로 M/P/C = `compute_p9.sample_values`(결과 unsupported·needs_clarification이고 분석 tool 실행 없음; M = UNSUPPORTED_QUESTION, C = needs_clarification, P = 그 밖).
문항 값 = k 표본 평균, 모델(arm × seed) 값 = 문항 평균.

| 지표 | 문항 |
|---|---|
| 정답률 | E1 개발 셋 149(valid98 98 + aux 51, 문항 수 가중) |
| 올바른 거부율 | refusal_dev v2 거부 90 |
| 과잉 거부율 | 거부가 아닌 모든 E1 문항: valid98·aux `expected_outcome: answered` + refusal_dev 대조 30(169문항) |
| 심각 오류 | 개발 셋 149의 U 등급(U1–U4, grounding_v13 `report.unacceptable`) 표본 수(모델당 합, 4 표본) |
| 속도 | 문항 wall latency(`finished_at − started_at`) p50·p95, 생성 토큰(문항 hf_calls 합), thinking token, 잘림(finish_reason length) 호출 수 |

1. **arm 효과**: A1·A2·A3 각각 − A0, 같은 순서 seed끼리 짝. 점 추정 = 세 seed 평균의 차. bootstrap: 반복마다 seed 짝 3개를 복원 재추출하고 문항도 두 arm에 같은 번호로 복원 재추출,
   통계량 = 재추출 seed 짝의 (arm − A0) 재추출 문항 평균 차의 평균. 10,000회, 비교마다 새 `numpy.random.default_rng(20261109)`(pilot_009·PLAN_J와 같은 값), 백분위 95% CI. 지표 = 위 표 넷 + U 수(seed 평균) + 속도(점 추정만).
   완료되지 않은 블록이 있으면 완료된 seed 짝만 쓰고 적는다.
2. **순서 편차**: V4 6 seed(기존 o43·o1016·o7 + A0 o1102·o211102·o2026113)의 seed 값, 평균, sd(ddof 1), 범위를 정답률·올바른 거부율·과잉 거부율에서 낸다(E1만; H-ans 없음).
   분산 분해(개발 셋 ok, V4 6 seed × 149문항 × 4 표본): 균형 2원 임의 효과 + 반복의 ANOVA 추정으로 seed / 문항 / seed×문항 / sampling(같은 seed·문항 안 표본) 성분. 참고로 base(k=4) 개발 셋의 문항 / sampling 성분.
   보충(기존 셀, 새 측정 아님): client_test_10000 10,000문항 V4 3 seed k=1과 base k=1–3에서 seed 사이 차와 sampling 회차 사이 차.
3. **template_group 대체**: E1에는 template_group이 없다. (a) 개발 셋 149를 정답 호출 유형 칸(`type_target.profile(render_full(...))["cell"]`)과 분석 tool로 묶어 V4 6 seed 사이 정답률 차(최대 − 최소)가 큰 상위 20칸.
   (b) o43 약점 유형 대응 부분집합: 정답 호출이 `get_billing_metrics`이고 장소 scope가 있는 문항("소속 택시 요금" 대응), 정답에 출발·도착 역할(OD)이 있는 문항 — 6 seed별 정답률.
   (c) client_test_10000 V4 3 seed의 template_group 차 상위 20(기존 셀).
4. **soup**: soup(1 모델, k=4) 값과 V4 6 seed의 평균·최솟값을 지표마다 비교. soup − 6 seed 평균의 CI는 문항 재추출 + 6 seed 복원 재추출(10,000회, `default_rng(20261109)`).
5. **과잉 거부 몰림**: 거부가 아닌 문항의 표본마다 (정답 분석 tool) × (시간 단위) × (지역 유형) 칸으로 거부 표본 수 / 표본 수.
   - 시간 단위: 정답 분석 호출에 `bucket`이 있으면 `bucket:<값>`(+ `rollup`이 있으면 `+rollup`), 없으면 `date` 값으로 일(YYYYMMDD 하나)·주(7일 범위·주 단위 상대 표현)·월(달 하나 전체 범위·월 단위 상대 표현)·기간(그 밖의 범위)·연·없음.
   - 지역 유형: 정답 `get_place_scope`의 `name`이 시도(17개 시도명, 특별시·광역시·도 붙어도 됨)·시군구(시·군·구로 끝남)·읍면동(읍·면·동·가·리로 끝남)·POI(그 밖 또는 `include_vicinity`)이고, 장소 호출이 없으면 없음. 둘 이상이면 가장 좁은 것.
   - 학습 시작 직후 기존 원문(client_test_10000 V4 3 seed·base k=1–3, pilot_010 S 셀 V4·V8·base·B2 F·P9)에 먼저 적용하고, 새 셀에도 같은 도구를 적용한다.

## 7. 도구 고정 순서

- 학습 시작 → 분석 도구 작성 → pilot_010 셀로 smoke(V4 3 seed 값이 `pilot_010/results/selection_s10.json`과 같아야 함: 올바른 거부율 86.48·과잉 거부 2.17·개발 셋 71.81) →
  `FREEZE_A11_tools.json` 커밋·푸시 → `gpu/ready/A11_TOOLS.json` 생성(이때부터 평가 작업 시작). 고정 뒤에는 도구를 고치지 않는다(오류를 찾으면 새 파일과 기록).

## 8. 산출물

`RESULTS.md`(arm별 효과표와 CI, 순서 편차, soup, 과잉 거부 교차표, 속도), `CRITERIA_DRAFT.md`(정답률·올바른 거부율·과잉 거부율·응답 속도 기준 후보 2–3안과 근거 수치, 확정 안 함),
`QUESTIONS.md`(사용자 결정 목록). 원문·셀·로그는 규칙 3대로 커밋. adapter 위치·sha256은 `/data/hwkim/sftdpo_work/ablation_011/adapters_sha256.txt`(커밋 안 함).
