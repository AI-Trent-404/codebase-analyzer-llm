# ADR 0003 — Deterministic metrics via a static analyzer, not the LLM

**Status:** Accepted

## Context

The output includes "code complexity and other noteworthy aspects." Complexity
metrics (lines of code, cyclomatic complexity, function counts) are *exact,
computable facts*. They could be produced by the LLM alongside the prose, or by
a dedicated static-analysis tool.

## Decision

Compute all quantitative metrics with **`lizard`** (a language-agnostic static
analyzer covering Java, Kotlin, Python, Go, C-family, and more). The LLM is
reserved for genuine comprehension — intent, roles, patterns, risks.

## Rationale

- LLMs are unreliable at counting and arithmetic; a hallucinated complexity
  number is worse than none, because it looks authoritative.
- Deterministic tooling is exact, reproducible, and free of token cost. Running
  it locally also means these facts are computed on the *original* source, with
  no dependence on what was sent to the model.
- This cleanly divides labor by the right criterion: **deterministic facts →
  deterministic tools; judgment → the LLM.** It cuts cost and hallucination
  surface simultaneously.

## Consequences

- **Positive:** trustworthy, reproducible metrics; lower token usage; metrics
  available even for files the LLM skips or that fail analysis.
- **Negative:** an extra dependency (`lizard`); metric coverage is bounded by the
  languages it supports (it degrades gracefully to zeros otherwise).
- **Example payoff:** the sample run flags `FilmEntity.equals` at cyclomatic
  complexity 16 — a *measured* hotspot, not a guess.
