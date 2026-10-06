# SFT·DPO 결정 기록

사용자가 내린 결정을 날짜와 함께 적는다. 바뀌면 지우지 않고 새 항목으로 덧붙인다.
GPU 사용 규칙(결정 1)은 `CLAUDE.md`의 SFT/DPO 규칙 5·6에 있다.

## 2026-10-06 — thinking 켬

- 학습·평가 모두 thinking 켬이다(`CLAUDE.md` 9번).
- 비교 기준: Ollama 경로는 E(79), HF 경로는 HF-E(84, `thinking_prep_001`).

## 2026-10-06 — thinking 파이프라인 pilot(`pipeline_pilot_001`) 조건

1. GPU 3은 Ollama를 쓰지 않을 때만 학습·HF 작업에 쓴다. GPU 2가 기본이다(`CLAUDE.md` 5·6번).
2. 지금 v003_t2pc thinking 데이터만으로 파이프라인 pilot을 돌린다.
   - 목적은 학습 → checkpoint 선택 → 평가가 끝까지 도는지 확인하는 것이다. 결과는 채택 판단에 쓰지 않는다.
   - 업체 100은 쓰지 않는다.
3. SFT loss 범위는 `full_response`(thinking과 JSON 전체)다.
4. 생성 token과 다시 tokenize한 결과가 다른 trace 10개(`thinking_prep_001/traces/tokenization_check.json`)는
   제외한다.
5. 학습 렌더링은 HF `enable_thinking=True` 형식을 유지한다. 나중에 등록할 모델의 TEMPLATE을 이 형식에 맞춘다.
6. DPO는 rejected를 운영 경로(조건 계층, compose, validate)로 다시 판정한다. 그 경로에서도 gold와 다른 쌍만 쓴다.
7. `compile_stop` 표시 항목은 포함한다.
8. 정답 표본이 하나도 없는 7문항은 이번에 제외한다.
9. DPO는 reference log-prob을 미리 계산해서 메모리를 줄인다.
10. checkpoint 선택
    - v003_t2pc valid 16문항을 HF-E와 같은 조건으로 잰다.
    - grounding_ok가 가장 높은 checkpoint를 고른다.
    - 동점이면 더 이른 checkpoint를 고른다(규칙은 `pipeline_pilot_001/PLAN.md`에 고정).

## 2026-10-06 — pilot 전 준비(`pilot_prep_002`)

11. valid 채점은 질문을 만들 때 쓴 장소를 아는 provider로 한다.
    - 학습 corpus의 합성 장소(가람구, 나래구 등)는 reference provider를 쓴다.
    - 업체 100은 지금처럼 mock을 쓴다.
    - pipeline 코드와 채점 코드는 같다.
12. 메모리 대책으로 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`를 확인한다. 학습 설정(데이터, 길이, 정밀도, LoRA)은
    바꾸지 않는다.

## 2026-10-06 — 진짜 pilot 데이터·기준선 준비(`pilot_prep_003`)

13. batch004 검토 결과. 사용자가 Claude의 검토 의견을 확인하고 승인했다. 기록의 reviewer는 사용자다.
    - 후보 gold 승인(18건): b004-05, 06, 15, 18, 19, 20, 21, 22, 23, 24, 27, 28, 30, 31, 34, 35, 40, 41.
    - 쌍 승인(11건): b004-05-hf, 06-hf, 15-hf, 19-hf, 22-hf, 23-hf, 27-hf, 28-hf, 30-hf, 34-hf, 35-hf.
    - 쌍 제외(4건): b004-24-hf, 31-hf, 40-hf, 41-hf. 날짜만 다르고 조건 계층이 고친다(결정 6).
    - v003 표시: compile에서 멈추는 SFT 17건은 포함한다(결정 7). DPO 표시 4건은 제외한다(결정 6).
14. 지원 불가 질문의 학습 target은 T2PC식 정지 grounding이다.
    - 측정값과 조건을 계약으로 적을 수 있으면, 실행할 수 없어도 grounding을 적는다.
    - `{"unsupported": true}`는 적을 수 없는 질문에만 쓴다.
    - b004-34, 35, 40, 41은 이 형식의 학습 target으로 쓴다.
15. 보호 범위는 넓히지 않는다.
    - 업체 100과 의미 family가 겹치는 b004-05, 06, 15, 30, 31도 학습에 쓴다.
    - 업체 100 결과는 학습 family에 속한 문항과 아닌 문항으로 나눠서도 보고한다.
16. checkpoint 선택용 valid는 stage_v7 + heldout_v8 + heldout_v9(100문항)다.
    - 선택에만 쓰고, 학습에는 계속 쓰지 않는다.
    - 저장 시점은 단계마다 4개 이하로 둔다.
    - v003_t2pc valid 16문항은 학습으로 옮긴다.
17. `expandable_segments`를 학습 기본값으로 쓴다. 기존 할당 설정을 한 번 더 돌리는 반복 측정을 1회 한다.
18. 학습 길이 한도는 수집한 데이터 길이에 맞춰 정한다.
    - pilot_prep_002의 추정 안전 한도를 넘지 않는다.
    - 한도를 넘는 레코드는 자르지 않고 빼서 보고한다.
19. Ollama 호출 금지를 해제한다. CLAUDE.md의 격리 측정 규칙과 HF·Ollama 순차 규칙은 그대로 유지한다.
20. `ollama create`를 두 가지에 승인한다.
    - base 변환본.
    - 나중에 진짜 pilot에서 고른 학습 모델(SFT, 최종).
    - 둘 다 새 이름으로 등록하고, 기존 모델을 덮어쓰거나 지우지 않는다.
    - pilot_prep_003에서는 base 변환본만 등록한다.
21. 정답 표본이 없는 7문항은 qwen3.8:27b(Ollama)로 teacher trace를 수집한다. 첫 pilot 데이터에는 넣지 않는다.
22. 업체 100 평가 절차(`vendor100_protocol/PROTOCOL.md`) 값. 이 값으로 PROTOCOL을 확정했다.
    - 비교할 adapter: SFT와 최종(SFT+DPO) 둘. 주 비교는 최종이다. SFT 비교는 같은 지표로 보고하되 참고로만 두고, 판정은 주 비교로 한다.
    - 운영 셀 생성 조건: Q4_K_M. num_predict는 E와 같게 지정하지 않는다.
    - 개선 기준: 주 비교에서 McNemar 양측 p<0.05, U 순증 ≤ 0, 조용한 오답 순증 ≤ 0.
    - 지연: 운영 셀의 지연 중앙값이 기준의 1.5배를 넘으면 악화로 본다.
    - 보조 보고: 결정 15의 family별 분리.
16-1. (2026-10-06, 사용자) v004를 합칠 때 thor 보호 검사(`Protection.current`: 이전 corpus 판의 validation family는 판이 바뀌어도
     풀지 않는다)가 v003_t2pc valid 16문항을 막았다. 결정 16에 따라 **이 16문항만 명시 해제**한다.
     - 해제는 `pilot_prep_003/import/merge_v004.py`의 목록(16개 source_record_id)으로만 한다. 이전 validation 출처를 빼고 다시 대조해
       다른 보호(평가 셋 질문·id·template·family)에 걸리지 않는 것을 확인한 경우에만 푼다.
     - thor 보호 규칙 자체와 다른 보호 대상은 바꾸지 않는다.
