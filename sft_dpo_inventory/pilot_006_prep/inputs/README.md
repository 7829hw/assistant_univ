# pilot_006_prep 입력 파일

출처: 사용자 제공(방법 2, scp로 workstation4의 이 경로에 복사, 2026-10-15 21:36). 계획서 v2와 300문항 v2. 업로드 커밋은 없다.

| 파일 | 크기(bytes) | sha256 | 내용 |
|---|---:|---|---|
| `two_branch_integration_and_300_dataset_plan_v2.md` | 30,141 | `3d43c6845455f58f7d03675f0535d824ec2e4398884395f74aebb09a09731b2b` | 통합 계획 v2. 지시 3절이 v2보다 우선한다 |
| `질문_증강_300문항_추가_v2.xlsx` | 89,005 | `2aeaaffb3b2ba4f0b4b47e3ec78f20d4057bf1a8ba6e01335afcb640a599a039` | 300문항 v2(수정 3건, 상태·family·risk_tags 열, 보호셋 겹침 시트) |

- xlsx 파일 이름은 NFD(자모 분리)로 복사돼 있어서 NFC로 바꿨다. 내용은 바꾸지 않았다(sha256 같음).
- `.gitignore`의 `*.xlsx`는 사용자 지시로 뺐다(결정 115). `git add -f`는 쓰지 않았다.
