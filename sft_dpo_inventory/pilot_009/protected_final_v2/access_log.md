# protected_final_v2 열람 기록(명세 2판 4.4)

원본(저장소 밖 `/home/hwkim/sftdpo_work/protected_final_v2/`, 700/600)을 다룬 모든 경우를 적는다. 허용 목적: 작성, 사람 검토, 기계 검사, 최종 측정, 측정 뒤 오류 분석.
Claude Code는 내용을 열지 않는다(결정 245) — 기계 검사는 수치·행 번호·코드만 출력하는 도구로만 한다.

| 시각 | 누구 | 목적 | 연 파일 | 비고 |
|---|---|---|---|---|
| 2026-10-27T13:36:31+09:00 | Claude Code(pilot_010 준비) | 파일 기록·권한(내용 열람 없음) | `protected_final_v2.xlsx`, 22,333바이트, sha256 `b93235152433cc57271060f394275f67ae9e14e50a88b29eac9ad571259f57e1` | 권한 775/664 → 700/600. 사용자 지시(사전 검사) |
| 2026-10-27T13:50:51+09:00 | Claude Code(pilot_010 준비) | 기계 검사(사전 검사, 고정 아님) | `protected_final_v2.xlsx`를 `pilot_010/protected_final_v2/precheck_pf2_10.py`(→ `validate_pf2.validate`)만 읽음 | 겹침 대상 = validate_pf2 대상(RC7·승인 corpus v4·v5·refusal_dev v1·v2·batch011·012 등) + batch013 초안 80. 출력 `precheck_pf2_10_20261027.json`·`precheck_stdout_20261027.txt`(700 디렉터리, 600, 커밋 안 함). ok false, rows 150, file_problems 0, row_problems 16행(contrast_code 14, overlap_same_grounding 2행), distribution_problems contrast_off_target, P·C 결과 불일치 0. pilot_010 판정 단계 데이터 빌드 뒤 겹침 대상을 바꿔 다시 검사하고 그때 고정 |
| 2026-10-27T18:37:58+09:00 | Claude Code(pilot_010 선택 단계) | 파일 기록·권한(내용 열람 없음) | `protected_final_v2.xlsx`, 22,359바이트, sha256 `c7174e710d56adfee4b055c1655836b49c84ae0df97c2732acf5a5e2b5631557`(수정 시각 18:27:17, 지시의 `b9323515…`에서 바뀜 — 사용자 저장으로 보임) | 권한 664 → 600(디렉터리 700 그대로). 결정 254 재검사 |
| 2026-10-27T18:37:58+09:00 | Claude Code(pilot_010 선택 단계) | 기계 검사(사전 검사, 고정 아님) | `protected_final_v2.xlsx`를 `pilot_010/protected_final_v2/validate_pf2b.py`(→ `validate_pf2.validate`, 근접 대조 짧은 이름 받음)만 읽음 | 겹침 대상 = 준비 세션과 같음(validate_pf2 대상 + batch013 초안 80). 출력 `precheck_pf2b_10_20261027.json`·`precheck_pf2b_stdout_20261027.txt`(700, 600, 커밋 안 함). ok true, rows 150, file_problems 0, row_problems 0, distribution_problems 0, 근접 대조 25/25, P·C 결과 불일치 0 |
| 2026-10-27T18:38:30+09:00 | Claude Code(pilot_010 선택 단계) | 기계 검사 비교(같은 파일, 이전 도구) | 같은 파일을 `precheck_pf2_10.py`(→ `validate_pf2`)만 읽음 | 출력 `precheck_pf2_10_old_tool_20261027b.json`(700, 600, 커밋 안 함). ok false: contrast_code 14행(6·11·31·37·38·54·72·73·96·118·140·141·143·148)·contrast_off_target(11/25) — 짧은 이름 때문임을 확인. overlap_same_grounding(1·41행)은 이전 도구에서도 없음(사용자 수정) |
