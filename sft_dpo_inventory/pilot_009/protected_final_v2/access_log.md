# protected_final_v2 열람 기록(명세 2판 4.4)

원본(저장소 밖 `/home/hwkim/sftdpo_work/protected_final_v2/`, 700/600)을 다룬 모든 경우를 적는다. 허용 목적: 작성, 사람 검토, 기계 검사, 최종 측정, 측정 뒤 오류 분석.
Claude Code는 내용을 열지 않는다(결정 245) — 기계 검사는 수치·행 번호·코드만 출력하는 도구로만 한다.

| 시각 | 누구 | 목적 | 연 파일 | 비고 |
|---|---|---|---|---|
| 2026-10-27T13:36:31+09:00 | Claude Code(pilot_010 준비) | 파일 기록·권한(내용 열람 없음) | `protected_final_v2.xlsx`, 22,333바이트, sha256 `b93235152433cc57271060f394275f67ae9e14e50a88b29eac9ad571259f57e1` | 권한 775/664 → 700/600. 사용자 지시(사전 검사) |
| 2026-10-27T13:50:51+09:00 | Claude Code(pilot_010 준비) | 기계 검사(사전 검사, 고정 아님) | `protected_final_v2.xlsx`를 `pilot_010/protected_final_v2/precheck_pf2_10.py`(→ `validate_pf2.validate`)만 읽음 | 겹침 대상 = validate_pf2 대상(RC7·승인 corpus v4·v5·refusal_dev v1·v2·batch011·012 등) + batch013 초안 80. 출력 `precheck_pf2_10_20261027.json`·`precheck_stdout_20261027.txt`(700 디렉터리, 600, 커밋 안 함). ok false, rows 150, file_problems 0, row_problems 16행(contrast_code 14, overlap_same_grounding 2행), distribution_problems contrast_off_target, P·C 결과 불일치 0. pilot_010 판정 단계 데이터 빌드 뒤 겹침 대상을 바꿔 다시 검사하고 그때 고정 |
