# pilot_010 판정 뒤 추가 측정(사후) 계획 — 결정 268

**판정 뒤 추가(사후)·기술 측정이다.** 판정 단계(결정 267, `PLAN_J.md`, `results/J_RESULTS.md`)의 C1–C4 결과를 본 뒤에 정했다. C1–C4 판정은 바꾸지 않는다.
이 수치로 변형·seed·checkpoint를 고르지 않는다. 새 학습, 데이터 변경, 새 후보의 판정, X4 분석, Ollama 작업, 논문 본문 수정은 하지 않는다.
이 계획은 측정 전에 커밋한다. 이 문서·결과 문서·표의 모든 수치에 "판정 뒤 추가(사후)"를 표시한다.

## 1. 먼저 고친 것

1. `results/J_RESULTS.md` 5절: "개발 셋·rdev v2 추가 측정은 하지 않음(PLAN_J 범위 밖으로 둠)" → D6의 선택 측정이었고 시간이 있었으나 하지 않았다고 정정(커밋 `c0dcdaa3`). 그 측정이 아래 E-A다.
2. `gpu/scheduler18.py`(커밋 `cbf4e1be`): scheduler17 사본. 다시 돌리기 작업(`RJP-NN`)이 원 작업의 `commit`을 물려받는다. 기록 위치 `gpu/JP`·`cells/JP`·`training/generated/pilot_010/cells_raw_JP`·`RERUNS_JP.json`. scheduler17은 그대로.
3. 잘림 비율 반올림 규칙(`completeness_B`: 소수 둘째 자리 반올림 뒤 `> 1.0`)은 그대로 둔다(기존 셀과 같은 동작).

## 2. GPU

- 승인 4장. 시작 전 기록 `gpu/JP/gpu_precheck.txt`(2026-11-18 14:33): 4장 모두 RTX 6000 Ada, 드라이버 595.99.02, 49,140 MiB, 사용 15 MiB, 다른 프로세스 없음, Ollama 컨테이너 없음(건드리지 않음).
  - 0 `GPU-2445b100…`, 1 `GPU-a5ce83d0…`, 2 `GPU-c8f1bae2…`(새로 추가), 3 `GPU-48f798cc…`(규칙 4의 Ollama GPU, 판정 단계에서 쓴 GPU).
- 새 GPU 장치 일치 확인(결정 83, `gpu/JP/device_check/`): valid98 앞 5문항 × base·V4_o101, 회차 seed 20261101, 기준 GPU `2445b100…` 대 새 GPU `c8f1bae2…`.
  - 1차(`run.sh`, `try1/`): 한 서버에 base·V4_o101 셀을 동시에 보내 배치 구성이 달라질 수 있는 설계라 장치 비교로 무효. 기록만 남김.
  - 2차(`run2.sh`, 동시 1·차례로, 같은 GPU 대조 ref2 포함, 판정 규칙을 측정 전 커밋 `cd7438db`): base는 ref = new, **V4_o101은 7호출 중 5호출이 다름**. 같은 GPU 대조(ref 대 ref2)도 두 모델 모두 다름.
  - 규칙대로 **새 GPU `c8f1bae2…`는 쓰지 않는다. 판정 단계와 같은 3장(`2445b100…`·`a5ce83d0…`·`48f798cc…`)으로 한다.** (참고: 이 vLLM 경로는 같은 GPU에서도 바이트 단위로 재현되지 않으므로, 결정 83 검사는 이 경로에서 통과할 수 없다.)
- 결정 114 그대로: 작업 하나 = GPU 하나, 커밋 고정 worktree, `gpu/JP/timeline.jsonl`.

## 3. 측정(평가만)

어댑터는 기록된 sha256과 같을 때만 쓴다(2026-11-18 확인: 모두 같음 — P9 5개 `pilot_009/adapters_P9.json` checkpoint-1993, V8 3개 `/data/hwkim/sftdpo_work/pilot_010/adapters_s10_sha256.txt` checkpoint-2071, V4 5개 `train_j/adapter_sha256_round{1,2}.txt`). 다르거나 없으면 그 arm을 건너뛰고 보고한다.

| 작업 | arm·seed | 셋 | k·회차 seed | 동시 | 다시 돌리기 | 셀 위치 |
|---|---|---|---|---|---|---|
| E-B PF2 (prio 10–14) | P9 o43·o1016·o7·o11·o2027(checkpoint-1993) | PF2 150 | k=4, 20261101–04 | 8 | 없음 | 저장소 밖 700 `protected_final_v2/cells`, `pf2_p9_<o>_s<k>` |
| E-C PF2 (20–22) | V8 o43·o1016·o7(S-V8, checkpoint-2071) | PF2 150 | k=4 | 8 | 없음 | 같음, `pf2_v8_<o>_s<k>` |
| E-B H-final (30–34) | P9 5 | H-final 3,000 | k=1, 20261101 | 32 | 잘림 > 1% 같은 seed 한 번 | `cells/JP/hfinal_p9_<o>_s1` |
| E-C H-final (40–42) | V8 3 | H-final 3,000 | k=1 | 32 | 같음 | `cells/JP/hfinal_v8_<o>_s1` |
| E-A (50–54) | 새 V4 o101·o523·o2029·o31·o20271027(checkpoint-1984) | refusal_dev v2·valid98·aux | 각 k=4 | 8 | PLAN_S 5절(rdev 잘림 ≥ 2·서버 오류 ≥ 2, 그 밖 > 1%) | `cells/JP/jp_v4_<o>_{rdevv2,valid98,aux}_s<k>` |

- PF2·H-final 셀은 판정 단계 J 셀과 같은 실행기·인자(PROTOCOL_v5, vLLM 0.30.0 BF16, flashinfer, LoRA 비병합, 17,408, `--sealed`, PF2 기준일 2026-10-26). E-A는 선택 단계 ES 셀과 같은 실행기(`pilot_006_prep/gpu_data/run_cell6x.py` — 선택 단계 `gpu/run_cell6x.py`의 결정 258 실행 사본)·인자.
- 작업 표 `gpu/make_jobs_jp.py` → `gpu/JP/jobs_jp.json`(모든 작업 `commit` = 도구 고정 커밋), 스케줄러 `scheduler18.py`, `--deadline` 2026-11-20T09:00+09:00.
- PF2 접근은 `pilot_009/protected_final_v2/access_log.md`에 적고 내용은 열지 않는다. 셀 유효성은 `results/validity_j.py`(개수·해시 접두·코드만).
- 무효 측정(실행 조건 위반)은 사유를 적고 같은 조건으로 교체할 수 있다. 결과를 본 뒤의 다시 측정은 하지 않는다.

## 4. 집계(GPU 없이) — `results/analyze_jp.py`

`analyze_j.py`(판정 단계, 고정)는 고치지 않고 함수(셀 읽기·채점·U1 bootstrap)를 불러 쓴다. CI = U1 계층 bootstrap 10,000회, 통계량마다 `default_rng(20261109)`.

1. arm(base·B2 F·P9·V8·V4)별 PF2 네 지표와 H-final 정답률·**H-final 과잉 거부율**(H-final 3,000은 모두 답하는 문항; 거부 = `analyze_j.sample_rows`).
2. 답하는 문항 결과 분해(H-final 3,000·PF2 답하는 100, arm별 seed 평균·seed별): 표본마다 하나, 이 순서로 먼저 맞는 범주 — 정답 → 거부 M·P·C → 잘림(호출 하나라도 `finish_reason = length`)
   → U(용납할 수 없는 실패, `compute_gates.scorer().load_sample` 등급) → 조용한 오답(U 아님) → 그 밖 실패(안전한 실패 중 거부·잘림이 아닌 것). U 안의 U1–U4 flag 족별 비율(겹침 허용)도 낸다.
3. H-final V4 − B2 F 정답률 차 분해: Δ정답 = −Σ Δ범주(전체 CI; 도구 유형·template_group별 점추정).
4. 비교(P1 올바른 거부, P2 과잉 거부 100·근접 25, P3 PF2 정답률, P4 H-final 정답률, + H-final 과잉 거부): V8 − P9, V4 − P9, V4 − V8, P9·V8·V4 − B2 F, − base.
5. 개발 셋 대 보호 셋: `gates/select_s10.py`(그대로)를 `gates/spec_jp_dev.json`(`make_spec_jp.py`: spec_s10에서 V8을 빼고 V4 셀만 E-A 셀로)에 돌려 `results/selection_jp_dev.json`.
   select_s10의 선택 판정 출력은 쓰지 않고 수치(올바른 거부·과잉 거부·개발 셋 정답률)만 읽는다. 선택 단계 3 seed(`results/selection_s10.json`: 86.48 / 2.17 / 71.81)와 나란히 둔다.
   - 측정 전 확인: select_s10을 V4 하나만 남긴 spec(선택 단계 셀)에 돌려 86.48 / 2.17 / 71.81을 그대로 재현했다.
- 측정 전 시험: `analyze_jp.py --smoke`(J 셀만)로 판정 단계 수치(V4 PF2 82.0 / 13.45 / 74.7, H-final 86.22, V4 − B2 F −3.92 [−8.09, −0.35])를 재현했다.
  이 시험에서 기존 셀의 결과 분해·H-final 과잉 거부도 함께 보았다(새 측정과 무관한 기존 셀의 기술 집계).
- PF2 P·C 거부 범주 설명은 출력하지 않는다(형 M·P·C만).

## 5. 보고 — `results/J_POSTHOC_RESULTS.md`, 수치 원본 `results/jp_posthoc.json`·`results/selection_jp_dev.json`

- 표 A: 행 base / B2 F / P9 / V8 / V4, 열 PF2 올바른 거부·과잉 거부(100·근접 25)·PF2 정답률·H-final 정답률·H-final 과잉 거부율(칸마다 seed 평균·95% CI·seed별·seed 수).
- 표 B: 4절 4의 차이와 CI. 표 C: 4절 2·3의 결과 분해. 표 D: 개발 셋 대 보호 셋. 표 E: arm별 문항당 LLM 호출·wall p50·p95·잘림 수.
- 계획과 달라진 점, 건너뛴 arm, 소요 시간을 모두 적는다. 결과가 예상과 달라도 그대로 보고한다.
- 작업 단위마다 검증 → 커밋 → push → SHA 보고.
