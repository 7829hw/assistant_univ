# pilot_002 셋·데이터 준비 보고 (`pilot_prep_005`, 결정 46–48)

작성: 2026-10-08. 학습은 하지 않았다. prompt, SEMANTIC_CODE, 업체 100은 바꾸거나 쓰지 않았다.
`PROTOCOL.md`, `ADDENDUM_three_way.md`, pilot_001의 기록, 기존 라벨·생성 데이터는 고치지 않았다.
실행 의미 코드 지문은 끝까지 `791c4a68…`이다.

## 1. 커밋

| 작업 | 커밋 | 내용 |
|---|---|---|
| 0 | 711f3d5 | 결정 46–48 기록(`../DECISIONS.md`) |
| 2 | 764ec30 | batch005 결정 기록·import, `reviewed_gold_v005_t2pc` |
| 4 | 03c0d1b | teacher 질문당 4개 상한, 사람 검토 표본 10개 목록 |
| 1 | 0f3e370 | 선택용·보조 시험 셋 고정, base HF-E 기준값, PROTOCOL_v2 확정 |
| 3 | 839295e | batch005 HF trace 요약·필터, 정답 없는 질문의 teacher 수집 규모 |
| 5 | 이 문서 | `scale/estimate.py`, `scale/estimate.json` |

## 2. 확인한 결과

**작업 1. 셋과 PROTOCOL_v2(결정 46)**

| 셋 | 문항 | sha256 | base HF-E grounding_ok | 첫 응답 일치 | 생성 상한 호출 | 시간 |
|---|---:|---|---:|---:|---:|---:|
| `selection_v1` | 100 | `405af9c8…` | 82 | 61 | 0 | 44.7분 |
| `aux_test_v1` | 51 | `692b792f…` | 27 | 21 | 2 | 29.9분 |

- 만든 방법: `sets/build_sets.py`, seed 20261008.
  - 선택용은 후보 154에서 유형 칸 × 정지 기대로 층을 나눠 100을 뽑았다.
  - 칸 분포는 후보와 같다(0.24 / 0.08 / 0.13 / 0.42 / 0.13). 정지 기대 7.
  - 출처: old44 29, indepv3 21, indepv2 18, indepv4 18, contrast 14.
  - 보조는 at 14 + final_v12 37, 전부.
- 조건을 다시 확인했다. v004 + batch005 승인분과의 family 겹침도 다시 확인했다. 빠진 문항은 0이다.
- 두 셋 사이: id 겹침 0, family 겹침 0, 거친 의미 family 겹침 16(나누지 않음, 결정 46).
- 출처별 base 정답: 선택용 old44 26/29, contrast 10/14, indepv2 12/18, indepv3 18/21, indepv4 16/18. 보조 at 10/14, final_v12 17/37.
  - 보조 셋은 base 정답률이 53%다. 업체 100의 HF-E 84%보다 훨씬 낮다.
- 장치: GPU 3에 다른 사용자(jmbae)의 프로세스 2개(약 6.4 GiB)가 있어 쓰지 않았다(`runs.log`, `gpu_check.txt`).
  - HF는 모두 GPU 2에서 차례로 돌렸다. Ollama 모델이 없을 때였고, Ollama 작업은 HF가 끝난 뒤에 했다.
- PROTOCOL_v2: 3절에 두 기준값을, 7절에 셋을 채웠다. 상태는 "확정(2026-10-08, 사용자)"이다. 확정판 sha256은 `f129bdd9…`이다.
  - 보조 셋의 Ollama 셀(E, B-conv)은 아직 재지 않았다. PROTOCOL_v2 2.2절은 학습 전에 잰다고 했다.

**작업 2. batch005 import(결정 47)**

- decisions 105행: gold 승인 58 / 제외 2(43, 53), 쌍 승인 36 / 제외 9(8개 + 53-hf).
  - b005-12·14는 파생 queue에서 새 문장으로 기록했다.
  - b005-59-hf는 결정 6 재판정에서 운영 경로 오답이었다(`MISSING_CONCEPT_VALUE`). 그래서 승인했다.
- `reviewed_gold_v005_t2pc`: SFT 111(v004 53 + batch005 58), DPO 75(39 + 36), 전부 학습.
  - 정지 target은 12개다.
  - thor 보호 검사에서 막힌 것은 0이다.
  - 확장 겹침 24는 모두 v004 항목이다. 결정 15 항목 5 + 기존 19이고, thor 정책상 막는 대상이 아니다. batch005는 0이다.

**작업 3. batch005 trace(`traces/`)**

- HF base 58질문, 2시간 25분, GPU 2.
  - greedy 정답 16, pass@8 28. 정답 표본이 하나도 없는 질문은 27이다.
  - 정답 없는 27: b005-01, 02, 03, 05, 06, 08, 09, 14, 22, 27, 28, 29, 30, 31, 32, 35, 36, 39, 41, 42, 45, 46, 47, 49, 52, 56, 59.
- SFT 필터: 103 → 86(29질문).
  - 결정 4 tokenize 불일치 11, 계약 필터 6, 루프 0, 길이 0.
  - 루프 1건(b005-06:sample:6, L1·L2)은 오답 trace라 SFT 후보 밖이었다.
  - 필터 뒤 SFT가 없는 질문: b005-11, 60.
- DPO 필터: 438 → 204쌍(19질문).
  - 결정 6 재판정 345쌍: 운영 경로 오답 204, 조건 계층이 고침 9, 같음 132.
  - 결정 4로 65, chosen 계약 실패로 28이 빠졌다.
  - 질문당 최대 20쌍(b005-33, 34)이다. 질문당 상한은 두지 않았다.
- teacher(qwen3.8:27b, Ollama 0.35.1, GPU 2, 38분)는 27질문 모두 정답 표본이 있다.
  - 216 중 182가 정답이다.
  - 질문당 4개 상한이면 101이다. 필터 전이며, 포함 여부는 정하지 않았다.
  - 질문별 정답 수: b005-01 3, 31·35·39 2, 42·45 4, 03 7, 08 6, 나머지 8.

**작업 4. teacher(결정 48)**

- 17질문 121 → 68(질문당 4, seed 20261008 + 질문 번호). 목록은 `teacher/selected_teacher.json`이다.
- 검토 표본 10개(seed 48): `training/generated/thinking_traces/teacher/human_review_teacher_10.md`.
  - ignore 경로라 커밋하지 않았다(`git status`로 확인).
  - sha256 `f50010f8dd1b8aa512859fb59b5c461135d029b9a1f712cd1656dee7bffc72b7`.
- 교차 DPO(27b chosen 대 8b rejected)는 만들지 않았다.

**작업 5. pilot_002 예상 규모(`scale/estimate.json`)**

| 경우 | SFT 레코드 | SFT 질문 | DPO 쌍(질문) | SFT 출처 비율 | 질문 칸 TV | 레코드 칸 TV | 정지 target 레코드 |
|---|---:|---:|---|---|---:|---:|---:|
| A teacher 없음 | 210 | 63 | 416(45) | r1 59%, batch005 HF 41% | 0.111 | 0.230 | 23 |
| B teacher 17 포함 | 278 | 80 | 416(45) | r1 45%, b005 HF 31%, teacher 24% | 0.073 | 0.156 | 23 |
| 참고: B + batch005 teacher(상한 4, 필터 전) | 379 | 107 | 416(45) | r1 33%, b005 HF 23%, teacher17 18%, b005 teacher 27% | 0.016 | 0.080 | 31 |

- DPO 416 = r1 212 + batch005 HF 204. 모두 HF 표본 쌍이다.
  - pilot_001과 같은 방식이다. 검토 queue의 HF 쌍(v004 39, batch005 36)은 r1처럼 직접 넣지 않은 수다.
- 레코드 칸 분포(개발 셋 454질문 대비):
  - "집계 있음·묶음 없음"이 A 50%, B 44%다(개발 28%).
  - "dim + dt"는 A 15%, B 26%다(개발 28%).
- 학습 레코드가 없는 승인 질문:
  - A: 48
  - B: 31
  - 참고: 4(b004-19, b004-35, b005-11, b005-60)

**예상 시간(pilot_001 실측 기준, 같은 학습 설정 가정)**

- **학습:**
  - SFT는 2 epoch, batch 1, 6.20초/step(pilot_001 전체 시간 / step). A 420 step 약 43분, B 556 step 약 57분.
  - DPO는 1 epoch, reference 계산 포함 24.2초/쌍. 416쌍이면 약 2.8시간.
- **선택용 셋:** base가 45분이었다.
  - pilot_001 checkpoint는 valid98에서 59–107분이 걸렸다(base보다 길다).
  - checkpoint당 45–100분이다. SFT 4 + DPO 4이면 6–13시간.
- **valid98 보조 기록:** 모델당 약 60–100분.
- **업체 100:** HF 셀은 SFT·최종 각 57–95분. Ollama 셀은 각 1.5–2시간.
- **보조 시험 셋:** HF 셀은 각 30–50분. Ollama 셀(E, B-conv 첫 측정 + SFT, 최종)은 각 45–60분으로 추정했다(업체 100의 약 절반).

## 3. 사람 검토가 필요한 항목

1. **teacher 표본 10개 검토**(결정 48, 결정 23 기준).
   - `human_review_teacher_10.md`를 본다. 결과는 결정 27 방식으로 68개에 적용한다.
2. **batch005 teacher 101개(27질문)를 넣을지.**
   - 넣지 않으면 batch005 승인 58질문 중 29만 학습 레코드가 있다.
   - 필터(결정 4·계약·루프·길이)는 아직 적용하지 않았다.
3. **승인된 검토 쌍 36개 중 14개는 결정 6 기준으로는 쌍이 아니다.**
   - 모델 출력이 운영 경로에서 gold와 같아진다.
   - 13개(11 제외)는 모델이 vicinity를 장소 개념 안에 적은 경우다. 코드(`geoflow/grounding.py` `_hoist_structural_factors`)가 이것을 factors로 옮긴다.
   - 즉 batch005 README의 "vicinity 누락 18" 중 13건은 실제로는 누락이 아니라 위치 차이였다(조건 계층 전 원출력 채점의 한계).
   - 해당 쌍: b005-11, 12, 20, 22, 23, 25, 27, 28, 30, 46, 48, 49, 50, 57 -hf.
   - 이 쌍은 corpus에 그대로 있다. pilot_002 데이터에서 검토 쌍을 쓸지, 쓴다면 이 14개를 뺄지 정해야 한다.
   - 같은 이유로 정답 없는 27질문 중 일부(22, 27, 28, 30, 46, 49 등)는 표본의 뜻이 맞아도 원출력 채점에서 오답이 됐을 수 있다. 확인하지 않았다.
4. **보조 시험 셋 base 정답률(27/51).**
   - final_v12가 17/37로 낮다. 셋을 바꾸지 않고 그대로 기록했다(PROTOCOL_v2 확정).
5. **DPO 질문당 상한.** batch005 HF 204쌍이 19질문에 몰려 있다(최대 20). 상한을 둘지 정한다.

## 4. pilot_002 전에 남은 일(순서대로)

1. 사용자가 teacher 표본 10개를 검토한다. 결과를 68개에 적용한다(결정 27 방식).
2. batch005 teacher trace 포함 여부를 정한다. 넣으면 필터와 질문당 4개 상한을 적용한다.
3. 위 3번 항목(검토 쌍 14개)과 DPO 질문당 상한을 정한다.
4. 보조 시험 셋의 Ollama 기준 셀(E, B-conv)을 학습 전에 한 번 잰다(PROTOCOL_v2 2.2절).
5. pilot_002 데이터를 만든다. SFT `json_only`, DPO `full_response`이고, 칸 분포를 다시 센다.
6. 학습 계획을 고정한다.
   - epoch과 checkpoint 후보를 정한다.
   - 선택용 셋 규칙: grounding_ok 최고, 동점이면 이른 step.
   - 등록할 모델 이름을 정한다(결정 20).

**결정 33과 다른 점:** 이번 trace 원본(batch005 HF, batch005 teacher)과 teacher 검토 문서는 작업 지시대로 ignore 경로에 두고 요약만 커밋했다.

- 원본 sha256:
  - HF `3511f2a4…`
  - teacher `eaade478…`
- 경로: `training/generated/thinking_traces/batch005/`, `…/teacher_qwen3.8_27b/batch005_no_correct/`, `…/teacher/`.

## 5. 다음 판단에 필요한 최소 자료

| 판단 | 자료 |
|---|---|
| teacher 표본 검토 | `training/generated/thinking_traces/teacher/human_review_teacher_10.md`(로컬), `teacher/selected_teacher.json` |
| batch005 teacher 포함 | `teacher/batch005_no_correct/summary.json`, `scale/estimate.json` |
| 검토 쌍 14개 | `traces/batch005_filtered.json`의 `reviewed_hf_pairs_rejudgment(reference)`, `../batch005/hf_outputs.json` |
| 데이터 규모·칸 분포 | `scale/estimate.json` |
| 셋과 기준값 | `../vendor100_protocol/PROTOCOL_v2.md` 3·7절, `sets/sets_summary.json`, `sets/runs/*.json` |
