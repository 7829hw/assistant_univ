# 평가 기록 신뢰성·검증 표시 정리와 실제 자료 검증 준비 (grounding_v15)

작성: 2026-10-05.
- T2PC 채택(grounding_v13)과 운영 기준 충족(grounding_v14) 기록은 그대로 둔다.
- 새 prompt 후보, 모델 탐색, 합성 held-out, 전체 모델 실측은 하지 않았다. 이번 단계의 모델 호출은 0회다.

## 1. 연속 실행의 재개

- **문제:** 이전 harness는 기존 JSONL에서 기준일·적재 방식·순서 세 값만 비교했다. 같으면 모델을 내리고 남은 문항만 실행해 같은 run에 붙였다.
  - `keep_loaded`에서는 앞선 처리 이력이 출력에 영향을 준다(grounding_v14). 그래서 이렇게 붙인 나머지 구간은 같은 연속 실행이 아니다.
  - 모델·prompt·코드·문항 파일·선택 문항·옵션이 바뀌어도 세 값만 같으면 기록이 섞일 수 있었다.
  - 명세가 없는 예전 행은 기본 조건으로 간주했다.
- **수정 (`evaluate_vendor100.py`, `execution_spec.py`):**
  - **실행 명세:** 결과에 영향을 주는 조건 전체를 명세로 묶는다. 명세의 hash는 각 행의 `run_spec_sha256`에, 명세 자체는 `<out>.spec.json`과 meta `run_spec`에 남긴다.
    - 모델·digest·Ollama 버전, planner prompt hash
    - 실행 의미 코드의 내용 지문, 문항 파일 hash
    - 선택 문항과 순서, 실행 옵션, 기준일·적재 방식·순서, 기록 재적용 출처 hash
  - **재개:** 명세가 다르면(다른 항목을 보여 줌) 또는 명세가 없는 이전 형식 행이면 이어 붙이지 않는다. 기존 기록은 그대로 읽고 채점할 수 있다.
    - `unload_per_question`: 문항마다 모델을 내리므로 명세가 같으면 새 세션 번호로 이어 붙인다.
    - `keep_loaded`: 재개를 거부한다. `--resume-new-session`일 때만 나머지를 별도 세션으로 기록한다.
    - 이전 요청을 다시 보내 상태를 복원하려 하지 않는다.
  - **측정 종류:** 행마다 `measurement`(live·replayed·mixed)를 적는다. meta에는 `sessions`, `pure_live`, `pure_continuous`가 남는다.
    - `pure_continuous`는 `keep_loaded`이고, 세션이 하나이고, 기록 재적용이 없을 때만 참이다.
- **테스트 (`tests/test_operational_controls.py`, 가짜 클라이언트와 작은 fixture):**
  - 중단 뒤 재개: 해제 run은 세션 2로 이어지고, keep_loaded run은 거부된다. 별도 세션으로 기록하면 순수 연속이 아님으로 표시된다.
  - 명세 불일치: digest·선택 문항·순서·옵션·문항 파일·코드 지문이 바뀌면 거부된다.
  - 이전 형식 행은 거부된다.
  - 기록 재적용 행은 순수 live가 아님으로 표시된다.

## 2. 검증 표시

- **문제:** 이전 표시는 모델·digest·Ollama·설정만 실행할 때 비교했다. prompt는 테스트에서만 확인했고, 코드는 실행 중 확인하지 않았다. 그런데도 "검증한 실행 명세와 같음"이라고 표시했다.
- **수정 (`assistant_cli.py`):**
  - **등록부:** 검증 명세를 등록부로 바꿨다. T2PC(기본)와 B(이전 기본, 되돌리기 대상)가 들어 있다.
  - **실행할 때 비교하는 항목:** 모델, digest, Ollama 버전, prompt hash, 실행 의미 코드 지문, 설정.
  - **표시 방식:** 머리말과 저장 기록에 일치·다름·확인 안 함(이유)·명세 밖을 나눠 적는다. "같음"은 다름과 확인 안 함이 모두 없을 때만 표시한다.
  - **코드 비교 방식:** 커밋이 아니라 `execution_spec.SEMANTIC_CODE` 파일 내용으로 비교한다.
    - 범위(64개 파일): geoflow/, 매크로·템플릿·예시, prompts/, schemas/, reference 데이터, Tool 실행·mock·reference provider, client·runtime.
    - 문서·평가 기록·테스트만 바뀐 커밋은 같은 지문이다. 예: b62f6dc와 현재 HEAD는 같은 지문 `97efa866…`.
    - `assistant_cli.py`는 지문에 넣지 않고, CLI가 넘기는 설정을 비교한다.
  - 사용자 지정 모델·환경변수 우선순위와 실행 허용은 그대로다.
- **테스트 (`tests/test_cli_run_settings.py`):**
  - 비교 결과가 일치·다름·확인 안 함으로 정확히 나뉜다.
  - 확인 안 함이 있으면 "같음"으로 표시하지 않는다.
  - 코드에 맞는 명세가 선택된다.
  - 현재 checkout이 기본 조합의 prompt·지문과 같다.
  - CLI 기본 설정이 검증 설정과 같다.

## 3. 되돌리기 (현재 HEAD 기준)

- **기존 절차가 충돌한다:** `git revert -m 1 b62f6dc`는 현재 HEAD에서 `assistant_cli.py`·`tests/test_cli_run_settings.py` 충돌로 적용되지 않는다. 별도 worktree에서 확인했다.
- **새 절차:** `scripts/geoflow_rollback_to_b.sh`.
  - geoflow/·prompts/와 T2PC 전용 테스트를 태그 `grounding-v12-baseline`으로 복원한다.
  - `GEOFLOW_DEFAULT_SPEC_NAME`을 B로 바꾼다.
  - 끝에서 기본 모델, prompt, 지문이 B 명세와 맞는지 확인한다.
- **별도 worktree에서 확인한 결과:**
  - 기본 조합 B, 기본 모델 qwen3:8b, prompt 522aa3b1, 지문 `7e99136d…`.
  - CLI 검증 표시: "B와 같음(일치 13)". qwen3.8:27b를 지정하면 "다름: model, model_digest".
  - 전체 테스트가 통과했다. 업체 원본 xlsx(git에 없는 파일)가 필요한 테스트 하나는 새 checkout이면 되돌리기와 무관하게 실패한다.
- 실제 작업 브랜치는 되돌리지 않았다.

## 4. grounding_v14 측정 도구와 계획 이탈의 정리

- **문서 정정:** v14 analysis.md 3절과 사전 등록의 "실행 후 기록"에 다음을 적었다.
  - 프록시 판별로 보장한 범위.
  - B W1·W3 재측정은 계획에 없던 실행이었다.
  - 예산이 480회에서 572회로 늘었다.
  - 운영 기준 충족과 실행 계획 이탈을 함께 기록했다.
- **프록시 판 2의 보장 범위:** "upstream 300초 상한, 상한에 걸리면 연결을 닫음"이었다. 클라이언트 연결 종료의 전달은 보장하지 않았다.
  - v14 재측정의 timeout은 모두 클라이언트 300초였으므로 사실상 같은 시점에 닫혔다.
  - 기록상 재시도와 다음 질문의 속도가 정상이었다.
  - 실제 영향 근거가 없으므로 재평가하지 않았다.
- **이번 수정 (판 3):**
  - 응답을 기다리는 동안 클라이언트 소켓 종료를 감시해 upstream을 바로 닫는다.
  - 상한 초과·오류에서도 닫는다.
- **확인 (`tests/test_record_proxy.py`, 짧은 timeout의 로컬 가짜 서버):**
  - 클라이언트가 0.3초에 끊으면 가짜 upstream이 1.5초 안에 끊김을 본다(상한 30초).
  - 상한 0.4초가 작동한다.
  - 정상 응답은 그대로 전달되고 기록된다.
  - 처음 구현은 상한 초과 경로에서 연결을 닫지 않았고, 이 테스트가 잡아냈다.

## 5. 실제 자료 검증 준비

`evaluation/real_data/`:
- `decisions.md`: D1–D4 결정표.
  - 질문 예시, 계약이 정한 것, 가능한 해석, 현재 정책, 현재 계약의 표현 가능 여부, 답변 차이, 결정할 사람에게 물을 것.
  - TIMS 미확인 계약 항목은 기존 문서(`evaluation/design/tims_lowering_contract.md`)를 참조한다.
- `record_schema.json`, `validate.py`: 실제 질문 검증 기록의 최소 형식과 검사(`tests/test_real_data_records.py`).
- `README.md`: 다음을 정리했다.
  - 지금 있는 것과 없는 것: 실제 TIMS 연결·응답·실제 사용자 질문은 없다.
  - 지금 확인할 수 있는 것과 외부 입력이 필요한 것.
  - 판단 목표별 표본 수.
  - 외부에서 받아야 할 입력 목록(보내지 않음).

## 6. 그대로인 것

- T2PC 유지 판단과 알려진 오류(grounding_v14 7절)는 그대로다.
- 책임 분담, 재질의 1회, 날짜 정책, 업체 위임·직접 재계산 기준도 그대로다.
- 다음 단계는 외부 입력(결정, 계약 답, 실제 질문, TIMS 접근)이 생긴 뒤에 설계한다.
