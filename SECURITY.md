# Security & Data Governance

This tool sends source code to an external Large Language Model endpoint. That is
a data-egress event and deserves explicit treatment — especially for proprietary
codebases and when routing through a third-party proxy. This document states the
threat model, the controls in place, and the residual risks a deploying team
should own.

## What leaves the machine, and to where

- The **content of source files** that pass ingestion filters is sent to the
  configured model endpoint over HTTPS.
- The endpoint is the official Anthropic API by default, or whatever
  `ANTHROPIC_BASE_URL` points at (a proxy, gateway, or self-hosted relay).
- Nothing else is transmitted: no environment variables, no git history, no
  files outside the analyzed tree. Deterministic metrics are computed locally and
  never require transmission.

## Controls in place

- **Secret redaction before egress (`redaction.py`).** Every file is scrubbed of
  credentials *before any bytes leave the process*: private-key blocks, Anthropic
  / OpenAI / AWS / Google / GitHub / Slack keys, JWTs, URL-embedded credentials,
  and quoted `secret = "…"` assignments are replaced with typed placeholders. It
  runs on the copy sent to the model; the on-disk source is never modified.
  Toggle with `ANALYZER_REDACT_SECRETS` (on by default).
- **Aggressive ingestion filtering.** Tests, build output, vendored code, and
  generated files are excluded before prompting, shrinking the egress surface.
- **Provider portability (ADR 0004).** `ANTHROPIC_BASE_URL` lets an organization
  route through an endpoint inside its own trust boundary — a corporate gateway
  or self-hosted model — so code need not reach a public API at all.
- **Secrets stay out of the repo.** The API key lives only in `.env`, which is
  git-ignored; no credential is ever written to the output or logs.

## Residual risks (owned by the deployer)

- **Redaction is defense-in-depth, not a guarantee.** Regex-based scrubbing
  catches common, high-confidence secret shapes; it will not catch every custom
  or obfuscated secret. It is not a substitute for keeping secrets out of source.
- **Third-party proxies see your code.** If `ANTHROPIC_BASE_URL` points at a
  reseller/proxy, that operator can observe transmitted (redacted) source. Use a
  provider and data-retention posture your organization has vetted; prefer the
  official API or a self-hosted endpoint for sensitive code.
- **Provider data-retention.** Review the endpoint's retention and training
  policy. For regulated code, confirm zero-retention terms before use.

## Recommended posture for sensitive codebases

1. Point `ANTHROPIC_BASE_URL` at an endpoint inside your trust boundary.
2. Keep `ANALYZER_REDACT_SECRETS=true` (default) and add project-specific
   patterns to `redaction.py` as needed.
3. Add sensitive paths to `exclude_dirs` so they are never read.
4. Run with a key scoped to the minimum necessary and rotate regularly.

## Reporting

For a real deployment, add a private disclosure channel here (security contact
or advisory process) so issues are reported responsibly rather than in public
issues.
