# pilot_010 JG 계획 — 운영 조건(결정적 디코딩)에서 봉인 셋 다시 재기, 결정 270

**판정 뒤 추가(사후)이며 PF2·H-final의 세 번째 사용이다.** 판정 단계(결정 267)·사후 측정(결정 268)·JQ(결정 269) 결과를 본 뒤에 정했다. C1–C4 판정은 바꾸지 않는다.
평가만 한다. 새 학습·새 데이터·새 구성·Ollama 작업·X4 분석·논문 수정은 없다. 이 수치로 구성·seed·checkpoint를 고르지 않는다.
이 계획(규칙·분석 스크립트 전부)은 측정 전에 커밋한다. 결과를 본 뒤 조건·규칙을 바꾸지 않고, 결과가 나빠도 그대로 보고한다. 모든 문서·표에 "판정 뒤 추가(사후), PF2·H-final 세 번째 사용"을 적는다.

## 0. 배경과 조건

지금까지의 J·JP·JQ 셀은 모두 sampling(temperature 0.6, top-p 0.95, top-k 20, min-p 0, repetition penalty 1, 호출마다 seed)이다. 실제 운영은 greedy다(결정 97의 기록).
조건은 하나만 미리 정한다. 여러 temperature를 재고 고르지 않는다.

| 이름 | decoding | PF2 | H-final | 실행기 |
|---|---|---|---|---|
| **G0(주 조건)** | temperature 0(greedy): client가 sampling 인자·seed 없이 `temperature: 0.0` 요청 | k=1 | k=1 | 기존 `run_cell_pf2.py`·`run_cell6x.py` + `--greedy`(이미 있는 인자, 결정 162 진단 셀과 같은 경로) |
| G1(대체) | temperature 0.2, top-p 0.95, top-k 20, min-p 0, repetition penalty 1, 호출 seed 규칙 그대로 | k=4(회차 20261101–04) | k=1(회차 20261101) | 사본 `run_cell_pf2_g1.py`·`run_cell6x_g1.py`(바꾼 것 = temperature 값 하나) |

그 밖은 기존 셀과 같다: 프롬프트 87048d0c, thinking ON, grounding_target full(791c4a68), max_new_tokens 8,192·서버 17,408, vLLM 0.30.0 BF16·flashinfer·LoRA 비병합(rank 16, 서버 하나에 어댑터 하나),
동시 요청 PF2 8·H-final/H-dev 32, PF2 기준일 2026-10-26, `--sealed`(PF2·H-final), 하네스 `pilot_005/vllm_eval_thinking5.py`·`protected_final_v2/vllm_eval_pf2.py`.

구성 이름(JQ와 같음): SFT = B2 F, RR = P9, RR+NM4 = V4(J), RR+NM8 = V8(S 3 + JQ 4), base = Qwen3-8B@b968826d. seed 표기 순서 = 아래 2절 표의 순서.

## 1. 조건 확정 smoke(개발 셋, 봉인 셋을 열기 전)

- 셋: H-dev(`ablation_012/e2/h_dev.yaml`, 2,000문항) 앞 300문항(gold 순서 0–299, `CLIENT-00002` … `CLIENT-02731`). 개발 셋이라 봉인하지 않는다.
- 셀 3개, G0, k=1: base, SFT `o43`, RR+NM4 `o101`(각 구성의 seed 표기 순서 첫째). `cells/JG/smoke/hdev300g0_{base,b2f_o43,v4_o101}_s1`. 다시 돌리기 없음.
  작업 표 `gpu/JG/jobs_jg_smoke.json`(`gpu/make_jobs_jg.py --phase smoke`), 스케줄러 `gpu/scheduler20.py`.
- 잘림 비율 = 잘린 호출(`finish_reason == "length"`) / 호출 수(호출 단위, `validity_j`·`completeness_B`와 같은 정의), 반올림하지 않고 비교.
- 규칙: 세 셀 중 하나라도 (G0 잘림 비율 > 3%) 또는 (G0 잘림 비율 > 2 × 같은 모델의 기존 sampling 셀 잘림 비율)이면 **G0를 버리고 G1로 확정**. 아니면 G0로 확정.
  **정답률·거부율은 판단에 쓰지 않는다**(`results/smoke_jg.py`는 판단을 먼저 계산하고, 보고용 수치를 따로 덧붙인다).
- 비교 기준(같은 모델의 기존 sampling 셀):
  - base: `ablation_012/cells/hdev_base_s1`·`s2`의 같은 300문항(두 회차 호출을 합친 비율).
  - SFT `o43`·RR+NM4 `o101`: **같은 300문항의 H-dev sampling 셀이 저장소에 없다**(B2 F와 J-V4 seed는 H-dev를 잰 적 없음). smoke 전에 다음 대체를 정한다:
    같은 어댑터의 H-final sampling 셀(`cells/J/hfinal_b2f_o43_s1`·`hfinal_v4_o101_s1`, 3,000문항, 같은 하네스·동시 32·회차 20261101) 전체의 잘림 비율.
    문항이 다르다는 점은 보고에 적는다. 이 대체는 지시에 없는 해석이며 smoke 결과를 보기 전에 이 문서로 고정한다.
- 판단 기록 `results/jg_smoke.json`. 확정한 조건 하나를 이 문서 6절에 적고 커밋·push한 뒤에 2절로 간다. smoke 수치는 보고에만 쓴다.

## 2. 측정(확정 조건 하나)

| 구성 | 어댑터 | seed(표기 순서) | sha256 기록 |
|---|---|---|---|
| RR+NM4 | `/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o*/checkpoint-1984` | o101·o523·o2029·o31·o20271027 | `FREEZE_JP.json` |
| SFT | `/data/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o*/checkpoint-1811` | o43·o1016·o7·o11·o2027 | `pilot_007/adapters_B2.json` |
| base | 없음 | — | — |
| RR+NM8 | `pilot_010/train_s10/S-V8-o*/checkpoint-2071`(3) + `pilot_010/train_jq/JQ-V8-o*/checkpoint-2071`(4) | o43·o1016·o7·o3110380·o1821915·o5415284·o3616422 | `FREEZE_JP.json`·`train/logs_jq/adapters_jq.json` |
| RR | `/data/hwkim/sftdpo_work/pilot_009/train_p9/P9-F-o*/checkpoint-1993` | o43·o1016·o7·o11·o2027 | `FREEZE_JP.json` |

- 어댑터는 `adapter_model.safetensors` sha256이 기록과 같을 때만 쓴다(`make_jobs_jg.py`가 대조, `gpu/JG/adapters_check_<phase>.json`). 다르면 그 seed 작업을 만들지 않고 보고한다.
  계획 단계 확인(2026-11-19 KST, `make_jobs_jg.py` 시험 실행): 22개 모두 같음. 작업 표를 만들 때 다시 대조한다.
- 셋: PF2 150(거부 50, 답하는 100 중 근접 대조 25)과 H-final 3,000. G0 = PF2 k=1·H-final k=1. G1 = PF2 k=4(회차 20261101–04)·H-final k=1(회차 20261101).
- 셀: PF2 `/data/hwkim/sftdpo_work/protected_final_v2/cells/pf2<cond>_<arm>_<seed>_s<k>`(700 디렉터리, umask 077, 커밋 안 함), H-final `cells/JG/hfinal<cond>_<arm>_<seed>_s1`
  (원문 `training/generated/pilot_010/cells_raw_JG`). `<cond>` = g0 또는 g1, `<arm>` = base·b2f·p9·v4·v8.
- 잘림·다시 돌리기·유효성은 J 셀과 같다: PF2는 다시 돌리기 없음, H-final은 잘림 > 1%(`completeness_B` 반올림)면 같은 조건으로 한 번(`RJG-NN`, `RERUNS_JG.json`), 유효성 `results/validity_j.py`(개수·해시 접두·코드만).
  무효 측정(실행 조건 위반)은 사유를 적고 같은 조건으로 교체할 수 있다. 결과를 본 뒤의 다시 측정은 하지 않는다.
- PF2 접근은 `pilot_009/protected_final_v2/access_log.md`에 적고 내용은 열지 않는다.
- 우선순위(작업 표 `gpu/JG/jobs_jg_main.json`, `make_jobs_jg.py --phase main --cond <확정>`): RR+NM4·SFT·base PF2(prio 10–20) → 같은 arm H-final(30–40) → RR+NM8 PF2(50–56)·H-final(60–66) → RR PF2(70–74)·H-final(80–84).
- GPU: 4장(0 `GPU-2445b100…`, 1 `GPU-a5ce83d0…`, 2 `GPU-c8f1bae2…`, 3 `GPU-48f798cc…`). 결정 83 장치 간 바이트 일치 검사는 JQ와 같이 면제(결정 270).
  시작 전 `gpu/JG/gpu_precheck.txt`에 UUID·모델·드라이버·메모리·다른 프로세스·Ollama 컨테이너 유무(건드리지 않음)를 적는다. 결정 114: 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/JG/timeline.jsonl`.
  스케줄러 `gpu/scheduler20.py`(scheduler19 사본, 기록 위치만 다름). 새 작업 시작 마감 `--deadline` 2026-11-20T21:00+09:00.
- 예상 시간(J·JQ 기록 기준): G0 ≈ PF2 23셀 × 8분 + H-final 23셀 × 45분 ≈ 1,220 GPU분 → 4장 약 5–6시간. G1 ≈ PF2 92셀이 더해져 약 7–8시간.

## 3. 분석 — `results/analyze_jg.py --cond <확정>`(측정 전 커밋), 수치 원본 `results/jg_results.json`

- 지표(J·JP·JQ와 같음): P1 PF2 올바른 거부(50), P2 과잉 거부(답하는 100·근접 대조 25), P3 PF2 정답률(100), P4 H-final 정답률, H-final 과잉 거부.
  문항 값 = seed 안 표본 평균(G0 = 표본 1개). CI = U1 계층 bootstrap 10,000회(`analyze_j.boot`, 통계량마다 `default_rng(20261109)`, 문항 모든 arm 공유 재추출 + arm별 seed 재추출; base는 문항만).
- arm별 값·CI·seed별 값: base, SFT 5, RR 5, RR+NM4 5, RR+NM8 7, **RR+NM 12 seed**(RR+NM4 5 + RR+NM8 7을 한 arm).
- 운영 조건 안의 차이: RR+NM4 − SFT, RR+NM8(7) − SFT, RR+NM4 − base, RR+NM8(7) − base, RR+NM8(7) − RR, RR+NM4 − RR+NM8(7), RR+NM 12 − SFT·− base·− RR. 기술용 추가: SFT − base, RR − base.
  sampling 셀(J·JP·JQ)에도 같은 표(RR+NM8 7·RR+NM 12 포함)를 같은 함수로 낸다.
- 운영 − sampling(arm별): 같은 어댑터 seed끼리 차 행렬(운영 문항 값 − sampling 문항 값, sampling = PF2 k=4·base k=8, H-final k=1·base 두 회차 평균)을 U1로(문항 공유 재추출, seed는 짝째 재추출).
- 세부: 결과 분해(정답 / 거부 M·P·C / 잘림 / U / 조용한 오답 / 그 밖, `analyze_jp.classify`; H-final 3,000·PF2 답하는 100), PF2 형별(M·P·C) 올바른 거부, 근접 대조 25 과잉 거부,
  H-final 도구 유형별 정답률(`common_pf2.TYPE_BY_TOOL`), template_group 붕괴 수(30문항 이상 그룹, 같은 조건 base 대비 −20·−30%p), 문항당 호출, wall p50·p95, 셀별 잘림 호출.
- 검사: sampling 단일 seed 평균이 `jp_posthoc.json`과 같은지(`analyze_jq.check_against_jp`, 다르면 멈춤).

## 4. 보고 — `results/JG_RESULTS.md` + `results/jg_results.json`·`results/jg_smoke.json`

맨 앞: smoke 결과와 조건 확정 근거. 표 (1) arm별 운영 조건 결과 (2) 운영 조건 안의 차이 (3) 운영 조건 대 sampling (4) 결과 분해·형별·유형별 (5) 비용.
계획과 달라진 점, 소요 시간. 작업 단위마다 검증 → 커밋 → push → SHA.

## 5. 계획 단계에서 이미 정한 해석·달라진 점

1. smoke 비교 기준: SFT `o43`·RR+NM4 `o101`은 같은 300문항의 기존 sampling 셀이 없어 같은 어댑터의 H-final sampling 셀(3,000문항) 잘림 비율로 대체한다(1절). smoke 전에 정함.
2. G1 실행기는 기존 파일을 고치지 않고 사본 두 개(`*_g1.py`, temperature 한 값만 다름)로 만든다(규칙 15). G0이 확정되면 쓰지 않는다.
3. 기술용 차이 SFT − base·RR − base를 더 낸다(지시의 차이 목록은 그대로).

## 6. 조건 확정(smoke 뒤에 적음)

(smoke 전: 비어 있음)
