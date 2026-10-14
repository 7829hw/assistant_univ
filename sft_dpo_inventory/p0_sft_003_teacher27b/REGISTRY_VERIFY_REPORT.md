# 27B Registry Manifest 검증

2026-10-14. 계획 `REGISTRY_VERIFY_PLAN.md`(커밋 `dd5ee24`), 결정 78. 원 기록은 `registry/`, 판정은 `registry_verdict.json`.

## 1. 결론

- 판정: **PROVENANCE_UNRESOLVED**(사전 등록 규칙).
  - registry 응답에 `Docker-Content-Digest` header가 없었다. 계획 4절은 이 header만 동일성 근거로 정했다.
- 다만 **받은 manifest body(986 B)의 sha256이 기대 digest와 64 hex 전체가 정확히 같다**: `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`.
  - Ollama의 로컬 모델 digest(`/api/tags`)는 manifest 파일 바이트의 sha256이다.
  - 그래서 이 일치는 현재 `library/qwen3.8:27b` tag가 과거 승인 teacher와 같은 manifest를 가리킨다는 강한 근거다.
  - 그러나 규칙을 결과 뒤에 바꾸지 않았다. 이 근거를 인정할지는 사용자 결정이다(10절).
- layer 크기 합 17,741,871,939 B(≈ 17.7 GB)가 과거 기록과 맞는다. layer `from`은 `qwen3.8:27b-q4_K_M`이다.
- model blob 다운로드 0 byte, 27B·8B·HF 호출 0회.

## 2. Git 무결성

- 시작: local = remote = `7400afc`, 작업 트리 깨끗함, branch `geoflow/partial-grounding`. 마지막 decision 77 → 이번 78.
- 작업 단위마다 commit → push → fetch 후 HEAD = `origin/geoflow/partial-grounding`을 확인했다.

| 단위 | commit |
|---|---|
| 계획·결정 78 | `dd5ee24` |
| manifest 조회 원 기록 | `3e000cd` |
| 판정 | `fd74065` |
| REPORT | 이 커밋 |

## 3. 요청 범위

| 항목 | 값 |
|---|---|
| endpoint | `https://registry.ollama.ai/v2/library/qwen3.8/manifests/27b` |
| method | GET 1회 |
| Accept | `application/vnd.docker.distribution.manifest.v2+json` |
| redirect | 0회 허용(`--max-redirs 0`) |
| 크기 제한 | 1 MiB |
| 인증 header | 보내지 않음 |
| 그 밖 | blob 요청·다른 tag 조회·pull 0 |

## 4. HTTP 응답(`registry/request_meta.json`, `response_headers.txt`)

| 항목 | 값 |
|---|---|
| 시각 | 2026-10-14T08:38:51Z |
| status | HTTP/2 200 |
| content-type | `application/vnd.docker.distribution.manifest.v2+json` |
| content-length | 986(받은 바이트 986) |
| redirect | 없음 |
| 그 밖 header | date, vary(Accept, User-Agent), via 1.1 google, server cloudflare, cf-cache-status DYNAMIC, cf-ray |
| 민감 header | 없음 |

## 5. Docker-Content-Digest

- **응답에 없음.** 그래서 기대값 `sha256:aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`과 header로 비교할 수 없었다.

## 6. Manifest metadata(`registry/manifest.json`, `hashes.json`)

| 항목 | 값 |
|---|---|
| schemaVersion | 2 |
| mediaType | `application/vnd.docker.distribution.manifest.v2+json` |
| runner / format | llamacpp / gguf |
| config | `sha256:492b2922d38e553cabc2d319345644ed482874fbf5e5c9e4495cbf8e17b0cf5f`(215 B) |

| layer mediaType | digest | size(B) | from |
|---|---|---:|---|
| image.projector | `sha256:ac3714bfdddeca31351f2752bf1a63f266f4df87c0b68c895e44945ca704448e` | 931,146,016 | qwen3.8:27b-q4_K_M |
| image.model | `sha256:f5f1dd8920d417aac2718b0bda3403da274301efdd6760b4f0f4b864ff2ad57d` | 16,810,714,464 | qwen3.8:27b-q4_K_M |
| image.license | `sha256:4c6a8e842ef0d8504549facfb03f1273a8d0022991519bc1888522cc1a5517d1` | 11,345 | qwen3.8:27b-q4_K_M |
| image.params | `sha256:906ee87bde6cff7bf3c3b1550f55cbbec261e027187fbb9f511f908ffc418334` | 114 | – |

- model layer 16,810,714,464 B(약 15.66 GiB). layer 합 17,741,871,939 B. config 포함 17,741,872,154 B.
- projector layer는 과거 capabilities의 vision과 맞는다.

## 7. 과거 digest와 비교

| 값 | 내용 | 기대값과 |
|---|---|---|
| HTTP Docker-Content-Digest | 없음 | 비교 불가 |
| manifest body 로컬 sha256 | `sha256:aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` | **64 hex 전체 일치** |
| config digest | `sha256:492b2922…` | 다른 종류의 값(비교 대상 아님) |
| model layer digest | `sha256:f5f1dd89…` | 다른 종류의 값(비교 대상 아님) |

## 8. Provenance 최종 판정

**PROVENANCE_UNRESOLVED**(사전 등록 규칙: header 없음).

- 이전 판정(PROVENANCE_PARTIAL)에서 달라진 점: registry tag가 지금 가리키는 manifest 바이트가 과거 digest와 정확히 같은 hash를 가진다는 근거가 생겼다.
- 이 근거를 동일성 증명으로 쓰려면 결정 78의 기준(header만 인정)을 바꾸는 사용자 결정이 필요하다.

## 9. 모델 반입 여부

- **반입하지 않았다.**
  - `ollama pull`, blob·layer 요청, import, copy 모두 0이다. model blob 다운로드 0 byte.
  - 27B·8B·HF 호출 0회. Ollama 모델을 올리지 않았고 GPU 상태도 바꾸지 않았다.
- `quality_gate_v1`은 바뀌지 않았다(`0c42288` 이후 변경 0).
- 31문항 manifest도 바뀌지 않았다(sha256 `65a016e0…`, id 순서 hash `9850b727…`).

## 10. 다음 승인 필요 사항

**A. body sha256을 동일성 근거로 인정하고 pull 승인(권장)**

- 근거: Ollama 로컬 digest의 정의가 manifest 바이트의 sha256이고, 받은 manifest 바이트가 그 값과 정확히 같다.
- pull 뒤에는 다음을 모두 통과해야 teacher generation을 시작한다(`GENERATION_PLAN.md` 4절):
  - `/api/tags` digest 전체 일치
  - Q4_K_M, Modelfile, capabilities, context, rendering 10문항
- 승인 문구 예:
  > "registry `library/qwen3.8:27b` manifest 바이트의 sha256이 과거 승인 digest aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813와 정확히 같으므로 이를 동일 artifact 근거로 인정한다(결정 78 보완). `ollama pull qwen3.8:27b`로 현재 Ollama store에 반입하는 것을 승인한다. 반입 뒤 digest·Q4_K_M·Modelfile·capabilities·context/rendering 검증을 통과하기 전에는 teacher generation을 시작하지 않는다."
- pull 시 registry가 manifest를 다시 받는다. 그때 manifest가 바뀌었으면 `/api/tags` digest 검증에서 걸린다.

**B. header 기준 유지**

- Docker-Content-Digest를 주는 다른 방법(예: 같은 endpoint를 HEAD로 조회)을 별도 결정으로 승인하거나, 옛 장비 원본을 찾는다.
- 이번 단계에서는 추가 조회를 하지 않았다(계획 5절).

승인을 받기 전에는 pull하지 않는다.
