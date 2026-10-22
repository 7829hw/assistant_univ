# protected_final_v1 열람 기록(SPEC 4.4)

원본(저장소 밖)을 연 모든 경우를 적는다. 허용 목적: 작성, 사람 검토, 기계 검사, 최종 측정, 측정 뒤 오류 분석. 그 밖의 열람은 사고로 기록하고 보고한다.

| 시각 | 누구 | 목적 | 연 파일 | 비고 |
|---|---|---|---|---|
| 2026-10-16 | Claude Code(세션 2b) | 도구 작성 | 없음(원본은 아직 없음, 가짜 문항 5개로만 시험) | H5 |
| 2026-10-20T01:37:39+09:00 | Claude Code(pilot_007 A3, PF1) | 파일 배치(내용 열람 없음) | `/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx`(이미 그 자리에 있어 옮기지 않음, 디렉터리 안 다른 사본 없음), sha256 `e4d8944c236af035833987edf44819443db9a10838ecca1ea1dcc8cbb254891b`, 18,911바이트 | 권한 775/664 → 700/600. 결정 193 |
| 2026-10-20T01:38:02+09:00 | Claude Code(pilot_007 A3, PF2) | 기계 검사(validate.py 실행만) | 같은 경로, sha256 `e4d8944c…` | ok false(rows 120, file_problems 0, row_problems 18행, distribution_problems 0). 보고·출력 파일은 같은 700 디렉터리에(커밋 안 함). 수치·번호·코드만 옮김. pin_hash 실행 안 함. 결정 193 |
| 2026-10-20T01:52:30+09:00 | Claude Code(pilot_007 A3, PF4) | 기계 검사(겹침 개수만, `pilot_007/analysis/pf4_overlap.py`가 validate.py의 load_rows로 읽음) | 같은 경로, sha256 `e4d8944c…` | RC5 학습 레코드와 겹침 개수만 기록(`pf4_overlap.json`): 같은 grounding 3질문(Full 16·Partial 9 레코드), 질문·Jaccard 0. 내용 출력 없음. 결정 193 |
| 2026-10-21T10:18:17+09:00 | Claude Code(pilot_007 T, PF1) | 파일 확인(내용 열람 없음) | `/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx`(사용자가 고친 파일, 같은 경로에 덮어씀), sha256 `90883ded83df51c4749036a1c4d45094567f4a2c0092d43ed1f1f77310f12296`, 19,138바이트 | 이전 `e4d8944c…`과 다름. 권한 디렉터리 700, 파일 664 → 600. 디렉터리 안 다른 xlsx 사본 없음(A3 검사 출력 2개만). 결정 201–202 |
| 2026-10-21T10:18:28+09:00 | Claude Code(pilot_007 T, PF2) | 기계 검사(validate.py 실행만) | 같은 경로, sha256 `90883ded…` | ok true(rows 120, file_problems 0, row_problems 0, distribution_problems 0). 출력 `validate_report_T.json`·`validate_stdout_T.txt`(700 디렉터리, 600, 커밋 안 함). 수치만 옮김 |
| 2026-10-21T10:19:00+09:00 | Claude Code(pilot_007 T, PF3) | 기계 검사(RC5 학습 레코드 겹침 수·행 번호만, `pilot_007/analysis/pf3_overlap_t.py`, A3 PF4와 같은 방법) | 같은 경로, sha256 `90883ded…` | 같은 grounding 1행(번호 76; Full 8·Partial 4 레코드, 학습 질문 1개), 질문·Jaccard 0. 출력 `pf3_overlap_T.json`(700 디렉터리, 600, 커밋 안 함). **PF4 불통과 → 고정 안 함, pin_hash 실행 안 함, 판정 안 함(R7 유지)** |
| 2026-10-21T10:26:39+09:00 | Claude Code(pilot_007 T 재검사, PF1) | 파일 확인(내용 열람 없음) | 같은 경로(사용자가 76번을 고친 파일로 덮어씀), sha256 `5a43e8d07c487ad54568331138237bbd5270df55b9d014346078e90f349af3dc`, 19,185바이트 | 직전 `90883ded…`·그 전 `e4d8944c…`과 다름. 권한 디렉터리 700, 파일 664 → 600. 디렉터리 안 다른 xlsx 사본 없음(검사 출력만). 결정 204 |
| 2026-10-21T10:26:47+09:00 | Claude Code(pilot_007 T 재검사, PF2) | 기계 검사(validate.py 실행만) | 같은 경로, sha256 `5a43e8d0…` | ok true(rows 120, file_problems 0, row_problems 0, distribution_problems 0). 출력 `validate_report_T2.json`·`validate_stdout_T2.txt`(700 디렉터리, 600, 커밋 안 함). 수치만 옮김 |
| 2026-10-21T10:26:53+09:00 | Claude Code(pilot_007 T 재검사, PF3) | 기계 검사(RC5 학습 레코드 겹침 수·행 번호만, `pf3_overlap_t.py`) | 같은 경로, sha256 `5a43e8d0…` | 겹침 0(질문·Jaccard·같은 grounding, Full·Partial 모두). 출력 `pf3_overlap_T.json`(직전 출력은 `pf3_overlap_T_r1.json`으로 이름 바꿈; 700 디렉터리, 600, 커밋 안 함). PF4 통과 |
| 2026-10-21T10:27:08+09:00 | Claude Code(pilot_007 T, 고정) | 고정(`pin_hash.py`, validate.py를 다시 부름, 내용 출력 없음) | 같은 경로, sha256 `5a43e8d0…` | `manifest_v1.json`(rows 120, author "사용자(이름 기록 안 함)", test false). 이 manifest 커밋이 고정 시점. 결정 202·204 |

## 고정 기록(2026-10-21, manifest 커밋 `2fb30faeed618866be3ed16f02ff507730757b68`, 파일 sha256 `5a43e8d07c487ad54568331138237bbd5270df55b9d014346078e90f349af3dc`)

- 작성: 새 Claude 대화, 초안
- 수정: 같은 대화, 검사 결과의 행 번호·코드만 전달(두 차례: 첫째는 A3 PF2의 18행, 둘째는 76번만 — PF3 같은 grounding)
- 검토: 사용자(120행 전체, 76번은 수정 뒤 다시; 이름 기록 안 함, 결정 138)
- 검사: Claude Code, 실행만(validate.py, pf3_overlap_t.py; 내용 열람·출력 없음)
- 고정: Claude Code(pin_hash.py)
| 2026-10-21T10:27:39+09:00 | Claude Code(pilot_007 B, R7 확인) | 기계 검사(`pilot_007/results/check_r7.py`: 원격 manifest·sha256 비교, validate.py `--report`의 ok만 읽음) | 같은 경로, sha256 `5a43e8d0…` | 고정 확인(manifest 커밋 2fb30fa, sha256 같음, ok true). 출력 `r7_validate_report.json`(700 디렉터리, 600, 커밋 안 함). 결정 200·203 |
| 2026-10-22T11:02:25+09:00 | Claude Code(pilot_007 최종 판정, 시작 확인) | 고정 확인(validate.py 실행만) | 같은 경로, sha256 `5a43e8d0…` | 원격 manifest 2fb30fa·sha256 같음·ok true. 출력 `validate_report_final.json`(700, 600, 커밋 안 함) |
| 2026-10-22T11:06:10+09:00 | Claude Code(pilot_007 최종 판정, S1 변환) | 평가 gold 변환(`pilot_007/final/convert_pf_gold.py`, 출력은 sha256·개수·번호만) | 같은 경로, sha256 `5a43e8d0…` | `pf1_gold.yaml`(sha256 `8ee5e10e…`)·`pf1_items_meta.json`(`5ef54e88…`) 700 디렉터리 600. 120문항(거부 10), 거부 아닌 110문항 mock match·grounding_check 참. 내용 출력 없음. 결정 215 |
| 2026-10-22T11:12:37+09:00 | Claude Code(pilot_007 최종 판정, 측정 시도 1) | 측정 시작 실패(모델 요청 전, client의 저장소 상대 경로 검사) | `pf1_gold.yaml` 경로만 전달 | 셀·원문 없음, shard 로그만 → `aborted_launch1/`(700, 내용 열지 않음). PLAN_FINAL_AMEND1 |
