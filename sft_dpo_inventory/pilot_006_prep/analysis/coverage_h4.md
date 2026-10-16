# H4 약점별 학습 재료(승인 corpus 416질문, 판정 10개 파일, TEACH 없음)

| 부분집합 | 질문 | Full 8b 정답 | Partial 8b 정답 | teacher 통과 | 두 arm 재료 | batch009 후보 |
|---|---:|---:|---:|---:|---:|---:|
| bucket | 32 | 32 | 32 | 0 | 32 | 0 |
| bucket_or_dimension | 227 | 162 | 174 | 0 | 151 | 43 |
| dimension | 195 | 130 | 142 | 0 | 119 | 43 |
| dt | 115 | 80 | 82 | 0 | 71 | 43 |
| implicit_endpoint | 23 | 13 | 12 | 0 | 11 | 24 |
| od_ne_dt | 54 | 36 | 40 | 0 | 32 | 28 |
| scope_reverse | 5 | 5 | 1 | 0 | 1 | 0 |
| silcha | 168 | 112 | 117 | 0 | 100 | 43 |
| valueless_place | 5 | 5 | 1 | 0 | 1 | 0 |
| vicinity | 59 | 38 | 41 | 0 | 32 | 0 |

최소 제안 30질문(두 arm 재료 기준). 모자란 곳: implicit_endpoint 11(−19), valueless_place 1(−29), scope_reverse 1(−29)
