# Remaining Teacher Recovery 사전 등록

고정: 2026-10-14, 모델 호출 전. 결정 83. 앞 단계 `p0_sft_003_teacher27b`(결정 79–82)의 설정·gate·검토 규칙을 그대로 쓴다.

## 1. 시작 상태(코드로 재계산, `partition.json`)

- reasoning coverage 110/154: R70 70, M2 회수 10, M3 회수 3, 27B P1/P2 승인 27. 출처 간 중복 0.
- missing 44 = M1 P3 28 + M2 실패 11 + M3 실패 1 + 27B 실패 4. 합·중복 검사 통과(`build_target_manifest.py`).

## 2. 두 track

| track | 대상 | 모델 호출 |
|---|---|---|
| A | M1 P3 28(A1) + M2 실패 11(A2) + M3 실패 1(A3) = 40 | 27B 최대 200 |
| B | 27B가 5/5 실패한 implicit-pickup 4(b006-05, b006-15, b006-20, b006-26) | **0**(8B 0, 27B 0) |

## 3. Track A 대상 manifest(`target_manifest.json`)

| 항목 | 값 |
|---|---|
| sha256 | `d8c1bd5d339fcc8085ff186d6e5423f05298d342cb89e51fd09dd901fbeca474` |
| item 순서 sha256 | `0bdcf110f4cdfc556499a42a6a17aa55a19fd63981cc90bee36c415eba9c4f69`(id를 `\n`으로 이은 문자열) |
| 순서 | A1 → A2 → A3, 그룹 안은 `p0_sft_003_prep/missing_reasoning_manifest.json` 순서. item_index 0–39 |
| 필드 | item_id, question, missing_class, old_priority, source, gap, semantic_family, measure, dimension, dimension_target, od_role, previous_8b_attempts, previous_27b_attempts(0), previous_failure_reason |

## 4. 모델·실행 조건(재확인 2026-10-14, 재-pull 없음)

- `qwen3.8:27b` digest `aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813`, capabilities completion·vision·tools·thinking, Q4_K_M, RENDERER qwen3.8 / PARSER qwen3.5.
- Ollama 0.40.3. GPU `GPU-d4308fbb-d17f-3609-676a-935c6072c831`(host·컨테이너 같음), compute 프로세스 0, `/api/ps` 빈 상태, 컨테이너 restart 0.
- 위가 G3 PASS 때와 같으므로 G3 compatibility 10문항은 다시 하지 않는다. 호출마다 precheck만 한다.

## 5. Generation(`p0_sft_003_teacher27b/teacher_generate.py`)

- 문항당 greedy 1(temperature 0) + sampling 4(temperature 0.6, top_p 0.95, top_k 20). 최대 200호출.
- **seed = 2026101600 + 10 × item_index + sample_index**(sampling만, greedy는 seed 없음). 이전 batch(2026101500 + …, 최대 2026101804)와 겹치지 않는다.
- `think: true`, P0 prompt `d7f4c12a`, gold 미제공, num_predict 미지정.
- 결정 80: 호출마다 `keep_alive: 0`. 다음 호출 전 `/api/ps` 빈 상태 + GPU compute 프로세스 0(runner 종료)을 기다린 뒤 precheck. resident·resident_isolated 사용 안 함.
- timeout 3600초, 재시도 0. 실패 호출도 기록한다.
- 속도 guard 79.13 tok/s(앞 G3 기준, 같은 GPU·runtime·artifact).
- guard 위반이면 중단하고 원문을 ABORTED로 둔다.
- 코드: 31문항 batch와 같은 스크립트에 manifest·경로·seed base 인자만 추가했다(기록용, 생성 방식 불변).
  - 판정 스크립트는 기본값으로 다시 돌려 31문항 `judge.json`이 바이트 단위로 같고 선택 27개가 같음을 확인했다.
- 명령:

```
python sft_dpo_inventory/p0_sft_003_teacher27b/teacher_generate.py --speed-threshold 79.13 \
  --manifest sft_dpo_inventory/p0_sft_003_teacher27b_remaining/target_manifest.json \
  --manifest-sha d8c1bd5d339fcc8085ff186d6e5423f05298d342cb89e51fd09dd901fbeca474 \
  --order-sha 0bdcf110f4cdfc556499a42a6a17aa55a19fd63981cc90bee36c415eba9c4f69 --n-items 40 \
  --raw-dir sft_dpo_inventory/p0_sft_003_teacher27b_remaining/generation/raw \
  --summary-dir sft_dpo_inventory/p0_sft_003_teacher27b_remaining/generation \
  --seed-base 2026101600 --batch p0_sft_003_teacher27b_remaining/track_a
```

- raw는 판정 전에 commit·push한다.

## 6. 판정·선택·검토(31문항 batch와 같음)

- `judge_select.py --raw … --out-dir …`. 5범주, 후보는 EXACT_OR_SEMANTIC_MATCH만. 필터: thinking·stop·결정 40-D 루프·결정 18 길이·문자열 왕복·중복.
- ranking: `quality_gate_v1.rank_key`(sha256 `f57e2d3e…`, 수정 금지). 문항당 top-1.
- judge·선택은 사람 검토 전에 commit·push한다.
- 사람 검토: 선택된 trace 전부를 직접 읽는다. 기준은 `p0_sft_003_recovery/PLAN.md` 4절, 그리고 탐색과 확정 오판의 구분. 거부하면 TEACHER_RECOVERY_FAILED이고 다른 표본으로 바꾸지 않는다.
- 결과는 그룹(A1·A2·A3)별, feature별로 보고한다.

## 7. Track B(모델 호출 0)

- 기존 27B 20 trace(`training/generated/p0_sft_003_teacher27b/raw/traces.jsonl`)와 v006 gold, P0 prompt만 읽는다.
- 문항별 gold 판정: CLEAR_GOLD / LINGUISTICALLY_AMBIGUOUS / CONTRACT_DEPENDENT / GOLD_PROBLEM. slot은 measure, place restriction, 그 od_role, grouping dimension, dimension_target, order, limit이다.
  - 장소 제한의 endpoint(od_role)와 grouping의 endpoint(dimension_target)는 따로 판단한다.
- 20 call failure matrix: dimension_target·od_role 각각 correct/omitted/wrong, 둘 다 맞음/틀림.
- thinking 수준 tag: SEMANTIC_UNDERSTANDING_FAILURE, SERIALIZATION_OMISSION, OD_ROLE_DIM_TARGET_COLLAPSE, PROMPT_COVERAGE_GAP(복수 가능).
- P0 prompt는 읽기만 하고 고치지 않는다.
- CLEAR_GOLD 문항에는 짧은 canonical rationale candidate를 쓴다. **training inclusion = false**이고 coverage에 넣지 않는다.

## 8. Coverage

- 110 + Track A 사람 승인(unique). Track B candidate는 더하지 않는다.
- 남은 문항 분류: NO_CORRECT_27B_TRACE / TOP1_REJECTED / IMPLICIT_PICKUP_REPEAT_FAILURE / OTHER, 그리고 원래 분류(M1 P3·M2·M3).
- 출처: HF 8B R70, HF 8B M2, M3 회수, 27B P1/P2, 27B remaining.

## 9. 하지 않는 것

- Track B 재생성, 31문항 batch 재실행, seed·num_predict·quality_gate_v1·prompt 변경, retry로 표본 늘리기.
- reviewed_reasoning_v001 freeze, SFT·DPO. `qwen3.8:27b` 삭제·재-pull.
