# RC5(pilot_007 A3, 결정 187) — A3 학습(Full)·B단계 후보

`../build7rc5.py`: RC5 = RC3(정리 전) 레코드 + teacher c2 편집(결정 185) + batch010 승인분(승인 corpus v3) + S-focus 정답 표본.

| | RC3 | RC3c | **RC5** |
|---|---:|---:|---:|
| 질문 | 386 | 369 | **391**(기존 343 + batch010 48) |
| Full 레코드(teacher / 8b) | 1,861(836 / 1,025) | 1,356(339 / 1,017) | **1,811(763 / 1,048)** |
| Partial 레코드 | 1,826(836 / 990) | 1,312(332 / 980) | **1,775(763 / 1,012)** |
| teacher loss token(Full / Partial) | 71.3% / 81.0% | 49.0% / 61.4% | **68.6% / 78.9%** |

- teacher: RC3 teacher 레코드의 c2 편집본. c2에서 빠진 trace(내용 손실) Full 19·Partial 18. batch010에는 teacher가 없다.
- **유형 상한(결정 187: 상한 칸에서 batch010 먼저)**: batch010 48문항 모두 들어감(2문항은 한 arm 레코드 없음: b010-42 Partial, b010-54 Full).
  밀려난 기존 질문 39(칸 "집계 있음|dim 없음|dt 없음" 30, "집계 없음|dim 있음|dt 있음" 9), batch010과 무관하게 상한을 넘은 기존 질문 4(두 칸 각 2) → 기존 43문항 빠짐.
  최종 TV 0.0892(≤ τ 0.09). 칸별 수와 밀려난 질문 id는 `build_summary.json` `type_cap`.
- 검사(`../rc_checks7.py --rc RC5`): 두 arm dry-run·tokenizer-check·손실 token·마스크 audit 통과(mismatch 0), 최대 길이 Full 10,835·Partial 11,775(≤ 12,288).
  두 arm 질문 목록 sha256 `22406d92…` 같음. 순서 파일 `order_o43/o20261016/o7.json`(두 arm 질문 순서가 순서 파일과 같음 — 빌드에서 확인).
- PF4: `protected_final_v1` 초안(고정 전)과 같은 grounding 3질문(Full 16·Partial 9 레코드), 질문·Jaccard 겹침 0 — 고치지 않음(`../../analysis/pf4_overlap.json`).
