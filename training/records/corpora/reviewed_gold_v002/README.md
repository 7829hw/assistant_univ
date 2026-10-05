# reviewed_gold_v002

Immutable semantic-grounding corpus extending v001; no training run.
SFT: train12 / validation5; DPO: train16 / validation4.
DPO semantic11 / constraint9. New approved SFT: RB002-02/04/09.
Review batch002 disposition: accepted18 / diagnostic2 / hold10.

The proposed 28 acceptances were conditional on lineage safety. Rechecking the
question-only protected assistant_univ_questions_100_v3.yaml exposed seven
semantic family collisions that the existing exact-text-only handling missed.
RB002-01/03/05/06/07/08/10 and their pairs23/25/26 remain hold. Targets were not
rewritten to bypass protection. See lineage_audit.json and decisions_002.jsonl.
RB002-11/12 remain diagnostic and are absent from all training datasets.
The workflow stores diagnostic dispositions as status=needs_fix plus
corpus_disposition=diagnostic_only; these are not semantic holds or rejections.
User explicitly adopted policies; Codex performed delegated verification.
No claim is made that the user individually inspected every field.

v001 records and train/validation assignments are preserved byte-equivalently.
New groups keep the original batch002 seed42 split preview; held groups were
removed, not shuffled into fresh validation. Only RPM-min09 is new validation.
DPO chosen is linked to actual accepted gold; source/role21/22 contrasts remain
raw planner-contract preferences even when their graphs/results are identical.
They are not numerical execution improvements.23 is held due chosen08 lineage.

02/04/19 remain semantic gold and are explicitly excluded from execution
benchmarks. policy_and_scope.json is a sidecar; existing evaluator does not
automatically enforce it. No real TIMS answer is certified by mock static
compile. v001 execution exclusions and RB001-10–20 holds remain unchanged.

manifest.json contains actual training files' prompt/schema/hashes/seed.
corpus_manifest.json freezes the corpus, config and verification evidence.
Strict SFT builder replays the annotation union in validation_evidence; its
temporary reshuffle is verification-only. Strict DPO builder uses an isolated
reviewed-candidate supplier replay, producing exactly the approved pairs. No
new synthetic negatives are generated and no source code is edited.

configs/*.yaml are CPU-validated 4-step pilot input profiles, not a new run.
Token lengths were measured offline with the frozen Qwen tokenizer and guarded
against truncation (token_validation.json). Do not resume old pilot adapters:
RB001-05 was previously training-exposed but is now held out. Start from Base,
freeze a new experiment and decoding conditions before any pilot. DPO path is
the new SFT output placeholder; select a validation checkpoint before DPO.

Data preflight, without GPU/model initialization:
python -m training.train_sft --config /home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_sft.yaml --dry-run
python -m training.train_dpo --config /home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_dpo.yaml --dry-run

Only fare1/speed1/rpm1 were added; passage_count/vacant_ratio/active counts and
ratios remain uncovered. New semantic validation pairs are absent (new valid
constraint is RPMsum30); old OD validation remains3. This is mechanically ready
for a limited corpus experiment, insufficient for the intended broad rare-
MEASURE/SFT-vs-DPO quality conclusion. Resolve the protected-corpus policy in a
separate explicit task; do not move or relabel existing evaluation families.
