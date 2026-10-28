# 학습 데이터·실행 기록 복구

`manifest.json`은 `migration_20261028/git_candidates.jsonl.gz`의 881개 후보별 출처, 원본 SHA-256 및 보존 방식을 기록한다. 스냅샷은 그대로 유지했다. Git 보존이나 후보 분류는 학습 승인, 평가셋 학습 사용 승인 또는 자료 삭제 허가가 아니다.

- 외부 기록 485개는 스냅샷과 크기·mtime·SHA-256을 확인한 후 실험별 `train_logs/migration_20261028/`에 복사하고 다시 해시를 확인했다. 이 중 후보 68건은 독립 검토에서 학습 표본 수집·재현·진단 기록으로 확인해 Git 보존 대상으로 판정했다. 이 판정은 학습 승인이 아니다.
- 외부 원본 57개는 동일한 Git index blob이 있는 경로를 매핑했다. 이 매핑은 원격 보존이나 경로별 중복 사본을 주장하지 않는다.
- `fix_hoist_rerun` 76개는 평가 원문 재적용 기록이다. `evaluation/fix_condition_hoist/verify_rerun.py` 6–12행의 별도 외부 보존 지침에 따라 경로와 해시만 기록했다.
- 요청 관련 문자열이 감지된 평가 또는 학습·평가 혼합 vLLM 서버 로그 17개는 외부에 유지하고 해시와 경로만 기록했다. 학습 표본 수집용 pilot_004 8300–8302 및 batch007 8700의 서버 로그는 Git 보존 기록으로 검토했다.
- 저장소의 기존 원문은 원래 경로에 둔다. `S128F_raw.jsonl`은 100 MiB를 초과하므로 원본을 로컬에 유지하고 옆의 `S128F_raw.jsonl.shards/`에 완전한 줄 단위 조각과 바이트 보존 속성 및 SHA-256 manifest를 둔다.

조각을 원본과 비교하지 않고 검증하려면 `python3 scripts/restore_missing_training_data.py verify-shards`를 실행한다. 재조합은 존재하지 않는 출력 경로를 지정해 `python3 scripts/restore_missing_training_data.py restore-shards --output /path/to/new/file`을 실행한다. 조각별 해시와 합친 원본의 크기·해시를 모두 확인한다. 기존 파일은 덮어쓰지 않는다.

도구는 원본 경로가 없을 경우 스냅샷에 기록된 `/data/hwkim/sftdpo_work` 통합 경로를 사용하고 크기·mtime·SHA-256을 검증한다. 원래 출처, 실제 읽은 경로, 통합 경로는 manifest에 별도로 기록한다. 기존 복구 작업을 재실행하기 전에 현재 manifest와 대상 파일 상태를 확인한다.
