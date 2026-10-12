# Ollama 진단 모델·pilot 모델 정리 목록(결정 78, T)

작성: 2026-10-12. **지우지 않았다.** 지우는 것은 사용자가 승인한 뒤에만 한다(`CLAUDE.md` 12번, 결정 78).
결정 76(R)으로 Ollama 양자화 경로가 운영 대상이 아니게 되어, 진단 모델과 pilot 모델을 지울 후보로 모은다.

자료: `/api/tags`(이름, digest, 크기)와 서버 저장소 manifest(`/data/hwkim/ollama/models/manifests/…`, 가중치 blob과 공유 여부). 조회만 했고 모델은 올리지 않았다.
크기는 manifest 전체(가중치 + TEMPLATE·PARAMETER 등 작은 층)다. "회수"는 지웠을 때 실제로 비는 가중치 blob 크기다(다른 모델과 나눠 쓰는 blob은 남는다).

## 1. 지울 목록(결정 78의 대상)

| 기록 이름 | Ollama 이름 | digest | 크기(B) | 가중치 blob | 회수 | 등록 목적(결정) |
|---|---|---|---:|---|---:|---|
| (c) | `geoflow-diag-qwen3-8b-official-hftmpl:q4km` | `f83b28a9a456` | 5,225,386,634 | `a3de86cd…`(qwen3:8b와 공유) | 0 | 변환 진단: 공식 blob + HF TEMPLATE(결정 61) |
| (d) | `geoflow-diag-qwen3-8b-b968826d-base:q8_0-hfthink` | `3c3843ae15ae` | 8,709,519,518 | `6f7c42fd…` | 8.71 GB | 변환 진단: base Q8_0(결정 61) |
| (e) | `geoflow-diag-qwen3-8b-pilot002-final:q8_0-hfthink` | `b608abf0337a` | 8,709,519,038 | `47ba910c…` | 8.71 GB | 변환 진단: pilot_002 최종 Q8_0(결정 61) |
| B-off | `geoflow-diag-qwen3-8b-b968826d-base:q4km-official-hfthink` | `662eadb20a95` | 5,225,375,904 | `c55752ae…` | 5.23 GB | 공식 방식 Q4 진단: base(결정 75) |
| F-off | `geoflow-diag-qwen3-8b-pilot002-final:q4km-official-hfthink` | `eab3da9ce9a1` | 5,225,375,424 | `6daac753…` | 5.23 GB | 공식 방식 Q4 진단: pilot_002 최종(결정 75) |
| pilot_001 SFT | `geoflow-qwen3-8b-pilot001-sft:q4km-hfthink` | `b4b4777c9cd4` | 5,027,784,384 | `d0b884ea…` | 5.03 GB | pilot_001 고른 SFT(결정 20) |
| pilot_001 최종 | `geoflow-qwen3-8b-pilot001-final:q4km-hfthink` | `c6ce2746dbc0` | 5,027,784,384 | `dc319447…` | 5.03 GB | pilot_001 최종 SFT+DPO(결정 20) |
| pilot_002 SFT | `geoflow-qwen3-8b-pilot002-sft:q4km-hfthink` | `1a813e0a6248` | 5,027,784,384 | `8cda8c95…` | 5.03 GB | pilot_002 고른 SFT(결정 20) |
| Ollama-final | `geoflow-qwen3-8b-pilot002-final:q4km-hfthink` | `c2d10cb20788` | 5,027,784,384 | `ab359d09…` | 5.03 GB | pilot_002 최종 SFT+DPO(결정 20) |

회수 합계(9개를 모두 지울 때): 약 48.0 GB.

## 2. 결정 78의 목록에 없어 사용자 확인이 필요한 것

| 기록 이름 | Ollama 이름 | digest | 크기(B) | 회수 | 등록 목적 | 비고 |
|---|---|---|---:|---:|---|---|
| B-conv | `geoflow-qwen3-8b-b968826d-base:q4km-hfthink` | `ab29de1974df` | 5,027,784,864 | 5.03 GB | base Qwen3-8B 변환(결정 20) | 결정 78의 대상(진단 모델, pilot 모델)에 이름이 없다. 지울지 사용자가 정한다. |

## 3. 남기는 것

- `qwen3:8b`(`500a1f067a9f`): 참고 셀 E(결정 76). (c)를 지워도 가중치 blob `a3de86cd…`는 이 모델이 쓰므로 남는다.
- 다른 사용자·다른 작업의 모델(gemma4, qwen3.5, qwen3.8): 이 목록과 무관하다.
- 저장소에 남은 LoRA blob: 결정 67로 그대로 둔다.

## 4. 지울 때(사용자 승인 뒤)

- 측정 중이 아닐 때(`/api/ps`가 비었을 때) 한 번에 하나씩 `ollama rm <이름>`으로 지우고, 지운 이름·digest·시각을 이 문서 아래에 적는다.
- 기록(평가 결과, 등록 기록, 렌더링 확인)은 저장소에 그대로 남는다. 지운 모델은 GGUF(저장소 밖)로 다시 만들 수 있다.

## 정리 결과(2026-10-13, 결정 82(X))

- 지우기 전(00:25, `/api/ps` 빈 상태, Ollama 0.35.1): 위 1절 9개 + 2절 B-conv(`ab29de1974df`, 5,027,784,864 B, base 변환 결정 20) = 10개. 이름·digest·크기·등록 목적은 1·2절과 같다(`/api/tags`로 다시 확인).
- 남길 모델의 digest(지우기 전): `qwen3:8b` `500a1f067a9f`(E), `qwen3.8:27b` `aaee06c39dcf`, `qwen3.5:9b` `6488c96fa5fa`, `gemma4:12b` `4eb23ef187e2`, `gemma4:e4b` `c6eb396dbd59`.
- 삭제: Ollama API `DELETE /api/delete`로 10개, 모두 HTTP 200(2026-10-13T00:25:24+09:00). 저장소 파일은 직접 지우지 않았다. 컨테이너는 건드리지 않았다.
- 지운 뒤 `/api/tags`: 위 5개만 남음. **E `qwen3:8b` digest `500a1f067a9f` 그대로.** 나머지 4개 digest도 그대로.
- 저장 공간: blob 디렉터리 99735288627 B → 46726582746 B(약 53.0 GB 감소, blob 파일 33 → 21개). `/data` 사용량 529,607,782,400 B → 476,598,919,168 B.
  예상(1절 48.0 GB + B-conv 5.03 GB = 53.0 GB)과 같다. (c)가 쓰던 `a3de86cd…` blob은 E가 쓰므로 남았다.
- 결정 67의 LoRA blob(`sha256-675ad6e6…`, 175,115,584 B)은 그대로 있다.
