# batch004 사람 검토 안내

이 디렉터리는 사람 검토용 자료다. 여기 있는 어떤 것도 승인된 학습 자료가 아니다.

- **누가 썼나.** 초안 grounding과 근거는 Claude가 2026-10-06에 썼다.
- **모델 출력.** base 모델(Qwen/Qwen3-8B@b968826d, thinking 끔, prompt 87048d0c)의 첫 응답이다. 검토 전 후보일 뿐이다.
- **형식 통과는 승인이 아니다.** validator·compose·compile 통과는 형식 검사다. 질문의 뜻이 맞다는 증거가 아니다.
- **승인은 사람의 결정뿐이다.** 사람이 질문을 읽고 내린 결정만 승인이며, 그 결정은 `workflow decide`로 decisions 파일에 남는다.

## 파일

| 파일 | 내용 |
|---|---|
| `batch004_review.xlsx`(커밋하지 않음) | 검토 화면. 시트: 안내, batch004(후보 18), hf_outputs(초안과 다른 모델 출력 15쌍), v003_flags(21), 결정요청(1). 저장소의 `*.xlsx` ignore 규칙과 thor 관례(XLSX view는 ignored binary)에 따라 커밋하지 않는다. `python sft_dpo_inventory/batch004/build_review.py --xlsx-only`로 커밋된 JSON에서 다시 만든다(queue·manifest는 바꾸지 않고, 다시 만든 행이 커밋된 queue와 같은지 확인한다) |
| `review_queue.jsonl`, `manifest.json` | thor `training.annotations.workflow` queue 형식(33행: SFT gold 18 + DPO 쌍 15). 권위 있는 기록 |
| `v003_flag_items.jsonl` | reviewed_gold_v003_t2pc 표시 항목(compile 정지 SFT 17, DPO 4쌍). workflow로 가져오지 않는다 |
| `decision_requests.jsonl` | 지원 불가 target 형식 결정 요청 |

## 열의 뜻

- **batch004 시트.**
  - 후보 id, 유형(채우려는 공백 유형), family(같은 뜻 또는 대조 문항 묶음), 질문, 초안 grounding, 근거.
  - 현재 코드 결과(T2PC 경로: 계약 통과·멈춤 코드·compile).
  - 평가 셋 겹침(확장 대조, 정보): vendor 형식 평가 셋의 정답 호출과 template·family가 같은지. thor 정책의 제외 대상은 아니다.
  - 비고: 정지 후보 4건(b004-34/35/40/41)은 지원 불가 target 형식 결정을 기다린다.
- **hf_outputs 시트.** 초안(chosen), 모델 첫 응답(rejected 후보), 첫 응답 기준 차이, 조건 계층 적용 뒤 차이(참고).
  - 조건 계층 뒤 차이가 없으면, 운영 경로에서는 코드가 날짜를 고쳐 같은 결과가 된다. v003의 "rejected = chosen" 쌍과 같은 성격이다.
- **결정 칸.** 승인 / 수정 / 보류 / 제외 중 하나와 수정 grounding(JSON), 메모, 검토자, 검토일.

## 판단 기준

1. **측정값과 사건.** 질문과 맞아야 한다. 통행량=passage_count(passage), 실차 건수=trip_count(trip), 요금=fare, 수입=revenue, 공차율=vacant_ratio(drive).
2. **조건.** 질문에 있는 조건만 있어야 한다(날짜·시간·택시 유형·운행 상태·근처). 없는 조건이나 집계를 지어내지 않았는지 본다.
3. **집계어.** 집계어가 없으면 aggregation이 없어야 한다.
4. **od_role과 dimension_target.** 장소의 od_role(장소가 제한하는 끝)과 dimension_target(결과를 묶는 끝)을 구분해야 한다.
5. **그룹 단위.** 시도·시군구·읍면동·요일이 질문과 같아야 한다.
6. **보호된 평가 셋과의 유사성.** 문장이 보호된 평가 셋의 질문을 바꿔 쓴 것처럼 보이면 제외하고 메모한다. 이 후보들은 Claude가 썼다. 같은 모델 계열이 쓴 기존 합성 평가 셋과 문장 습관이 비슷할 수 있다.
7. **hf_outputs 쌍.** 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다.
   - 초안이 맞으면 승인한다. 그 쌍이 DPO rejected가 된다.
   - 모델이 맞으면 그 쌍은 제외하고, batch004 시트의 같은 후보를 수정한다.

## 결정 기록과 가져오기(검토 뒤에 실행한다. 이번 작업에서는 실행하지 않았다)

```bash
# 0) 보호 기준 디렉터리 재구성(ignored. queue manifest의 gold_dir).
python -m training.data.retarget_prompt --archive training/records/corpora/reviewed_gold_v003 \
  --version reviewed_gold_v003_t2pc --output training/generated/reviewed_gold_v003_t2pc \
  --records /tmp/v003_t2pc_records_check     # 이미 있으면 생략. 커밋된 기록과 같은 hash인지 비교한다
cp training/records/corpora/reviewed_gold_v003/corpus_manifest.json training/generated/reviewed_gold_v003_t2pc/

# 1) 채운 시트에서 decide 명령을 만든다(출력만 한다). 검토자가 확인한 뒤 실행한다.
python sft_dpo_inventory/batch004/sheet_to_commands.py FILLED.xlsx \
  --decisions sft_dpo_inventory/batch004/review/decisions_004.jsonl

#    직접 기록할 수도 있다(한 행씩):
python -m training.annotations.workflow decide --queue sft_dpo_inventory/batch004/review \
  --decisions sft_dpo_inventory/batch004/review/decisions_004.jsonl --id b004-18 \
  --status accepted --reviewer "<이름>" --reason "<근거>" --semantic-checks-confirmed

# 2) 승인된 행만 새 reviewed corpus 판으로 만든다. 보호 셋·출처·prompt가 queue 작성 때와 다르면 거부한다.
python -m training.annotations.workflow import-reviewed --queue sft_dpo_inventory/batch004/review \
  --decisions sft_dpo_inventory/batch004/review/decisions_004.jsonl \
  --output training/generated/corpora/reviewed_gold_v004_candidate --version reviewed_gold_v004_candidate
```

- **결정 대응:**
  - 승인 → `accepted`.
  - 수정 → `accepted` + `--corrected-grounding`.
  - 보류 → `needs_fix`.
  - 제외 → `rejected`.
  - hf_outputs 쌍을 승인하면 `--negative-is-wrong`도 붙인다(모델 출력이 틀렸다는 판단).
- **정지 후보 4건은 가져오지 않는다.** `training_blockers: unsupported_target_format_undecided`로 import에서 빠진다. 형식이 정해지면 새 queue로 다시 만든다.
- **import 결과는 v003_t2pc와 합치지 않는다.** v003_t2pc와 합치는 일, v003 표시 항목의 처분을 반영하는 일은 별도 단계다(REPORT 6절).
