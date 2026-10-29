# client_test_10000 결과 — pilot_010 V4, 10,000문항 k=1(결정 259)

요약 도구 `summarize_ct10k.py` → `results_ct10k.json`. 셀 `cells/ct10k_v4_<seed>_c<1-5>_s1.json`, 원문 `training/generated/client_test_10000/raw/`.
측정 2026-10-29 14:34–17:06, 고정 커밋 `1150688a`, 작업 하나 = GPU 하나(`gpu/timeline.jsonl`). 3작업 모두 status ok, 묶음 15/15, 서버 오류·실패 묶음 0.

## 1. 정답률(category == match, 10,000문항 모두 답이 있는 문항)

| seed | GPU | 정답 | 정답률 % | grounding_ok | 답했으나 틀림 | 실패(오류) | 거부(지원 안 함) | 잘림 호출 / LLM 호출 | wall(5묶음) |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| o43 | 0 `2445b100` | 8,594 | **85.94** | 8,416 | 614 | 680 | 112 | 43 / 10,111 | 2h26m |
| o1016 | 1 `a5ce83d0` | 9,423 | **94.23** | 9,318 | 248 | 160 | 169 | 42 / 10,137 | 2h19m |
| o7 | 2 `48f798cc` | 9,384 | **93.84** | 9,305 | 330 | 138 | 148 | 75 / 10,142 | 2h28m |
| 평균 | – | – | **91.34** | – | – | – | – | – | – |

- 세 seed 모두 맞힌 문항 7,911, 하나라도 맞힌 문항 9,958.
- 묶음별 정답률(2,000문항씩): o43 86.2·85.8·85.4·86.3·86.0 / o1016 94.8·93.5·94.4·93.6·94.9 / o7 93.8·94.2·93.2·94.0·94.0 — 시간에 따른 변화 없음.
- 거부 112–169건은 모두 답이 있는 문항에 대한 과잉 거부다(이 셋에는 거부가 정답인 문항이 없다).

## 2. 나눠 본 정답률 %

| seed | independent (3,749) | vendor100_date_variant (5,272) | train_skeleton (967) | verbatim_vendor100 (12) | client_qa (1,653) | synthetic_qa (8,347) |
|---|---:|---:|---:|---:|---:|---:|
| o43 | 85.28 | 85.47 | 91.21 | 75.00 | 86.15 | 85.90 |
| o1016 | 93.65 | 94.21 | 96.48 | 100.00 | 94.80 | 94.12 |
| o7 | 94.03 | 93.17 | 96.79 | 91.67 | 93.77 | 93.85 |

## 3. 오류 코드(많은 순)

- o43: AMBIGUOUS_PORT 303 · UNUSED_CONCEPT 204 · INVALID_FACTOR 120 · UNCONSUMED_CONDITION 68 · UNSUPPORTED_QUESTION 30 · JSON_PARSE_FAILED 21 · …
- o1016: AMBIGUOUS_PORT 124 · UNSUPPORTED_QUESTION 115 · NO_OPERATOR 46 · …
- o7: UNSUPPORTED_QUESTION 134 · NOT_FOUND 55 · AMBIGUOUS_PORT 39 · UNUSED_CONCEPT 22 · …

## 4. o43이 낮은 이유(진단, 판정 아님)

o43만 틀리고 o1016은 맞힌 문항 1,173개가 특정 문항 유형(template_group)에 몰려 있다.
- "〇〇 소속 택시의 평균·최대·최소 요금" 유형: 소속 지역(place)을 grounding에서 빠뜨리거나(`places` 차이) INVALID_FACTOR. 예: `synthetic-family-1c3cb876…` 174문항 중 109, `…449f5bf2…` 177 중 102, `…6c262dd5…` 91 중 77.
- 지역 간 OD 상위 N 유형: 출발지 역할을 `pickup` 대신 `both`로 둬 UNUSED_CONCEPT(`…cd5fe2f2…` 85 중 52).
묶음별로 고르게 낮으므로 서버·측정 문제가 아니라 seed adapter의 차이로 본다. pilot_010 개발 셋에서도 o43(70.97%)은 o1016(74.50%)보다 낮았다.

## 5. 정답 확인과 측정 기록

- 정답 호출을 그대로 pipeline에 넣은 확인(`evaluate_vendor100.py --gold … gold`, CPU): 10,000/10,000 match(`gold_check.json`). 채점기가 모든 문항을 처리할 수 있다.
- 서버 기동 때 세 GPU 모두 `gpu_ok` 통과(used 2 MiB, 다른 프로세스 0, Ollama 모델 0; `gpu/gpu_check.txt`).
  `serve7.sh`가 기록 위치(P3)를 pilot_007/gpu로 고정하고 있어 그 줄이 `pilot_007/gpu/runs.log`·`gpu_check.txt`에 덧붙었다. 그 줄은 `gpu/serve_runs.log`·`gpu/gpu_check.txt`로 옮기고 pilot_007 파일은 커밋된 내용으로 되돌렸다.
- Ollama 컨테이너는 14:34:57에 사람이 내렸다(Docker 이벤트 kill → stop → destroy, `ollama_default` 네트워크 삭제). 이 테스트는 vLLM만 쓰므로 측정에는 영향이 없다. 컨테이너에는 손대지 않았다.
- 동시 요청 32(pilot_010 셀은 8). 이 값은 pilot_010 셀과 비교하지 않는다.
