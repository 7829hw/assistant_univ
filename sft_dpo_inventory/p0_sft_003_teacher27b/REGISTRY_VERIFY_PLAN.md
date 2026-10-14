# 27B registry manifest 검증 계획

고정: 2026-10-14, registry 요청 전. 결정 78.

이번에 하는 일은 manifest metadata 조회뿐이다. pull, blob 다운로드, import, copy, 27B·8B·HF 호출은 하지 않는다.

## 1. 요청(정확히 1회)

- **endpoint**: `https://registry.ollama.ai/v2/library/qwen3.8/manifests/27b`
- **method**: GET 1회. 응답 header와 manifest body를 함께 받는다(HEAD를 따로 보내지 않는다).
- **Accept**: `application/vnd.docker.distribution.manifest.v2+json`(Ollama manifest 형식)
- **redirect**: 따라가지 않는다(curl `-L` 없음). 3xx가 오면 Location만 기록하고 중단한다.
- **크기 제한**: `--max-filesize 1048576`(1 MiB). 넘으면 curl이 받기를 멈춘다. manifest는 수 KB여야 한다.
- **시간 제한**: 30초.
- 인증 header는 보내지 않는다. 응답의 token·secret 성격 header(`Authorization`, `Set-Cookie`, `Www-Authenticate`)가 있으면 값을 지우고 저장한다.
- 쓰지 않는 것:
  - `/v2/.../blobs/<digest>` 요청
  - layer range 요청
  - 다른 tag·endpoint 탐색
  - `ollama pull`

## 2. 기대값

- `Docker-Content-Digest` = `sha256:aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`
- 64 hex가 전체로 같아야 한다. prefix 일치는 인정하지 않는다.

## 3. 저장(`registry/`)

| 파일 | 내용 |
|---|---|
| `response_headers.txt` | 응답 header 원문(민감 header 값 제거) |
| `manifest.json` | 응답 body 원문 바이트 그대로 |
| `request_meta.json` | timestamp, endpoint, method, HTTP status, content-type, content-length, redirect chain, user-agent, 받은 바이트 수 |
| `hashes.json` | 아래 digest를 서로 섞지 않고 따로 적는다 |

`hashes.json`에 따로 적는 digest:

- HTTP `Docker-Content-Digest`
- manifest body 로컬 sha256
- config.digest
- layer digest 목록

manifest에서 기록할 것:

- schemaVersion, mediaType
- config.digest, config.size
- layers[]의 mediaType·digest·size·from(있으면)
- model layer 크기, 전체 layer 크기 합(과거 17.7 GB와 대략 비교, 크기만으로 동일성 판정하지 않음)

## 4. 판정

| 판정 | 조건 |
|---|---|
| PROVENANCE_REGISTRY_MATCH | Docker-Content-Digest가 기대값과 전체 일치 |
| PROVENANCE_REGISTRY_MISMATCH | Docker-Content-Digest가 있고 기대값과 다름 |
| PROVENANCE_UNRESOLVED | 404, 인증 문제, header 없음, 예상 밖 형식, registry 불가 |

- 동일성 판정은 Docker-Content-Digest exact match만 근거로 한다.
- 참고값: body 로컬 sha256이 Docker-Content-Digest와 같은지도 기록한다.

## 5. stop rule

다음이면 즉시 중단하고 보고한다.

- 응답이 1 MiB를 넘음
- content-type이 manifest가 아님(binary·octet-stream 등)
- 3xx redirect
- blob 성격 응답

결과가 기대와 달라도 다른 endpoint·tag를 반복 조회하지 않는다. 추가 조사는 별도 결정으로 한다.
MATCH여도 pull하지 않는다(별도 사용자 승인).
