# RC3c(pilot_007 A단계 S1, 결정 166)

RC3(`../../../pilot_006/build/RC3`)에 teacher 정리만 적용했다(`../build7c.py`, 검사 `../../teacher/teacher_checks7.py`). 나머지 빌드 규칙·8b 레코드·유형 상한·순서는 RC3 그대로.

| | RC3 Full | RC3c Full | RC3 Partial | RC3c Partial |
|---|---:|---:|---:|---:|
| 질문 | 386 | 369 | 386 | 369 |
| 레코드 | 1,861 | 1,356 | 1,826 | 1,312 |
| teacher(`full_response`) | 836 | 339 | 836 | 332 |
| 8b(`json_only`) | 1,025 | 1,017 | 990 | 980 |
| teacher loss token 비율 | 71.3% | 49.0% | 81.0% | 61.4% |

- 빠진 teacher 레코드 이유: (ii) 346/347, 영어 생각(d)+영어 노출·메타(e) 148/154, (e)만 1/2.
- 두 arm 모두 레코드가 남지 않은 질문 17개는 두 arm에서 뺐다(질문 목록 sha256 같음). 목록은 `build_summary.json`.
- 검사(`../rc_checks7.py`): 두 arm dry-run·tokenizer-check·출처별 손실 token·마스크 audit 통과(`checks_summary.json`, mismatch 0).
- teacher 정리 상세·약점 커버리지: `../../teacher_cleanup.json`.
