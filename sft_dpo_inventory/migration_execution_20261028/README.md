# SFT/DPO 저장소 통합 실행 완료 — 2026-10-29

사용자가 검사된 전체 목록에 따라 실제 이관과 누락 자료 Git 업로드를 지시해 실행했다. 외부 자료의 기준 위치는 **`/data/hwkim/sftdpo_work`**다. 기존 `/home/hwkim/sftdpo_work`와 검증용 임시 격리 폴더를 정리했으며, 구 경로에 호환 링크를 두지 않았다. Git 저장소 자체는 `/home/hwkim/assistant_univ`에 유지한다(승인된 목록의 범위).

## 물리 이관과 보존 증거

- 원본 변경 여부를 재열거한 결과 목록 182,900개와 일치했고 추가·삭제·메타데이터 변경은 0이었다. 관련 실행 프로세스는 관찰되지 않았다.
- `rsync -aHAXS --numeric-ids --ignore-existing`으로 home의 일반 파일 163,617개, 논리 크기 302,538,396,980 B를 복사했다. 기존 data 자료를 덮어쓰지 않았다. 겹친 디렉터리 5곳은 data 쪽 원래 수정 시각을 복원했다.
- 전체 182,900개 목록 항목을 검증했다. 일반 파일 SHA-256 일치 163,684개, 보호 최종셋의 기계적 바이트 비교 일치 87개, 링크 1,102개, 디렉터리 18,027개로 실패 0이었다. 합쳐진 실제 원래 경로는 중복 디렉터리를 제외한 182,895개다.
- 직접 절대 링크 3개를 data 경로로 재작성해 연쇄 링크 2개도 구 home 의존성을 해소했다. 원래 링크 원문은 과거 목록에 남아 있다. 원래 링크 1,102개 모두 끊어지지 않았다.
- 복사된 llama.cpp Git index를 검사 도구가 갱신한 1건은 원본과 같은 바이트로 복구하고 수정 시각도 복원했다. `preservation_repair.json`에 별도 기록했다.
- 구 home을 먼저 임시 이름으로 격리해 **원래 home 경로 없이** 네 환경 import·의존성 검사 및 실제 CPU 학습 dry-run이 성공하는지 확인했다.
- 원본 정리 직전에 전체 대상 바이트를 다시 검증했다. 이어 각 소스 파일을 지우기 직전에도 대상 SHA-256 또는 보호 파일의 기계적 바이트 비교를 수행했다. 검토된 원본 집합·inode·권한·소유자·시각·xattr와 대상 식별자를 확인한 뒤 목록의 파일·링크만 unlink하고 빈 디렉터리만 rmdir했다. 파일 163,617개, 링크 1,102개, 디렉터리 18,005개를 정리했고 잔여 원본은 없다.

보호 최종셋은 내용이나 파일별 해시를 모델·보고서에 출력하지 않았다. 정리는 동시 writer가 없는 운영 조건에서 수행했다. 도구는 알 수 없는 항목이나 변경을 만나면 잔여 원본을 남기고 중단하며, 전체 작업의 원자적 rollback을 보장하지 않는다. 실제 실행은 실패 없이 완료됐다.

| 기록 | 확인할 내용 |
|---|---|
| [physical/preflight.json](physical/preflight.json) | 실행 전 목록 대조 |
| [physical/copy_completion.json](physical/copy_completion.json), [copy.log](physical/copy.log) | 복사 명령·수량·종료 |
| [physical/full_copy_verification.json](physical/full_copy_verification.json) | 최초 전체 바이트·메타데이터 검증 |
| [physical/postcopy_link_updates.json](physical/postcopy_link_updates.json) | 링크 3개 의도된 변경 |
| [physical/source_isolation.json](physical/source_isolation.json) | 원본 임시 격리 이력 |
| [physical/source_cleanup.json](physical/source_cleanup.json) | 전체 재검증·삭제 직전 검증·실제 원본 정리 완료 |
| [physical/final_state.json](physical/final_state.json) | 구 경로 부재·대상 전체 항목·링크·여유 공간 |

`source_isolation.json`과 초기 복사 검증은 해당 시점의 이력이다. 현재 완료 상태는 `source_cleanup.json`과 `final_state.json`을 따른다. 과거 [이관 목록](../migration_20261028/README.md)과 16개 기계 산출물은 원래 바이트 그대로 보존했다.

## Git 누락 복구

**`1a82099`를 `origin/geoflow/sft-dpo-t2pc`에 업로드했다.** 원문·복구 도구·출처 manifest 등 558개 파일, 논리 blob 크기 795,543,122 B를 편입했다. GitHub의 100MiB 제한을 넘는 원문 한 개는 완전한 줄 단위 조각 5개로 보관하며 전체 112,103,234 B의 재조합 SHA-256이 원문과 일치한다.

검토 대상 881개의 처리는 다음과 같다. 세부 경로·해시·분류 근거는 [복구 manifest](../migration_restore_20261028/manifest.json)에 있다.

| 처리 | 항목 수 |
|---|---:|
| 외부 학습·검토·재현 기록을 원문 그대로 복사 | 485 |
| 이미 같은 바이트인 Git blob 경로 매핑 | 57 |
| 저장소의 원래 학습·검토 원문 경로 보존 | 245 |
| 큰 원문을 손실 없이 분할 | 1 |
| 기존 평가 전용 외부 보존 규칙 유지 | 76 |
| 평가·혼합 vLLM 요청 로그 외부 보존 | 17 |

위 485·57·245 = **787개 항목**은 실제 `1a82099`의 Git blob과 크기·SHA-256까지 다시 대조했다([검증 기록](git_blob_verification.json)). 별도 inventory generated 기록 7개도 편입했다. 가중치·환경·캐시는 외부에 둔다. 기존 평가 전용 93개는 data의 통합 경로에 보존되며 학습·검토 원문 미커밋 규칙의 근거로 재사용하지 않는다. Git 보존은 학습 승인과 별개다.

원문 보존 정책은 결정 256·257과 [DATA_RETENTION.md](../DATA_RETENTION.md)를 따른다. `S128F_raw.jsonl` 원본만 GitHub 제한 때문에 정확한 경로로 ignore하며, 추적되는 조각·manifest가 전체 원문 바이트를 보존한다. `git add -f`는 사용하지 않았다.

## 새 실행 환경과 경로

실행 환경은 `/data/hwkim/sftdpo_work/runtime/envs/`의 `hf`, `vllm`, `llamacpp`, `uvtool`이다. 각각 Python 3.12.3 / 3.12.14 / 3.12.3 / 3.12.3 및 관측된 배포 패키지 106 / 199 / 30 / 2개의 버전이 일치한다. 네 환경 `pip check`와 CPU import가 통과했다. HF·vLLM의 CPU import 파일 접근 trace에서는 구 home 접근 0건이었다.

오프라인 캐시를 사용했고, 캐시에 없던 HF CUDA 배포 패키지 16개는 원래 설치 파일의 RECORD 해시·크기를 검증해 wheel로 재구성했다. 이는 원래 배포 wheel과 동일하다는 주장이 아니다. [환경 설명](runtime/README.md), `*_wheels.json`, `environment_validation.json`에 출처와 범위를 기록했다. 모델을 다운로드하지 않았다.

llama.cpp b11434의 CPU quantizer는 `runtime/native/llama.cpp-b11434/build/bin/llama-quantize`로 새로 빌드했다. 동적 라이브러리 누락·구 home 의존은 없다. help/version 검사에서는 usage를 출력하고 종료 코드 1을 반환했으며, 모델 로딩·양자화 자체는 실행하지 않았다. OpenSSL 헤더가 없어 HTTPS 지원은 비활성이다.

과거 동결 스크립트·설정은 바꾸지 않고 sibling `gpu_data`, `train_data`, `teacher_data` 실행 파일 149개를 새로 만들었다. `runtime/render_manifest.json`은 모든 원본·파생 해시와 치환을 기록한다. 코드·설정·guard·timeline 도구는 고정 worktree에서 가져오고, 기존 입력·로그·ready·결과는 원래 main 저장소 경로를 사용한다. 경로 검토에서 발견한 HERE 기반 입력 누락과 main 코드 참조를 수정했다. 원본·파생 해시, Python/셸/JSON 구문, 경로 검사 및 작업 명령 구성 25개가 통과했다.

새 작업은 **이 문서와 실행 스냅샷을 포함한 커밋**을 기준으로 worktree를 고정해 실행한다. 작업표·설정 생성은 커밋과 pin 전에 끝낸다. 새 `make_jobs_rerun10.py`의 `--apply`는 기존 자료와 고정 스냅샷을 덮어쓰지 못하도록 차단했다. 복사된 작업표는 과거 기록이며 완료 실험 재실행 지시가 아니다.

이관 관련 CPU 테스트 **27개 통과**. GPU·Ollama·학습 작업·모델 추론은 시작하지 않았다. 새 경로의 실제 GPU 동작과 모델 결과 동등성은 이번 검증 범위에 포함되지 않는다.
