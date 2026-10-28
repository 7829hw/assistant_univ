# 학습·검토 자료 Git 보존 정책

2026-10-28 사용자 지시, 결정 257. 학습·검토 원문을 커밋하지 않거나 요약만 커밋하던 과거 지시를 대체한다. 실데이터에도 결정 256의 원본 보존 정책을 적용한다.

## Git 보존 대상

- SFT·DPO 학습 데이터, thinking·teacher·자체 표본의 원문, 필터 전후 trace, 제외 표본과 제외 사유, trace 원본 모음(`combined_traces.jsonl`).
- 학습 후보를 검토하기 위한 모델 첫 응답, annotation 초안·queue·검토/승인 기록, 검토 문서와 XLSX.
- 데이터·순서·split·빌드 manifest, 해시와 출처, 실제 실행 설정, 학습 프로파일·loss·로그 등 재현 기록.
- 실제 질문·TIMS 응답·실행·검토·판정 기록의 원본(결정 256).

원문을 저장한 경로·해시나 요약만 커밋해 원본 보존을 대신하지 않는다. 이미 만들어 둔 학습·검토 원문도 같은 기준으로 편입한다. 데이터는 `training/generated/`, 기록은 `sft_dpo_inventory/<실험>/` 등 저장소 내부에 보존한다.

`training/runs/`, `training/experiments/`, `training/annotations/generated/`, `training/checkpoints/`, `sft_dpo_inventory/generated/` 전체를 무시하던 규칙도 해제한다. 이 경로의 학습·검토 데이터와 JSON 출처·학습 상태 기록은 추적 대상이며, 모델 가중치·바이너리 체크포인트는 파일 종류별 제외 규칙을 적용한다.

범용 `build/` 제외는 저장소 루트의 `build.py --dump` 출력(`/build/`)으로 한정한다. 새 실험의 `build/` 폴더와 annotation 빌드 결과도 Git에 보이게 한다.

## 혼합 폴더와 별도 보관 대상

- 가중치·adapter·병합 모델·GGUF·optimizer/RNG 등 바이너리 체크포인트, 가상환경·캐시·임시 파일은 계속 Git에서 제외한다.
- 기존에 명시적으로 제외한 평가 전용 원문과 최종 평가셋의 실험상 열람·보존 규칙은 구분한다. 자료의 Git 보존은 초안 승인이나 평가 자료의 학습 사용을 허가한 것으로 해석하지 않는다.
- `training/generated/pilot_006_prep/raw/`는 학습 후보 검토용 첫 응답 두 파일과 평가 파일 59개가 섞여 있다. `aug300_base_first_raw.jsonl`, `batch008_base_first_raw.jsonl`은 Git 보존 대상이다. 평가 파일 59개의 정확한 경로만 제외하며 폴더 전체를 무시하지 않는다. 새 학습·검토 파일도 Git에 보이게 한다.

## 적용과 검증

1. 현재 작업 지침은 `CLAUDE.md` 규칙 3과 이 문서를 따른다. 과거 보고서·동결된 설정·스크립트의 원문 비커밋 설명은 당시 기록으로 보존하고, 현재 정책으로 재사용하지 않는다.
2. `git check-ignore --no-index <원문 경로>`로 학습·검토 원문이 차단되지 않는지 확인한다. 차단되면 해당 규칙을 고치며 `git add -f`를 사용하지 않는다.
3. 실제 원문을 편입할 때 출처·크기·SHA‑256과 승인/제외 상태를 보존한다. 큰 JSONL은 원문을 손실 없이 재조합할 수 있는 분할과 원본 해시 등 저장 방식을 적용한다.
4. [이관 목록](migration_20261028/README.md)은 정책 변경 전 스캔·검사 기록이다. 그 목록의 `ignored` 값이나 당시 보고한 비커밋 상태를 현재 규칙으로 사용하지 않는다.

이번 정책 수정은 원문 경로를 Git 추적 가능하게 만드는 작업이다. 기존 원문의 일괄 편입과 `/data/hwkim/sftdpo_work` 통합은 해당 실행 단계에서 별도로 수행한다.
