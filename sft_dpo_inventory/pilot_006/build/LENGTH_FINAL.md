# 학습 길이 최종(C11, 결정 125 F4)

2026-10-16, 세션 2. 모델 호출 없음. 계산: `length_final.py` → `length_final.json`, 빌드: `build6.py --mode provisional --with-j6 --max-seq-length 12288`
→ `PROVISIONAL_L12288/`(학습에 쓰지 않음). 이 디렉터리에는 `lengths.json`·`build_summary.json`·manifest만 남겼다(`sft_train.jsonl`은 `PROVISIONAL`과 sha256이 같아 지움, manifest의 `output_hashes`로 확인).

## 결론: 규칙 3, `max_seq_length = 12,288`(두 arm 같음)

| 단계 | 값 |
|---|---|
| 규칙 1 `L_req`(J6 포함 모든 후보) | **12,800**(최대 12,701 = Partial J6 정답 표본 `aug300-340:sample:1`) |
| 규칙 2 M1 `L_req` 12,800 | Full 42.91 GiB, **Partial 46.05 GiB(47,158 MiB) > 46.0 GiB** → 넘음 |
| 규칙 3 M1b 12,288(12,288 이하 가장 긴 10개) | Full 42.91 GiB, Partial 43.90 GiB(44,956 MiB) → **통과**, step 7.5초(Full)·8.3초(Partial) |
| 적용 | 두 arm 모두 `max_seq_length = 12,288`. 12,288을 넘는 레코드는 규칙 4(B')처럼 뺀다 |

GiB 기준(pilot_004 peak 43,900 MiB를 "약 44 GB"로 적은 것과 같은 단위)은 `m1_result_v2.json`. 첫 M1 기록(`m1_result.json`)은 decimal GB·torch 0 결함이 있어 v2로 대신한다.

## 12,288을 넘는 레코드와 질문(B' 처리 대상)

| 후보 | 개수 | 12,288 초과 |
|---|---:|---:|
| Full teacher(pilot_004 판) | 247 | 0 |
| Full 8b 자체(pilot_004 판) | 289 | 0 |
| Full J1 정답 표본 전부 | 1,730 | 0 |
| Partial teacher(pilot_004 판 thinking + Partial 렌더) | 247 | 0 |
| Partial 8b 자체(시험 빌드에 들어간 J6) | 54 | 0 |
| Partial J6 정답 표본 전부 | 1,668 | **2**(`aug300-340:sample:1` 12,701, `aug300-281:sample:5` 12,580) |

- 빠지는 레코드: Partial 2개. 두 질문 모두 다른 정답 표본이 남는다(aug300-340: 3개 중 2개, aug300-281: 9개 중 8개). **빠지는 질문 0.**
- 두 질문은 아직 승인 전 aug300 질문이라 시험 빌드(52질문)에는 없다. 시험 빌드는 한도를 걸어도 바뀌지 않는다
  (`PROVISIONAL`과 `PROVISIONAL_L12288`의 `sft_train.jsonl` sha256 같음: Full `aa1e5559…`, Partial `9a18e09f…`, 질문 목록 `064b211b…`).
- 세션 3 teacher(표현 중립 지시) 추정: T0 160 trace를 두 arm 레코드로 만들면 Full 최대 9,482(p90 8,792), Partial 최대 10,901(p90 10,217), 초과 0.
  Partial 입력(system + 질문)이 약 8,730 token이라 Partial teacher 응답이 약 3,550 token을 넘으면 걸린다(T0 응답 최대 2,123). 지시를 고친 뒤(C5 제안) 길이가 달라질 수 있어
  세션 3 빌드에서 다시 센다.

## 세션 3 빌드에 적용

- `build6.py`(final 모드)에 `--max-seq-length 12288`을 쓴다. 한도는 질문당 상한(teacher 4, 8b 4) 선택 **전**에 적용해 짧은 레코드가 자리를 채운다.
- 어느 arm이든 레코드가 남지 않은 질문은 기존 "두 arm 질문 목록" 규칙으로 두 arm 모두에서 빠지고, 질문 목록 sha256은 두 arm이 같다.
  빠진 레코드 수·질문 수를 `lengths.json`(`over_limit_build_candidates`, `questions_without_records_after_limit`)과 보고에 적는다.
- 학습 config의 `max_seq_length`는 12,288(pilot_005 V1 config 값에서 이 값만 바꿈).
