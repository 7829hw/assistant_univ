# H4 약점별 학습 재료(승인 corpus 473질문, 판정 16개 파일, TEACH 없음)

| 부분집합 | 질문 | Full 8b 정답 | Partial 8b 정답 | teacher 통과 | 두 arm 재료(teacher 포함) | 두 arm 재료(8b만) | batch009 후보 |
|---|---:|---:|---:|---:|---:|---:|---:|
| bucket | 32 | 32 | 32 | 0 | 32 | 32 | 0 |
| bucket_or_dimension | 270 | 195 | 210 | 0 | 186 | 186 | 43 |
| dimension | 238 | 163 | 178 | 0 | 154 | 154 | 43 |
| dt | 157 | 100 | 110 | 0 | 94 | 94 | 43 |
| implicit_endpoint | 47 | 19 | 18 | 0 | 16 | 16 | 24 |
| od_ne_dt | 79 | 49 | 57 | 0 | 46 | 46 | 28 |
| scope_reverse | 19 | 19 | 1 | 0 | 1 | 1 | 0 |
| silcha | 210 | 136 | 149 | 0 | 127 | 127 | 43 |
| valueless_place | 19 | 19 | 1 | 0 | 1 | 1 | 0 |
| vicinity | 59 | 47 | 50 | 0 | 45 | 45 | 0 |

최소 제안 30질문. 모자란 곳(teacher 포함): implicit_endpoint 16(−14), valueless_place 1(−29), scope_reverse 1(−29)
모자란 곳(8b만): implicit_endpoint 16(−14), valueless_place 1(−29), scope_reverse 1(−29)
