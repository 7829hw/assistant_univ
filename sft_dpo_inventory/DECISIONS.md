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
