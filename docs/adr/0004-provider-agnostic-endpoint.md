# ADR 0004 — Provider-agnostic endpoint via an optional base URL

**Status:** Accepted

## Context

The tool targets Anthropic Claude, but users may need to route requests through
a different endpoint: an OpenAI-compatible proxy, a corporate API gateway, a
regional relay, or a self-hosted deployment. Hard-coding the official endpoint
would block those environments and couple the code to one vendor's billing.

## Decision

Keep the model client behind a single module (`llm.py`) and expose an optional
`ANTHROPIC_BASE_URL`. When set, requests route through that endpoint; when unset,
the official Anthropic API is used. The model id is likewise configurable
(`ANALYZER_MODEL`), since compatible endpoints publish their own model names.

## Rationale

- A one-line seam (base URL + model id) unlocks proxies, gateways, and
  self-hosting without touching pipeline logic — a large portability win for
  negligible complexity.
- It also enables **data-governance** choices (see SECURITY.md): an organization
  can point the tool at an endpoint inside its own trust boundary.
- Isolating all model construction in one place keeps the rest of the codebase
  free of provider details and makes the client trivially mockable in tests
  (a heuristic stand-in powers `--dry-run`).

## Consequences

- **Positive:** works against official, proxied, gateway, and self-hosted
  endpoints; billing and data-residency become deployment choices, not code
  changes; testable without network or keys.
- **Negative:** compatible endpoints vary in tool-calling fidelity, so structured
  output can occasionally fail there — handled by retries and skip-on-failure.
- **Trade-off accepted:** a full multi-provider abstraction (OpenAI, Gemini, …)
  was intentionally *not* built; it is speculative for this scope and would add
  surface area with no current requirement.
