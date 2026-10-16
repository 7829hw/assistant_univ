# H4 약점별 학습 재료(승인 corpus 473질문, 판정 18개 파일, TEACH 있음)

| 부분집합 | 질문 | Full 8b 정답 | Partial 8b 정답 | teacher 통과 | 두 arm 재료(teacher 포함) | 두 arm 재료(8b만) | batch009 후보 |
|---|---:|---:|---:|---:|---:|---:|---:|
| bucket | 32 | 32 | 32 | 23 | 32 | 32 | 0 |
| bucket_or_dimension | 270 | 206 | 215 | 179 | 270 | 196 | 43 |
| dimension | 238 | 174 | 183 | 156 | 238 | 164 | 43 |
| dt | 157 | 107 | 113 | 106 | 157 | 100 | 43 |
| implicit_endpoint | 47 | 19 | 18 | 39 | 47 | 16 | 24 |
| od_ne_dt | 79 | 54 | 59 | 58 | 79 | 51 | 28 |
| scope_reverse | 19 | 19 | 2 | 18 | 19 | 2 | 0 |
| silcha | 210 | 146 | 152 | 145 | 210 | 136 | 43 |
| valueless_place | 19 | 19 | 2 | 18 | 19 | 2 | 0 |
| vicinity | 59 | 50 | 52 | 50 | 59 | 49 | 0 |

최소 제안 30질문. 모자란 곳(teacher 포함): valueless_place 19(−11), scope_reverse 19(−11)
모자란 곳(8b만): implicit_endpoint 16(−14), valueless_place 2(−28), scope_reverse 2(−28)
