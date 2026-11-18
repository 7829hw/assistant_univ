# pilot_010 JQ 계획 — (A) seed 앙상블 사후 분석 + (B) RR+NM8 새 seed 4개, 결정 269

**판정 뒤 추가(사후)이며 PF2·H-final의 두 번째 사용이다.** 판정 단계(결정 267)·사후 측정(결정 268) 결과를 본 뒤에 정했다. C1–C4 판정은 바꾸지 않는다.
이 수치로 구성·seed·checkpoint를 고르지 않는다. 새 데이터·교사 응답·새 구성·규칙 조정·X4 분석·Ollama 작업·논문 수정은 하지 않는다.
이 계획(규칙 전부)은 계산·학습·측정 전에 커밋한다. 결과를 본 뒤 규칙을 바꾸지 않고, 결과가 나빠도 그대로 보고한다. 모든 문서·표에 "판정 뒤 추가(사후), PF2·H-final 두 번째 사용"을 표시한다.

## 0. 구성 이름

| 이 문서 | 저장소 이름 | 어댑터 | seed |
|---|---|---|---|
| SFT | B2 F(pilot_007, 거부 목표 없는 SFT) | `B2-F-o*/checkpoint-1811` | o43·o1016·o7·o11·o2027 (5) |
| RR | P9(pilot_009 P9-F) | `P9-F-o*/checkpoint-1993` | o43·o1016·o7·o11·o2027 (5) |
| RR+NM4 | V4(판정 단계 J-V4) | `J-V4-o*/checkpoint-1984` | o101·o523·o2029·o31·o20271027 (5) |
| RR+NM8 | V8(선택 단계 S-V8) | `S-V8-o*/checkpoint-2071` | o43·o1016·o7 (3) |
| RR+NM8 새 | V8(이번 B) | `JQ-V8-o*/checkpoint-2071` | 아래 B1 (4) |
| base | Qwen3-8B@b968826d | 없음 | PF2 k=8·H-final 2회차를 한 단위로 |

seed 표기 순서 = 위 표의 순서(앙상블 동률 규칙에 쓴다). 7 seed 합은 기존 3(o43·o1016·o7) 다음에 새 4(B1 순서).

## A. seed 앙상블(다수결) — 기존 셀만, GPU 없음, `results/analyze_jq.py`

### A1. 표본 결과(셀 행 하나)

- 거부: `analyze_j.sample_rows`의 refused(결과 상태 ∈ {unsupported, needs_clarification} 그리고 `get_place_scope` 아닌 실행 호출 0). 경로 M·P·C도 거기서.
- 거부가 아니면 결과 = 그 셋 채점기가 비교하는 정규형(문자열로 직렬화, `json.dumps(sort_keys=True)`).
  - PF2(채점 = `EV.grounding_check`, final_ok는 결과 상태가 거부 상태가 아님도 요구): 키 = (결과 상태가 거부 상태인가, `EV._grounding_view(row["grounding"])`). view가 없으면 (`no_grounding`, 결과 상태·error_code).
  - H-final·CT10K·H-dev(채점 = `EV.score`의 `category`): 키 = (결과 상태, `get_place_scope` 호출의 `_place_key` 정렬 목록(중복 포함), 분석 호출 수, 마지막 분석 호출 tool, `EV._normalized(tool, args)`).
    결과 상태가 answered가 아니거나 호출이 없으면 키 = (`no_plan`, 결과 상태·error_code).
- 표본의 정답(기존 정의 그대로): PF2 = `scored.ok` 참 그리고 결과 상태가 거부 상태 아님. H-final·CT10K·H-dev = `category == "match"`.

### A2. 앙상블 규칙(n = 구성의 seed 수)

1. 한 문항에서 n개 모델 결과를 모은다. 거부한 모델 수 > n/2 이면 앙상블은 거부한다. 경로 = 거부한 모델들의 경로 최빈값(동률이면 seed 표기 순서가 앞선 모델의 경로).
2. 아니면 거부하지 않은 모델들의 키 중 최빈값을 답으로 한다. 동률이면 seed 표기 순서가 앞선 모델의 키.
3. 앙상블의 정답 = 그 키를 낸 모델 중 seed 순서가 가장 앞선 모델(대표 표본)의 정답 값. 답의 결과 분해 범주(analyze_jp.classify: 잘림·U·조용한 오답·그 밖 실패)도 대표 표본의 것.
   검사: 같은 문항·같은 키인 표본들의 정답 값이 모두 같은지 센다(다르면 그 수를 보고; 규칙은 그대로).
4. PF2는 seed마다 표본 j(1–4)를 같은 j끼리 묶어 j마다 앙상블한다 → 앙상블 한 개가 k=4 표본을 갖고, 문항 값 = 4표본 평균. H-final은 k=1 그대로. CT10K·H-dev도 k=1.
5. 앙상블 지표는 단일 모델과 같은 정의: PF2 올바른 거부(50), 과잉 거부(답하는 100·근접 25), 정답률(100). H-final 정답률, 과잉 거부율(= 앙상블 거부), 결과 분해(analyze_jp 범주 8개),
   도구 유형별 정답률(`common_pf2.TYPE_BY_TOOL`), template_group 붕괴 수(30문항 이상 그룹 중 앙상블 그룹 정답률 < base 그룹 정답률 − 20%p·− 30%p, base = 두 회차 평균; analyze_j와 같은 정의).

### A3. 계산

1. 구성별 전체 seed 앙상블: SFT(5)·RR(5)·RR+NM4(5)·RR+NM8(3). PF2·H-final 위 지표.
2. n=3 앙상블: seed 5개 구성(SFT·RR·RR+NM4)은 3개 조합 10가지 모두 → 지표마다 조합 평균·최소·최대(점추정). RR+NM8은 조합 하나(= 전체).
3. 재현 확인: CT10K·H-dev에 같은 규칙. 셀이 3개 이상(seed 3개 이상)인 구성은 RR+NM4(V4) 하나:
   - CT10K 6 seed = `client_test_10000/cells/ct10k_v4_{o43,o1016,o7}_c1–c5_s1` + `ablation_012/cells/ct10k_a0_{o1102,o211102,o2026113}_c1–c5_s1`(A0 = V4 데이터 그대로 다른 순서 seed). base = `ct10k_base_c1–c5_s1–3`(3회차 평균).
   - H-dev 6 seed = `ablation_012/cells/hdev_v4_{o43,o1016,o7}_s1` + `hdev_a0_{o1102,o211102,o2026113}_s1`. base = `hdev_base_s1·s2`. gold `ablation_012/e2/h_dev.yaml`.
   - seed 순서 = 위 나열 순서. 지표: 정답률·과잉 거부율, 전체 6 앙상블과 3개 조합 20가지의 평균·범위, 단일 평균, base.
   - 지시에 적힌 수(6 seed)를 따른다. 같은 V4 데이터의 다른 A0 seed(ablation_013 `hdev_a0_o2026117·o2026131`, topic2 `ct10k_t2_a0_*`)는 넣지 않는다(보고에 적음).
4. 단일 모델 안의 거부 재확인(PF2만): seed마다 표본 (1,2)·(3,4)를 짝짓는다. 첫 표본이 거부가 아니면 첫 표본 결과. 첫 표본이 거부면 둘째 표본을 보고,
   둘 다 거부일 때만 거부, 아니면 둘째(거부하지 않은) 표본의 결과. → seed마다 문항당 2표본, 같은 지표. 구성별 seed 평균(U1 CI)과 단일(4표본) 평균을 나란히. 호출 수 = 실제로 본 표본의 호출 합.
5. CI: 앙상블은 seed 집합이 고정이므로 문항만 bootstrap 10,000회(`analyze_j.boot`, 1×n 행렬 → seed 재추출 없음, 문항 번호는 모든 arm 공유, 통계량마다 `default_rng(20261109)`).
   단일 모델 seed 평균은 J·JP와 같은 U1(문항 + arm별 seed 재추출). 차이: 각 앙상블 − SFT 단일 평균, − SFT 앙상블, − base(지표 6개: PF2 4 + H-final 정답률·과잉 거부).
   앙상블 − 자기 구성 단일 평균도 같이 낸다(보고용).
6. 비용: 앙상블의 문항당 LLM 호출 = 모델별 `hf_calls` 수의 합(PF2는 j마다, 문항·j 평균). 병렬 호출 가정 응답 시간 = 문항마다 모델별 wall(started→finished)의 최댓값, 그 p50·p95.
   단일 모델 값(모델별 호출·wall p50·p95의 평균)과 나란히. 이 wall은 측정 때 동시 요청 수(PF2 8, H-final 32)의 영향을 받은 값이며 실제 병렬 배치 시간이 아니다.

## B. RR+NM8 새 seed 4개 — GPU 4장

### B1. 학습

- 데이터: `pilot_010/build/V8/full/sft_train.jsonl` 그대로(2,071레코드, sha256 `5f830f36…`, 질문 목록 `3878a2e7…`, 선택 단계와 같은 파일). 다시 빌드하지 않는다.
- recipe·wrapper·프롬프트·thinking은 J 단계와 같다: R1''(1 epoch, lr 2e-4 → 0 linear, batch 1·accum 1, warmup 1, LoRA r16/α32/0.05·7 모듈, 12,288), 모델 seed 43(`seed`·`data_seed`),
  bf16, thinking ON(`by_source`), 프롬프트 87048d0c, grounding_target full(791c4a68), `expandable_segments:True`, `pilot_007/train/train_b7b.py`. 쓰는 checkpoint = epoch 끝 `checkpoint-2071`.
- 순서 seed 4개(`build/pick_seeds_jq.py` → `build/seeds_jq.json`): `default_rng(20261119).integers(1_000_000, 10_000_000)`을 차례로 뽑아 저장소 전체 `git grep -w -l` 0건인 값 앞에서 4개
  = **3110380 · 1821915 · 5415284 · 3616422**(뽑은 첫 4개가 모두 0건, HEAD `a4e390ca`).
- 순서 파일 `build/V8/order_b2_o<seed>.json`(`build/make_orders_jq.py`: seed 43 재현 바이트 일치, 최대 연속 2 ≤ 4). config `train/configs_jq/JQ-V8-o<seed>.yaml`
  (`train/make_jq_configs.py`: `configs_s10/S-V8-o43.yaml`에서 순서 seed·순서 파일·출력만 바꿈 — J의 `make_j_configs.py`와 같은 키). CPU dry-run 4개 통과(`configs_jq/dryrun.log`).
- 출력 `/data/hwkim/sftdpo_work/pilot_010/train_jq/JQ-V8-o<seed>`(커밋하지 않음, sha256만 기록).
- GPU마다 하나씩 한 바퀴(4장 동시). 실패(OOM·NaN·비정상 종료)는 같은 seed·config로 한 번만 다시 한다(scheduler19 `-retry`, 실패 출력 `.failed1`). 또 실패하면 그 seed 없이 진행하고 보고한다.

### B2. GPU

- 4장 모두 쓴다: 0 `GPU-2445b100…`, 1 `GPU-a5ce83d0…`, 2 `GPU-c8f1bae2…`, 3 `GPU-48f798cc…`. 결정 83 장치 간 바이트 일치 검사는 이번 작업에서 면제(결정 269; JP device_check에서 같은 GPU끼리도 불일치).
- 시작 전 기록 `gpu/JQ/gpu_precheck.txt`: UUID·모델·드라이버·메모리·다른 프로세스·Ollama 컨테이너 유무(건드리지 않음). 학습 전 torch UUID 확인(scheduler19 preflight).
- 결정 114: 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/JQ/timeline.jsonl`. 스케줄러 `gpu/scheduler19.py`(scheduler18 사본, 기록 위치만 다름). 새 작업 시작 마감 `--deadline` 2026-11-20T21:00+09:00.

### B3. 측정(J 셀과 같은 프로토콜·규칙)

| 작업 | 셋 | k·회차 seed | 동시 | 다시 돌리기 | 셀 |
|---|---|---|---|---|---|
| PF-V8-o<seed> (prio 10–13) | PF2 150 | k=4, 20261101–04 | 8 | 없음 | 저장소 밖 700 `protected_final_v2/cells/pf2_v8_o<seed>_s<k>` |
| HF-V8-o<seed> (prio 20–23) | H-final 3,000 | k=1, 20261101 | 32 | 잘림 > 1% 같은 seed 한 번 | `cells/JQ/hfinal_v8_o<seed>_s1` |

- PROTOCOL_v5: vLLM 0.30.0 BF16, flashinfer, LoRA 비병합(rank 16), 17,408, `--sealed`, PF2 기준일 2026-10-26. 실행기 `protected_final_v2/run_cell_pf2.py`·`pilot_006_prep/gpu_data/run_cell6x.py`
  (도구 커밋 `19d91001`과 같은 파일, FREEZE_JQ에 sha256). 작업 표 `gpu/make_jobs_jq.py` → `gpu/JQ/jobs_jq.json`(모든 작업 `commit` = 고정 커밋).
- PF2 접근은 `pilot_009/protected_final_v2/access_log.md`에 적고 내용은 열지 않는다. 셀 유효성은 `results/validity_j.py`(개수·해시 접두·코드만).
- 무효 측정(실행 조건 위반)은 사유를 적고 같은 조건으로 교체할 수 있다. 결과를 본 뒤의 다시 측정은 하지 않는다.

### B4. 분석(`results/analyze_jq.py`의 B 부분)

- 새 4 seed의 P1–P4(+ H-final 과잉 거부): seed 평균, U1 bootstrap 10,000(J·JP와 같음).
- 차이: 새 4 − SFT, − base, − RR, − RR+NM4, 그리고 새 4 − 기존 RR+NM8 3(기술).
- 표: 기존 3 seed와 새 4 seed를 나란히(seed별 값), 7 seed를 합친 값(한 arm, 7 seed U1)과 7 seed − SFT·− base·− RR·− RR+NM4.
- 앙상블(A 규칙): 새 4 seed 앙상블(n=4, 거부 ≥ 3), 7 seed 앙상블(n=7, 거부 ≥ 4). A3.5와 같은 차이.

## 보고 — `results/JQ_RESULTS.md`, 수치 원본 `results/jq_ensemble.json`(A)·`results/jq_v8new.json`(B)

표 (1) 구성별 단일 평균 대 앙상블 (2) 차이와 CI (3) n=3 조합의 범위 (4) CT10K·H-dev 재현 (5) 거부 재확인 규칙 (6) RR+NM8 새 seed 대 기존 seed (7) 비용.
A는 계산이 끝나는 대로 먼저 보고한다(B를 기다리지 않음). 계획과 달라진 점·소요 시간을 모두 적는다. 작업 단위마다 검증 → 커밋 → push → SHA.

## 계획 단계에서 이미 달라진 점

1. 순서 seed 범위: 처음 `integers(100, 100000)`으로 시작했으나 5자리 값 대부분이 저장소에 이미 있어(시험한 5자리 값 8개 모두 1건 이상) 값을 고르기 전에 멈추고 7자리 범위로 바꿨다. 결과와 무관하다.
