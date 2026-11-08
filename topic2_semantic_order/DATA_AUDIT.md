# DATA_AUDIT

## A/B (this experiment)
- Training file sha256 `3575c7f06c2ee7baaf59233b01c926504589ec2fbf3136f255a45599ced10e3f` = pinned value, contained in `pilot_010/build/V4/full/manifest.json` (G1).
- 1,984 records, 494 questions, 1,079 `full_response` (teacher) + 905 `json_only` (own samples); unchanged for A and B (G2/G3), so loss-token budget, teacher/JSON-only share and optimizer steps are identical by construction.
- Labels: `approved_train_v6.jsonl` (`view`, `execution` for tool). 420 answering + 74 refusal questions; 288 answering questions have gold execution, 132 use `view` only; coarse groups 11 (+refusal), fine groups 249 incl. refusal. `unknown|speed` and `unknown|vacant_ratio` (57 records) have no executed train evidence for the tool, so tool stays `unknown` (not guessed).
- No evaluation item, error, or H-final information enters labels or orders (the module reads only the train file and the approved train corpus).

## C/D coverage arms — **BLOCKED, not run**
Reasons (from `ablation_013/QUESTIONS.md` items 1-3 and decision 120/C-1):
1. The 44 approved driving-fare (운행 요금) questions absent from V4 were removed by type cap C-1; re-including them is an exception that the user has not decided (QUESTIONS 3).
2. batch014 (46 drafts) is **not approved** (QUESTIONS 1); T1/T2 structures are all blocked by protected net families; T1v is out of scope pending decision.
3. Matching the loss-token budget and teacher/JSON-only share with replaced records requires approved replacement records plus a tokenizer ledger; none exist.
4. The Ollama container (teacher collection) is down, so no new teacher traces can be produced.
`audit_coverage_arm.py`/`coverage_o4prime.py` remain fail-closed. Because coverage would change records/loss tokens, no C/D result could be interpreted as an order effect; it is therefore not mixed in.
Unblocking requires: user approval of a replacement set, a protected-id/family overlap audit by the repository tool (`ablation_012/e2/build_e2.py` PoolRule), equal record count and loss tokens (±1%), and then Arms C/D plus A/B reuse.
