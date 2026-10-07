# batch005 사람 검토 안내

이 디렉터리는 사람 검토용 자료다. 여기 있는 어떤 것도 승인된 학습 자료가 아니다.

- **누가 썼나.** 질문, 초안 grounding, 근거는 Claude가 2026-10-07에 썼다(결정 45).
- **모델 출력.** base 모델(Qwen/Qwen3-8B@b968826d, thinking 켬, greedy, 8192, prompt 87048d0c)의 첫 응답이다. 검토 전 후보일 뿐이다.
- **형식 통과는 승인이 아니다.** validator·compose·compile 통과는 형식 검사다. 질문의 뜻이 맞다는 증거가 아니다.
- **승인은 사람의 결정뿐이다.** 사람이 질문을 읽고 내린 결정만 승인이다. 그 결정은 `workflow decide`로 decisions 파일에 남는다.
- **학습 trace는 승인 뒤에 모은다.** 승인한 질문만 trace 수집(결정 45)과 pilot_002 데이터 구성으로 넘어간다.

## 파일

| 파일 | 내용 |
|---|---|
| `batch005_review.xlsx`(커밋하지 않음) | 검토 화면. 시트: 안내, batch005(후보 60), hf_outputs(초안과 다른 모델 출력). 저장소의 `*.xlsx` ignore 규칙에 따라 커밋하지 않는다. `python sft_dpo_inventory/batch005/build_review.py --xlsx-only`로 커밋된 JSON에서 다시 만든다 |
| `review_queue.jsonl`, `manifest.json` | thor `training.annotations.workflow` queue 형식(SFT gold 60행 + 초안과 다른 HF 출력 행). 권위 있는 기록이다. 모델 원문(thinking 포함)은 여기에 있다 |

## 열의 뜻

**batch005 시트**

- 후보 id, 유형 칸(결정 40-C 배분), family(같은 뜻 또는 대조 묶음), 질문, 초안 grounding, 근거.
- 현재 코드 결과(T2PC 경로: 계약, 멈춤 코드, compile).
- 기대 결과:
  - `answered`: 답하는 질문.
  - `t2pc_stop_grounding`: 결정 14의 정지 target. 조건을 grounding으로 적고 코드가 멈춘다.
- 비고: 정지 후보 8건(b005-05, 06, 07, 18, 19, 20, 25, 44)에는 이유를 적었다.
  - 택시 유형 조건을 `trip_count`·`rpm`의 Tool이 받지 않는다.

**hf_outputs 시트**

- 초안(chosen), 모델 응답의 JSON 본문(rejected 후보), thinking 길이·생성 token·종료 이유.
- 첫 응답 기준 차이, 조건 계층 적용 뒤 차이(참고).
  - 조건 계층 뒤 차이가 없으면, 운영 경로에서는 코드가 고쳐 같은 결과가 된다.
- 생성 상한(8192)에 걸려 JSON이 없는 출력은 `model_output_note`다. DPO rejected로 쓰지 않는다.

**결정 칸**

- 승인 / 수정 / 보류 / 제외 중 하나를 적는다.
- 수정 grounding(JSON), 메모, 검토자, 검토일도 적는다.

## 판단 기준

1. **측정값과 사건이 질문과 맞는가.**
   - 실차 건수 = `trip_count`(trip)
   - 통행량 = `passage_count`(passage)
   - rpm·분당 회전 속도 = `rpm`(passage)
   - 공차율 = `vacant_ratio`(drive)
   - 가동률 = `active_taxi_ratio`(operation)
   - 수입 = `revenue`(operation)
2. **조건.** 질문에 있는 조건만 있어야 한다(날짜, 시간, 택시 유형, 운행 상태, 근처). 없는 조건이나 집계를 지어내지 않았는지 본다.
3. **집계어.** 집계어(평균·최댓값·최솟값·중간값·합계)가 없으면 `aggregation`이 없어야 한다.
4. **od_role과 dimension_target.**
   - od_role은 장소가 제한하는 끝이다. 한 장소 안에서 출발과 도착이 모두 일어나면 그 장소 하나에 `both`다.
   - dimension_target은 결과를 묶는 끝이다(출발·도착·조합).
   - 두 `both`는 뜻이 다르다.
5. **그룹 단위.** 시도·시군구·읍면동·H3·요일이 질문과 같아야 한다. 순위어가 없으면 `order`·`limit`이 없어야 한다.
6. **vicinity.** 근처·주변·부근이 있을 때만 붙는다.
7. **정지 후보.** 질문이 택시 유형을 요구하는데 Tool이 받지 않으면, 조건을 버리고 답하는 대신 멈추는 것이 결정 14의 방식이다.
   - 이 질문들을 정지 target으로 둘지 정한다.
   - 정지 target으로 두지 않으려면 '제외'하고, 메모에 "조건을 뺀 질문으로 다시 쓰기" 등을 적는다.
8. **보호된 평가 셋과의 유사성.**
   - 문장이 보호된 평가 셋의 질문을 바꿔 쓴 것처럼 보이면 제외하고 메모한다.
   - 이 후보들은 Claude가 썼다. 같은 모델 계열이 쓴 기존 합성 평가 셋과 문장 습관이 비슷할 수 있다.
   - 자동 검사(정규화 질문, id, template, family)에는 걸리지 않았다. 사람의 파생 관계 확인은 따로 필요하다.
9. **hf_outputs 쌍.** 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다.
   - 초안이 맞으면 승인한다. 그 쌍이 DPO rejected 후보가 된다.
   - 모델이 맞으면 그 쌍은 제외하고, batch005 시트의 같은 후보를 수정한다.

## 결정 기록과 가져오기(검토 뒤에 실행한다. 이번 작업에서는 실행하지 않았다)

```bash
# 1) 한 행씩 결정을 기록한다(검토자 이름과 근거).
python -m training.annotations.workflow decide --queue sft_dpo_inventory/batch005/review \
  --decisions sft_dpo_inventory/batch005/review/decisions_005.jsonl --id b005-01 \
  --status accepted --reviewer "<이름>" --reason "<근거>" --semantic-checks-confirmed

#    채운 XLSX에서 명령을 만들려면 batch004의 도구를 쓴다(출력만 한다. 검토자가 확인한 뒤 실행한다).
python sft_dpo_inventory/batch004/sheet_to_commands.py FILLED.xlsx \
  --decisions sft_dpo_inventory/batch005/review/decisions_005.jsonl

# 2) 승인된 행만 새 reviewed corpus 후보 판으로 만든다. 보호 셋·출처·prompt가 queue 작성 때와 다르면 거부한다.
python -m training.annotations.workflow import-reviewed --queue sft_dpo_inventory/batch005/review \
  --decisions sft_dpo_inventory/batch005/review/decisions_005.jsonl \
  --output training/generated/corpora/reviewed_gold_v005_candidate --version reviewed_gold_v005_candidate
```

- **결정 대응:**
  - 승인 → `accepted`
  - 수정 → `accepted` + `--corrected-grounding`
  - 보류 → `needs_fix`
  - 제외 → `rejected`
  - hf_outputs 쌍을 승인하면 `--negative-is-wrong`도 붙인다(모델 출력이 틀렸다는 판단).
- `sheet_to_commands.py`는 batch004 시트 형식(시트 이름 `batch004`)을 읽도록 쓰였다. batch005 시트에 쓸 수 있는지는 실행 전에 확인한다(이번에 확인하지 않음).
- import 결과는 v004와 합치지 않는다. 합치는 일과 trace 수집은 별도 단계다.
