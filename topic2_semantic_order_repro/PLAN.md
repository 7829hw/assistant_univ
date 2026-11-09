# PLAN — topic2_semantic_order_repro (사전 등록, 신규 학습 결과를 보기 전에 고정)

기준: 브랜치 `geoflow/topic2-repro`(기준 커밋 `8166a6f0`에서 분기), 기존 `topic2_semantic_order`의 실패 판정(S1–S4)과 결과는 변경하지 않는다. H-final은 봉인. 이번 실험은 새 방법의 우수성을 입증하지 않는다.

## 1. 목표
(1) 동일 데이터·순서·설정 재학습의 변동성 정량화, (2) Semantic-balanced의 T1 악화 원인 규명(관찰 가능한 범위). 새 스케줄러는 만들지 않는다.

## 2. Stage 1 (완료, GPU 미사용)
`DIAGNOSIS_T1.md`, `DIAGNOSIS_T5.md`, `ORDER_EXPOSURE_ANALYSIS.md`, `SIGNATURE_AUDIT.md`. 신규 학습의 조건·평가·통계는 아래 3–6에서 Stage 1 결과와 무관하게 사용자 지시대로 고정한다. (Stage 1은 학습 조건을 바꾸지 않았다.)

## 3. 신규 학습 10회 (설정 고정)
| order seed | A (O4′) | B (Semantic-balanced) |
|---|---|---|
| 1102 | r1 기존, **r2, r3 신규** | r1 기존, **r2, r3 신규** |
| 211102 | r1 기존, **r2, r3 신규** | r1 기존, **r2, r3 신규** |
| 2026131 | r1·r2 기존, **r3 신규** | r1·r2 기존, **r3 신규** |
- 신규 설정 = 해당 arm·seed의 r1 설정에서 `training.output_dir`, `profiling.output`만 변경(자동 검증 `configs/manifest.json`: 10/10 경로만 다름). 모델 Qwen3-8B@b968826d, LoRA r16/α32/dropout 0.05(7 모듈), lr 2e-4 선형 → 0(warmup 1 step), batch 1 × accum 1, 1 epoch = 1,984 step, bf16, max_seq 12,288, thinking ON, loss scope `by_source`, **학습 seed 43 고정**(반복마다 바꾸지 않음), 데이터 V4 `sft_train.jsonl`(sha `3575c7f0…`), 순서 파일 r1과 동일. 결정론 옵션을 켜지 않는다(원래 설정 유지).
- 학습 스크립트: A = `ablation_011/train/train_a11.py`, B = `topic2_semantic_order/train_semantic.py`(기존 r1·r2와 동일 경로).
- 체크포인트 `/data/hwkim/sftdpo_work/topic2_semantic_order_repro/train/{A0,B}-o<seed>-r<n>/`. 기존 체크포인트는 덮어쓰지 않는다(경로 분리, ablation_011~013·topic2_semantic_order 불변).

## 4. GPU 운영
scheduler17(= scheduler16 사본, 경로·태그만 변경), 커밋 고정 worktree, 한 작업 = GPU 하나(GPU UUID 0·1·2 최대 3개 병렬), 작업별 `gpu/timeline.jsonl`, runs.log. 학습 순서(우선순위 순) `gpu/make_jobs_repro.py`: A-1102-r2, B-211102-r2, A-2026131-r3, B-1102-r2, A-211102-r2, B-2026131-r3, A-1102-r3, B-211102-r3, A-211102-r3, B-1102-r3 — arm·seed·run이 한 GPU에 편중되지 않게 교차하며, 실제 GPU 배정은 비는 GPU 순으로 이루어지므로 로그의 GPU UUID로 사후 검증한다. 다른 사용자 프로세스는 건드리지 않는다. 학습 OOM/NaN은 기존 규칙대로 1회 재시도 후 기록.

## 5. 평가 (H-dev 2,000문항만)
신규 10개 모두 H-dev k=1(기존 명령: `run_cell6x.py`, seed-base 20261100, concurrency 32, grounding full)로 평가하며, 선별하지 않는다. 기존 r1/r2의 H-dev 셀은 재사용한다(총 18개). **CT10K 재평가는 하지 않는다**(원 실험의 주 평가셋이며, T1 H-dev는 171문항이라 검정력이 낮다는 한계를 보고서에 명시). 추후 CT10K가 필요하면 목적·범위를 결과 확인 전에 별도 기록한다. 잘림 재실행 규칙은 기존과 동일(rdev 해당 없음, 잘림 > 1% 또는 서버 오류 ≥ 2이면 같은 seed로 1회 재실행, 원본 `cells/replaced/`). H-final은 열지·실행·분석·모델 선택에 쓰지 않는다.

## 6. 통계 분석 계획 (고정)
- 데이터: 18 모델 × H-dev. 지표: 전체 정확도, T1·T5 정확도(문항 유형은 gold 호출 기반), semantic_fine 그룹 정확도(≥ 20문항), worst-group, collapse20(base 평균 − 20pp, 기존 정의 재사용), refused_unsupported 비율(과거부), answered_mismatch(조용한 오답), failed(도구 실행 실패), 잘림 비율, 문항 불일치율.
- 분산 분해: y = μ + Arm + Seed + Arm×Seed + Residual(재학습). 3 seed × 2 arm × 3 run 균형 설계. 방법 = 기댓값 평균제곱 방식(method of moments, 음수 성분은 0으로 절단하되 원값 병기) + 보조로 cell별 SD. 오직 3개 order seed이므로 Seed·Arm×Seed 성분의 불확실성이 매우 크며 이를 모든 표에 명시한다.
- 불확실성: 계층 부트스트랩(10,000회, `default_rng(20261110)`): order seed → 같은 seed·arm 안의 run → template_group 클러스터(문항은 독립 반복이 아님). seed가 3개뿐이어서 CI가 불안정함을 병기하고, 대체로 seed 수준 차이(df=2)의 t-구간도 함께 보고한다.
- 질문과 사전 고정 판정:
  - Q1: 같은 설정 재학습의 SD(전체, T1, T5, worst-group, collapse20) = cell 내 표본 SD의 풀링 값.
  - Q2: "T1 붕괴 run" = H-dev T1 정확도 < 50%. B-o1102와 B-o211102에서 3 run 중 붕괴 run 수 보고; 두 cell 모두 ≥ 2/3이면 "재현", 그 외 "부분 재현/재현 안 됨".
  - Q3: 반복 평균 기준 Arm 효과(B−A, 전체 정확도)와 계층 CI; CI가 0을 제외하면 "차이 존재", 아니면 "구분 불가(동일하다는 뜻이 아님)".
  - Q4: 전체 B−A 차이를 T1 항목과 나머지 항목 기여로 분해(문항 비중 × 유형별 차이), 유형별 오류 분류(`stage1_failure_types.py`와 같은 규칙) 비교.
  - Q5: 관측한 재학습 SD와 Arm 효과 SE로 현재 설계의 최소 검출 효과(80% 검정력, 양측 5%)와 필요한 seed·run 수 추정.
  - 문항 불일치율: 같은 arm·seed의 run 쌍에서 (정답 ≠ 정답) 문항 비율, arm 간 쌍과 비교.
- T1 고유 분산: T1 정확도의 재학습 SD ÷ 전체 정확도 재학습 SD.
- 인과 가설 M1(LR-가중 노출), M2(contrast teacher 이웃), M3(서명 불일치): **신규 순서를 학습하지 않으므로** 노출 통계가 B 전 seed에서 거의 동일하다(Stage 1). seed 간 용량-반응을 검정할 수 없어 M1·M2는 "일관되나 검정 불가 = inconclusive"가 상한이다. 정답·오답으로 새 스케줄러를 튜닝하지 않는다.

## 7. 연구 방향 판정 규칙 (Stage 5, 결과 보기 전 고정)
- 방향 A(재현성): 재학습 SD(전체) ≥ 1pp이고 T1 재학습 SD가 Arm 효과(T1)보다 크면 권고.
- 방향 B(LR-aware)/C(실행 의미 서명)/D(커버리지): 신규 학습 없이 이 데이터로 검정 가능한 증거가 있을 때만 "근거 있음"; 그렇지 않으면 "가설"로 표기. 승인되지 않은 데이터 사용·보호 정책 변경은 하지 않는다. C/D 학습은 자동 진행하지 않는다.

## 8. 중단 규칙
기준 데이터 해시 불일치, 기존 설정 불일치, 재학습 순서 불일치, GPU 메모리·디스크 안전 조건 실패, 보호 데이터 정책 위반, 평가 도구 불일치 시 해당 단계를 중단하고 보고. 학습률·seed·batch 등을 바꿔 성공시키지 않는다.
