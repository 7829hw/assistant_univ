# pilot_prep_006 — 기록 원인 분석, PROTOCOL_v3 확정, pilot_003 데이터 준비(결정 76–79)

작성: 2026-10-13. 학습 없음. prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`(작업 내내 같음). 업체 100·aux_test_v1은 평가에 쓰지 않았다
(batch006 겹침 검사의 대상으로만 읽었다). Ollama 모델을 등록하거나 지우지 않았고, 컨테이너는 건드리지 않았다.

| 작업 | 자료 | 커밋 |
|---|---|---|
| 0. 결정 R–U 기록(76–79), 결정 72–74의 바뀐 부분에 대체 표시, `CLAUDE.md` 7·9번 | `../DECISIONS.md`, `/CLAUDE.md` | `cccac56` |
| 0. 연속 측정 기본값(옵션으로 예전 격리 방식 유지) | `evaluate_vendor100.py`, `calibration_001/run_cal.sh`, `pilot_002/ollama_gpu_guard.py`, 테스트 | `5274987` |
| 1. 기록만 쓰는 원인 분석 | `../operational_gap/ANALYSIS.md`, `analysis.json` | `3862e80` |
| 2. PROTOCOL_v3 확정, Ollama 정리 목록 | `../vendor100_protocol/PROTOCOL_v3.md`(sha256 `9964cc70…`), `../ollama_cleanup_list.md` | `b86c693` |
| 3. batch006 후보·검토 시트 | `../batch006/` | `91ee4c2` |

## 0. 결정 기록과 측정 방식 변경

- 결정 76(R) 운영 경로 HF BF16, 77(S) 작업 순서, 78(T) PROTOCOL_v3 9절 확정 항목, 79(U) Ollama 연속 측정.
- 결정 72(주 비교·HF 판정 제외), 73(Ollama 선택 경로), 74(양자화 후보 규칙)에 "결정 76(R)으로 대체됨"을 붙였다.
- 연속 측정 구현: `evaluate_vendor100.py llm` 기본 `--model-state keep_loaded`, 시작할 때도 내리지 않음(`--start-unload`로 예전 keep_loaded,
  `--model-state unload_per_question`으로 격리 방식 재현). meta에 `pipeline.isolation`·`pipeline.start_unload`. `run_cal.sh`는 `ISOLATION=continuous`(기본)·`per_question`.
  guard precheck `--allow-loaded MODEL`(같은 모델만 올라가 있으면 통과). 결정 55의 생성 속도 확인은 그대로다. 테스트 1,303개 통과(skip 8, expected failure 1).
- `evaluate_v2.py`·`evaluate_prompt_ab.py`는 관측마다 모델을 내리는 예전 harness로 남겼다(`CLAUDE.md` 7번에 새 셀에 쓰지 않는다고 적음).

## 1. 기록만 쓰는 원인 분석(`../operational_gap/ANALYSIS.md`)

- **HF와 Ollama 학습 모델의 차이는 응답 처리 단계가 아니라 모델 출력의 차이다 — 확인됨.**
  분류 밖 오답 HF-final 29 대 (e) 52·F-off 49. 그 증가분에서 thinking 분리 문제·잘림·JSON 형식 오류는 0건이고, 계약 밖 필드는 셀마다 1–4건으로 경로와 무관했다.
  늘어난 몫은 형식이 맞고 계약 안의 값으로 뜻이 다른 출력(검증 실패, 오답, 확인 요청)이며 오류 코드 11가지에 퍼져 있다.
- 같은 경로 base와 비교: Q8_0 base는 HF base와 같다(30 대 32). Q4 base는 base부터 늘어난다(48–67). 최종 모델만 Q8에서 떨어지는 이유는 **미확인**.
- 조용한 오답: HF-base 1.50% → HF-최종 2.00%, 차이 +0.50 [−0.75, 2.00](selection_v1), +0.51 [−0.77, 2.04](selection_v2). 대부분 aggregation_spec.

## 2. PROTOCOL_v3 확정(`../vendor100_protocol/PROTOCOL_v3.md`)

- 상태 "확정(2026-10-12, 사용자)". 운영 경로 HF BF16, 주 비교 HF-base → HF-최종(업체 100, k=8), E는 연속 방식 참고 셀(판정 안 함).
- checkpoint 선택: HF BF16, selection_v2, k=4, 단계마다 2개. 중단 규칙(결정 73)은 HF-base → checkpoint CI 하한 > 0. 지연 기준은 HF-base 대비 1.5배.
- aux_test_v1 k=4 보고. 업체 100에서 SFT 참고 셀·추가 HF 참고 셀·Ollama 등록 모델은 재지 않는다.
- "확정 시 참고": HF 경로 조용한 오답 비율이 낮아(1.5–2.0%) 문항 몇 개로 CI 하한이 0을 넘을 수 있다는 점, 대부분 aggregation_spec이라는 점. 규칙은 바꾸지 않았다.
- 예상 시간: 선택 약 19시간, 업체 100 판정·참고 약 18시간, aux 약 4.4시간(GPU 하나, 순차).
- Ollama 정리 목록(`../ollama_cleanup_list.md`): 결정 78 대상 9개(회수 약 48.0 GB). B-conv(base 변환본)는 결정 78의 목록에 이름이 없어 따로 적었다. **지운 것 없음.**

## 3. pilot_003 데이터 준비(`../batch006/README.md`)

- 결정 66 대조 묶음 28건(의도 7 × 실차 통행량·공차 통행량·상태 없는 통행량·실차 건수). 묶음 기준은 시군구·H3·H3+근처.
  묶음 없는 통행량(h30과 같은 형태)·읍면동별·순위 통행량은 보호 family라 만들지 않았다. family 지문은 taxi_status를 보지 않는다.
- 겹침 검사(thor leakage, 확장, selection_v1·v2·aux_test_v1·valid98·업체 100 셋별, 업체 100 문자 3-gram ≥ 0.5): 걸린 후보 0, 3-gram 최댓값 0.40.
- 현재 코드: 28건 모두 답, 계약·compile 통과, 조건 계층이 뜻을 바꾼 후보 0.
- HF base(GPU 3, thinking 켬, greedy, 8192): 초안과 같음 4/28. **실차 통행량 0/7**(trip_count로 읽음 3, 상태 없는 passage_count 4). 질문에 없는 `sum` 13건.
  DPO rejected 후보 24, 그중 결정 6 표시 4(조건 계층 뒤 같아짐).
- 검토 시트: queue 52행(SFT gold 28, DPO 쌍 24), XLSX(커밋 안 함), 한국어 검토 안내. 응답 원문은 ignore 경로. trace 수집·import 없음.

## 4. pilot_003 전에 남은 일

1. **사용자의 batch006 검토**: 28건 초안과 24쌍. 특히 실차 통행량의 정답 형태(결정 62·66), 날짜 표기(월 대 범위), 한 장소 both 대 두 장소.
2. **승인분 trace 수집**(결정 45 방식, 승인 뒤에만).
3. **데이터 구성**: batch006 승인분을 pilot_002 corpus(v005)에 더하는 방법과 비율, 결정 65·71 기준의 학습 데이터 검사.
4. **학습 계획 고정**: 단계별 checkpoint 2개를 학습 config에 미리 적기(PROTOCOL_v3 7절), 학습 여부는 원인 분석 결과를 보고 정한다(결정 77).
5. **운영 서빙 방식의 별도 결정**(결정 76): 실제 배포의 서빙 엔진과 CLI 연결. 정해지면 HF BF16과의 차이를 따로 잰다.
6. 사용자 승인 뒤 Ollama 정리(`../ollama_cleanup_list.md`), B-conv 처리 여부.
