# batch006 사람 검토 안내

이 디렉터리는 사람 검토용 자료다. 여기 있는 어떤 것도 승인된 학습 자료가 아니다.

- **누가 썼나.** 질문, 초안 grounding, 근거는 Claude가 2026-10-12에 썼다(결정 66·77).
- **무엇을 위한 것인가.** 결정 66의 "실차 통행량" 대조 묶음이다. 학습 데이터에 "실차 통행량"(passage_count + taxi_status occupied)
  정답이 하나도 없고, "실차"가 든 질문의 정답은 모두 trip_count였다. valid98 h30에서 base 모델이 실차 통행량을 trip_count로 읽었다
  (`../../selection_decline/PASSAGE_STATUS.md`). 업체 100과 selection 셋의 문항에서 파생하지 않았다.
- **모델 출력.** base 모델(Qwen/Qwen3-8B@b968826d, thinking 켬, greedy, 8192, prompt 87048d0c)의 첫 응답이다. 검토 전 후보일 뿐이다.
- **형식 통과는 승인이 아니다.** validator·compose·compile 통과는 형식 검사다. 질문의 뜻이 맞다는 증거가 아니다.
- **승인은 사람의 결정뿐이다.** 사람이 질문을 읽고 내린 결정만 승인이다. 그 결정은 `workflow decide`로 decisions 파일에 남는다.
- **학습 trace는 승인 뒤에 모은다.** 이번 작업에서는 trace 수집과 import를 하지 않았다.

## 파일

| 파일 | 내용 |
|---|---|
| `batch006_review.xlsx`(커밋하지 않음) | 검토 화면. 시트: 안내, batch006(후보 28), hf_outputs(초안과 다른 모델 출력). `*.xlsx` ignore 규칙에 따라 커밋하지 않는다. `python sft_dpo_inventory/batch006/build_review.py --xlsx-only`로 다시 만든다 |
| `review_queue.jsonl`, `manifest.json` | thor `training.annotations.workflow` queue 형식(SFT gold 28행 + 초안과 다른 HF 출력 행). 권위 있는 기록이다 |
| 응답 원문(커밋하지 않음) | `training/generated/batch006/raw/hf_outputs_raw.jsonl`(ignore 경로). queue에는 원문 sha256과 파싱한 JSON만 있다. XLSX의 "모델 응답 JSON 본문" 칸은 이 파일에서 채운다 |

## 대조 묶음

의도 7개(family `b006-i1`…`b006-i7`)마다 같은 장소·날짜·시간·묶음 기준으로 네 질문이 있다.

| 대조(variant) | 뜻 | 초안 grounding |
|---|---|---|
| occupied | 실차 통행량(손님을 태운 택시의 통행량) | passage_count + taxi_status occupied |
| vacant | 공차 통행량(빈 택시의 통행량) | passage_count + taxi_status vacant |
| plain | 운행 상태 없는 통행량 | passage_count(taxi_status 없음) |
| trip | 실차 건수 | trip_count(taxi_status 없음, 장소 od_role과 dimension_target) |

- 묶음 기준은 시군구(i1·i2), H3(i3·i6·i7), H3 + 근처(i4·i5)다. 묶음이 없는 통행량, 읍면동별 통행량, 순위가 붙은 통행량은 보호된 평가 셋의
  family라 쓰지 않았다. 요일별·집계 통행량은 현재 계약에서 멈춘다.
- 실차 건수(trip)는 장소가 출발·도착 중 어느 끝을 제한하는지 질문에 적었다. "대구의 실차 건수"처럼 끝이 없는 문장은 만들지 않았다.

## 열의 뜻

**batch006 시트**: 후보 id, 대조, family(의도), 질문, 초안 grounding, 근거, 현재 코드 결과(T2PC 경로), 업체 100과의 문자 3-gram 유사도 최댓값,
비고, 결정 칸.

**hf_outputs 시트**: 초안(chosen), 모델 응답 JSON 본문(rejected 후보), thinking 길이·생성 token·종료 이유, 첫 응답 기준 차이, 조건 계층
적용 뒤 차이(참고), 결정 6 표시, 오류 태그, 검토 질문, 결정 칸.

- **결정 6 표시**: 조건 계층을 적용하면 초안과 같아지는 쌍이다. 운영 경로에서 코드가 고쳐 뜻이 같아지므로 DPO 쌍으로 쓰지 않는다.

**결정 칸**: 승인 / 수정 / 보류 / 제외 중 하나와 수정 grounding(JSON), 메모, 검토자, 검토일.

## 판단 기준

1. **실차 통행량 대 실차 건수.**
   - 실차 통행량 = 손님을 태운 택시가 장소를 지나간 양 = `passage_count` + `taxi_status: occupied`.
   - 실차 건수 = 손님을 태운 운행 구간의 수 = `trip_count`. trip은 실차 구간 자체라 `taxi_status`를 붙이지 않는다.
   - "실차"라는 말만으로 trip_count로 읽지 않는다. 측정 대상이 "통행량"인지 "건수(구간)"인지가 기준이다.
2. **운행 상태.** 공차(빈 차)는 `vacant`, 실차(손님 태움)는 `occupied`다. 질문에 상태가 없으면 `taxi_status`를 만들지 않는다.
3. **통행량의 장소.** passage에는 출발·도착이 없다. 장소에 `od_role`을 붙이지 않고, 묶음에 `dimension_target`을 두지 않는다.
4. **실차 건수의 끝.** 장소가 제한하는 끝(`od_role`: pickup·dropoff·both)과 결과를 묶는 끝(`dimension_target`)을 질문대로 적었는가.
5. **조건과 집계.** 질문에 없는 집계(예: `sum`)·순위·조건을 지어내지 않았는가. 근처·주변이 있을 때만 `vicinity`.
6. **그룹 단위.** 시군구·H3가 질문과 같은가.
7. **보호된 평가 셋과의 유사성.** 자동 검사(정규화 질문, id, template, family, 셋별 비교, 업체 100 문자 3-gram)에는 걸리지 않았다.
   문장이 보호된 평가 셋의 질문을 바꿔 쓴 것처럼 보이면 제외하고 메모한다. 사람의 파생 관계 확인은 따로 필요하다.
8. **hf_outputs 쌍.** 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다.
   - 초안이 맞으면 승인한다. 그 쌍이 DPO rejected 후보가 된다.
   - 모델이 맞으면 그 쌍은 제외하고, batch006 시트의 같은 후보를 수정한다.
   - 결정 6 표시가 있는 쌍은 제외한다.

## 결정 기록과 가져오기(검토 뒤에 실행한다. 이번 작업에서는 실행하지 않았다)

```bash
# 1) 한 행씩 결정을 기록한다(검토자 이름과 근거).
python -m training.annotations.workflow decide --queue sft_dpo_inventory/batch006/review \
  --decisions sft_dpo_inventory/batch006/review/decisions_006.jsonl --id b006-01 \
  --status accepted --reviewer "<이름>" --reason "<근거>" --semantic-checks-confirmed

#    채운 XLSX에서 명령을 만들려면 batch004의 도구를 쓴다(출력만 한다. 검토자가 확인한 뒤 실행한다).
python sft_dpo_inventory/batch004/sheet_to_commands.py FILLED.xlsx \
  --decisions sft_dpo_inventory/batch006/review/decisions_006.jsonl
```

승인분의 trace 수집, 데이터 구성, import는 검토가 끝난 뒤 따로 한다.
