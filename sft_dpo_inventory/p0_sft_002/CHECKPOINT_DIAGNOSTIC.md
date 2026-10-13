# p0_sft_001 intermediate checkpoint 진단 결과

2026-10-13. 계획 `CHECKPOINT_DIAGNOSTIC_PLAN.md`(커밋 `cda6cac`). 숫자는 `checkpoint_diagnostic.json`에서 왔다.

**이 결과는 사후 진단이다. checkpoint selection이 아니다.** 어떤 중간 checkpoint도 최종 모델로 고르지 않는다.

## 1. 실행

- 8 run(Gold-only·Clean-Hybrid × checkpoint-77, checkpoint-154, checkpoint-231, checkpoint-308) × 56문항.
  - 15:10–15:32 UTC, 모두 rc=0, cell마다 precheck 통과. Ollama 호출은 없었다.
- **재현:** checkpoint-308의 문항별 category가 p0_sft_001 최종 평가와 56/56 같다(두 arm 모두).
- Base는 p0_sft_001 결과의 panel 문항을 썼다(다시 재지 않음).

## 2. trajectory(panel 56문항)

| run | epoch | train loss(직전 77 step 평균) | 정답 | `<think>` | 첫 token | thinking 글자 중앙값 | 생성 token 중앙값 | structural | grounding failure |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Base | – | – | **38** | 56/56 | `<think>` 56 | 3,006 | 855 | 5 | 5 |
| Gold-only checkpoint-77 | 0.5 | 0.198 | 29 | **0/56** | `{` 56 | 0 | 79 | 11 | 10 |
| Gold-only checkpoint-154 | 1.0 | 0.035 | 25 | 0/56 | `{` 56 | 0 | 78 | 11 | 11 |
| Gold-only checkpoint-231 | 1.5 | 0.014 | 29 | 0/56 | `{` 56 | 0 | 82 | 8 | 8 |
| Gold-only checkpoint-308 | 2.0 | 0.009 | 30 | 0/56 | `{` 56 | 0 | 81 | 10 | 10 |
| Clean-Hybrid checkpoint-77 | 0.5 | 0.202 | 28 | **0/56** | `{` 56 | 0 | 82 | 9 | 10 |
| Clean-Hybrid checkpoint-154 | 1.0 | 0.041 | 27 | 0/56 | `{` 56 | 0 | 72 | 3 | 3 |
| Clean-Hybrid checkpoint-231 | 1.5 | 0.014 | 33 | 0/56 | `{` 56 | 0 | 75 | 5 | 6 |
| Clean-Hybrid checkpoint-308 | 2.0 | 0.012 | 34 | 0/56 | `{` 56 | 0 | 77 | 2 | 4 |

malformed JSON(첫 응답)은 Base 2이고, 모든 SFT checkpoint에서 0이다.

stratum별 정답(정답/문항):

| run | scope 역조회 6 | refusal 8 | od_ne_dt 10 | dimension_target 10 | bucket 10 | ordinary 12 |
|---|---|---|---|---|---|---|
| Base | 5 | 4 | 6 | 7 | 10 | 6 |
| Gold-only 77 / 154 / 231 / 308 | 2 / 0 / 0 / 0 | 3 / 5 / 5 / 5 | 4 / 7 / 7 / 7 | 7 / 7 / 7 / 7 | 7 / 2 / 2 / 4 | 6 / 4 / 8 / 7 |
| Clean-Hybrid 77 / 154 / 231 / 308 | 1 / 2 / 2 / 4 | 4 / 5 / 5 / 5 | 7 / 6 / 7 / 7 | 6 / 6 / 7 / 6 | 4 / 4 / 3 / 5 | 6 / 4 / 9 / 7 |

## 3. 해석(계획 5절 규칙)

- **Case A에 해당한다.**
  - 두 arm 모두 첫 저장 시점(checkpoint-77, 0.5 epoch, train loss ≈ 0.20)에서 이미 `<think>` 0/56, 첫 token `{` 56/56이다.
  - thinking suppression은 학습 아주 초기에 일어났다. 학습 기간이 길어져서 생긴 것이 아니다.
- **Case B가 아니다.** thinking이 남아 있다가 사라지는 구간이 없다.
- **Case C가 아니다.** semantic correctness가 초기 checkpoint에서 더 높지 않다.
  - Gold-only: 29 → 25 → 29 → 30
  - Clean-Hybrid: 28 → 27 → 33 → 34
  - 0.5 epoch에서 이미 Base(38)보다 낮다. 그 뒤로는 계속 떨어지지 않는다.
- **dimension_target·od_ne_dt:** 0.5–1 epoch 안에 이미 Base 수준이거나 그보다 높다(od_ne_dt 6 → 7).
- **bucket:**
  - Gold-only는 0.5 epoch 7/10에서 1 epoch 2/10으로 떨어졌다. Base는 10/10이다.
  - Clean-Hybrid는 처음부터 3–5/10이다.
  - bucket 하락은 첫 epoch 안에 생긴다.
- **scope 역조회:** Gold-only는 0.5 epoch 2/6에서 1 epoch 이후 0/6으로 떨어졌다. Clean-Hybrid는 1–4/6이다.
- **과적합 기여:** 제한적이다.
  - train loss는 1 epoch 뒤 0.01–0.04로 거의 외운 상태다. 그러나 1–2 epoch 사이에 semantic correctness가 더 떨어지지 않는다.
  - 전체 하락의 대부분은 0.5 epoch 안에 thinking이 사라진 것과 함께 이미 나타난다.
  - 다만 Gold-only의 bucket·scope 역조회는 0.5 → 1 epoch에서 더 나빠졌다. 학습 기간이 일부 유형의 하락에 기여했을 수 있다.
- 56문항 panel이라 차이 2–4문항은 노이즈 범위로 본다.

## 4. 다음 실험(R70)에 주는 근거

- thinking collapse는 epoch 수와 무관하게 json_only 초기에 일어난다. 그러므로 R70 비교에서 epoch를 늘릴 이유가 없다.
- 70문항뿐이고 p0_sft_001이 1 epoch 뒤 train loss가 거의 0이었다. 따라서 **R70은 1 epoch**(70 step)로 고정한다(PLAN.md).
