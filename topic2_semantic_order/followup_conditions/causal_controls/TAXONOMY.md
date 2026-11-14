# Tool and grounding error taxonomy

The frozen scorer category remains the outcome. Multi-label flags reuse tool, argument, aggregation, grounding and refusal diagnostics, alongside truncation and pipeline stage fields. An argument mismatch can also be an aggregation mismatch. Silent wrong is the frozen answered-mismatch category. Unhandled exceptions are grouped as evaluator or transport because the recorded fields do not reliably distinguish them. Composition, validation, template and compile failures are recorded as deterministic-stage failures. This is a failure location, not an attribution of origin.

Compare required and executed get_place_scope calls by name, region and vicinity with multiplicity. This look-up diagnostic is restricted to accepted answers or rows that executed at least one tool. It distinguishes zero place calls from partial or wrong lookups. Refusals and early failures retain their separate flags.

For zero place calls, apply these rules in order.

1. A single parsed model plan with no LOCATION and no recorded repair or truncation supports a model-plan location omission.
2. A plan with the exact required place set and an explicitly empty final grounded place list supports loss during grounding.
3. A plan with that exact place set and passing final grounding supports a missing downstream lookup.
4. Missing responses, repairs, invalid plans, nonmatching place values, vicinity-sensitive cases and unresolved evidence remain ambiguous.

This uses the existing parser and stored plan content. The aggregates preserve intersections and the SHA of each input. The original taxonomy snapshot stays frozen. The expanded diagnostics are post-hoc.
