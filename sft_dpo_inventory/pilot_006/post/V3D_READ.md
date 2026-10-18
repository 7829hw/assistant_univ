# T-v3d(teacher 지시 v3d smoke) 결과와 읽기 검사 — 판정 아님(결정 164), trace는 학습에 쓰지 않음

실행: 2026-10-18 15:36–16:06, Ollama 0.40.6, `qwen3.8:27b`(digest `aaee06c3…`), Ollama GPU 48f798cc, 문항 (v) 20 × 표본 8 = 160, seed_base 20261916.
지시 `grounding/prompts/teacher_neutral_v3d.md`(sha256 `31371e0c…`, 커밋 `09c4eb4`, smoke 뒤 고치지 않음). 원문 `training/generated/pilot_006/teacher_tv3d/traces.jsonl`.
결정 55: precheck 통과(컨테이너가 48f798cc를 봄, 0.40.6, 다른 모델·프로세스 없음), 첫 기록에서 100% GPU, 최저 생성 속도 72.2 tok/s(guard 33.71, 느린 호출 0).
도구: `post/tv3d/`(`tv3d_summary.json`, `tv3d_analysis.json`, `tv3d_read_sample.json`, `tv3d_extra_checks.json`).

## 1. 자동 검사

| | v3d (T-v3d) | v3c (T0c, 참고: 0.40.3·다른 20문항) |
|---|---:|---:|
| trace 통과 (a)∧(b)∧¬(c) | **132/160 (82.5%)** | 57/160 (35.6%) |
| (a) 필드 이름 없음 | 95.6% | 98.8% |
| (b) 다섯 줄 = canonical | 99.4% | 100% |
| (c) 노출 문구 | 13.1% | 64.4% |
| A2 유형 (i)/(ii)/(iii)/(iv) | 0 / **0** / 0 / 7.5% | 0.6 / 0.6 / 63.1 / 2.5% |
| 생성 token 중앙값 | 845 | 686 |

(c)에 걸린 21개 중 13개는 지시의 금지어 목록을 생각 안에서 그대로 되읊은 것("Let me make sure I don't use any forbidden words: 결론, 정답, …")이다.

## 2. 자동 검사가 못 잡은 것 — 영어 생각과 영어 노출

통과 132개를 다시 셌다(규칙은 `tv3d_extra_checks.json`):

| | v3d 통과 | v3c 통과 | v3b TEACH 통과(RC3 출처) |
|---|---:|---:|---:|
| 영어 단어 5개 이상 이어진 구간이 있음 | **90/132 (68.2%)** | 6/57 (10.5%) | 400/1,846 (21.7%) |
| 영어 글자 비율 중앙값 | **0.70** | 0.00 | 0.00 |
| 영어로 받은 줄을 가리킴("This matches the five lines provided" 등) | 30 | – | – |
| 메타 문장("Now let me write the thinking in Korean" 등) | 80 | – | – |
| 엄격 깨끗(영어 구간·영어 노출·메타 모두 없음) | **42/160 (26%), 20문항 중 12** | 51/160 (32%)* | 1,446/1,960 (74%)* |

*v3c·v3b의 "엄격 깨끗"은 영어 구간만 뺀 값(노출은 원래 (c)로 이미 걸러짐).

v3d는 "결론" 문장을 없앴지만(ii 0%), 고정된 "생각의 짜임"과 "학습자는 질문만 본다"는 틀 때문에 27b 모델이 **영어로 계획을 세운 뒤 한국어 풀이를 따로 쓰겠다고 하는** 2단계 생각을 하게 됐다.
thinking 안에 영어 분석 + (때로) 한국어 초안 + 메타 문장이 섞이고, 실제 출력(content)은 다섯 줄뿐이다. 받은 줄과 대조하는 문장도 영어로 옮겨 가 (c)를 빠져나갔다.

## 3. 읽기 검사(통과 trace 10개, `analyze_tv3d.py`의 결정적 선택)

| trace | 영어 비율 | 판단 | 메모 |
|---|---:|---|---|
| b005-39:1 | 0.80 | 못 씀 | 영어 분석, 끝에 "Let me verify against the five lines provided … All match" |
| b005-42:2 | 0.27 | 경계 | 판단은 한국어, 앞뒤가 영어("Let me break this down", "Now let me write the thinking in Korean") |
| b005-40:1 | 0.83 | 못 씀 | "But wait, the five lines say '끝: 없음'" — 받은 답에서 거꾸로 추론 |
| b005-23:1 | 0.07 | **씀** | 한국어, 짜임대로(질문 인용 → 다섯 단락), 끝·주변 근거가 질문 표현. 영어는 "rpm"뿐 |
| b005-41:1 | 0.00 | **씀** | 한국어, "승차 읍면동별"의 승차를 끝이 아닌 묶음 기준으로 정확히 따짐 |
| b005-45:1 | 0.83 | 못 씀 | 영어, "This matches the provided five lines. Good." |
| b005-44:1 | 0.89 | 못 씀 | 영어, "This matches the five lines provided." |
| b005-24:2 | 0.93 | 못 씀 | 영어(노출 문장은 없음) |
| b006-08:1 | 0.81 | 못 씀 | 영어 |
| b006-12:1 | 0.10 | 경계 | "Let me analyze this question carefully in Korean." 뒤 한국어, 끝 "이제 생각의 짜임에 맞춰 쓰자." |

씀 2 / 경계 2 / 못 씀 6. 한국어로 쓴 trace(b005-23·41)는 v3c·v3b보다 짧고 질문 표현 중심이라 질이 좋다 — 문제는 그 비율이다.

## 4. 뜻(판정 아님)

- v3d는 **"결론" 문장 문제를 풀었지만 한국어 생각 요구를 크게 깨뜨렸다.** 이대로는 teacher로 쓸 수 없다(엄격 깨끗 26%, 문항 coverage 12/20).
- pilot_007에서 teacher를 다시 모은다면 (d) **한국어 검사**(영어 단어 5개 이상 구간 없음, 영어 글자 비율 < 0.05)와 (e) **영어 노출·메타 문장 검사**를 (a)–(c)에 더해야 한다.
- v3b TEACH 통과 trace의 21.7%, RC3 teacher 레코드의 17.8%(Full 149/836)·18.7%(Partial 156/836)가 영어 비율 0.5를 넘는 영어 생각이었다(지금까지 검사에 없었음).
  그런데도 학습한 네 모델의 e1 출력 thinking은 **영어 0%**(base는 100% 영어)였고, e2에서 s43 두 모델이 4.1%·6.9% 영어로 돌아갔다.
- v3e를 만든다면 v3c(자유 형식, 한국어 생각이 지켜짐)에 v3d의 이름표 변경("[다섯 줄]")만 옮기고 "생각의 짜임"·학습자 틀은 빼는 쪽이 후보다 — 실행은 pilot_007 결정 뒤.

## 5. 기록 메모

- `analyze_tv3d.py`가 출력(`tv3d_analysis.json`, `tv3d_read_sample.json`)을 스크립트 옆(고정 worktree `wt_09c4eb4_T-v3d-run`)에 써서, main에서 같은 코드로 다시 돌려 만들었다(두 결과 `cmp` 동일).
