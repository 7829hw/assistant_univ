# thor 학습 패키지의 T2PC 적용 (geoflow/sft-dpo-t2pc)

출처: `geoflow/sft-dpo-thor` b3149040fb0fc57bedd1e8ff4436333f55d41e5a. 경로 단위로 가져왔다(`git checkout <SHA> -- <경로>`).
merge·rebase·cherry-pick은 하지 않았다. 기준: prompt 87048d0c, 조건 계층 켬, 실행 의미 코드 지문 `791c4a68…`
(`sft_dpo_inventory/batch004/BASELINE.md`).

## 가져온 경로

- `training/` 코드 전부: `__init__.py`, `data/`, `annotations/`, `configs/`, trainer·추론·평가·pilot·profiling 모듈,
  `requirements*.txt`, 문서(`README.md`, `ARCHITECTURE.md`, `VALIDATION.md`, `THOR*.md`, `PILOT*.md`).
- `training/records/corpora/` (reviewed gold v001–v003: annotation, decision, manifest, `dataset_index.json`, assembly recipe).
- `training/records/reviews/review_batch_001`–`003` (검토 근거. v003 assembly recipe와 테스트가 읽는다).
- `training/records/validation/thor_v003_token_smoke_002`, `training/records/README.md`, `COMMIT_VALIDATION.md`,
  `snapshot_manifest.json`, `.gitattributes`.
- 테스트 `tests/test_training_*.py` 10개.
- `.gitignore`의 학습 산출물 규칙(`training/generated/`, `checkpoints/`, `runs/`, `experiments/`, `annotations/generated/`).

## 가져오지 않은 경로

| 경로 | 이유 |
|---|---|
| `geoflow/aggregation.py`의 `to_flat` | production(SEMANTIC_CODE) 파일. 같은 정의를 `training/data/aggregation_flat.py`에 둔다 |
| `evaluate_planner.py`(thor 판) | production 파일. thor 판 전체를 `training/thor_evaluate_planner.py`로 두고 training 코드만 이것을 쓴다 |
| `AGENTS.md` | thor 브랜치의 작업 규칙. 이 브랜치는 `CLAUDE.md`를 따른다 |
| `training/records/pilots/` (43 files, 1.7MB) | pilot 001/002 실험 기록. 재구성에 필요 없다. snapshot hash 검사는 이 경로를 "없음"으로 확인한다 |
| `training/evaluations/vendor_100_baseline_001/` | 업체 100 평가 기록(보호 질문 포함). 학습·재구성에 쓰지 않는다 |

## 현재 조건에 맞춘 수정

- **prompt 기대값.** `training/data/common.py`의 `EXPECTED_PROMPT_SHA256 = 87048d0c…`와 `check_expected_prompt()`를 추가했다.
  - SFT·DPO builder와 trainer `load_records`가 이 값을 확인한다. thor 코드는 실행 시점 prompt hash만 manifest와 비교했다.
- **조건 계층을 거치는 판정.** `training/data/validation.py`의 `assess_t2pc`·`t2pc_chosen_ok`를 추가했다.
  - 흐름: stub client로 운영 planner(condition_check 켬) → compose → validate(mock Tool) → compile(mock·legacy) 기록.
  - thor의 `assess`·`chosen_ok`는 비교용으로 그대로 둔다. trainer의 입력 검사도 thor 판정을 그대로 쓴다.
- **v003 재구성.** `training/data/retarget_prompt.py`를 추가했다.
  - archive의 prompt marker만 현재 prompt로 바꾸고, 라벨·split·metadata는 그대로 둔다.
  - T2PC 판정 표시는 `review_flags.json`에 둔다.
- **token 한도.** `training/configs/qwen3_8b_t2pc_v003_{sft,dpo}.yaml`을 추가했다.
  - 값: SFT 7552, DPO total 7552 / prompt 7424 / completion 256(실측 최소 7519 / 7520 / 7331 / 188 이상).
  - `safety.unified_memory: false`(GPU 2 RTX 6000 Ada). thor 원래 config는 바꾸지 않았다.
  - 이 profile로 학습·memory smoke를 하지 않았다.
- **import 경로.** `training/pilot.py`, `pilot_report.py`, `evaluate_checkpoint.py`, `tests/test_training_evaluation.py`, `tests/test_training_pilot.py`.
  - `evaluate_planner` 대신 `training.thor_evaluate_planner`를 import한다.
  - `pilot.py`의 evaluator hash도 그 파일로 바꿨다.
- **테스트 조정.** thor 시점의 상태를 확인하던 검사만 바꿨다.
  - `test_training_reviewed_gold_v003.py`:
    - archive를 현재 prompt로 재구성한 레코드가 archive와 prompt만 다른지 확인한다.
    - 원래 복원은 `Production prompt drift`로 멈추는지 확인한다.
    - thor 시점 production 파일 hash는 thor commit 내용과 대조한다.
    - thor 장비의 ignored config 경로는 커밋된 사본으로 대조한다.
  - `test_training_review_decisions_003.py`: 가져오지 않은 `pilots/` snapshot은 없는 것을 확인한다.
- **새 테스트.** `tests/test_training_t2pc.py`.
