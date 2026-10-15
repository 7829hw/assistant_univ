# batch007 사람 검토 안내

이 디렉터리는 사람 검토용 자료다. 여기 있는 어떤 것도 승인된 학습 자료가 아니다.

- **누가 썼나.** 질문, 초안 grounding, 근거는 Claude가 2026-10-15에 썼다(결정 104).
- **무엇을 위한 것인가.** "실차"라는 말 없이 운행 상태를 표현한 통행량 질문(예: 손님을 태운 택시의 통행량, 승객이 탄 택시가 지나간 양)과,
  이와 헷갈리는 대조 질문(손님을 태운 건수, 빈 택시의 통행량 등)이다. 계기는 selection_v2의 indepv2/n33이다
  (pilot_004에서 "실차"가 있는 g02·g04는 고쳐졌지만 "실차" 없이 표현한 n33은 그대로 틀렸다). 질문은 n33이나 보호된 평가 셋에서 파생하지 않고 새로 썼다.
- **모델 출력.** base 모델(Qwen/Qwen3-8B@b968826d, thinking 켬, vLLM 0.30.0 BF16 flashinfer, greedy, 8192, prompt 87048d0c)의 첫 응답이다. 검토 전 후보일 뿐이다.
- **형식 통과는 승인이 아니다.** validator·compose·compile 통과는 형식 검사다. 질문의 뜻이 맞다는 증거가 아니다.
- **승인은 사람의 결정뿐이다.** 사람이 질문을 읽고 내린 결정만 승인이다. 그 결정은 `workflow decide`로 decisions 파일에 남는다.
- **학습 trace는 승인 뒤에 모은다.** 이번 작업에서는 trace 수집과 import를 하지 않았다.
- **다음 판에서 이 데이터로 학습하면** selection_v2 결과를 n33을 넣은 것과 뺀 것 둘 다로 보고한다(결정 104).

## 파일

| 파일 | 내용 |
|---|---|
| `batch007_review.xlsx`(커밋하지 않음) | 검토 화면. 시트: 안내, batch007(후보 27), vllm_outputs(초안과 다른 모델 출력). `*.xlsx` ignore 규칙에 따라 커밋하지 않는다. `python sft_dpo_inventory/batch007/build_review.py --xlsx-only`로 다시 만든다 |
| `review_queue.jsonl`, `manifest.json` | thor `training.annotations.workflow` queue 형식(SFT gold 27행 + 초안과 다른 vLLM 출력 행). 권위 있는 기록이다 |
| 응답 원문(커밋하지 않음) | `training/generated/batch007/raw/vllm_outputs_raw.jsonl`(ignore 경로). queue에는 원문 sha256과 파싱한 JSON만 있다. XLSX의 "모델 응답 JSON 본문" 칸은 이 파일에서 채운다 |

## 대조 묶음

의도 7개(family `b007-i1`…`b007-i7`)마다 같은 장소·날짜·시간·묶음 기준으로 네 질문이 있다(b007-08은 보호 셋 family와 겹쳐 뺐다).

| 대조(variant) | 뜻 | 초안 grounding |
|---|---|---|
| occupied | "실차" 없이 손님·승객이 탄 택시의 통행량(지나간 양) | passage_count + taxi_status occupied |
| vacant | 빈 택시(손님 없이 다닌 택시)의 통행량 | passage_count + taxi_status vacant |
| plain | 운행 상태 없는 통행량 | passage_count(taxi_status 없음) |
| trip_pickup | 손님을 태운 건수(= 승차 실차 건수) | trip_count, 장소 od_role pickup, dimension_target pickup |
| trip_dropoff | 손님을 내려준 건수(= 하차 실차 건수) | trip_count, 장소 od_role dropoff, dimension_target dropoff |

- occupied 표현은 의도마다 다르다: 손님이 타고 있던 택시, 승객이 탄 택시가 지나간 양, 승객을 싣고 다닌 택시, 손님 태운 택시들이 얼마나 지나갔는지, 승객 탑승 택시,
  손님을 태우고 지나간 택시, 승객이 타고 있는 택시, 손님을 모시고 달린 택시, 손님 있는 택시, 승객을 태운 택시가 지나간 양.
- 가장 헷갈리는 짝은 같은 의도 안의 "손님(승객)을 태운 택시가 지나간 양"(occupied, 통행량)과 "손님(승객)을 태운 건수"(trip_pickup, 건수)다(예: b007-25와 b007-27).
- 묶음 기준은 시군구(i1·i2), H3(i4·i6·i7), H3 + 근처·주변(i3·i5)이다. 건수 질문은 묶는 끝(승차·하차)을 질문에 적었다.

## 열의 뜻

**batch007 시트**: 후보 id, 대조, family(의도), 질문, 초안 grounding, 근거, 현재 코드 결과(T2PC 경로), 업체 100과의 문자 3-gram 유사도 최댓값,
비고, 결정 칸.

**vllm_outputs 시트**: 초안(chosen), 모델 응답 JSON 본문(rejected 후보), thinking 길이·생성 token·종료 이유, 첫 응답 기준 차이, 조건 계층
적용 뒤 차이(참고), 결정 6 표시, 오류 태그, 검토 질문, 결정 칸.

- **결정 6 표시**: 조건 계층을 적용하면 초안과 같아지는 쌍이다. 운영 경로에서 코드가 고쳐 뜻이 같아지므로 DPO 쌍으로 쓰지 않는다.

**결정 칸**: 승인 / 수정 / 보류 / 제외 중 하나와 수정 grounding(JSON), 메모, 검토자, 검토일.

## 판단 기준

1. **통행량 대 건수.**
   - 손님·승객이 탄 택시의 통행량(지나간 양) = `passage_count` + `taxi_status: occupied`. "실차"라는 말이 없어도 같다.
   - 손님을 태운 건수·내려준 건수 = 실차 운행 구간의 수 = `trip_count`. trip은 실차 구간 자체라 `taxi_status`를 붙이지 않는다.
   - "태운"이 있어도 측정 대상이 "통행량·지나간 양"이면 passage_count다. 기준은 측정 대상이 통행량인지 건수인지다.
2. **운행 상태.** 빈 택시·손님 없이 다닌 택시는 `vacant`, 손님·승객이 탄 택시는 `occupied`다. 질문에 상태가 없으면 `taxi_status`를 만들지 않는다.
3. **통행량의 장소.** passage에는 출발·도착이 없다. 장소에 `od_role`을 붙이지 않고, 묶음에 `dimension_target`을 두지 않는다.
4. **건수의 끝.** 태운 곳(승차)은 `pickup`, 내려준 곳(하차)은 `dropoff`. 장소가 제한하는 끝(`od_role`)과 묶는 끝(`dimension_target`)을 질문대로 적었는가.
5. **조건과 집계.** 질문에 없는 집계(예: `sum`)·순위·조건을 지어내지 않았는가. 근처·주변이 있을 때만 `vicinity`.
6. **그룹 단위와 날짜.** 시군구·H3, 날짜 범위(예: 2026년 8월 = 20260801-20260831)와 시간이 질문과 같은가.
7. **보호된 평가 셋과의 유사성.** 자동 검사(정규화 질문, id, template, family, 셋별 비교, 업체 100 문자 3-gram)에는 b007-08 말고 걸리지 않았다.
   n33과의 문자 3-gram Jaccard는 최댓값 0.163이다(`../candidates_checked.json`). 문장이 보호된 평가 셋의 질문을 바꿔 쓴 것처럼 보이면 제외하고 메모한다.
8. **vllm_outputs 쌍.** 초안과 모델 중 어느 쪽이 맞는지 먼저 정한다.
   - 초안이 맞으면 승인한다. 그 쌍이 DPO rejected 후보가 된다.
   - 모델이 맞으면 그 쌍은 제외하고, batch007 시트의 같은 후보를 수정한다.
   - 결정 6 표시가 있는 쌍은 제외한다.

## 결정 기록과 가져오기(검토 뒤에 실행한다. 이번 작업에서는 실행하지 않았다)

```bash
# 1) 한 행씩 결정을 기록한다(검토자 이름과 근거).
python -m training.annotations.workflow decide --queue sft_dpo_inventory/batch007/review \
  --decisions sft_dpo_inventory/batch007/review/decisions_007.jsonl --id b007-01 \
  --status accepted --reviewer "<이름>" --reason "<근거>" --semantic-checks-confirmed

#    채운 XLSX에서 명령을 만들려면 batch004의 도구를 쓴다(출력만 한다. 검토자가 확인한 뒤 실행한다).
python sft_dpo_inventory/batch004/sheet_to_commands.py FILLED.xlsx \
  --decisions sft_dpo_inventory/batch007/review/decisions_007.jsonl
```

승인분의 trace 수집, 데이터 구성, import는 검토가 끝난 뒤 따로 한다.
