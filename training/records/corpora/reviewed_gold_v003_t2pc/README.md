# reviewed_gold_v003_t2pc

reviewed_gold_v003(thor, prompt 522aa3b1)의 학습 입력만 현재 prompt 87048d0c로 바꾼 판이다.
- 라벨·split·family·metadata는 archive와 바이트 단위로 같다(`tests/test_training_reviewed_gold_v003.py`가 확인).
- 새 승인은 없다. 레코드를 빼거나 고치지 않았다.

- 재구성(CPU, 모델 호출 없음):
  ```bash
  python -m training.data.retarget_prompt --archive training/records/corpora/reviewed_gold_v003 \
    --version reviewed_gold_v003_t2pc --output training/generated/reviewed_gold_v003_t2pc \
    --records training/records/corpora/reviewed_gold_v003_t2pc
  ```
  JSONL·학습용 manifest는 `training/generated/`(ignored)에 생긴다. 이 디렉터리에는 manifest 사본, `review_flags.json`,
  `build_receipt.json`(출력 hash), token 길이(`token_lengths_{sft,dpo}.json`)를 커밋한다.
- 규모: SFT train 19 / valid 16, DPO train 18 / valid 14(semantic 21, constraint 11). split은 thor seed 42 배정 그대로다.
- token(Qwen/Qwen3-8B@b968826d, enable_thinking=False):
  - SFT total 최대 7519.
  - DPO total 최대 7520, prompt 최대 7331.
  - `training/configs/qwen3_8b_t2pc_v003_*.yaml`의 dry-run과 tokenizer check는 통과했다.
- **표시(`review_flags.json`)는 처분이 아니다.** 아래 항목은 사람 검토로 넘긴다(batch004 검토 시트).
  - SFT 17건: T2PC 경로의 compile에서 멈춘다(`UNVERIFIED_TIMS_CONTRACT`, 주·월 구간 + rollup). grounding 계약은 통과한다.
  - DPO 3쌍: 조건 계층을 거치면 rejected가 chosen과 같아진다(`t2pc_rejected_equals_chosen`).
  - DPO 1쌍: constraint rejected가 T2PC 경로에서 계약을 통과한다(`t2pc_constraint_rejected_passes_contract`). 운영에서는 실행된다.
