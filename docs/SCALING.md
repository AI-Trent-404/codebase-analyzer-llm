# Scaling & Productionization

How this design behaves as the input and the operational demands grow, and what
would come next to run it as a service rather than a CLI.

## Cost model

Cost is dominated by per-file LLM calls in the map stage plus one (or a few)
reduce calls. Grounded in the reference run:

| Metric | Reference run (spring-rest-sakila) |
|---|---|
| Files analyzed | 188 |
| Source lines | ~10,100 |
| Input / output tokens | ~349k / ~133k |
| Estimated cost | ~$3.04 |
| Wall time (concurrency 6) | ~7.5 min (cold), ~1 min (warm cache) |

A useful rule of thumb: **cost ≈ (files analyzed) × (avg tokens/file) × price**,
so it scales roughly *linearly with the number of files that survive filtering* —
which is why pre-filtering is the highest-leverage cost control. Approximate
planning figure: **~$1.5–3 per 1,000 small-to-medium source files** on Sonnet,
before caching.

## Levers already in the design

- **Pre-filtering** removes tests/build/vendor/generated files before any spend.
- **Content-addressed cache** makes re-runs near-free; on a changed branch only
  the changed files re-run (the warm-cache column above).
- **Concurrency** (`max_concurrency`) trades wall-clock for throughput against
  the endpoint's rate limits.
- **`max_files` / model selection** allow cheap sampling runs and cost/quality
  trade-offs (e.g. Haiku for a first pass, Sonnet for depth).

## Scaling to a large monorepo (50k+ files)

- **Ingestion** is already streaming and O(files); it does not hold the tree in
  memory. The map stage is embarrassingly parallel.
- **Reduce** is the part that must not blow the context window. The hierarchical
  reduce (per-package summaries, then combine) already handles this; for very
  large trees it generalizes to more levels (package → module → service → repo).
- **Incremental analysis:** persist the cache between runs (e.g. keyed by git
  blob SHA) so CI analyzes only the diff of a pull request rather than the whole
  tree.

## Running it as a service

- **Rate limiting & backpressure:** replace the fixed thread pool with a token-
  bucket limiter honoring the endpoint's RPM/TPM; add a queue so large repos are
  processed as jobs rather than one blocking call.
- **Durability:** checkpoint completed file records (the cache already provides
  most of this) so a crash resumes instead of restarting.
- **Observability:** emit structured logs and metrics (files/sec, tokens, cost,
  cache-hit rate, skip rate) to a collector; the per-run `statistics` block is
  the seed of this.
- **Isolation & secrets:** run under a scoped key via a secrets manager; route
  through an in-boundary endpoint (see SECURITY.md); sandbox the clone step.
- **Delivery:** expose as a CI action (annotate PRs with complexity hotspots) or
  a small service that writes `analysis.json` to object storage and indexes it.

## What I would build next (roadmap)

1. **Cross-file linking** — a call/dependency graph across files, so the output
   captures relationships, not just per-file facts.
2. **Interactive query mode** — layer RAG (embeddings + vector store) *on top of*
   the generated knowledge base for natural-language Q&A (see ADR 0001).
3. **Incremental CI mode** — diff-aware analysis keyed on blob SHAs.
4. **Multi-provider + model routing** — cheap model for the map pass, stronger
   model for reduce and for flagged hotspots.
5. **Eval harness in CI** — gate prompt/model changes on a labeled set
   (see [EVALUATION.md](EVALUATION.md)).
