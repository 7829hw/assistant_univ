# SFT/DPO 전체 이관 목록과 독립 검사 — 2026-10-28, 분류 2판

두 외부 작업 폴더를 `/data/hwkim/sftdpo_work`로 통합하기 위한 파일 단위 목록이다. **이번 작업에서는 원본을 이동·삭제하거나 학습 데이터를 새로 Git에 편입하지 않았다.** 목록과 생성·검사 도구만 작성했다.

물리 스캔: 2026-10-28 22:58:20–23:08:09 KST. 기준 HEAD: `01648d55fb4354dd6fdf32f39a9b3addec8597c2`. 그 뒤 생산 목적 문서와 GPT‑6.1 Terra 검토를 반영한 분류 2판을 적용했다. 분류 보정 전후 물리 증거 필드는 동일하다.

## 범위와 완전성

| 원본 | 전체 항목 | 일반 파일 | 디렉터리 | 링크 | 파일 논리 크기 GiB | 파일 할당 블록 합 GiB |
|---|---:|---:|---:|---:|---:|---:|
| `/home/hwkim/sftdpo_work` | 182,724 | 163,617 | 18,005 | 1,102 | 281.761 | 282.128 |
| `/data/hwkim/sftdpo_work` | 176 | 154 | 22 | 0 | 97.227 | 105.721 |

- 외부 합계 **182,900개**. 빈 디렉터리, 가상환경, 캐시, 빌드 산출물, 중첩 `.git`, 링크를 모두 포함한다. 링크를 따라 원본 범위를 확장하지 않았다.
- 일반 파일 **163,771개** 중 **163,684개**는 새로 SHA‑256을 계산했다. 최종 평가셋 **87개**는 기존 실험 열람 제한에 따라 이름·크기·권한 등 메타데이터만 기록했다. 해시와 본문은 읽지 않았다.
- 저장소 내부 보조 목록 **2,133개**도 포함한다. 일반 파일 2,010개는 모두 해시를 계산했다. 범위는 `training/generated`, `training/annotations/generated`, `training/experiments`, `evaluation/real_data/records`이며, 현재 존재하는 것은 첫 번째뿐이다.
- 스캔 전후 재열거에서 원본 추가·삭제·메타데이터 변경 0, 순회 오류 0, 해시 오류 0. Git HEAD와 index도 스캔 동안 같았다.
- 독립 검토자가 다른 열거 코드로 외부 182,900개와 저장소 2,133개를 실제 경로와 대조해 누락·추가 0을 확인했다.

논리 크기는 파일 길이의 합이다. 할당 블록 합은 각 일반 파일의 `st_blocks × 512` 합이며 파일시스템 전체 사용량이나 이전 후 필요한 공간의 확정값이 아니다. 디렉터리 블록과 파일시스템의 별도 비용도 이 표의 파일 합과 다르다.

## 산출물

| 파일 | 용도 |
|---|---|
| [external_entries.jsonl.gz](external_entries.jsonl.gz) | 외부 전체 항목별 원본·목적지·유형·크기·SHA·권한·소유자·시간·inode·xattr 해시·링크·보존 분류 |
| [repository_entries.jsonl.gz](repository_entries.jsonl.gz) | 저장소 내부 데이터와 현재 Git 보존 상태 |
| [actions.csv](actions.csv) | Git 보존 검토 대상별 경로·ignore·근거·필요 조치 |
| [groups.csv](groups.csv) | 원본별 최상위 폴더 건수와 크기 |
| [git_candidates.jsonl.gz](git_candidates.jsonl.gz) | Git 보존 검토 대상 881개와 제안 보존 경로 |
| [collisions.json](collisions.json) | 외부 목적지가 겹치는 항목과 조상 경로 충돌 |
| [git_archive_conflicts.json](git_archive_conflicts.json) | 제안 Git 보존 목적지 충돌 검사 |
| [link_analysis.jsonl.gz](link_analysis.jsonl.gz) | 링크 1,102개의 원문과 보존·재작성 시 경로 투영 |
| [path_references.json.gz](path_references.json.gz) | 기존 경로를 참조하는 Git 추적 텍스트 파일 2,583개와 줄 번호 |
| [classification_review.json](classification_review.json) | 생산 목적에 근거한 최종 분류 규칙 |
| [classification_changes.json](classification_changes.json) | 2차 검토에서 바꾼 224개 항목 |
| [classification_changes_r1.json](classification_changes_r1.json) | 1차 보정 153개의 이력 |
| [classification_review_r1.json](classification_review_r1.json) | 1차 보정 규칙 |
| [summary.json](summary.json), [scan_issues.json](scan_issues.json) | 합계, 범위, 오류·변경 및 검증의 한계 |
| [artifacts.json](artifacts.json) | 기계 산출물 15개와 `.gitattributes` 보존 설정의 파일 크기·SHA‑256(총 16개) |
| [REVIEW.md](REVIEW.md) | GPT‑6.1 Terra 3개 서브에이전트의 독립 검사 결과 |

JSONL 압축 파일은 한 줄이 한 항목이다. `source_path`가 원본, `destination_path`가 물리 보존 목적지다. `git_archive_path`는 Git에 원본 기록을 편입할 때 사용할 **제안 위치**이고, 실제 편입·중복 판단은 별도다. `category`와 `git_disposition`에서 확정 역할과 생산 목적 검토 후보를 구분한다.

`artifacts.json`은 자체와 설명 문서 `README.md`, `REVIEW.md`를 제외한다. 설명 문서는 Git 커밋으로 함께 보존한다. `.gitattributes`의 `* -text`로 CSV의 CRLF를 포함한 원본 바이트를 체크아웃에서도 유지한다. 생성기·분류 보정기 SHA‑256은 `summary.json`에 있다.

## 물리 이관 매핑

`home/<상대경로>` → `/data/hwkim/sftdpo_work/<상대경로>`로 원본 바이트와 메타데이터를 보존한다. 기존 `data/<상대경로>`는 현재 위치에 유지한다. 동일 이름의 `pilot_002`는 home의 checkpoint·기록과 data의 merged 모델이 함께 들어가는 구조다. 저장소 자체의 물리 위치 변경은 이번 목록의 범위에 포함하지 않았다.

내용이 다른 일반 파일, 유형, 조상 경로 및 제안 Git 보존 목적지의 충돌은 **0개**다. 양쪽에서 겹치는 디렉터리는 루트, `gguf`, `pilot_002`, `pilot_004`, `pilot_005`의 **5쌍**이다. 실제 차이는 수정 시각이며 mode 775·uid/gid 1004·xattr는 같다. 양쪽 원래 시각은 목록에 각각 보존했다. 합쳐진 디렉터리의 시각 처리 방식을 이관 실행 기록에 남겨야 한다.

복사는 원본을 남긴 채 수행하고, 파일 해시·링크·권한을 검증한 뒤 구 경로를 정리한다. 가상환경·빌드·worktree의 보존 목적지에 파일이 있다는 사실은 해당 환경이 실행 가능함을 뜻하지 않는다. `runtime_requirement`가 `rebuild` 또는 `recreate_worktree`인 그룹은 새 실행 환경으로 재구축한다. 과거 동결 설정·manifest·로그의 내부 경로와 해시는 일괄 치환하지 않는다.

## Git 보존 검토 결과

- 전체 후보 **881개**, 파일 크기 합 **1,028,642,450 B**. 이미 동일 바이트가 index에 있는 자료도 포함한다. 경로 단위 집계이며 내용 중복을 제거한 수가 아니다.
- 동일 index blob을 찾지 못한 후보 **630개**. 정보 자체가 사라졌다는 의미는 아니며, 다른 형태의 요약·로그가 있을 수 있다.
- producer 검토 상태인 후보 **301개**. 이 중 과거 평가 증거 76개는 당시 보관 정책을 확인한 뒤 Git 편입 여부를 정한다. 후보 표시는 학습 승인이나 자동 복사 지시가 아니다.
- 학습·검토 원문 **54개**는 제안 경로가 현재 `.gitignore`에 걸린다. 실제 복구 단계에서 해당 학습 원문 제외 규칙을 바꾸고 일반 `git add`를 사용한다.
- `training/generated/pilot_006/self_2d/raw/S128F_raw.jsonl`은 **112,103,234 B**다. 손실 없는 JSONL 분할과 원본 재조합 SHA‑256 확인 등 보존 방식을 먼저 정한다.
- 실데이터에는 결정 256의 Git 보존 정책을 적용한다. 해당 `records/` 디렉터리는 현재 존재하지 않는다.

문서 근거 검토로 batch006·007 및 aug300·batch008의 첫 응답을 학습 후보 검토 기록으로, `realtrip_vllm`을 실제 학습 원천으로 분류했다. pilot 003–005와 pilot_006_prep의 나머지 59개 원문은 선택·판정·smoke·중단 평가 기록으로 확인했다. tokenizer/model card/config 등 모델 배포 부속 165개도 학습 기록 후보에서 분리했다. 최종 `pending_classification` 항목은 0이지만, 위의 producer 검토 후보는 남아 있다.

원시 파일의 Git blob SHA‑1과 index를 바이트 단위로 대조한다. 다른 경로에서 동일 blob이 발견됐다는 사실과 같은 경로에서 추적된 사실은 구분한다. `.gitattributes`/줄바꿈 정규화를 적용한 동등성, 과거 Git 이력, 원격 보존까지 증명하는 검사는 아니다.

## 구 home 의존 링크

| 원본 상대경로 | 현재 링크 대상 |
|---|---|
| `cuda_link/libcudart.so` | `/home/hwkim/sftdpo_work/vllmvenv/lib/python3.12/site-packages/nvidia/cu13/lib/libcudart.so.13` |
| `uv-python/cpython-3.12-linux-x86_64-gnu` | `/home/hwkim/sftdpo_work/uv-python/cpython-3.12.14-linux-x86_64-gnu` |
| `vllmvenv/bin/python` | `python3.12` |
| `vllmvenv/bin/python3` | `python3.12` |
| `vllmvenv/bin/python3.12` | `/home/hwkim/sftdpo_work/uv-python/cpython-3.12.14-linux-x86_64-gnu/bin/python3.12` |

직접 절대 참조 3개와 링크 연쇄 참조 2개다. 제안된 재작성 후 투영에서는 5개 모두 통합 트리의 대상으로 이어진다. 다른 링크 9개는 OS 등 기존 외부 경로에 의존한다. 파일 경로 투영은 실행 환경 검증을 대신하지 않는다. pip shebang·`pyvenv.cfg`·CMake 경로 등 파일 내부 참조는 환경 재구축과 새 실행 설정으로 처리한다.

## 검사와 다음 실행 조건

생성기 경계·실제 CLI·보호 파일·동일 inode·링크와 `..`·목적지 조상 충돌·분류 보정에 대한 CPU 테스트 **17개 통과**. 독립 목록 검사와 무결성 검사는 통과했다. 이관은 아직 수행하지 않았다.

실제 이관 직전에는 새 스캔으로 원본 변화를 확인하고, producer 후보 301개·ignore 54개·대용량 원문 1개·디렉터리 시각 5쌍·home 의존 링크 5개·환경 재구축·보호 최종셋 87개의 보존 검증 절차를 실행 계획에 반영한다. 보호 최종셋은 내용과 해시를 읽지 않았으므로 bytes 동일성을 이번 목록으로 입증하지 않는다.

## 재생성 도구

- [build_migration_inventory.py](../../scripts/build_migration_inventory.py): 원본 읽기 전용 전체 열거·해시·충돌·링크·index 대조.
- [list_migration_path_references.py](../../scripts/list_migration_path_references.py): Git 추적 텍스트의 경로 참조 위치만 수집. 보호 이름 경로 28개와 비대상 형식은 내용 검색하지 않는다.
- [refine_migration_inventory.py](../../scripts/refine_migration_inventory.py): 문서 근거 분류 보정. 물리 증거를 유지하고 revision별 이전 검토 이력을 남긴다.

기존 확정 목록을 덮어쓰지 않고 새 출력 디렉터리로 재생성한다. 전체 해시는 디스크 읽기를 수반하므로 낮은 I/O·CPU 우선순위로 실행한다. SQLite 해시 캐시는 `/tmp`에만 두었고 저장소에 포함하지 않았다. 이번 스캔은 모든 일반 파일을 새로 읽었으며, 보호 최종셋은 해시 캐시에도 넣지 않았다.
