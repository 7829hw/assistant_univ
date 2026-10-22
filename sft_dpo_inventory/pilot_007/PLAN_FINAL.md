# pilot_007 최종 판정 계획(측정 전 고정) — 후보 F를 protected_final_v1로 base와 한 번 비교

결정 211–216(V1–V6). 이 문서와 `FREEZE_FINAL.json`이 측정 전에 커밋된다. 결과를 본 뒤 후보·채점 규칙·판정 규칙을 바꾸지 않는다. 측정은 한 번뿐이다(SPEC 1절).

## 1. 후보(결정 211·212)

- **F를 후보로 지정한 것은 PLAN_B2 사전 규칙과 다른 사용자 결정이다**(PLAN_B2 채택 규칙으로는 후보 없음; F 선행 하한 −0.14, 다시 돌리기 전 원래 셀로는 +0.04).
- 후보 = **B2-F-o11**(R1'', O4' 순서 seed 11, 모델 seed 43, `checkpoint-1811`), 개발 셋 평균(valid98·aux 149문항 가중) 73.15로 다섯 중 최대(`analysis/select_final.json`).
  adapter `/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811`, `adapter_model.safetensors` sha256 `2d94933b5756c769c1b1068a6003540fd92d64ab7717b1fc4ea6793ef78574f2`.
- 주 셋·protected_final_v1은 고르는 데 쓰지 않았다.

## 2. 셋(결정 215)

- protected_final_v1(manifest 커밋 `2fb30fa`, xlsx sha256 `5a43e8d0…`, 120문항: 7유형 110 + 거부 10). 측정 직전 확인: 원격 manifest·sha256 같음·validate ok(`session_final_check.txt`).
- 평가 gold: `final/convert_pf_gold.py` → `/home/hwkim/sftdpo_work/protected_final_v1/pf1_gold.yaml`(600) sha256 `8ee5e10ea86bf1d2bfd6553aa4d5bcc38a5c3c9b671ef566c6ad3cb0d28fdcd5`,
  문항 메타 `pf1_items_meta.json`(유형·hard factor·난이도·거부, 600) sha256 `5ef54e882caee847ae9686287493adbf565e273f0027b48871dc5ff88821b0d4`.
  변환 확인: 120문항, 거부 10, 거부 아닌 110문항 모두 gold 파이프라인 mock = match·`grounding_check` 참(validate.py와 같은 방법).
- 문항 id `pf1/<번호 3자리>`. 거부 문항은 `gold: []`·`expected_outcome: unsupported`(작성 지침: 지원하지 않는 질문).

## 3. 셀(결정 214·216, `gpu/jobs_final.json`, `final/make_jobs_final.py`)

| 셀 | 대상 | 서버 | 셋 | k | GPU |
|---|---|---|---|---|---|
| PF-base | vLLM-base, Full prompt | `b17408` | protected_final_v1 120 | 8 | GPU 0 또는 1 |
| PF-cand | B2-F-o11(LoRA `B2_F_o11`, 비병합) | `lora:` | protected_final_v1 120 | 8 | 다른 한 장 |
| L-final | base → 후보, 고정 30문항 순차(동시 1) | `lora:F=…` | `serving_vllm_fp8/latency_ids.txt`(protected 아님) | 1 | 한 장, 다른 두 장 빔 |

- PROTOCOL_v5 경로: vLLM 0.30.0 BF16, flashinfer(attention·sampler, 셀 meta `vllm.kernels`), LoRA 비병합, 동시 요청 8, `--max-model-len` 17,408(결정 117),
  PROTOCOL_v4 3절 sampling(temperature 0.6, top_p 0.95, top_k 20, min_p 0, max_tokens 8192), thinking on. 셀 실행기 `pilot_006_prep/gpu/run_cell6x.py`(`--sealed`).
- sampling seed(`final/cell_seeds_final.json`): 두 셀 모두 회차 S_k = 20261100 + k(k = 1…8), 호출 seed = `EV.call_seed(S_k, 문항 id, 호출 번호)`. 지연 셀 회차 20261101.
- 스케줄러 `gpu/scheduler8.py`, `--gpus` GPU 0·1(`2445b100…`, `a5ce83d0…`), `--ollama-uuid` GPU 2(`48f798cc…`, worker 아님). 작업 하나 = GPU 하나, 고정 commit worktree, timeline 기록.
- 저장(결정 215): 셀 json·원문·실행 출력은 `/home/hwkim/sftdpo_work/protected_final_v1/{cells,raw,logs}`(700) 안 600(`umask 077`). 저장소의 작업 로그(`gpu/PF-*.log`)에는 내용이 없다.
- 재측정 없음. 실행 조건 위반(flashinfer 미사용, 장치 확인 실패, 서버 장애 등)으로 무효인 셀만 결과를 보기 전에 이유를 기록하고 처음부터 한 번 다시. 또 무효면 멈춤.
  B2의 잘림 1% 다시 돌리기 규칙은 쓰지 않는다 — 잘림은 그대로 채점하고 건수만 보고.

## 4. 채점(결정 214, `final/final_score.py`, 시험 `tests/test_final_score.py`)

```python
REFUSAL_OUTCOMES = ("unsupported", "needs_clarification")   # 기존 분류 refused_unsupported·refused_clarification의 결과 상태


def final_ok(is_refusal_item, grounding_ok, outcome, analysis_calls):
    refused = outcome in REFUSAL_OUTCOMES
    if is_refusal_item:                       # 거부 문항: 분석 tool을 실행하지 않고 거부로 끝나면 정답
        return bool(refused and analysis_calls == 0)
    return bool(grounding_ok is True and not refused)   # 거부 아닌 문항: 기존 grounding_ok, 거부로 끝나면 오답(과잉 거부)
```

- `grounding_ok` = `analyze_cal.load_sample`의 `EV.grounding_check`(pilot_006 판정과 같은 견고성 패치). `analysis_calls` = 실행된 호출 중 `get_place_scope`가 아닌 것의 수.
- U·조용한 오답 = 기존 `report_class`(U = "용납할 수 없는 실패", 조용한 오답 = "조용한 오답(U 아님)"). U 분류기의 원본 gold는 프로세스 안에서 `pf1` 셋으로 등록.

## 5. 판정(결정 214 = PROTOCOL_v4 6절, v3 6절 포함)

- 문항 값 = k=8 표본 평균(정답, U, 조용한 오답). d = 후보 − base. 95% CI = 문항 단위 쌍 bootstrap 10,000회, 비교마다 새 `numpy.random.default_rng(20261109)`(`compute_gates.ci`).
- **개선**(모두): 정답률 차 CI 하한 > 0, U 차 CI 하한 ≤ 0, 조용한 오답 차 CI 하한 ≤ 0, 지연 비 ≤ 1.5.
- **악화**(하나라도): 정답률 차 CI 상한 < 0, U 차 CI 하한 > 0, 조용한 오답 차 CI 하한 > 0, 지연 비 > 1.5.
- **차이 없음**: 그 밖 — "이 셋·k에서 구분되지 않는다". CI가 0을 포함하면 그대로 보고하고 기준은 바꾸지 않는다.
- 지연 비 = L-final의 문항 모델 시간 중앙값(`compute_gates.latency`) 후보 / base. 정답률 셀(동시 요청)의 시간은 판정에 쓰지 않는다.
- 판정은 이 비교 하나. 보정·재측정·부분 재사용 없음. 측정 뒤 protected_final_v1은 끝난다(다시 쓰지 않음).

## 6. 보고 형식(수치만, 결정 215)

- `results/final_judgment.json`(집계)·`results/final_items.json`(문항 번호별 k=8 정답·U·조용한 오답·잘림·거부 값, 문장 없음)·`results/FINAL_RESULTS.md`.
- 정답률·U·조용한 오답(base, 후보, 차이 [CI]), 지연 비, 결론 범주; 유형(8)·hard factor·난이도별 정답률; 거부(올바른 거부·과잉 거부); 완료성(행 수·sha256·잘림·서버 오류);
  vicinity 빠짐(PROTOCOL_v4 7절, 판정에 안 씀); 생성 속도; 요청 로그 요약; 안정 정답 문항 수; GPU 작업 표·사용률.
- 질문 문장·정답 호출·모델 응답은 저장소·보고·대화에 옮기지 않는다. access_log.md에 변환·측정·판정을 한 줄씩.
