# 학습 데이터 기반 준비: thor 패키지 이식, v003_t2pc, batch004 후보와 검토 시트

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`. 학습, `ollama create`, prompt 변경, SEMANTIC_CODE 변경은 없다.
승인된 corpus에는 아무것도 추가하지 않았다.

## 0. 요약

- **이식.** thor 학습 패키지를 경로 단위로 가져와 현재 조건(prompt 87048d0c, 조건 계층 켬)에 맞췄다.
  - 가져온 테스트를 포함한 전체 테스트가 통과한다.
  - 실행 의미 코드 지문은 작업 시작과 끝 모두 `791c4a68…`이다.
- **v003_t2pc.** 라벨을 바꾸지 않고 학습 입력만 새 prompt로 다시 만들었다(SFT 35, DPO 32).
  - inventory가 찾은 항목은 표시만 했다: compile 정지 SFT 17, rejected=chosen DPO 3, 실행 가능해지는 constraint DPO 1.
- **batch004 후보.** 41개를 새로 썼고, thor 보호 검사가 23개를 semantic family 겹침으로 뺐다.
  - **taxi_status 후보는 하나도 남지 않았다.** thor family 기준이 taxi_status·time·날짜·장소를 무시하기 때문이다(3.2절).
  - 남은 18개 중 4개는 현재 코드에서 멈추는 질문이라 지원 불가 target 형식 결정을 기다린다.
- **HF 출력.** base 모델의 첫 응답은 18개 중 15개가 초안과 달랐다. 조건 계층을 적용하면 그중 4개는 같아진다.
- **검토량.** 55항목: batch004 gold 18 + 모델 출력 쌍 15 + v003 표시 21 + 결정 요청 1.

## 1. 기준값

| 항목 | 값 |
|---|---|
| merge | `origin/geoflow/dev-v2`(7efccbd, 조건 개념 정리 예외 수정)를 merge(`4c9419b`), 충돌 없음 |
| 작업 시작 지문 | `791c4a68a59647131321e3efad2325e549a46bc522230b25b2954a88c42eac6e`(64 files, `BASELINE.md`) |
| 작업 끝 지문 | `791c4a68a59647131321e3efad2325e549a46bc522230b25b2954a88c42eac6e`(같음) |
| prompt | `87048d0c…`(`training.data.common.EXPECTED_PROMPT_SHA256`) |
| 기준일 | 2026-09-25(평가 harness와 같음. 후보의 상대 날짜와 조건 계층·compile에 쓴다) |

## 2. thor 학습 패키지 이식

경로 목록과 수정 내용은 `training/PORTING.md`에 있다.

- **가져온 것:**
  - `training/` 코드·configs·문서.
  - `training/records/corpora`(v001–v003), `records/reviews`(001–003), `records/validation`.
  - 테스트 10개, 학습 산출물 ignore 규칙.
- **가져오지 않은 것:**
  - `training/records/pilots/`(1.7MB, 재구성에 불필요).
  - `training/evaluations/vendor_100_baseline_001/`(보호 질문 포함).
  - production 파일(`geoflow/aggregation.py`의 `to_flat`, thor 판 `evaluate_planner.py`)과 `AGENTS.md`.
- **production에 기대던 기능:**
  - `to_flat` → `training/data/aggregation_flat.py`.
  - thor 판 `evaluate_planner` → `training/thor_evaluate_planner.py`(training 코드만 import).
  - 그래서 지문이 바뀌지 않았다.
- **현재 조건에 맞춘 수정:**
  - prompt 기대값 87048d0c를 builder와 trainer가 확인한다.
  - `assess_t2pc`(조건 계층을 거치는 판정)를 추가했다. thor `assess`는 비교용으로 남겼다.
  - `retarget_prompt`(archive 재구성)를 추가했다.
  - token 한도 config를 추가했다: SFT 7552, DPO 7552 / prompt 7424 / completion 256.
- **테스트:** 전체 통과(skip 2는 opt-in GPU 테스트로 thor와 같다).
  - thor 시점의 상태를 확인하던 검사 2개만 조정했다(prompt drift 거부 확인, thor commit 대조, pilots 제외 확인).
  - 새 테스트 10개는 `tests/test_training_t2pc.py`에 있다.

## 3. reviewed_gold_v003_t2pc

| 항목 | 값 |
|---|---|
| 규모 | SFT train 19 / valid 16, DPO train 18 / valid 14(semantic 21, constraint 11) |
| split | thor seed 42 배정과 family 그대로(라벨·split·metadata는 archive와 바이트 단위로 같음, 테스트로 확인) |
| token(Qwen3-8B@b968826d) | SFT total 최대 7519, DPO total 최대 7520, prompt 최대 7331. dry-run·tokenizer check 통과 |
| thor 판정 재현 | SFT 35/35, DPO chosen 32/32, rejected 32/32 |
| 생성물(ignored) | `training/generated/reviewed_gold_v003_t2pc/`. hash는 `training/records/corpora/reviewed_gold_v003_t2pc/build_receipt.json` |

표시만 하고 빼거나 고치지 않은 항목(`review_flags.json`, 검토 시트 v003_flags):
- SFT 17건: T2PC 경로의 compile에서 멈춘다(`UNVERIFIED_TIMS_CONTRACT`, 주·월 구간 + rollup).
- DPO 3쌍: 조건 계층을 거치면 rejected가 chosen과 같아진다.
- DPO 1쌍: constraint rejected가 T2PC 경로에서 계약을 통과해 실행된다.
- 참고: chosen이 compile에서 멈추는 DPO 쌍은 12개다. 위 SFT 17건과 같은 gold를 쓴다.

## 4. batch004 후보

- 초안: `candidates_draft.yaml`. 결과: `candidates_checked.json`. 제외 목록: `excluded.json`.
- 질문은 Claude가 새로 썼다. 보호된 셋을 보거나 바꿔 쓰지 않았고, D1–D4 유형은 만들지 않았다.

### 4.1 유형별 후보 수

| 유형 | 작성 | thor 보호 검사로 제외 | 남음 | 남은 것 중 현재 코드에서 멈춤 |
|---|---:|---:|---:|---:|
| passage_count | 6 | 4 | 2 | 0 |
| taxi_status | 6 | **6** | **0** | – |
| time | 5 | 4 | 1 | 0 |
| dimension_target | 7 | 0 | 7 | 0 |
| no_aggregation_word | 5 | 3 | 2 | 0 |
| dimension_unit | 6 | 2 | 4 | 2(b004-34/35, 장소 없는 요일별 속도: `MISSING_REQUIRED_INPUT`) |
| vacant_ratio | 6 | 4 | 2 | 2(b004-40/41, 시군구별 공차율: `UNCONSUMED_CONDITION`) |
| **합계** | **41** | **23** | **18**(family 9, intent 12) | **4** |

- **제외 이유.** 23개 모두 `protected_semantic_family`이고, 그중 2개(b004-01/02)는 `protected_semantic_template`이기도 하다. 정규화 질문이나 id 겹침은 없다.
- **정지 후보 4건**은 사실상 T2PC식 정지 target이다. 이번에는 만들지 않기로 한 유형이 결과로 생긴 것이다.
  - 지우지 않고 `training_blockers: unsupported_target_format_undecided`로 import에서 빠지게 했다.
- **확장 대조(정보, 제외 안 함).** 남은 18개 중 template 11개, family 13개가 vendor 형식 평가 셋의 역산 grounding과 같다.
  - thor 정책은 이 범위를 보지 않는다. 보호 범위 결정은 inventory 7절 2번 그대로 남아 있다.

### 4.2 thor family 보호와 공백 유형

- **thor `family_key`가 보는 것과 보지 않는 것.** 측정값, OD 역할, 집계·그룹·순위 factor만 본다. taxi_status, time, date, 장소, taxi_type은 보지 않는다.
- **그 결과.** taxi_status나 time만 다른 질문은, 보호 셋에 같은 측정값·집계 구조의 문항이 하나라도 있으면 같은 family로 막힌다.
  - 이번에 taxi_status 6/6, time 4/5가 막혔다.
- **문장을 바꿔도 피할 수 없다.** 피하려면 측정값·집계 구조를 보호 셋에 없는 조합으로 바꿔야 한다. 그것은 공백 유형을 채우는 것이 아니라 검사를 피하는 것이므로 하지 않았다.
- **사람이 정할 것.** family 기준에 조건 factor를 넣을지(보호를 좁힘), 지금 기준을 유지하고 이 유형을 비워 둘지.

### 4.3 한계

- 문장은 Claude가 썼다. 같은 모델 계열이 쓴 기존 합성 평가 셋(grounding_v1–v12)과 표현 습관이 비슷할 수 있다.
  - 정규화 중복과 family 검사는 이런 문체 유사성을 잡지 못한다.
- 장소는 실제 지명에 상위 지역을 붙였다. 실제 TIMS 자료에서 조회되는지는 확인하지 않았다(mock·legacy compile까지만).
- 초안 gold는 승인이 아니다. validator·compile 통과는 형식 검사다.

## 5. HF 출력(GPU 2)

- **수집 조건.** 시작 전에 UUID를 확인했다(`gpu_uuid_check.txt`). Ollama는 `GPU-48f798cc`(host 3), torch `cuda:0`은 `GPU-a644de12`(host 2)였고, GPU 2 사용량은 2 MiB였다.
- **모델과 생성 설정.**
  - 모델: Qwen/Qwen3-8B@b968826d(base, adapter 없음), BF16, SDPA.
  - 입력: prompt 87048d0c, `enable_thinking=False`.
  - 생성: greedy, max_new_tokens 1024, seed 42. peak 메모리 약 18.3GB.
- **결과.** `hf_outputs.json`(첫 응답 원문 포함). 18개 중 초안과 같음 3, 다름 15.

| 유형 | 대상 | 다름 | 조건 계층 적용 뒤에도 다름 |
|---|---:|---:|---:|
| dimension_target | 7 | 4 | 3 |
| dimension_unit | 4 | 4 | 3 |
| passage_count | 2 | 2 | 2 |
| no_aggregation_word | 2 | 2 | 2 |
| vacant_ratio | 2 | 2 | 0 |
| time | 1 | 1 | 1 |
| **합계** | **18** | **15** | **11** |

- **첫 응답 기준 차이 태그**(문항 중복 집계):
  - factor_date 9, place_or_od_role 6, factor_aggregation_spec 4, factor_dimension 2, factor_vicinity 2, factor_limit 1, factor_order 1.
- **조건 계층 적용 뒤에 남는 차이:**
  - places 6: od_role 누락·추가, 장소명이 "읍면동"·"시군구" 같은 단위 말이나 null.
  - aggregation_spec 4: 질문에 없는 집계·bucket.
  - dimension 2, vicinity 2, limit 1, order 1.
- 날짜 차이는 모두 조건 계층이 질문 표현으로 고친다.
- **다른 15개는 DPO rejected 후보로만 두었다.** 초안과 모델 중 어느 쪽이 맞는지를 검토 항목으로 표시했다. 어떤 corpus에도 넣지 않았다.

## 6. 검토 시트와 다음 단계

- **위치.** `sft_dpo_inventory/batch004/review/`.
  - `review_queue.jsonl`(thor workflow queue 33행), `manifest.json`, `v003_flag_items.jsonl`, `decision_requests.jsonl`, `README.md`(한국어 안내·판단 기준·가져오기 명령).
  - `batch004_review.xlsx`는 저장소의 `*.xlsx` ignore 규칙과 thor 관례에 따라 커밋하지 않았다.
    - 현재 로컬 파일 sha256은 `813254c84740594d298e3719821d910878766d44c7ab3692641a5332c96fc010`이다.
    - zip 시각이 들어가 다시 만들 때마다 바뀐다. `build_review.py --xlsx-only`로 다시 만든다.
- **thor workflow 연결 확인.**
  - `load_queue`를 통과했다.
  - 결정 없는 `import-reviewed`는 보호·출처·prompt 확인을 지난 뒤 "No reviewed … annotations"로 거부했고, 출력은 생기지 않았다.
- **예상 검토량:** 55항목.
  - batch004 gold 18: 질문·grounding 1쌍씩.
  - 모델 출력 쌍 15: 초안과 모델 비교.
  - v003 표시 21: 처분 선택.
  - 결정 요청 1.
- **검토가 끝난 뒤의 선택지**(필요 자료와 비용만. 효과는 추정하지 않는다):

| 선택지 | 필요한 것 | 비용 |
|---|---|---|
| (1) SFT pilot: v003_t2pc + batch004 승인분 | 검토 결정, import(`reviewed_gold_v004_candidate`), v003 표시 처분 반영 방식, 학습 profile(단계·LR) 확정, GPU 2 memory smoke(7552 한도 미검증) | 자료 최대 SFT 35 + 14(answer gold) / DPO 32 + 15. 평가 셀: Ollama F(qwen3:8b, think off, 기준 57)와 같은 조건의 학습 모델 셀(GGUF 변환·Ollama 등록·template 일치 확인 필요), HF 87048d0c Base 셀(새로 재야 함) |
| (2) 보호 범위 결정 후 batch005 | family 기준에 조건 factor를 넣을지, vendor 형식 셋 family 보호를 넓힐지 결정 | taxi_status·time 후보 재작성과 검토(유형당 수십 항목) |
| (3) 지원 불가 target 형식 결정 후 정지 target 추가 | 결정 요청의 답 | batch004 정지 후보 4건 재분류, registry unsupported 54 intent 재라벨 여부 검토 |
| (4) 학습 보류 | 없음 | 없음 |

## 7. 생성물과 커밋

- **커밋:** `training/` 이식분과 records, `tests/test_training_*`, `sft_dpo_inventory/batch004/`(초안, 결과, 제외 목록, HF 출력, review queue·manifest·안내).
- **커밋하지 않음(ignored):**
  - `training/generated/reviewed_gold_v003_t2pc/`(JSONL·학습 manifest·보호 이력 사본).
  - `batch004_review.xlsx`.
  - 저장소 밖 HF venv·model cache(`/home/hwkim/sftdpo_work`).
