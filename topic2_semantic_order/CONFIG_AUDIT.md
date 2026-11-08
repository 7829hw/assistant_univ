# CONFIG_AUDIT — A vs B controls (generated evidence: `gates/GATES.json`, `gates/*.log`)

| Control | A (existing A0, reused) | B (new) | Evidence |
|---|---|---|---|
| Base model/revision | Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218 | same | config diff (G6) |
| LoRA | r16, alpha 32, dropout 0.05, q,k,v,o,gate,up,down | same | G6 |
| LR / schedule | 2e-4, warmup 1 step, linear to 0 (`lr_plan`: step 1984 lr 1.0e-7) | same | dry-run logs |
| Batch / accum / epoch / steps | 1 / 1 / 1 / 1,984 | same | `optimizer_steps_total: 1984` in every B dry-run |
| Loss scope / thinking | `by_source`, enable_thinking true | same | G6 |
| Prompt / template | prompt_hash 87048d0c… | same | dry-run `prompt_hash` |
| Record set | 1,984 records / 494 questions | identical set, each once | G2/G3 |
| Data file | `pilot_010/build/V4/full/sft_train.jsonl` sha256 3575c7f0…ed10e3f | same (manifest-verified) | G1 |
| Training seed | 43 (data_seed 43) | 43 | G6 |
| Sampler | SequentialSampler (order7.install_sequential_sampler) | same function, installed by `train_semantic.py` | G7 functional check + `trainer_sampler` in logs |
| **Order** | O4' slot permutation (`default_rng(order_seed)`) | Semantic-balanced file `orders/semantic_order_o<seed>.json` | only intended difference |

`config diff` (G6): the only differing keys between each A0 config and its B config are the order keys, `training.output_dir` and `profiling.output`. The five A0 configs differ from each other only in the same keys.

Wrapper: B uses `train_semantic.py`, which reuses `train_a11.install_override()` (no-op for V4 because no record carries the a11 override mark), `train_b7b.lr_plan`, `trainer_common.cli`, `train_sft.train` and `SaveAt` — i.e. the code path of A0, with `apply_order_a11` replaced by an order loader that checks: unique ids, same set, sequence sha, max question run <= 4, and training-file sha equals the order file's recorded sha.

Reuse of A0 checkpoints: the A0 configs are the ones that produced the checkpoints (training_provenance.json holds the same config); all five have checkpoint-1984; adapter sha256 are in the external `adapters_sha256.txt` files (decision 255, not committed). Known residual: A and B evaluations are separate vLLM sessions; the repeat pair on o2026131 measures run-to-run training nondeterminism, and re-running CT10K for A0-o2026117/o2026131 in this experiment keeps those two A cells on the same session type as B.

Model initialisation: B models start from the pretrained base only (config `model.name_or_path`, no `adapter`/resume key; checked in G6 since any such key would show up as a diff).
