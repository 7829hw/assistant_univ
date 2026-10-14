# 27B teacher provenance 조사 계획

고정: 2026-10-14, 조사 전. 결정 74–77. 모델 반입·복사·호출은 하지 않는다(읽기 전용 조사).

## 1. 대상

과거 승인 teacher는 Ollama `qwen3.8:27b`, digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`, Q4_K_M다.

## 2. 조사 범위(읽기 전용)

1. **저장소 현재 tree 전체**: `git grep`(모든 tracked 파일)으로 아래 검색어를 찾는다.
   - `qwen3.8:27b`, `aaee06c3`, `aaee06c39dcf2437`, `27b`, `Q4_K_M`
   - `ollama pull`, `ollama create`, `Modelfile`, `manifest`, `models/blobs`, `sha256-aaee`
2. **git history(모든 branch, 원격 포함)**:
   - `git log --all -S'qwen3.8:27b'`, `git log --all -S'aaee06c3'`, `git log --all -G'ollama (pull|create)'`
   - 최초 등장 commit, 그 앞뒤 commit, 주변 diff.
   - 원격 branch는 fetch만 한다. history는 바꾸지 않는다.
3. **현재 서버 파일시스템**: 저장소 기록이 가리키는 경로와 프로젝트 경로만 본다.
   - Ollama store `/data/hwkim/ollama`(manifests, blobs 이름)
   - `/data/hwkim`, `/home/hwkim`의 프로젝트 관련 디렉터리(최상위 이름, 기록이 가리키는 경로)
   - 기록에 나오는 옛 경로(`/home/hwkim/sftdpo_work` 등)의 존재 여부
4. **shell history**: 정확한 문자열(`qwen3.8:27b`, `ollama pull`, `aaee06c3`)만 검색한다. 관련 없는 내용은 보고서에 옮기지 않는다.
5. **Docker/Ollama metadata**: `docker inspect ollama`의 mount·image 정보, 컨테이너 로그에서 `27b`·`aaee06c3` 줄만 본다(읽기만).

## 3. 기록 항목

evidence마다 다음을 남긴다(`provenance.json`):

- path 또는 명령
- commit
- line 또는 key
- timestamp
- claim

## 4. 판정

| 등급 | 조건 |
|---|---|
| PROVENANCE_EXACT | 원본 artifact·registry와 exact source identifier, 예상 digest, 과거 digest 연결 근거가 모두 있음 |
| PROVENANCE_COPY_SOURCE | registry 원본은 모르지만, 과거 Ollama store의 정확한 manifest·blob을 가진 승인 가능한 복사 원본이 있음(digest로 동일성 확인 가능) |
| PROVENANCE_PARTIAL | alias, digest, quantization, runtime metadata만 있고 원본은 모름 |
| PROVENANCE_CONFLICT | 후보 원본이 여럿이고 어느 것이 `aaee06c3…`인지 확정 못 함 |

- PARTIAL이면 이름만 보고 pull하지 않는다. 웹에서 비슷한 이름도 찾지 않는다. 사용자에게 원본 지정을 요청한다.
