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
3. SFT loss 범위는 `full_response`(thinking과 JSON 전체)다. **결정 24로 대체됨(SFT 한정).**
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

## 2026-10-06 — 진짜 pilot(`pilot_001`)

23. 추론 표본 10개 검토 결과(`training/generated/thinking_traces/v003_t2pc_train/human_review_10.md`, sha256 `7dd14274…`).
    사용자가 Claude의 검토 의견을 확인하고 확정했다. 판정표는 `reasoning_review_001/VERDICTS.md`.
    - 판정 기준: 채점(`grounding_check`)이 보는 핵심 필드(측정값·사건, 집계 구조, 조건, 장소 값)에서 추론이 틀렸는데 JSON만
      맞으면 "우연히 정답"이다. 채점이 보지 않는 필드(role, answer, source, id, text)의 오류는 "경미"로 둔다.
    - 타당 3, 타당(경미) 5, 우연히 정답 2(`ann-d983889cf8c496178106:sample:7`, `ann-ea359d5569ef6070f9e4:sample:3`).
24. SFT의 loss 범위는 `json_only`다. 결정 3(`full_response`)을 대체한다. 결정 23의 규칙대로라면 `full_response` 유지였지만,
    판정이 경계선이라 사용자가 보수적으로 골랐다.
25. trace 선별 기준은 바꾸지 않는다. 채점 기준과 같게 두고, role이 gold와 달라도 채택한다.
26. DPO는 `full_response`로 유지하고, PROTOCOL(결정 22)은 바꾸지 않는다. DPO는 `json_only`를 지원하지 않으므로, 최종 모델은
    DPO 단계에서 추론 문장까지 학습한다.
27. 결정 23에서 "우연히 정답"으로 판정한 trace 2개를 학습에서 뺀다. 이 trace가 chosen인 DPO 쌍도 뺀다. 검토하지 않은 다른
    trace는 그대로 둔다.
28. 학습 길이와 저장 시점. 나머지 학습 설정은 pipeline pilot과 같은 thor profile을 쓰고, 탐색하지 않는다.
    - SFT: 2 epoch, 0.5 epoch마다 저장(4개).
    - DPO: 1 epoch, 25%마다 저장(4개). 고른 SFT checkpoint에서 시작한다.
    - 선택 규칙: valid98 grounding_ok가 가장 높은 checkpoint. 동점이면 더 이른 쪽.
29. checkpoint 선택용 valid는 결정 16의 100문항에서 h03과 `heldout_v8/t10`을 뺀 98문항(valid98)이다.
    - h03: gold는 "출발·도착 둘 다 수성구"를 장소 두 개로 적었지만, 현재 계약은 이 경우를 "C 하나에 od_role both"로 적게 한다.
      (사용자 문장에는 `heldout_v8/h03`으로 적혔다. 이 내용의 문항은 `heldout_v9/h03`이다. heldout_v8에는 h03이 없다.)
    - t10: gold도 조건 계층에서 멈춘다.
    - 평가 라벨 원본은 고치지 않는다.
30. PROTOCOL의 판정은 그대로 둔다. 업체 100에서 평가하는 고른 SFT와 최종(SFT+DPO) 각각에 대해, 운영 경로의 E·B-conv·학습
    모델 삼자 비교를 보조 분석으로 한다(`vendor100_protocol/ADDENDUM_three_way.md`). 판정에 쓰지 않는다.
31. 운영 측정의 안전장치. 판정 규칙은 바꾸지 않고, 실행 조건만 맞춘다.
    - 학습 모델을 등록할 때마다 base 때와 같은 렌더링 확인 10문항(token 수, think 미지정 시 thinking 켬, thinking·본문 분리)을
      통과해야 업체 100을 잰다. 통과하지 못하면 그 모델의 Ollama 측정은 하지 않고 보고한다.
    - 학습 모델 측정 직전에 Ollama 버전을 확인한다. E·B-conv를 잰 버전(0.35.1)과 같으면 기존 기록을 쓴다. 다르면 E와 B-conv를
      같은 버전에서 다시 잰 뒤 학습 모델을 잰다. 판정과 삼자 비교에는 같은 버전의 값을 쓰고, 이전 값도 함께 기록한다.

## 2026-10-07 — 실행 조건 변경

32. 당분간 Ollama 측정도 GPU 2에서 한다. 사용자가 기존 Ollama 컨테이너의 GPU 배정을 3에서 2로 바꾸는 방식을 골랐다
    (`CLAUDE.md` 4·5번의 해당 부분을 이 결정으로 바꾼다). 계기: 다른 사용자의 작업이 GPU 0·1·3에 올라와 GPU 3을 공유하게 됐다.
    - 같은 이미지·모델 저장소(`/data/hwkim/ollama`)·포트를 쓴다. 바꾸는 것은 `device_ids`뿐이다. 원래 값("3")은 기록해 둔다.
    - GPU 2는 HF 학습·평가와 같이 쓰므로, HF 작업과 Ollama 측정은 계속 순서대로 한다(동시에 돌리지 않는다).
    - 장치가 바뀌므로 pilot_001의 E와 B-conv는 GPU 2에서 다시 재고, 판정·삼자 비교는 같은 장치의 값으로 한다(결정 31과 같은 논리).
      GPU 3에서 잰 이전 값도 함께 기록한다.
33. 앞으로 모든 데이터를 커밋한다. 범위는 생성 데이터(학습 corpus, thinking 학습 데이터)와 원문(thinking·teacher trace, 평가 원문)이다.
    weights(adapter, checkpoint, merge 모델, GGUF)와 cache는 계속 커밋하지 않는다. 이미 만든 데이터도 커밋한다.
    `.gitignore`에서 `training/generated/`를 빼고, weight 파일 형식을 명시적으로 막는다. `CLAUDE.md` 3번을 바꾼다.
32-1. (2026-10-07, 사용자) GPU 2와 GPU 3은 동일 사양이므로 장치 변경만으로 E·B-conv를 다시 재지 않는다. pilot_prep_003에서 GPU 3으로 잰
     E(79)·B-conv(77)를 재사용한다. 결정 32의 "E와 B-conv는 GPU 2에서 다시 잰다"를 대체한다. Ollama 버전이 0.35.1과 다를 때 다시 재는
     결정 31은 그대로다. 학습 모델 셀은 GPU 2에서 재므로, 판정·삼자 비교에서 기준 셀과 학습 모델 셀의 장치가 다르다는 점을 결과에 적는다.


## 2026-10-07 — pilot_001 결과 처리와 원인 분석(`pilot_001_analysis`)

34. pilot_001의 최종 모델과 SFT 모델은 채택하지 않는다. PROTOCOL 판정에서 두 경로의 주 비교가 모두 "악화"였기 때문이다.
    등록한 두 모델(`geoflow-qwen3-8b-pilot001-sft:q4km-hfthink`, `geoflow-qwen3-8b-pilot001-final:q4km-hfthink`)은 분석용으로
    남겨 두고 지우지 않는다. 운영 기본값은 바꾸지 않는다.
35. 다음 방향은 원인 분석이다. 이번 작업에서는 학습하지 않는다.
36. 업체 100 결과는 원인을 설명하는 데에만 쓴다.
    - 다음 학습 데이터를 설계하는 근거로 쓰지 않는다. 업체 100 문항의 내용을 학습이나 annotation 후보에 쓰지 않는다.
    - 다음 데이터 설계의 근거는 valid98과 학습 데이터 쪽 오류에서만 찾는다.
37. 장치 영향을 확인한다. E와 B-conv를 지금 GPU 2에 있는 Ollama에서 업체 100으로 다시 잰다.
    이 측정은 보조 기록이다. 확정된 PROTOCOL 판정은 바꾸지 않는다.
38. Ollama 컨테이너는 당분간 GPU 2에 둔다. 컨테이너를 옮기거나 재시작하지 않는다. `CLAUDE.md`의 GPU 규칙을 지금 배치에 맞게 고친다
    (4·5·6번; 결정 32의 "HF 작업은 GPU 2 기본"을 대체한다).
    - Ollama는 GPU 2(UUID `GPU-a644de12…`)에 있다.
    - HF 작업이나 학습에는 GPU 3(UUID `GPU-48f798cc…`)을 기본으로 쓴다. GPU 2는 Ollama 모델이 올라가 있지 않을 때만 쓴다.
    - 어느 GPU든 쓰기 전에 host `nvidia-smi`로 UUID, 사용 중인 메모리, 다른 사용자의 프로세스를 확인한다. 다른 프로세스가 있으면
      그 GPU를 쓰지 않고 보고한다.

## 2026-10-07 — pilot_002 준비(`pilot_prep_004`)

39. 이 트랙의 목표는 소형 LLM(qwen3:8b)을 파인튜닝해서 잘 되게 하는 것이다. 트랙 보류는 선택지에서 뺀다.
40. pilot_002의 방향은 C, A, D다(`pilot_001_analysis/REPORT.md` 4절의 선택지).
    - C: 집계가 없는 질문과 `dimension`·`dimension_target` 유형을 새 annotation 약 60건(batch005)으로 보강한다. 학습 데이터 전체의 유형
      비율이 보호 개발 셋 전체의 비율에 가까워지게 한다. 개발 셋은 문항 내용이 아니라 집계 통계만 쓴다.
    - A: teacher trace 17문항을 학습 데이터에 넣는다. 출처를 `source=teacher`로 표시한다.
    - D: 반복 루프 trace를 학습 데이터에서 뺀다. 기준은 적용하기 전에 고정한다.
    - B(loss 범위 조정)는 하지 않는다. SFT는 `json_only`(결정 24), DPO는 `full_response`(결정 26)를 유지한다.
41. 다음 판의 checkpoint 선택에는 새 선택용 셋(약 100문항)을 쓴다. 결정 28의 선택 규칙에서 valid98을 이 셋으로 바꾼다.
    - 아직 분석이나 데이터 설계에 쓰지 않은 보호 개발 셋에서 만들고, 학습에는 쓰지 않는다.
    - valid98은 보조 기록으로만 잰다.
42. 업체 100과 함께 보고할 보조 시험 셋을 하나 더 둔다.
    - 아직 쓰지 않은 보호 개발 셋에서 만들고, 새 선택용 셋과 family가 겹치지 않게 나눈다.
    - 판정은 업체 100으로 하고, 보조 시험 셋은 같은 지표로 함께 보고한다.
43. 미확인 실험은 두 개만 한다(`pilot_001_analysis/REPORT.md` 3d·3e).
    - HF 경로의 장치 일치: pilot_001 SFT step 124를 GPU 2에서 valid98로 다시 재서 GPU 3 기록과 비교한다.
    - 변환 경로 영향: valid98에서 B-conv와 Ollama-최종을 잰다.
44. pilot_002에는 새 `vendor100_protocol/PROTOCOL_v2.md`를 쓴다. pilot_001의 `PROTOCOL.md`는 고치지 않는다.
    - PROTOCOL_v2는 PROTOCOL.md(결정 22)와 `ADDENDUM_three_way.md`(결정 30)를 그대로 이어받는다. 바뀌는 것은 두 가지다.
      - U와 조용한 오답의 악화 기준: 각각 순증 ≤ 2를 허용한다. 3 이상 늘면 악화다.
      - 결정 42의 보조 시험 셋 보고를 추가한다.
    - 학습 전에 확정한다.
45. C 보강 annotation(batch005)은 batch004와 같은 절차로 한다.
    - Claude가 질문과 초안 gold를 쓰고, HF 출력을 붙여 검토 시트를 만든다. 사용자가 검토해서 승인한다.
      초안 gold와 validator PASS는 승인이 아니다.
    - 학습용 trace는 승인한 뒤에 수집한다.

## 2026-10-08 — pilot_002 셋·데이터 준비(`pilot_prep_005`)

46. 선택용 셋과 보조 시험 셋은 `pilot_prep_004/sets/SURVEY.md` 3절의 선택지 1로 만든다.
    - 제외 단위는 문항 family다. v13·v14 비교에 쓰인 이력은 T2PC 코드·prompt 선택용 평가였으므로 이력으로만 둔다.
      SFT 쪽(오류 유형 분석, 공백 유형, batch004 근거 136문항)에 쓰인 문항은 그 family째 뺀다.
    - 선택용 셋: old44·contrast·indepv2–4의 조건 통과 154문항에서 약 100문항을 고른다. 고정 seed로, 유형 분포를 유지하도록
      층화 추출한다.
    - 보조 시험 셋: at·final_v12의 51문항.
    - 두 셋 사이의 거친 의미 family 분리는 하지 않는다. 셋이 다르므로 id와 contrast family는 이미 겹치지 않는다.
47. batch005 검토 결과. 사용자가 Claude의 검토 의견을 확인하고 승인했다. 기록의 reviewer는 사용자다.
    - 후보 gold
      - 승인 56건: b005-12, 14, 43, 53을 뺀 전부. 정지 target 8건(b005-05, 06, 07, 18, 19, 20, 25, 44)을 포함한다(결정 14).
      - 수정 2건(질문 문장만 고치고 gold는 그대로):
        - b005-12 → "2026년 9월 5일 동성로 근처에서 시작하고 끝난 실차 구간은 몇 건이야?"
        - b005-14 → "지난달 부산 광안리 근처에서만 오간 택시 실차는 몇 건이었나요?"
      - 제외 2건: b005-43, b005-53. 업체 100의 026, 025 문장을 거의 그대로 따른 것으로 보여 결정 36에 따라 뺀다.
    - 모델 출력과의 쌍
      - 승인 36개: b005-03, 05, 06, 08, 09, 11, 12, 14, 16, 17, 19, 20, 22, 23, 25, 27, 28, 29, 30, 31, 34, 37, 39, 40,
        41, 42, 45, 46, 47, 48, 49, 50, 53, 56, 57, 60의 `-hf`. 53-hf는 gold 제외에 따라 함께 뺀다.
        12-hf와 14-hf는 고치기 전 문장으로 생성된 출력이라는 점을 기록한다.
      - 제외 8개: b005-01, 02, 04, 32의 `-hf`(한 장소 `both`와 출발+도착 두 항목은 표기만 다르고 뜻은 같음),
        b005-35, 36, 43, 52의 `-hf`(날짜 형식만 다르고 조건 계층이 고침).
      - 조건부 1개: b005-59-hf. 결정 6의 운영 경로 재판정 결과를 따른다.
    - 원칙: 한 장소 `both`와 출발+도착 두 항목은 뜻이 같다. 계약이 정한 표기는 한 장소 `both`이고, gold는 이 표기로 둔다.
48. teacher 데이터.
    - 질문당 최대 4개를 쓴다. 필터를 통과한 정답 trace 중에서 고정 seed로 고른다.
    - 27b chosen과 8b rejected로 만드는 교차 DPO 쌍은 쓰지 않는다.
    - 고른 teacher trace에서 표본 10개를 사용자가 결정 23과 같은 기준으로 검토한다. 결과는 결정 27과 같은 방식으로 반영한다.

## 2026-10-08 — pilot_002 진행(`pilot_002`)

49. teacher 표본 10개 검토 결과(`training/generated/thinking_traces/teacher/human_review_teacher_10.md`, sha256 `f50010f8…`).
    사용자가 Claude의 검토 의견을 확인하고 확정했다. 기준은 결정 23과 같다. 판정표는 `reasoning_review_002/VERDICTS.md`.
    - 타당 8: `ann-2d254560f2214204db4b:teacher:2`, `:teacher:6`, `ann-77e9dacb0b34a3273630:teacher:1`,
      `ann-914c48dad91bc9a62ab4:teacher:8`, `ann-e645cbc11600d7348d68:teacher:1`, `b004-06:teacher:4`,
      `b004-15:teacher:3`(판교역 표본, 문서 9번), `b004-31:teacher:1`.
    - 타당(경미) 2:
      - `ann-914c48dad91bc9a62ab4:teacher:3`: region을 잘못 말했다가 추론 안에서 근거를 들어 고침. JSON에 `answer: value`.
      - `ann-dd838f31807ef8546525:teacher:3`: 합계 집계를 넣을지 오래 망설인 끝에 맞는 근거로 넣지 않음.
    - 우연히 정답 0. 결정 27 방식으로 빠지는 trace가 없으므로 기존 teacher 68개를 모두 쓴다.
    - 관찰: 추론이 8b의 주요 오류 지점(질문에 없는 집계, 묶음 기준을 장소로 만들기)을 직접 짚는다. 장소 role은 10개 모두 gold와
      같은 SUBCOND다.
50. batch005에서 정답 표본이 없는 27질문의 teacher trace를 학습에 넣는다.
    - 기존 teacher와 같은 필터를 적용한다: tokenize 왕복·렌더 경계, 계약, 길이(결정 18), 루프(결정 40-D).
    - 필터를 통과한 trace 중에서 질문당 최대 4개를 고정 seed로 고른다.
    - 교차 DPO는 만들지 않는다(결정 48).
51. 승인했던 검토 쌍 14개(b005-11, 12, 20, 22, 23, 25, 27, 28, 30, 46, 48, 49, 50, 57의 `-hf`)는 결정 6에 따라 DPO에서 뺀다.
    - 이 중 13개는 모델이 vicinity를 장소 개념 안에 적은 경우다. 코드(`geoflow/grounding.py` `_hoist_structural_factors`)가
      제자리(factors)로 옮기므로 운영 경로에서 뜻이 같다.
    - **정정:** batch005 README(`batch005/README.md` 4절 "vicinity 18건, 모두 초안 있음 → 모델 없음")와 Claude 검토 의견에 적힌
      "vicinity 누락"은 대부분 누락이 아니라 이 위치 차이였다. 조건 계층 전 원출력을 채점했기 때문이다. README 자체는 고치지 않는다.
52. DPO는 질문당 최대 8쌍이다.
    - 모든 출처(v004, batch005)에 적용한다.
    - 고정 seed를 쓰되, rejected의 오류 유형(`grounding_diffs` 필드 종류)이 다양하게 남도록 고른다.
53. pilot_002는 pilot_001과 같은 학습 설정을 쓴다. 바뀌는 것은 데이터와 선택용 셋뿐이다.
    - 학습 길이와 저장 시점: 결정 28과 같다(SFT 2 epoch·0.5 epoch마다 4개, DPO 1 epoch·25%마다 4개, 고른 SFT에서 시작).
    - SFT `json_only`(결정 24), DPO `full_response`(결정 26). reference 미리 계산, `expandable_segments`.
    - checkpoint 선택: selection_v1(결정 46)의 grounding_ok가 가장 높은 것. 동점이면 더 이른 쪽.
    - valid98은 선택한 SFT와 최종 모델에 대해서만 보조로 잰다(결정 41).
    - `ollama create` 승인(결정 20)을 pilot_002의 SFT와 최종 모델 등록에도 적용한다. 새 이름으로 등록하고 기존 모델은 건드리지 않는다.
