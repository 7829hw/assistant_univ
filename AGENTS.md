# 작업 브랜치와 커밋 정책

- 현재 SFT/DPO·Thor·annotation 후속 작업은 `geoflow/sft-dpo-thor`에서 진행한다.
- 사용자가 다른 브랜치를 명시하지 않는 한 `geoflow/dev-v2`에는 커밋하지 않는다.
- 작업 단위가 끝나면 테스트/검증 → diff 및 staged diff 확인 → 논리적인 커밋 → SHA 보고 순서로 처리한다. 별도의 커밋 요청을 기다리지 않는다.
- Push, merge/rebase, 기존 history rewrite는 별도 사용자 요청 없이 수행하지 않는다.
- Model/adapter weights, checkpoints, caches, temporary files, ignore 대상 산출물을 커밋하지 않는다. `git add -f`로 ignore 규칙을 우회하지 않는다.
- Production의 책임 경계를 유지한다: LLM은 question → grounding JSON까지만 생성하며 이후 graph composition, validation, compilation, execution은 deterministic pipeline이 담당한다.
- Annotation 추천과 validator PASS를 human approval로 간주하지 않는다. 기존 보호된 dev/validation/diagnostic 데이터를 training으로 이동하지 않는다.
- GPU 학습이나 시스템 설정 변경은 해당 작업의 사용자 승인 범위를 확인한 뒤 실행한다.
