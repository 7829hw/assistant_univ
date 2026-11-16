# X4 데이터 승인

- 2026-11-16 KST, 사용자: "x4승인" (X4_DATA.md 승인 요청에 대한 답).
- 승인 대상: `x4/V4S/full/sft_train.jsonl` sha256 `0f1d0bc7695f69b7841600f820cae8994a2dc42336444032084f5312d6b05af5`(규칙 `x4-scope-slot-v1`, `--relabel narrow`).
- 해석: 사용자가 따로 고르지 않았으므로 X4_DATA.md의 권고안 그대로로 읽는다 — 표현 고치기는 narrow(17건, 편집 19곳), 풀이 안의 "다섯 줄" 표현은 그대로.
  사용자가 다르게 정하면 학습 전이면 데이터를 다시 만들고, 학습 뒤면 그 사실을 RESULTS에 적는다.
- 학습 설정: `x4/train/configs/`(18개), 쌍 배정 `x4/train/pairs.json`. CPU dry-run·tokenizer-check 통과(`x4/train/checks/`).
