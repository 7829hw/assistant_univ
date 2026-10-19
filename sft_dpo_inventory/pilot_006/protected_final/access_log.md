# protected_final_v1 열람 기록(SPEC 4.4)

원본(저장소 밖)을 연 모든 경우를 적는다. 허용 목적: 작성, 사람 검토, 기계 검사, 최종 측정, 측정 뒤 오류 분석. 그 밖의 열람은 사고로 기록하고 보고한다.

| 시각 | 누구 | 목적 | 연 파일 | 비고 |
|---|---|---|---|---|
| 2026-10-16 | Claude Code(세션 2b) | 도구 작성 | 없음(원본은 아직 없음, 가짜 문항 5개로만 시험) | H5 |
| 2026-10-20T01:37:39+09:00 | Claude Code(pilot_007 A3, PF1) | 파일 배치(내용 열람 없음) | `/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx`(이미 그 자리에 있어 옮기지 않음, 디렉터리 안 다른 사본 없음), sha256 `e4d8944c236af035833987edf44819443db9a10838ecca1ea1dcc8cbb254891b`, 18,911바이트 | 권한 775/664 → 700/600. 결정 193 |
| 2026-10-20T01:38:02+09:00 | Claude Code(pilot_007 A3, PF2) | 기계 검사(validate.py 실행만) | 같은 경로, sha256 `e4d8944c…` | ok false(rows 120, file_problems 0, row_problems 18행, distribution_problems 0). 보고·출력 파일은 같은 700 디렉터리에(커밋 안 함). 수치·번호·코드만 옮김. pin_hash 실행 안 함. 결정 193 |
| 2026-10-20T01:52:30+09:00 | Claude Code(pilot_007 A3, PF4) | 기계 검사(겹침 개수만, `pilot_007/analysis/pf4_overlap.py`가 validate.py의 load_rows로 읽음) | 같은 경로, sha256 `e4d8944c…` | RC5 학습 레코드와 겹침 개수만 기록(`pf4_overlap.json`): 같은 grounding 3질문(Full 16·Partial 9 레코드), 질문·Jaccard 0. 내용 출력 없음. 결정 193 |
