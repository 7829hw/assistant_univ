# 27B teacher 반입 계획(계획만, 반입·호출하지 않음)

2026-10-14. 결정 72. 대상은 `teacher27b_manifest.json`(31문항)이다.

## 1. 과거 승인 teacher의 정확한 identity(저장소 기록)

| 항목 | 값 | 근거 |
|---|---|---|
| 이름 | Ollama `qwen3.8:27b` | 결정 21·48·50, `pilot_prep_003/teacher/collect_teacher.py` |
| digest | `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813` | `pilot_prep_003/teacher/*/summary.json`, README "검증한 실행 명세" |
| 형식 | Ollama 모델(GGUF), 양자화 Q4_K_M | 같은 summary(`quantization`) |
| 경로 | Ollama `/api/chat`. HF가 아니다 | collect_teacher.py |
| 크기 | 17.7 GB | README 1366행, `evaluation/vendor/meeting_brief_260917.md` |
| GPU 사용 | size_vram 18,542,682,438 B(약 17.3 GiB), 모델 기본 context 262,144 | `evaluation/grounding_v11/runs/small/t2p/dev.json` meta |
| capabilities | completion, vision, tools, thinking | 같은 meta |
| Modelfile 기본값 | temperature 1, top_k 20, top_p 0.95, min_p 0, presence_penalty 0, repeat_penalty 1, draft_num_predict 4 | 같은 meta |
| 과거 실행 | Ollama 0.34.4(평가)·0.35.1(teacher), 옛 장비 GPU 3 컨테이너 | summary, README |
| 과거 teacher 설정 | `think: true`, temperature 0.6, 질문당 표본 8, seed = 20261006 + 1000×순번 + 표본 번호, 그 밖은 Modelfile 기본. prompt는 Full `87048d0c` | collect_teacher.py, summary |

- **출처(registry·원본 파일)는 저장소에 기록이 없다.**
  - `qwen3.8:27b`는 별칭이고, 어디서 받거나 만든 모델인지 적힌 곳이 없다.
  - 그래서 별칭만 보고 같은 이름의 모델을 받지 않는다.
  - 반입 원본은 사용자가 지정해야 한다(예: 옛 장비 Ollama 저장소의 blob). 반입 뒤 digest가 `aaee06c3…`와 같아야 같은 모델로 인정한다.

## 2. 현재 환경(2026-10-14 확인, 읽기 전용 조회)

| 항목 | 값 |
|---|---|
| Ollama 컨테이너 버전 | 0.40.3(과거 teacher 0.35.1과 다르다) |
| 모델 저장소 | `/data/hwkim/ollama`(4.9 GB). `qwen3:8b`(digest `500a1f06…`)만 있다 |
| 27B 존재 | **없다**(`/api/tags`에 없음) → 새 반입이 필요하다 |
| 디스크 | `/data` 여유 약 11 TB. 17.7 GB 반입에 문제없다 |
| GPU | RTX PRO 6000 Blackwell 1장(97,887 MiB), HF와 Ollama가 같이 쓴다. 지금 비어 있다 |

## 3. 반입 절차(사용자 승인 뒤에만)

1. 사용자가 원본을 지정한다(옛 장비 Ollama 모델 저장소 또는 승인된 registry 경로).
2. 원본 manifest의 digest가 `aaee06c39dcf…`인지 반입 전에 확인한다.
3. 반입 방법은 사용자 승인 범위 안에서만 쓴다(CLAUDE.md 4번: pull 금지·컨테이너 재설정 금지). 예: 승인된 blob 복사 뒤 컨테이너 저장소 인식.
4. **무결성**: 반입 뒤 `/api/tags` digest = `aaee06c3…`, 그리고 `/api/show`의 Modelfile 파라미터·capabilities가 1절 기록과 같은지 확인한다.
5. **렌더링 확인**: 결정 31과 같은 방식으로 thinking 켬·thinking/본문 분리를 10문항에서 확인한다.
   - 0.40.3에서 context 기본값이 바뀌었을 수 있다. `context_length`를 기록하고 과거(262,144)와 다르면 보고한다.
6. **삭제 정책**: 기존 Ollama 모델은 덮어쓰거나 지우지 않는다(CLAUDE.md 12번 취지). teacher 수집과 검토가 끝난 뒤 삭제 여부는 사용자가 정한다.

## 4. 승인 뒤 teacher 생성 계획(지금 고정)

- **대상**: `teacher27b_manifest.json` 31문항(M1 ∩ {P1, P2}). M2 결과로 바꾸지 않는다.
- **prompt**: P0(`d7f4c12a`)이며 입력은 [system, user]다. gold를 주지 않는다. `think: true`.
- **표본**:
  - 문항당 greedy 1(temperature 0) + sampling 4(temperature 0.6, top_p 0.95, top_k 20을 명시), 최대 155 호출.
  - sampling seed = `2026101500 + 10 × 문항 순번 + 표본 번호`(문항 순번 = manifest 정렬 순서). 과거 seed와 겹치지 않는다.
  - num_predict는 지정하지 않는다(과거와 같음). 생성 상한 도달은 기록한다.
- **격리**: Ollama 데이터 수집이므로 문항마다 모델을 내리는 unload_per_question이다(CLAUDE.md 14번, resident 계열 금지).
  - 셀마다 GPU 확인과 속도 guard를 한다(CLAUDE.md 13번). 기준값은 첫 셀 전에 PLAN_DEVIATIONS에 적는다.
- **HF 작업과 동시에 돌리지 않는다**(GPU 1장 공유).
- **판정**: `collect_p0_traces_hf.judge`와 같은 5범주다. EXACT_OR_SEMANTIC_MATCH만 reasoning 후보로 둔다.
- **필터·선택·검토**: 8B M2와 같다.
  - 필터: 왕복·루프·길이
  - ranking: CLEAN_DIRECT → MINOR_SELF_CORRECTION → SELF_CORRECTED, 문항당 1개
  - 사람 검토 APPROVE/REJECT, 거부 시 대체하지 않음
- **보완 제안**: 이번 M2 검토에서 자동 tier가 "묶음 단위어를 concept·장소로 냄"을 잡지 못했다(CLEAN_DIRECT 3개 거부).
  - 27B 단계에서는 이 패턴을 감지하는 자동 지표를 ranking 앞에 추가하는 것을 별도 사전 등록으로 검토한다.
- **provenance**: teacher_model `qwen3.8:27b`, digest, Ollama 버전, generation_batch, seed, quality_tier, review_decision을 남긴다. 8B trace와 섞지 않는다.

## 5. 예상 비용

- 호출 155. 과거 teacher 기록상 문항당 수 초–수십 초이고, unload_per_question 로딩(17.7 GB)이 문항마다 붙는다.
- 대략 1–2시간으로 추정한다(실측 전 추정).
- 디스크 17.7 GB. GPU 약 17–19 GiB(context 설정에 따라 다름).
