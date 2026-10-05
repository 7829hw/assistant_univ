# Implementation analysis (geoflow/dev-v2, initial HEAD 65e9ea2)

`GeoFlowPlanner` grounds concepts and factors, never graphs or tool calls. Its
default `aggregation_grounding="flat"` system prompt combines the YAML via
`build_prompt` with live operator vocabulary, factor specs, semantics and
constraints. Raw responses contain `concepts`/`factors`, or `unsupported: true`.
The runtime tolerates explanatory keys and JSON fences; training emits JSON only.

`parse_grounding` checks enum/subtype/role/source, duplicate IDs, values, factors,
scope provenance and exactly one measure. Runtime normalization hoists misplaced
conditions and repairs place shapes. Planner drops invented upper regions.
`Grounding.to_dict()` additionally includes aggregation, calendar and normalization
state; it is NOT the output contract and is not a training target.

`MacroComposer` searches backwards from MEASURE through IO ports in five macro
YAMLs. It checks factor co-occurrence, aggregation meaning, location relations and
unused conditions. Registry-based implicit EVENT inference is valid runtime
behavior: simply omitting such an EVENT is not automatically a negative.
`operator_mapping.resolve` determines the unique semantic operator from input
ports, output type and factors. The older template registry remains available to
tests and legacy paths; it is not the planner output contract.

`validator.validate` implements G1 acyclicity, G2 role ordering, G3 type
compatibility, G4 executability, G5 connectivity, G6 scope provenance and G7
aggregation semantics. `compile_plan` topologically lowers semantic transformations
to provider-specific calls or local analysis operations; executor resolves state
and invokes them. This change leaves all these responsibilities intact.

The question-graph store has structured aggregation annotations, answerable,
clarification and unsupported outcomes, and reviewer provenance (including labels
still awaiting human review). Store verification checks annotations against the
composer and serialized graph. Training converts only this explicit source mode
to flat, checks aggregation equivalence, then revalidates the flat target.
Clarification outputs have no production JSON label and are excluded with a report.

`evaluation/corpus_registry.yaml` marks several former holdouts as development;
v2 labels are also unreviewed. Being development is not automatic training consent:
all registered corpora, question sets, their parents and files under evaluation/
are reserved. Exact question overlap is blocked. New independent benchmark families
are necessary for a final uncontaminated comparison.

`evaluate_planner.evaluate_once` and `summarize` already score concepts/subtypes/
roles, macro/operator labels (including legacy corpus projection), validation,
optional execution and planning repairs. Add only missing raw/factor/grounding
metrics there; the checkpoint wrapper delegates evaluation to these functions.
Execution measurements in this evaluator concern the first composed plan and do
not measure runtime execution repair. Factor and raw metrics concern first output.

Dependencies use requirements.txt with pins/ranges; tests use unittest. Optional
training dependencies stay in training/requirements.txt. CPU builders and dry-run
use runtime dependencies only. Implement serializer, SFT validation, grouped split
and provenance first, then semantic DPO/mine interface, trainers, evaluation and
documentation. Keep production defaults/public APIs unchanged.
