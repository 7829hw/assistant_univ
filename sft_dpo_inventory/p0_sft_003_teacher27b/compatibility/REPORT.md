# G3 compatibility 결과

2026-10-14. 계획 `IMPORT_AND_TEACHER_PLAN.md` G3, 보완 `G2_SUPPLEMENT.md`(결정 81). 원문 `raw/calls.jsonl`, 요약 `result.json`, 로그 `compat_run.log`.

## 1. 판정: **PASS**(10/10)

| 기준 | 통과 |
|---|---|
| 1. HTTP 200, 오류 없음 | 10/10 |
| 2. `message.thinking` 비어 있지 않음 | 10/10 |
| 3. content 비어 있지 않고 `<think>`·`</think>` 없음 | 10/10 |
| 4. `parse_planner_json`으로 JSON 객체 | 10/10 |
| 5. done_reason stop | 10/10 |
| 6. 관측한 size_vram == size(CPU fallback 없음) | 10/10 |

- 호출 전 precheck(host·컨테이너 GPU UUID `GPU-d4308fbb…`, compute 프로세스 0, 컨테이너 running restart 0, `/api/ps` 빈 상태)는 10회 모두 통과했다.
- 실제 27B 호출: 10회. 무효가 된 첫 실행 1회(`raw/ABORTED_calls_run1.jsonl`, guard 순서 오류, `G2_SUPPLEMENT.md` 7절)는 판정에 쓰지 않았다.
- `/api/ps` digest는 10회 모두 `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`이다.

## 2. 문항별

| id | done | eval_count | prompt_eval_count | tok/s | load s | thinking 글자 | 정답(참고) |
|---|---|---:|---:|---:|---:|---:|---|
| ann-d983889cf8c496178106 | stop | 810 | 6,176 | 155.13 | 6.5 | 1,924 | EXACT |
| ann-cc38d74754ba7eab68a8 | stop | 826 | 6,178 | 164.76 | 5.9 | 1,757 | EXACT |
| ann-da98b3941dfa1c7ce800 | stop | 843 | 6,182 | 152.62 | 6.0 | 1,883 | EXACT |
| ann-77e9dacb0b34a3273630 | stop | 1,143 | 6,181 | 158.56 | 6.0 | 2,964 | EXACT |
| ann-9d8392a4f8ca9ff8cfc2 | stop | 871 | 6,179 | 157.95 | 6.0 | 1,984 | EXACT |
| ann-0e4edbda1cb1bec194c1 | stop | 794 | 6,185 | 162.13 | 6.0 | 1,983 | EXACT |
| ann-0d51b49a28500bb47b0d | stop | 589 | 6,185 | 163.34 | 6.0 | 1,284 | EXACT |
| b004-05 | stop | 443 | 6,179 | 154.99 | 6.0 | 909 | EXACT |
| b004-06 | stop | 1,065 | 6,177 | 145.60 | 6.0 | 3,074 | EXACT |
| b004-15 | stop | 457 | 6,188 | 169.31 | 6.6 | 732 | EXACT |

- 정답 여부(`reference_correctness.json`, v006 target 기준 `collect_p0_traces_hf.judge`)는 참고값이다. PASS 기준이 아니다.
- `ann-da98b3941dfa1c7ce800`, `ann-0e4edbda1cb1bec194c1`은 31문항 대상과 겹친다. 이 출력은 G4·판정·학습에 쓰지 않는다.

## 3. Ollama 0.40.3 `think: true` 실측 동작

- 응답 `message` key: `role`, `content`, `thinking`. thinking은 별도 필드로 오고 content에는 think tag가 없다(PARSER qwen3.5가 분리).
- 응답 최상위 key: `created_at`, `done`, `done_reason`, `eval_count`, `eval_duration`, `load_duration`, `message`, `model`, `prompt_eval_cached_count`, `prompt_eval_count`, `prompt_eval_duration`, `total_duration`.
  - thinking 수준(low·medium·xhigh)을 알려 주는 필드는 응답에 없다. `think: true`가 어느 수준으로 매핑되는지는 관측되지 않았다. 요청은 계획대로 `think: true`만 썼다.
  - `prompt_eval_cached_count`는 새 필드다. 값은 저장하지 않았다(호출마다 unload하므로 cache 재사용은 없다고 본다).
- thinking 꼴: 영어로 질문을 항목별로 분해하고 factor 초안을 적은 뒤 "This looks correct." 식으로 끝난다. thinking 글자 수 중앙값 1,903.5, eval_count 중앙값 818.

## 4. context·num_predict

- `/api/ps` context_length: 262,144(10회 모두). 과거 기록과 같다. ≥ 16,384 조건 충족.
- num_predict는 지정하지 않았다. 10회 모두 stop으로 끝났고 최대 eval_count는 1,143이다.
- prompt_eval_count 6,176–6,188(P0 prompt).

## 5. 속도 기준(G4 guard)

- tok/s 중앙값 158.255 → **속도 기준 79.13 tok/s**(× 0.5).
- 참고: 무효가 된 첫 실행의 첫 호출은 같은 문항에서 eval_count 810, 75.16 tok/s였다(pull 직후 첫 로드). 이번 측정의 첫 호출은 155.13 tok/s다. G4에서 기준 미만이 나오면 계획대로 중단한다.
- load_duration 중앙값 6.0초(호출마다 unload·reload).
