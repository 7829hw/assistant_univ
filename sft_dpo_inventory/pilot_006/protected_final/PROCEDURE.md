# protected_final_v1 실행 절차서(H5)

| 단계 | 누가 | 무엇 | 산출(저장소) |
|---|---|---|---|
| 0 | 사람 | 서식 복사: `protected_final_v1_template.xlsx` → `/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx`, `chmod 700` 디렉터리 | 없음 |
| 1 | 사람(작성자) | 120문항 작성(`AUTHORING_GUIDE.md`) | `access_log.md`에 작성 기록 |
| 2 | 사람 또는 Claude(실행만) | `validate.py --xlsx …` 반복. Claude가 돌리면 출력(수치·행 번호)만 보고 문장을 대화에 옮기지 않는다 | 원하면 `--report`로 요약 JSON(수치만) |
| 3 | 사람(검토자) | 내용 검토(작성자와 다른 사람 권장). 고칠 행은 작성자가 고친다 | `access_log.md` |
| 4 | 사람 또는 Claude(실행만) | `pin_hash.py --xlsx … --author …` → `manifest_v1.json` 커밋(고정 시점) | `manifest_v1.json` |
| 5 | — | 고정 뒤 이 셋으로 모델 출력을 만들지 않는다(smoke·길이·렌더 확인 포함) | — |
| 6 | Claude(측정) | 채택 후보가 정해진 뒤: `pin_hash.py --verify`(sha256 같아야 함) → base·후보 k=8 셀(PROTOCOL_v5 경로) 한 번 | 셀 원문, `access_log.md` |
| 7 | Claude(보고) | PROTOCOL_v4 6절 판정(쌍 bootstrap, 보정 없음). 측정 뒤 원본 gold와 셀 원문을 커밋 | 판정 보고 |

- 학습 데이터 빌드(RC·final)는 이 셋을 보호 목록으로 쓴다: 빌드 때 `validate.py`의 겹침 검사와 같은 방법으로 학습 레코드 질문이 이 셋과 겹치는지 보고
  **개수만** 남긴다(세션 3, 원본은 저장소 밖에서 읽기만).
- 측정 장애(규칙 13 등 실행 조건 위반)로 무효가 된 셀만 처음부터 다시 잴 수 있다(결과를 보기 전, 이유 기록).
- 도구 시험: 가짜 문항 5개(`make_fake.py`, mock 장소로 만든 무의미한 문항) → `selftest_fake5_report.json`(문제 행 5번 형식 오류, 1·2·4번 기존 셋과 같은 grounding,
  분포 미달은 시험이라 정보), 해시 고정 시험 `selftest_pin_manifest.json`(검사 실패 시 고정 거부, 재고정 거부, `--verify` 불일치 exit 2 확인).
