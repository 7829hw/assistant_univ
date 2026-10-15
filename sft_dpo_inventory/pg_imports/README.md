# pg_imports — `geoflow/partial-grounding` 자산 이식본(결정 111)

작성: 2026-10-15(pilot_006 준비 W3). 원본 브랜치·커밋: `geoflow/partial-grounding` **`ab9d215`**. partial-grounding에는 커밋하지 않았고 `git show`로만 꺼냈다.

- **승인 상태를 그대로 옮겨 온 것이고 새 승인이 아니다.** 이 디렉터리의 어떤 레코드도 trunk의 승인된 corpus에 넣지 않았다.
- partial-grounding의 수치(replay, ab_p0*, p0_sft_*)는 다른 장비(RTX PRO 6000 Blackwell, torch 2.11)와 HF greedy·Ollama 경로에서 나왔다. **참고값이다**(지시 1·3절).
- 이름 바꿈(결정 111): batch `pg_batch006`, id `pg-b006-NN`(원래 `b006-NN`, `orig_id`에 남김). 결정 참조는 **`PG-57`–`PG-87`**:
  partial-grounding 결정 57–87은 trunk 결정 57–87과 번호가 모두 겹친다(지시 D6은 81–87만 적었다). 원문은 `ab9d215:sft_dpo_inventory/DECISIONS.md`.
- `pg_batch006/approved.jsonl` 43행(Gap A 26, B 17)의 `review_decision`: APPROVE 33, EDIT_REQUIRED 7, APPROVE_WITHOUT_MOCK 3. 값은 원본 그대로다.
  Gap C(원 b006-44–53)는 PG-67로 미승인이라 승인본에 없다.

## 파일(원본과 sha256 비교, 27개 모두 같음)

| 파일 | 크기 | sha256 | 원본 경로(ab9d215) | 원본과 |
|---|---:|---|---|---|
| `pg_batch006/approved.jsonl` | 54,584 | `d1899344e210840665fc87422657b83f47b41874c3cdc118b36da19e4c27289e` | `(이름 바꾼 사본: orig_approved.jsonl의 id b006-NN → pg-b006-NN)` |  |
| `pg_batch006/orig_approved.jsonl` | 46,629 | `8540c321497dbe85cab7edbe7e540b132ca0df995e4714cc1f45f14bc9886894` | `sft_dpo_inventory/batch006/approved.jsonl` | 같음 |
| `pg_batch006/orig_candidates_draft.yaml` | 37,941 | `125b1c85bf03fd3897e56a0b79ddf04e31fa3b27c7bfbdc444fec346ab958e95` | `sft_dpo_inventory/batch006/candidates_draft.yaml` | 같음 |
| `pg_batch006/orig_review_decisions.json` | 18,174 | `6ce28bad9edef8b171d06533a6c5e362806f125717aae39985cd7f5528dbad0b` | `sft_dpo_inventory/batch006/review_decisions.json` | 같음 |
| `prompts/partial_p0.yaml` | 25,122 | `b024e07954c6b3d4b76274b6afa7f83814671d44c7e59e711636020423425922` | `evaluation/partial_grounding/prompts/partial_p0.yaml` | 같음 |
| `prompts/partial_p0_1.yaml` | 28,941 | `6ab87b1a807cb499585f6a9fdd3615c000d134b778c67a666d9978ed53f087d2` | `evaluation/partial_grounding/prompts/partial_p0_1.yaml` | 같음 |
| `prompts/partial_p0_2.yaml` | 31,716 | `9a314dfe95173a6d2795f2bccb131f12c1c26600d32241a87fe006c93e45e9ab` | `evaluation/partial_grounding/prompts/partial_p0_2.yaml` | 같음 |
| `prompts/partial_p0_3.yaml` | 35,007 | `596634843af7c4d00b05a9d65a864cbb3e1215f7d3ce45ee390615bef5220b10` | `evaluation/partial_grounding/prompts/partial_p0_3.yaml` | 같음 |
| `replay/analysis.txt` | 9,694 | `f3ec24ef46efce888c59da05c51979d776793a09cbb10c8f817ca11db7b1c796` | `evaluation/partial_grounding/analysis.txt` | 같음 |
| `replay/regression_event_refusal.yaml` | 4,037 | `28e088b6515e13a674c3a92cc835ebd7de5bc5016256f96f497ad002db76fccb` | `evaluation/partial_grounding/regression_event_refusal.yaml` | 같음 |
| `replay/replay_log.txt` | 16,028 | `7d8e7f29dc4480cc591fdb16f331ca1d44e4a99d94561549fa20a58c7ab0d15f` | `evaluation/partial_grounding/replay_log.txt` | 같음 |
| `replay/replay_result.json` | 4,359,225 | `7ccb87f33167c99b867ea2c4afbfe420722496a290b1615f4890f82983c775ea` | `evaluation/partial_grounding/replay_result.json` | 같음 |
| `reports/batch006_REPORT.md` | 7,401 | `12622df418507c0283ba631b8e047259116ef601d9a0a3df18912dc0163a5dbd` | `sft_dpo_inventory/batch006/REPORT.md` | 같음 |
| `reports/p0_sft_004_REPORT.md` | 18,377 | `d871febf4097b8f70e0c7a119dec511f11fd6ad63304495101a28a6fd254c54c` | `sft_dpo_inventory/p0_sft_004/REPORT.md` | 같음 |
| `reports/partial_grounding_README.md` | 6,073 | `d5126c03a72cea51f9b8e47738aacc76bcf2fdfb2cddbc9bc01409dcc8a87eb4` | `evaluation/partial_grounding/README.md` | 같음 |
| `reviewed_gold_v006_p0/manifest.json` | 1,182 | `da2370ca30ae043b40c15c744fb170bd5f41e7589c0c5067aba025557441f477` | `training/generated/reviewed_gold_v006_p0/manifest.json` | 같음 |
| `reviewed_gold_v006_p0/sft_train.jsonl` | 3,994,998 | `e792ee5e5093bd57c234cb982f4a558d4ed0a109b2666ccb9350b7eb38bb2b41` | `training/generated/reviewed_gold_v006_p0/sft_train.jsonl` | 같음 |
| `reviewed_reasoning_v001/REPORT.md` | 3,850 | `000e2d82bd2ae2f447c66ab540d62da72ced3b9bd2ef6cf34e44e3cce6acc0bc` | `sft_dpo_inventory/reviewed_reasoning_v001/REPORT.md` | 같음 |
| `reviewed_reasoning_v001/build_canonical.py` | 3,301 | `0c8d15240060d0c0d96043d6d7edeea9cd3a4ec23295be34bebf1aa28967d037` | `sft_dpo_inventory/reviewed_reasoning_v001/build_canonical.py` | 같음 |
| `reviewed_reasoning_v001/build_dataset.py` | 15,767 | `4e821edfe6b2cd14d11149250617158cd95729ac1bac6a21719fa808885ba9f1` | `sft_dpo_inventory/reviewed_reasoning_v001/build_dataset.py` | 같음 |
| `reviewed_reasoning_v001/canonical_rationales.jsonl` | 6,448 | `ffd618c74a8c79518ed25d797a0b34660e23aa6e9ab38225a8ad5134c09a93d5` | `sft_dpo_inventory/reviewed_reasoning_v001/canonical_rationales.jsonl` | 같음 |
| `reviewed_reasoning_v001/canonical_review.json` | 9,527 | `9fb42251df3e03cb1bf4f18335f191621f33204fdad535ee5d5c81c40aa3bc3f` | `sft_dpo_inventory/reviewed_reasoning_v001/canonical_review.json` | 같음 |
| `reviewed_reasoning_v001/canonical_source.py` | 8,112 | `f89725fd3605089bdb403365f7a071d8794d706cdf26c1ac10e8090f60c68a83` | `sft_dpo_inventory/reviewed_reasoning_v001/canonical_source.py` | 같음 |
| `reviewed_reasoning_v001/contamination.json` | 30,201 | `9cd347c4283d2b4839bd22d2297338f920f2c3d27e02f0de85e33b00f7482d01` | `sft_dpo_inventory/reviewed_reasoning_v001/contamination.json` | 같음 |
| `reviewed_reasoning_v001/dataset.jsonl` | 4,593,171 | `071ccdbee8c74694a189e861bb572975c6198da9c79b7cc93a558f531decea49` | `sft_dpo_inventory/reviewed_reasoning_v001/dataset.jsonl` | 같음 |
| `reviewed_reasoning_v001/integrity.json` | 50,003 | `b9dcab002074074631754c62c687eb953d31f81eefe7ad8057a125bd794c418d` | `sft_dpo_inventory/reviewed_reasoning_v001/integrity.json` | 같음 |
| `reviewed_reasoning_v001/manifest.json` | 137,914 | `8df179188bcc3e00c60976a9926a88b569caa708c55f54c7d3bf7a919bc2d199` | `sft_dpo_inventory/reviewed_reasoning_v001/manifest.json` | 같음 |
| `reviewed_reasoning_v001/token_lengths.json` | 27,102 | `fa29673798a2aadac154e1e665975607140dd358a120a9c8ea901c0c4cc9b73c` | `sft_dpo_inventory/reviewed_reasoning_v001/token_lengths.json` | 같음 |

## PG 결정 대응(번호만, 원문은 원본 DECISIONS.md)

| PG | 요지(원문 첫 줄 앞부분) |
|---|---|
| PG-57 | (2026-10-09, 사용자) Full vs Partial-P0 출력 contract A/B를 Ollama `qwen3:8b`(base, cell E 조건)로 업체 100에서 잰다. |
| PG-58 | (2026-10-10, 사용자) ab_p0에서 structural·grounding failure gate가 불통과해 Partial-P0.1 prompt(사용자 교체안, 예시 실행 |
| PG-59 | (2026-10-11, 사용자) Partial-P0.2: P0.1에 scope/place value 보존 규칙(규칙 10)과 scope 예시 6만 더해 같은 조건으로 |
| PG-60 | (2026-10-11, 사용자) P0.2를 동결하고 valid98에서 Full vs P0.2 paired A/B를 잰다(`evaluation/partial_grounding/ab_valid98/PL… |
| PG-61 | (2026-10-11, 사용자) Partial-P0.3: P0.2의 output_format에 규칙 11(pickup/dropoff/both·week/month 값의 출력 위치)만 더한다 |
| PG-62 | (2026-10-12, 사용자) P0.3 sel154 결과(commit `7baf67b`, 분기 B) 뒤 두 가지를 정한다. |
| PG-63 | (2026-10-13, 사용자) 결정 62 이후 세 가지를 정리한다. 새 prompt·P0.4·HF 재현·SFT·DPO·pruning은 하지 않는다. |
| PG-64 | (2026-10-13, 사용자) P0를 Partial Grounding SFT의 기준 contract로 확정한다. 아직 학습하지 않는다. |
| PG-65 | (2026-10-13, 사용자) `evaluate_vendor100._grounding_view`는 지금 고치지 않는다(평가 정규화 기술 부채로 남긴다). |
| PG-66 | (2026-10-13, 사용자) P0 SFT 준비 절차. |
| PG-67 | (2026-10-13, 사용자) P0 SFT 데이터셋 확정과 trace 출처. |
| PG-68 | (2026-10-13, 사용자) P0 contract 첫 SFT 실험(`sft_dpo_inventory/p0_sft_001`). 새 prompt·P0.4·P1·DPO·pruning·quantizat… |
| PG-69 | (2026-10-13, 사용자) P0 SFT 1차 실패 원인 분리(`sft_dpo_inventory/p0_sft_002`). 데이터 보강·27B 반입·DPO·pruning으로 넘어가지 않는다. |
| PG-70 | (2026-10-14, 사용자) p0_sft_002 결과에 따라 27B teacher 즉시 반입을 보류한다. |
| PG-71 | (2026-10-14) p0_sft_003_prep 분석 결론(`sft_dpo_inventory/p0_sft_003_prep/REPORT.md`). 학습·teacher 호출은 하지 않았다. |
| PG-72 | (2026-10-14, 사용자) P0 full-reasoning 데이터 회수 1단계(`sft_dpo_inventory/p0_sft_003_recovery`). |
| PG-73 | (2026-10-14) 회수 1단계 결과(`sft_dpo_inventory/p0_sft_003_recovery/REPORT.md`). |
| PG-74 | (2026-10-14, 사용자) 27B 실제 반입 전에 provenance exactness를 요구한다. |
| PG-75 | (2026-10-14, 사용자) 27B 결과를 보기 전에 trace 검토 보조 규칙 `quality_gate_v1`을 고정한다. 27B 결과를 본 뒤 v1을 바꾸지 않는다. 고칠 필요가 있으면 v2… |
| PG-76 | (2026-10-14, 사용자) quality gate는 risk flag와 ranking 도구이며 자동 승인기가 아니다. |
| PG-77 | (2026-10-14, 사용자) 이번 단계에서는 모델을 반입하거나 호출하지 않는다. |
| PG-78 | (2026-10-14, 사용자) Ollama registry `library/qwen3.8:27b`의 manifest metadata 조회만 승인한다(GET 1회, `REGISTRY_VERIFY_P… |
| PG-79 | (2026-10-14, 사용자) 결정 78을 보완한다(78은 그대로 둔다). |
| PG-80 | (2026-10-14, 사용자) teacher 데이터 수집은 데이터 독립성을 위해 모델을 상주시키지 않는다. |
| PG-81 | (2026-10-14, 사용자) 27B teacher G2 metadata 기준을 보완한다(G2_COMPATIBILITY_RULE_SUPPLEMENTED). 기존 G2 FAIL 기록은 그대로 둔다. |
| PG-82 | (2026-10-14, 결과 기록) 27B teacher recovery(M1 ∩ {P1, P2} 31문항)의 결과를 기록한다. 기준은 결정 79–81과 사전 등록 그대로다. |
| PG-83 | (2026-10-14, 사용자) 남은 reasoning 공백 44문항을 두 track으로 나눈다(`p0_sft_003_teacher27b_remaining/PLAN.md`). |
| PG-84 | (2026-10-14, 결과 기록) 남은 reasoning 공백 두 track의 결과를 기록한다(`p0_sft_003_teacher27b_remaining/REPORT.md`). 기준은 결정 83과… |
| PG-85 | (2026-10-14, 사용자) reviewed_reasoning_v001(154)을 freeze한다(`sft_dpo_inventory/reviewed_reasoning_v001/`). |
| PG-86 | (2026-10-14, 사용자) p0_sft_004 Full-Reasoning SFT 1차를 사전 등록대로 실행한다(`sft_dpo_inventory/p0_sft_004/PLAN.md`). |
| PG-87 | (2026-10-15, 결과 기록) p0_sft_004 결과(`sft_dpo_inventory/p0_sft_004/REPORT.md`). 기준은 결정 86과 사전 등록 그대로다. |
