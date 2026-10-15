# `sft-dpo-t2pc` × `partial-grounding` 통합 및 신규 300문항 활용 계획 (v2)

개정: 2026-10-15. v1(같은 파일명, v2 표시 없음)을 두 브랜치의 최신 커밋과 300문항 검증 결과에 맞춰 고쳤다.
함께 고친 데이터: `질문_증강_300문항_추가_v2.xlsx`.

## 0. v1에서 바뀐 것

| 항목 | v1 | v2 |
|---|---|---|
| 출발점 | pilot_003, P0.2/P0.3 | pilot_004·005와 p0_sft_001–004까지 반영 |
| 실험 이름 | Pilot 004 | **pilot_006** (pilot_004·005는 이미 있음) |
| 실험 질문 | Partial target을 학습하면 되는가 | pilot_005 수준의 학습에서 Partial target이 p0_sft_004의 구조 회귀 없이 Full과 동등한가 |
| 학습 단계 | SFT + DPO | **SFT만**(pilot_005 V1 recipe). DPO는 주 비교에서 뺀다 |
| 300문항 분할 | SFT 180 / DPO 60 / holdout 60, 유형·난이도 층화 무작위 | **train 162 / holdout 53 / 보류 58 / 제외 5 / 축소 22**, family 단위 |
| 300문항 gold | 그대로 | 3문항 수정(130·305·306), SCOPE_NAME 난이도 30건 수정 |
| vendor100 | 최종 보호 셋으로 전제 | 지위를 먼저 결정(D1). 300문항이 vendor100에서 파생됐고 partial-grounding이 이미 개발 셋으로 썼음 |
| 판정 | holdout 60에서 −1%p 비열등 등 | PROTOCOL_v5 통계 규칙, selection_v2 기준, 마진은 검정력 확인 뒤 고정 |
| Git 통합 | 공통 파일 수동 반영 | 먼저 이름 공간 정리(batch006·결정 번호 충돌), 그다음 Full arm 재현 확인 |

---

## 1. 목적

두 브랜치를 Git으로 합치는 것 자체가 목적이 아니다.

> **pilot_005에서 검증된 SFT recipe 위에 Partial Grounding의 출력 계약을 얹고, 같은 질문·같은 학습 설정·같은 평가 경로에서 Full-trained와 Partial-trained를 직접 비교한다.**

실험 질문은 하나다.

> **pilot_005 수준의 학습량에서 Partial target을 학습한 모델이, p0_sft_004에서 나온 구조 회귀(value 없는 place, scope 역조회 붕괴) 없이 Full-trained와 동등한 의미 정확도를 내면서 구조 오류와 생성 비용을 줄이는가?**

신규 300문항은 이 비교의 학습 데이터 일부와 진단 holdout으로 쓴다. 약점 보강의 주 재료는 아니다(6.4절).

---

## 2. 현재 상태

### 2.1 `geoflow/sft-dpo-t2pc`

| 판 | 핵심 결과 | 기록 |
|---|---|---|
| pilot_003 | 학습 효과 확인. aggregation_added 크게 감소. dt 누락·vicinity 누락·실차 통행량 오독은 남음 | `sft_dpo_inventory/pilot_003*` |
| pilot_004 | 결정 86: teacher `full_response`, 8b 자체 `json_only`. SFT 934는 base 대비 +9.18%p [2.30, 16.08]. **DPO 단계가 조용한 오답을 +5.36%p [2.04, 9.44] 늘림, 주로 dt_missing 3.32 → 6.38%**. 중단 규칙에서 멈춤 | `pilot_004/REPORT.md` |
| pilot_004 실차 | "실차"라는 말이 있는 g02·g04 오독은 사라짐. "손님을 태운 택시"(n33)는 그대로 | 같은 보고 5절 |
| pilot_005 | 후보 7개 중 **SFT-only v1_step467** 선택: 86.22%, +11.22%p, 99.29% CI [2.55, 20.15]. U 조건 만족. 업체 100 평가 대기 | `pilot_005/selection_table.md` |
| batch007 | "실차" 없는 occupied 표현 대조 후보 27건. 검토 전(결정 104) | `batch007/README.md` |

정리하면 다음과 같다.

- v1이 "다음 방향"으로 적은 teacher `full_response` / 8b 자체 `json_only`는 이미 적용됐고 효과가 있었다.
- DPO는 이번 실험이 가장 신경 쓰는 dimension_target을 악화시켰다. 현재 최선의 Full 후보는 SFT-only다.
- 실차 통행량의 남은 문제는 "실차"라는 말이 없는 표현이다.

### 2.2 `geoflow/partial-grounding`

| 단계 | 핵심 결과 | 기록 |
|---|---|---|
| replay | Full correct → Partial wrong 0, Full wrong → Partial correct 46, 최종 JSON token 약 46–48% 감소 | `evaluation/partial_grounding/` |
| P0.2/P0.3 prompt | dt 누락 증가, week/month·dimension 혼동, 구조 오류가 answered_wrong으로 이동. P0.3은 비열등 미확정 | 같은 위치 |
| p0_sft_001 | 2 epoch 답 학습: dt +25문항, 대신 thinking·bucket·scope를 잃음 | `sft_dpo_inventory/p0_sft_001/` |
| p0_sft_004 | **Partial target 학습 실험.** FULL154(`full_response`) base 대비 −1.0%p [−5.7, +3.7], **first-response 구조 오류 41 → 52**(MULTIPLE_MEASURES 2 → 17, NO_MEASURE 1 → 10). JSON154(`json_only`) −10.7%p. implicit endpoint canonical 6문항 0/6. 결론 NOT_READY | `p0_sft_004/REPORT.md` |

정리하면 다음과 같다.

- "Partial target을 학습한 모델" 실험은 이미 1 epoch로 해 봤다. 의미 정확도는 지켰지만 새 구조 오류가 생겼다.
- 새 구조 오류의 원인은 두 가지다. value 없는 place가 measure로 읽혔고, scope 역조회 학습 예가 없었다(결정 67).
- 같은 레코드에서 reasoning까지 학습하면 `json_only`보다 +9.7%p 나았다. JSON만 학습하면 크게 손상된다.

### 2.3 이 계획에 주는 영향

1. Full arm의 기준 recipe는 pilot_005 V1(SFT-only)이다.
2. Partial arm에는 p0_sft_004에서 터진 구조 회귀를 막는 데이터(6.4절)와 전용 gate(11절 Gate D)가 있어야 한다.
3. 8b 자체 trace의 손실 범위는 두 브랜치의 증거가 서로 다르다. 그래서 결정 D2로 정한다.

---

## 3. 시작 전에 정할 것

아래 여섯 가지는 사용자 결정으로 `DECISIONS.md`에 남긴 뒤 진행한다. 권장안은 근거와 함께 적었다.

### D1. vendor100의 지위

현황은 다음과 같다.

- 300문항은 vendor100에서 파생됐다. 질문 ID가 101–400으로 이어지고, 장소·날짜·시간대가 같다.
  - 정답 tool call이 vendor100 문항과 같은 것: 25문항
  - 문자 3-gram Jaccard ≥ 0.5: 47문항
  - 위 둘의 합집합: 61문항
  - tool·인자 키 template이 같은 것: 150문항
- partial-grounding은 vendor100을 403문항 development benchmark에 넣어 여러 번 평가했다. p0_sft_004 REPORT도 "final holdout 아님"이라고 적었다.
- 따라서 Partial 표현(P0.x)은 vendor100을 보면서 다듬어졌다.

선택지:

- **(a) vendor100 유지.**
  - 겹침 58문항(합집합 61 중 다른 보호 셋과 겹쳐 제외된 3문항 뺀 수)은 학습에 쓰지 않는다.
  - template 겹침은 결정 54처럼 "알려진 겹침"으로 기록한다.
  - Full vs Partial 판정에서 Partial 쪽이 vendor100을 미리 본 사실을 보고서에 적는다.
- **(b) vendor100을 개발 셋으로 내림.**
  - 새 최종 보호 셋 `protected_final_v1`을 만든다. 보호 셋을 보지 않고 새로 쓰며, batch007과 같은 방식이다.
  - 보류 58문항은 train으로만 복귀하고, holdout은 바꾸지 않는다.

**권장: (b).** 두 arm 모두에 깨끗한 최종 셋은 (b)에서만 나온다.

### D2. 8b 자체 trace의 손실 범위(두 arm 공통)

- 선택지:
  - by_source: teacher `full_response`, 8b 자체 `json_only`. 결정 86 그대로다.
  - 전부 `full_response`.
- 근거:
  - Full에서는 by_source가 효과를 냈다(pilot_004·005).
  - Partial에서는 `json_only`만 쓴 JSON154가 −10.7%p였다. 다만 by_source는 `json_only` 손실 token 비중이 18.2%라 위험이 훨씬 작다.
- **권장: 두 arm 모두 by_source.**
  - 사전 등록에 감시 지표를 둔다. Partial arm의 thinking 길이 p90이 base 대비 30% 넘게 줄면 보고한다(JSON154의 손상 신호).
  - 두 arm이 다른 손실 범위를 쓰면 표현 말고 다른 변수가 섞이므로 그렇게 하지 않는다.

### D3. 평가 경로

**권장: PROTOCOL_v5 경로로 통일한다.**

- vLLM 0.30.0 BF16, flashinfer, LoRA 비병합, k=4, 동시 요청 8
- sampling: temperature 0.6, top_p 0.95, top_k 20

partial-grounding의 HF greedy 403 결과는 참고로만 쓴다. Partial 경로의 completion·compose 코드가 vLLM 평가 harness 안에서 Full과 같은 실행 서명으로 채점되는지 smoke로 먼저 확인한다(4.3절).

### D4. 비열등 마진

- v1의 −1%p는 검정할 수 없다. selection_v2 98문항 k=4에서도 base 대비 차이의 95% CI 폭이 약 14%p였다.
- **권장:**
  - pilot_005 문항별 결과로 "두 학습 모델 간 차이"의 CI 반폭을 미리 추정한 뒤 마진을 고정한다.
  - 잠정값은 −5%p다.
  - 반폭이 마진보다 크면 다음 중 하나를 사전 등록 때 정한다.
    - k=8로 늘린다.
    - selection_v2 + augmentation holdout 53을 합친 151문항을 주 셋으로 쓴다.

### D5. DPO

**권장: 주 비교에서 뺀다.**

- pilot_004에서 DPO가 dt_missing을 늘렸고, pilot_005 선택도 SFT-only였다.
- 두 arm이 SFT 비교를 통과한 뒤에 별도 판으로 다룬다.

### D6. 이름 공간

두 브랜치에서 같은 이름이 다른 것을 가리킨다.

| 이름 | `sft-dpo-t2pc` | `partial-grounding` |
|---|---|---|
| `batch006` | 실차 통행량 대조 묶음 28건 | Gap A·B 43건 + Gap C 10건(`approved.jsonl`) |
| `b006-05` | occupied 문항 | implicit pickup canonical 문항 |
| `reviewed_gold_v006_*` | `_t2pc` | `_p0` (같은 v006, 내용 다름) |
| 결정 81–87 | 결정 W–AB (86 = 손실 범위 출처별) | 27B teacher·p0_sft_004 (86 = p0_sft_004 실행) |

**권장:** partial-grounding 쪽에 접두어를 붙인다.

- batch: `pg_batch006`, `pg-b006-NN`
- 결정 번호: `PG-81`–`PG-87`
- 문서 안의 참조도 함께 바꾼다.
- 이 작업은 partial-grounding 브랜치에서 커밋한 뒤에 이식한다.

---

## 4. 두 브랜치 통합 전략

### 4.1 trunk와 실험 브랜치

```text
geoflow/sft-dpo-t2pc            (trunk, 지금처럼)
        │
        └── geoflow/pilot-006-partial-training
                 ├── pilot_006/full
                 └── pilot_006/partial
```

`sft-dpo-t2pc`를 trunk로 두는 이유:

1. 학습 pipeline, PROTOCOL_v5, 선택·중단 규칙이 이 브랜치에 있다.
2. 현재 최선의 Full 후보(pilot_005 v1_step467)가 이 브랜치의 recipe다.
3. Partial 계약은 아직 확정되지 않았다. P0.3은 비열등 미확정, p0_sft_004는 NOT_READY다.

### 4.2 이식 순서

**Step 0 — 이름 공간 정리(D6).** `partial-grounding`에서 커밋한다.

**Step 1 — 실험 브랜치 생성.**

```bash
git checkout geoflow/sft-dpo-t2pc
git checkout -b geoflow/pilot-006-partial-training
```

**Step 2 — 선택적 이식.** 가능하면 commit 단위로 cherry-pick한다.

| 가져올 것 | 위치(partial-grounding) |
|---|---|
| Partial 계약 parser·structural completion(subtype→concept, role, source, id, EVENT) | `geoflow/grounding.py`, `geoflow/planner.py`의 Partial 경로 |
| Full ↔ Partial 변환, replay, 분석 | `evaluation/partial_grounding/` |
| failure taxonomy, 구조 오류·grounding failure 측정 | 같은 위치, `p0_sft_004/analyze.py` |
| dimension_target·od_role·implicit endpoint 부분집합 정의 | `p0_sft_004/define_subsets.py`, `subsets.json` |
| loss-mask audit | `p0_sft_004/loss_mask_audit.py`, `p0_sft_002/loss_mask_audit.py` |
| reviewed_reasoning_v001(154)과 canonical 6 | `sft_dpo_inventory/reviewed_reasoning_v001/` |
| batch006(→ `pg_batch006`) 승인본 | `sft_dpo_inventory/batch006/approved.jsonl` |

바로 채택하지 않을 것:

- P0.2·P0.3 prompt를 최종 계약으로 보는 결정
- partial-grounding이 바꾼 학습 코드 경로(`training/data/build_thinking.py`, `training/data/thinking.py`, `training/trainer_common.py`, `training/inference.py`). 두 arm은 trunk의 학습 코드 하나를 쓴다. Partial에 꼭 필요한 변경만 config 분기로 옮긴다.

수동 reconciliation이 필요한 공통 파일(두 브랜치 모두 수정, 26개 중 핵심):

```text
CLAUDE.md
evaluate_vendor100.py
geoflow/grounding.py
geoflow/planner.py
training/data/build_thinking.py
training/data/thinking.py
training/trainer_common.py
training/inference.py
tests/test_operational_controls.py
sft_dpo_inventory/DECISIONS.md
sft_dpo_inventory/VENDOR100_ACCURACY.md
```

### 4.3 통합 직후 회귀 확인(학습 전 필수)

| 확인 | 기준 |
|---|---|
| Full 학습 경로 | pilot_005 V1 config와 pilot_004 데이터 판으로 dry-run·tokenizer-check 통과. 출처별 손실 token 검사 467/467, teacher 81.8% / 8b 자체 18.2%가 그대로 |
| 실행 의미 | `SEMANTIC_CODE` 지문 `791c4a68`이 그대로. 바뀌면 그 이유를 기록하고 진행 여부를 사용자 결정으로 |
| Full 평가 경로 | selection_v2에서 vLLM-base 셀 1개가 pilot_prep_007 기준값 분포 안 |
| Partial 평가 경로 | P0.3 replay 결과(Full correct → Partial wrong 0, 46 회복)가 같은 코드로 재현. vLLM harness에서 Partial 출력이 compose → validate → compile 뒤 Full과 같은 실행 서명으로 채점됨(smoke 10문항) |

하나라도 실패하면 학습으로 가지 않는다.

### 4.4 Full / Partial은 config로 분리

```yaml
grounding_target: full      # 또는 partial
system_prompt: prompts/<arm>.txt   # arm마다 다르다(표현의 일부)
```

```yaml
# 두 arm 공통(D2·D5 반영)
loss_scope: by_source       # teacher full_response, 8b 자체 json_only
stages: [sft]               # DPO 없음
base_model: Qwen/Qwen3-8B@b968826d
recipe: pilot_005 V1
question_set: same
checkpoint_policy: same
evaluation: PROTOCOL_v5 경로
```

---

## 5. Canonical Gold

### 5.1 정의

source of truth는 질문마다 하나의 canonical 레코드다. 두 층으로 이루어진다.

```text
canonical record
├── execution     : 실행 tool call 열(vendor 형식). 정답의 불변 조건
└── semantics     : measure(text span 포함), conditions(subtype, text span, value, od_role),
                    dimension, dimension_target, bucket/rollup, aggregation, order/limit,
                    vicinity, refusal
```

- `render_full_target(semantics)` → Full SFT target
- `render_partial_target(semantics)` → Partial SFT target

### 5.2 검증 사슬(모든 레코드)

```text
semantics
 → render_full   → normalize → compose → validate → compile ─┐
 → render_partial → completion → compose → validate → compile ─┤ → execution과 같아야 함
                                                               └→ mock execute
```

Full과 Partial이 같은 execution을 만들지 못하면 그 레코드는 학습에 쓰지 않고 목록으로 보고한다.

### 5.3 레코드를 어디서 가져오나

| 출처 | 형태 | 처리 |
|---|---|---|
| `reviewed_gold_v006_t2pc`(trunk) | Full target | parser로 semantics 추출 |
| `reviewed_gold_v006_p0`, `reviewed_reasoning_v001`(partial-grounding) | Partial target | parser + completion으로 semantics 추출 |
| 두 출처에 같은 질문이 있음 | | 두 semantics가 다르면 충돌 목록으로 사람 검토. 임의로 한쪽을 고르지 않음 |
| 300문항(v2) | **execution만 있음** | measure text·조건 span 등 semantics는 Claude 초안 → 사람 검토(결정 45). 초안과 validator PASS는 승인이 아님 |
| batch007, 6.4절 보강 | 초안 | 같은 절차 |

---

## 6. 신규 300문항

### 6.1 v2에서 고친 것(`질문_증강_300문항_추가_v2.xlsx`)

수정한 셀은 노란색이고, 셀 메모에 수정 전 값이 있다. 전체 목록은 `수정_이력` 시트에 있다.

| ID | 문제 | 수정 |
|---|---|---|
| 305 | 질문에 출발지가 없는데 정답과 Factors에는 대구 수성구 출발 조건이 있음 | 질문에 출발지 복원(정답 유지). od_role pickup ≠ dimension_target dropoff 문항이 됨 |
| 306 | 질문에 도착지가 없는데 정답과 Factors에는 부산 수영구 도착 조건이 있음 | 질문에 도착지 복원(정답 유지). od_role dropoff ≠ dimension_target pickup 문항이 됨 |
| 130 | "초량동의 읍면동별"은 읍면동 안을 읍면동으로 나누는 한 행짜리 질문 | 장소를 부산진구로 교체(질문·정답·Factors) |
| SCOPE_NAME 30건 | 단일 `get_scope_name` 호출인데 medium·complex로 표시됨 | 난이도 simple. 전체 비율은 90/120/90 → 120/102/78 |

나머지 297건은 규칙 검사를 통과했다. 검사 항목은 날짜, 시간, 택시 유형, 운행 상태, 순위 방향, limit, 집계, 묶음 단위, 장소명이 질문에 있는지, vicinity 표현과 `include_vicinity`의 일치다.

### 6.2 보호 셋 겹침과 상태

| 상태 | 수 | 기준 |
|---|---:|---|
| `제외` | 5 | selection_v1·selection_v2·valid98·aux_test_v1과 문자 3-gram Jaccard ≥ 0.5. 학습·holdout 모두 쓰지 않음 |
| `보류_vendor100` | 58 | vendor100과 정답 tool call 동일 또는 Jaccard ≥ 0.5. D1이 (b)면 train으로 복귀 |
| `축소` | 22 | SCOPE_NAME 42건은 표현 3종 × scope 14개의 반복. scope당 1문항만 남김 |
| `holdout` | 53 | family 단위 분할 |
| `train` | 162 | family 단위 분할 |

- template 겹침(150건)은 `vendor100 template 겹침` 열에 표시만 했다.
- 같은 tool 공간에서 template 겹침은 피할 수 없으므로 결정 54처럼 기록한다.

### 6.3 분할 방법

- **family:** Semantic Type + tool·인자 키 template + 실행 방식으로 정한다.
  - SCOPE_NAME은 scope 종류로 나눈다.
  - 같은 장소의 vicinity 유무 대조쌍(예: 광안리 / 광안리 주변)은 같은 family로 묶는다.
- **분할 대상:** 보류·제외·축소를 뺀 215문항을 family 단위로 나눈다. holdout 목표는 25%다.
  - 유형, 난이도, hard factor의 holdout 비율이 25%에서 벗어나는 정도를 벌점으로 둔다.
  - 무작위 탐색으로 벌점이 가장 작은 분할을 골랐다(seed는 `메타` 시트).
  - 2문항 이상인 hard factor는 train과 holdout 양쪽에 모두 있다.
- **고정 시점:** 이 분할은 **제안**이다. D1–D6 확정 뒤, 모델 출력을 하나도 보기 전에 holdout 53문항 목록과 sha256을 커밋해 고정한다.
  - 이후 holdout은 학습, prompt 예시, 오류 기반 보강 설계에 쓰지 않는다.
  - 셋 이름은 `augmentation_holdout_v1`이다.

hard factor 분포(v2):

| risk tag | train | holdout | 보류_vendor100 |
|---|---:|---:|---:|
| dt_pickup | 3 | 1 | 1 |
| dt_dropoff | 3 | 1 | 1 |
| dt_both | 12 | 5 | 5 |
| od_both_dt_one | 1 | 1 | 0 |
| occupied_passage | 5 | 2 | 3 |
| vicinity | 12 | 3 | 3 |
| bucket(week+month) | 4 | 3 | 2 |

### 6.4 300문항이 채우지 못하는 것 — 보강 데이터

300문항은 넓은 회귀 방지와 진단에는 좋다. 하지만 두 브랜치가 아직 못 푼 경계는 거의 담고 있지 않다(`보강_필요` 시트).

| 약점 | 300문항 안 | 채울 곳 |
|---|---|---|
| "실차" 없는 occupied 통행량(손님·승객을 태운 택시) | 0건. occupied 10건 모두 "실차"라는 단어 | batch007 27건 검토·승인(결정 104) |
| implicit endpoint 동사형 dt("태운 곳", "내려준 곳") | 0건. dt 단서가 모두 명시적 | partial-grounding reviewed_reasoning_v002 후보(Gap A 동사형). 같은 6문항 반복 대신 새 문항 |
| 순위 없는 dimension_target | 0건. dt 32건 모두 order와 함께 | 신규 작성. "순위 질문이면 dt" 지름길 차단 |
| OD 조건 ≠ dimension_target | 2건(305·306) | `pg_batch006` Gap B 승인분 + 신규 |
| scope 역조회 결합 | 0건 | `pg_batch006` Gap C(b006-44–53, 결정 67로 미승인) 재검토 |
| value 없는 place 대조 | 0건 | 신규 작성. Partial 구조 회귀(MULTIPLE_MEASURES) 대응 |
| bucket ↔ dimension 대조 | bucket 7건(사용 가능) | 같은 지표·기간에서 bucket/dimension만 다른 쌍 신규 |

- 보강 데이터는 6.2절과 같은 겹침 검사를 거친다.
- n33이나 보호 셋 문장에서 파생하지 않는다(결정 104 원칙).
- 300문항의 dt train 예는 18건뿐이다. 그래서 dt 능력의 주 재료는 위 보강분이다.

### 6.5 태그

`risk_tags` 열(자동 산출, 실패 분석에도 그대로 쓴다):

```text
dt_pickup / dt_dropoff / dt_both / od_both_dt_one
occupied_passage / silcha_trip / status_vacant / status_stationary
vicinity / bucket_week / bucket_month
agg_explicit / agg_absent / group_by / ranking / direct_scope / global
```

---

## 7. pilot_006 학습 데이터

```text
pilot_004 데이터 판의 질문 131 (canonical 변환)
∪ reviewed_reasoning_v001의 질문 154 (canonical 변환, 질문 기준 중복 제거)
∪ 300문항 train 162 (+ D1=(b)면 보류 58)
∪ batch007 승인분
∪ 6.4절 보강 승인분
        │
   canonical 검증(5.2) 통과분
        │
   ┌────┴────┐
 Full 렌더   Partial 렌더
```

- 유형 상한(결정 88·92)과 평가 셋 겹침 검사는 지금처럼 적용한다.
- 두 arm의 질문 목록은 sha256까지 같아야 한다.

---

## 8. Trace 정책

### 8.1 teacher trace — 표현에 묶이지 않게

v1처럼 teacher trace 하나에 arm별 JSON만 바꿔 붙이면 문제가 생긴다. trace가 concept·role·id 같은 출력 필드를 언급하면 reasoning과 최종 JSON이 어긋난다. p0_sft_004의 FULL154 오답에서 이미 관찰됐다(t26, n02, h21).

- teacher 지시를 바꾼다. 출력 필드 이름 대신 의미 판단만 적게 한다.
  - 무엇을 세는가(passage vs trip)
  - 어느 끝인가(pickup / dropoff / both)
  - 무엇으로 묶는가(dimension vs bucket)
  - 집계가 질문에 있는가
  - 장소와 주변
- 자동 검사 두 가지를 둔다.
  - (a) trace에 arm 전용 필드 이름이 없다.
  - (b) trace의 결론과 각 arm의 JSON이 일치한다(dt, od_role, measure, aggregation).
- 같은 trace에 Full JSON과 Partial JSON을 붙여 두 arm에 쓴다. 이렇게 해야 teacher reasoning이 두 arm에서 같다.
- 우선 대상: dimension_target, OD endpoint, 실차 통행량 vs trip_count, vicinity, aggregation 유무, bucket vs dimension.

### 8.2 8b 자체 trace

- arm마다 자기 system prompt로 같은 sampling 설정(vLLM BF16, 결정 98 방식)을 써서 따로 모은다.
- 손실 범위는 D2를 따른다.
- 원문은 ignore 경로에 보관한다.

---

## 9. 실험 매트릭스

| 셀 | 모델 | Target | 역할 |
|---|---|---|---|
| R1 | vLLM-base | Full | 기준값(pilot_prep_007 셀 재사용) |
| R2 | vLLM-base | Partial(P0.3) | prompt-only Partial 참고 |
| R3 | pilot_005 v1_step467 | Full | 현재 최선 Full(참고, 데이터가 다름) |
| **F** | **pilot_006 Full** | Full | 학습된 Full control |
| **P** | **pilot_006 Partial** | Partial | 핵심 실험군 |

핵심 비교는 **F vs P**다. R1–R3은 해석을 돕는 참고값이고 판정에 쓰지 않는다.

---

## 10. 학습 recipe (두 arm 동일)

| 항목 | 값 |
|---|---|
| base | Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing |
| LoRA | r16 / α32 / dropout 0.05, 7개 projection |
| 최적화 | AdamW lr 5e-5, warmup 1 step, batch 1, accum 1, max_seq_length 11,392 |
| 길이 | 2 epoch, epoch 1·2 저장(pilot_005 V1과 같음) |
| seed | 사전 등록 때 하나로 고정(두 arm 같게) |
| 손실 범위 | D2 |
| DPO | 없음(D5) |
| GPU | arm마다 1장, 결정 105 규칙 |

다른 것은 target 표현과 그에 딸린 system prompt뿐이다.

---

## 11. 평가와 판정

### 11.1 셋

| 셋 | 역할 |
|---|---|
| selection_v2(98) | 주 판정. PROTOCOL_v5 경로, k=4(D4에 따라 k=8) |
| augmentation_holdout_v1(53) | 진단. risk tag별 표. D4에서 정하면 주 셋에 합침 |
| valid98, aux_test_v1 | 보조 |
| selection_v2 n33 포함/제외 | 결정 104대로 둘 다 보고(batch007로 학습하는 경우) |
| 최종 셋(D1) | 아래 12절 |

### 11.2 arm별 선행 조건(PROTOCOL_v5 그대로)

각 arm은 체크포인트 2개 중 하나를 고르고 vLLM-base와 비교한다.

- 정답률 차이의 97.5% CI(Bonferroni m=2, 1 − 0.05/2, 20,000회) 하한 > 0
- U 비율 차이의 95% CI 하한 ≤ 0

F가 이 조건을 통과하지 못하면 F vs P 비교는 해석하지 않고 보고만 한다.

### 11.3 F vs P gate (모두 문항 단위 쌍 bootstrap, 같은 표본)

| Gate | 지표 | 통과 조건 |
|---|---|---|
| A 의미 비열등 | grounding_ok | P − F 차이의 95% CI 하한 ≥ −M (M은 D4) |
| B dimension_target | dt_missing 비율 | P − F 차이의 95% CI 하한 ≤ 0(증가가 확인되지 않음) |
| C 조용한 오답 | answered_wrong 비율 | P − F 차이의 95% CI 하한 ≤ 0 |
| D 구조 | first-response 구조 오류(MULTIPLE_MEASURES, NO_MEASURE, INVALID_*, JSON_NOT_FOUND), grounding failure, repair 호출 비율 | (1) MULTIPLE_MEASURES + NO_MEASURE: P − F의 95% CI 하한 ≤ 0, **그리고** (2) 셋 중 하나 이상에서 P − F의 95% CI 상한 < 0(개선 확인) |
| E 효율 | 최종 JSON token 중앙값, 전체 생성 token, wall p50 | JSON token 30% 이상 감소, 전체 생성 token과 wall p50은 F 대비 +10% 이내 |

- **채택 조건:** A–E 모두 통과일 때만 Partial을 채택 후보로 본다. JSON token 감소만으로 채택하지 않는다.
- **D4 결과:** CI 반폭이 M보다 크게 나오면 Gate A 불통과는 "열등"이 아니라 "판정 불가"로 보고한다.

### 11.4 함께 보고할 것(판정에 쓰지 않음)

- 의미 실패 유형:
  - dt omission / wrong endpoint, od_role ↔ dt 혼동
  - occupied passage 오독(실차 표현, n33 따로)
  - vicinity·place 누락, aggregation added/missing, bucket/dimension 혼동
- 부분집합: implicit endpoint, od≠dt, scope 역조회, value 없는 place
- thinking: 방출률, 길이 p50/p90(D2 감시), reasoning–final 충돌 표본 검토
- augmentation_holdout_v1 risk tag별 표(각 n이 작으므로 수만 보고)

---

## 12. 최종 판정 셋

- **D1 = (a):** 채택 후보 하나만 vendor100으로 판정한다(PROTOCOL_v5 5절). Partial 쪽이 개발 중 vendor100을 본 사실을 함께 적는다.
- **D1 = (b):** 채택 후보 하나만 `protected_final_v1`로 판정한다. vendor100은 개발 셋 결과로 함께 보고한다.

어느 쪽이든 최종 셋은 iteration마다 보지 않는다. F와 P 중 하나가 정해진 뒤 한 번만 쓴다.

---

## 13. 실행 순서

| # | 작업 | 산출물 | 넘어가는 조건 |
|---|---|---|---|
| 0 | D1–D6 결정 기록 | `DECISIONS.md` | 사용자 결정 |
| 1 | partial-grounding 이름 공간 정리 | 커밋(pg_ 접두어) | 참조 깨짐 0 |
| 2 | 실험 브랜치, 선택 이식, 수동 reconciliation | 커밋 목록 | 테스트 통과 |
| 3 | 통합 회귀 확인(4.3) | `pilot_006/integration_check.json` | 네 항목 모두 통과 |
| 4 | canonical 계층과 기존 데이터 변환 | `canonical/`, 충돌 목록 | 충돌 해소, 5.2 통과 |
| 5 | 300문항 v2 semantics 초안·검토, holdout 고정 | `canonical/augmentation_300.jsonl`, holdout sha256 | 모델 출력 보기 전 커밋 |
| 6 | batch007·6.4절 보강 초안·검토 | 각 batch README | 승인 |
| 7 | teacher trace(8.1)와 8b 자체 trace(8.2) | trace manifest, 자동 검사 결과 | 검사 통과 |
| 8 | arm별 데이터 판 생성 | `pilot_006/{full,partial}/data/` | 질문 목록 sha256 일치, 손실 token 검사, 겹침 검사 |
| 9 | 사전 등록 | `pilot_006/PLAN.md` | 학습 시작 전 고정, D4 마진 포함 |
| 10 | 두 arm 학습(GPU 2장 동시) | train_logs | 장애 시 결정 105 |
| 11 | 체크포인트 선택, 선행 조건, Gate A–E | `pilot_006/selection.json`, 표 | |
| 12 | 보고 | `pilot_006/REPORT.md` | |
| 13 | 채택 후보가 있으면 최종 판정(12절) | | |
| 14 | 성공 시 partial-grounding 코드 정식 통합, 실패 시 P0.x는 평가 기록으로 보존 | | |

---

## 14. Repository 구조

```text
sft_dpo_inventory/
├── canonical/
│   ├── README.md
│   ├── conflicts.json
│   ├── augmentation_300.jsonl        # v2, 상태·family·risk_tags 포함
│   ├── train_162.jsonl
│   ├── holdout_53.jsonl              # 고정 후 sha256 기록
│   └── held_vendor100_58.jsonl
├── pg_batch006/                      # partial-grounding batch006 이식본
├── batch007/
├── pilot_006/
│   ├── PLAN.md
│   ├── integration_check.json
│   ├── full/{data,config.yaml,train_logs,results}/
│   ├── partial/{data,config.yaml,train_logs,results}/
│   └── REPORT.md
└── evaluation/
    └── augmentation_holdout_v1/

grounding/
├── canonical.py
├── full_renderer.py
├── partial_renderer.py
├── completion.py
└── validation.py      # 5.2 검증 사슬
```

---

## 15. 위험과 한계

1. **dt 학습 재료가 300문항 안에서는 적다**(train 18건). 보강분이 늦어지면 Gate B의 해석이 약해진다.
2. **holdout 53문항은 작다.** risk tag별 n이 1–5라 진단용으로만 쓴다.
3. **두 arm은 system prompt도 다르다.** 이것은 표현의 일부로 보고 분리하지 않는다. 보고서에 명시한다.
4. **Partial 구조 회귀의 원인은 아직 확정되지 않았다**(p0_sft_004 21절). 보강 데이터가 막지 못하면 Gate D에서 걸린다. 그 경우 실패가 아니라 원인 진단 결과로 보고한다.
5. **D1 = (a)를 고르면** Full/Partial 최종 판정에 vendor100을 미리 본 쪽(Partial)의 낙관 편향이 남는다.

---

## 16. 최종 권고

1. D1–D6을 먼저 정한다. 특히 vendor100의 지위(D1)와 8b 자체 trace 손실 범위(D2)다.
2. 이름 공간을 정리한 뒤 이식하고, 학습 전에 Full arm 재현을 확인한다.
3. 300문항은 v2(수정 3건, 상태·family·risk tag 부여)를 쓰고 holdout 53을 모델 출력 전에 고정한다.
4. 약점 보강은 300문항이 아니라 batch007, implicit endpoint 동사형, scope 역조회, value 없는 place 대조로 채운다.
5. pilot_005 V1 recipe로 Full과 Partial 두 arm을 SFT만으로 학습한다.
6. PROTOCOL_v5 통계 규칙과 사전 고정 마진으로 Gate A–E를 판정한다. Partial은 의미 비열등, dt·조용한 오답 비악화, 구조 개선, 효율 개선을 모두 만족할 때만 채택 후보가 된다.

가장 중요한 질문:

> **"Partial을 학습시키면 되는가?"가 아니라, "pilot_005 수준의 학습에서 Partial 출력 계약이 구조 회귀 없이 Full과 같은 의미 정확도를 내면서 구조 오류와 생성 비용을 줄이는가?"**
