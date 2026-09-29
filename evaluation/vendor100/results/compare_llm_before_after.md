# 변경 전후 비교: llm

- 전: `962432d561` {'answered_mismatch': 13, 'match': 65, 'failed': 18, 'refused_unsupported': 4}
- 후: `962432d561` (작업 트리 변경 있음) {'answered_mismatch': 14, 'match': 65, 'failed': 18, 'refused_unsupported': 3}

| 문항 | 업체 판정 | 전 | 후 | 후 오류/인자 차이 |
|---|---|---|---|---|
| 100 | Tool 흐름/인자 오류 | refused_unsupported (UNSUPPORTED_PARTITION_SIZE) | answered_mismatch |  [["aggregation", "sum", "max"], ["taxi_type", "corporate", null]] |
