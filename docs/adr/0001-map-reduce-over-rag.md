# ADR 0001 — Map-reduce over the file set, not retrieval (RAG)

**Status:** Accepted

## Context

The task is to extract a *complete* structured knowledge base from a codebase
that is far larger than any single model context window (the reference repo is
~10k LOC across 188 files). Two families of approach exist:

1. **Retrieval-Augmented Generation (RAG):** embed all chunks into a vector
   store, then, per question, retrieve the top-k most relevant chunks and answer.
2. **Map-reduce:** analyze every unit independently (map), then synthesize the
   partial results into a whole (reduce).

## Decision

Use **map-reduce over the file set**. Each file is analyzed independently to a
structured record (map); per-file digests are then synthesized into a project
overview, collapsing to per-package summaries first when the digest set is large
(hierarchical reduce).

## Rationale

- The deliverable requires **exhaustive** coverage — every file's methods and
  complexity — not the *most relevant* answer to a query. RAG optimizes for the
  latter and would systematically miss files that never surface in retrieval.
- RAG introduces an embedding model, a vector store, and a retrieval-quality
  tuning surface — real operational cost for no benefit to a whole-repo sweep.
- Map-reduce parallelizes trivially and scales past any context window via the
  hierarchical reduce.

## Consequences

- **Positive:** complete coverage; embarrassingly parallel; no vector
  infrastructure; deterministic and cache-friendly.
- **Negative:** cost scales with repo size (one+ call per file) rather than per
  query — mitigated by pre-filtering, caching, and concurrency.
- **Future:** a RAG layer is still the right tool for an *interactive Q&A* mode
  over the produced knowledge base; it would be added on top, not instead.
