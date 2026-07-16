# Evaluation — how we know the output is *good*, not just valid

Valid JSON is a floor, not a guarantee of correctness. An LLM can return a
perfectly-shaped record that misdescribes a method. This document defines how the
quality of the extracted knowledge is assessed and kept from regressing.

## Layers of assurance (cheapest first)

1. **Schema validation (automated, always on).** Every record is validated
   against the Pydantic contract before it is written. Catches structural errors
   and type violations for free. *Necessary, not sufficient.*
2. **Deterministic cross-checks (automated).** Facts that can be verified without
   a model are: complexity metrics come from `lizard` (not the model at all), and
   every reported method signature can be checked to actually occur in the source
   file. A cheap post-pass can flag any `key_methods[*].name` that does not appear
   in the file text — a concrete hallucination detector.
3. **Determinism / self-consistency.** With `temperature = 0` and fixed ordering,
   re-running an unchanged file must yield an identical record (the cache relies
   on this). Running a sample at low temperature N times and measuring agreement
   surfaces fields where the model is unstable.
4. **Golden-set spot checks (human, periodic).** Maintain a small labeled set of
   files with hand-written "correct" summaries and method lists. Score new runs
   against it with an LLM-as-judge rubric (faithfulness, completeness, no
   invented methods) plus a human review of a handful.

## A concrete, buildable eval harness

```
eval/
  golden/            # ~15-25 files spanning roles: controller, entity, mapper,
                     # config, custom repo — with reviewed expected records
  rubric.md          # scoring dimensions (see below)
  run_eval.py        # analyze golden files, score vs expected, emit a report
```

**Scoring dimensions (0–2 each):**

- **Faithfulness** — no invented methods, dependencies, or behavior.
- **Completeness** — the important methods/risks are present (trivial getters
  excluded, as instructed).
- **Signature accuracy** — signatures match the source exactly.
- **Role/summary correctness** — the architectural role and summary are right.

## Regression gating in CI

- Run the harness on every change to prompts, schema, or model configuration.
- Fail the build if the aggregate score drops below a threshold, or if the
  signature-occurrence check finds any hallucinated method in the golden set.
- Track score and cost over time so prompt/model changes are judged on
  quality-per-dollar, not vibes.

## Metrics worth tracking per run (already partly emitted)

- Files analyzed / skipped (a rising skip rate signals a prompt or endpoint
  regression).
- Tokens and estimated cost (quality-per-dollar).
- Cache-hit rate (efficiency).
- Hallucinated-signature count from the deterministic cross-check (correctness).

## Honest limitations

- LLM-as-judge is itself imperfect; it complements, not replaces, human review.
- The golden set is small by nature; it catches systematic regressions, not every
  edge case. It should grow whenever a real miss is found in the field.
