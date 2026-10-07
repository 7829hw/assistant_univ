# pilot_002 준비 보고 (`pilot_prep_004`, 결정 39–45)

작성: 2026-10-07. 학습은 하지 않았다. prompt, SEMANTIC_CODE, 업체 100은 바꾸거나 쓰지 않았다.
`PROTOCOL.md`, `ADDENDUM_three_way.md`, pilot_001의 판정·기록, 기존 라벨·생성 데이터, 승인된 corpus는 고치지 않았다.
실행 의미 코드 지문은 끝까지 `791c4a68…`이다(`execution_spec.code_fingerprint`, 64 파일).

## 1. 커밋

| 작업 | 커밋 | 내용 |
|---|---|---|
| 0 | 5540bcc | 결정 39–45 기록(`../DECISIONS.md`) |
| 2 | 25225ea | 선택용·보조 시험 셋 후보 조사. **셋 생성 보류**(아래 2절) |
| 3 | d6d68ce | 유형 분포 목표와 batch005 배분 |
| 5-D | db1dab6 | 루프 trace 제외 기준 고정(적용 전) |
| 5-A·D | 0ccc620 | builder의 `source=teacher` 지원, teacher 규모, 루프 기준 적용 결과 |
| 6 | 4a76114 | `PROTOCOL_v2.md` 초안. **확정 보류**(아래 2절) |
| 1 | 89c0e2b | 결정 43 실험 두 개(`../pilot_001_analysis/REPORT.md` 6절) |
| 4 | 7743890 | batch005 후보 60건과 검토 시트 |
| 7 | 이 문서 | |

## 2. 확인한 결과

**작업 1(결정 43). 새 모델 호출 있음. 업체 100은 쓰지 않음.**

- **HF 장치 일치:** SFT step 124를 GPU 2에서 valid98로 쟀다. GPU 3 기록과 첫 응답 98/98, 모든 호출 98/98이 바이트 단위로 같았다.
  - grounding_ok 61 = 61, 생성 상한 0 = 0.
  - pilot_001 SFT 선택에 장치가 섞였다는 근거는 없다. 선택은 바꾸지 않았다.
- **변환 경로(valid98, 같은 가중치):**

| 쌍 | HF | Ollama | HF−Ollama | b / c | p | 갈린 문항 |
|---|---:|---:|---:|---|---:|---:|
| 학습 전: HF-base / B-conv | 55 | 48 | 7 | 9 / 16 | 0.23 | 25 |
| 학습 뒤: HF-최종 / Ollama-최종 | 65 | 54 | 11 | 10 / 21 | 0.071 | 31 |

  - 학습 효과는 HF에서 +10(b 14, c 4, p 0.031), Ollama에서 +6(b 15, c 9, p 0.31)이다.
  - 학습 뒤 변환 손실이 커지는 방향이고, 업체 100의 7 → 9와도 방향이 같다. 다만 차이의 차이(4문항)는 검정하지 않았고, Ollama 셀끼리의 흔들림보다 작다.

**작업 2(결정 41·42). 멈춤.**

- 규칙("문항 단위 결과를 설계·분석에 쓴 셋은 뺀다")을 셋 단위로 적용하면 남는 셋이 0이다.
  - 업체 100·stage_v7·heldout_v8·v9를 뺀 11개 셋이 모두 grounding_v13·v14 비교에 문항 단위로 쓰였다.
- 조건을 통과한 문항은 384개 중 302개다. 선택지와 규모는 `sets/SURVEY.md` 3절에 있다.
- 셋 고정, base(HF-E) 기준값 측정, PROTOCOL_v2의 셋 항목은 하지 않았다.

**작업 3(결정 40-C).**

- 개발 셋 454질문 대비 학습 51질문(r1 34 + teacher 17)의 칸 분포 TV는 0.257이다. 60건을 배분하면 0.006이 된다.
- 배분: 집계 없음·묶음 없음 30, dimension+dimension_target 15, 집계만 7, dimension만 5, 집계+dimension 3.

**작업 4(결정 45). 새 모델 호출 있음.**

- Claude 초안 60건. 칸별 배분은 지켰고, 칸 안 세부는 보호 family를 피하느라 목표와 다르다(`../batch005/README.md` 2절).
- 겹침 검사: thor leakage 0, 확장 겹침 0, 학습 데이터 겹침 0. 뺀 후보는 0이다.
- 현재 코드 결과: 답 52, 정지 8. 정지 8건은 `trip_count`·`rpm`에 택시 유형이 붙어 `UNCONSUMED_CONDITION`이 나는 경우다.
- HF base 첫 응답: 초안과 같음 15, 다름 45, 생성 상한 0.
  - 차이: vicinity 누락 18, 집계 `sum` 추가 13, 장소 od_role 15, 날짜 표기 11, 기타 10.
- 검토 queue는 105행(SFT 60 + DPO 쌍 45)이다. XLSX는 커밋하지 않았다.
- trace 수집과 import는 하지 않았다.

**작업 5(결정 40-A·D).**

- A: builder가 teacher trace를 `source=teacher`로 받는다. 관련 시험은 통과했다.
  - teacher 136개 중 정답 121개가 모든 필터를 통과해 121 레코드(17질문)다.
- D: 기준(L1 끝부분 반복 ≥ 3, L2 압축률 ≤ 0.086, L3 같은 줄 반복 ≥ 21)을 적용 전에 커밋했다.
  - v004 477, teacher 136, r1 SFT·DPO 레코드 모두 0개가 걸렸다.

**작업 6(결정 44).**

- `../vendor100_protocol/PROTOCOL_v2.md`에 두 변경(U·조용한 오답 각각 순증 ≤ 2 허용·≥ 3 악화, 보조 시험 셋 보고)을 적었다.
- 보조 시험 셋이 정해지지 않아 "확정"으로 표시하지 않았다.

**실행 환경**

- GPU 3에는 다른 사용자(jmbae)의 프로세스가 있어 이번 작업 내내 쓰지 않았다.
- HF 작업 두 개(작업 1의 SFT 124, 작업 4의 base 출력)는 GPU 2에서 했다. 둘 다 Ollama 모델이 올라가 있지 않고 Ollama 측정이 없을 때였다. Ollama와 HF는 차례로 돌렸다.
- Ollama 컨테이너, 등록 모델은 건드리지 않았다.

## 3. 사람 검토가 필요한 항목

1. **선택용·보조 시험 셋의 선택지**(`sets/SURVEY.md` 3절).
   - 0: 규칙대로, 셋 없음.
   - 1: 문항 family 단위. 선택용 154 → 약 100, 보조 at·final_v12 51.
   - 2: 셋 단위. 보조 51만.
   - 3: 새 보호 셋 작성. 약 150건의 사람 검토가 더 든다.
   - 두 셋 사이에 거친 의미 family 분리까지 요구할지도 정한다.
2. **batch005 검토**(`../batch005/review/README.md`). 60건과 DPO 쌍 45개.
   - 정지 후보 8건: 정지 target으로 둘지, 택시 유형을 뺀 질문으로 다시 쓸지.
   - 날짜 표기 차이 10건(범위 대 `YYYYMM`): v004 승인 corpus에 둘 다 있다. 뜻이 같으면 DPO 쌍에서 뺀다.
   - 한 장소 `both` 대 pickup+dropoff 두 항목(5건 이상): 질문 문장이 어느 뜻인지.
   - 보호 셋 문장과의 파생 관계 확인. 자동 검사로는 잡지 못한다.
3. **teacher 레코드의 비중과 DPO 사용.**
   - 그대로 넣으면 SFT의 49%가 teacher다. 질문당 상한을 둘지 정한다.
   - 27b chosen 대 8b rejected 쌍(463개 가능)을 DPO에 넣을지 정한다.
   - 결정 27 기준("우연히 정답")의 사람 검토는 아직 하지 않았다.
4. **PROTOCOL_v2 확정.** 1번의 셋이 정해지면 7절을 채우고 "확정(날짜, 사용자)"로 표시한다.

## 4. pilot_002 전에 남은 일(순서대로)

1. 셋 선택지를 고른다 → 셋 고정(목록·sha256) → base HF-E 기준값을 두 셋에서 한 번씩 잰다 → PROTOCOL_v2를 확정한다. 학습 전에 끝낸다.
2. 사용자가 batch005를 검토하고 승인한다(`workflow decide` → `import-reviewed` → `reviewed_gold_v005_candidate`).
3. 승인한 질문만 HF base 학습 trace를 모은다(결정 45). 루프 기준(D)과 계약 필터를 적용한다.
4. pilot_002 데이터를 만든다: v004 + batch005 승인분 + teacher(`source=teacher`).
   - SFT `json_only`, DPO `full_response`(결정 40, B 없음).
   - 칸 분포를 레코드 단위로 다시 센다.
5. 학습 계획을 고정한다: checkpoint 후보, 선택용 셋으로 고르는 기준, 등록할 모델 이름(결정 20).

## 5. 다음 판단에 필요한 최소 자료

| 판단 | 자료 |
|---|---|
| 셋 선택지 | `sets/SURVEY.md` 1–3절, `sets/options.json` |
| batch005 승인 | `../batch005/review/README.md`, `review_queue.jsonl`(XLSX는 `build_review.py --xlsx-only`로 만든다), `../batch005/README.md` 3–4절 |
| teacher 비중·DPO | `teacher_scale/SCALE.md`, `teacher_scale/teacher_scale.json` |
| 변환 경로가 운영 판정에 주는 영향 | `../pilot_001_analysis/REPORT.md` 6절 b, `../pilot_001_analysis/decision43/comparison.json` |
| PROTOCOL_v2 확정 | `../vendor100_protocol/PROTOCOL_v2.md` 2절과 7절 |
