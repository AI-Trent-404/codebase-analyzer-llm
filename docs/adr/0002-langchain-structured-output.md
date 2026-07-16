# ADR 0002 — LangChain with schema-bound structured output

**Status:** Accepted

## Context

The output must be "consistent and machine-readable." An LLM emits free text by
default; turning that into reliable JSON is the central reliability risk. Options:

1. Prompt for JSON and parse the text (regex / `json.loads` with repair).
2. Use the provider SDK's tool/function-calling directly.
3. Use an orchestration framework (LangChain / LlamaIndex) that wraps tool
   calling as typed **structured output**.

## Decision

Use **LangChain** with `ChatAnthropic.with_structured_output(PydanticModel)`.
A Pydantic schema is bound to the model as a tool it must call; the response is
validated against that schema before it is returned.

## Rationale

- Text-parsing (option 1) is brittle: it breaks whenever the model rephrases,
  adds prose, or emits trailing commas. It is the most common failure mode in
  LLM apps and is avoidable.
- Structured output makes valid, identically-shaped JSON a property of the call
  rather than of the prompt wording. The **schema**, not the prompt, defines the
  contract — so the prompt stays short and cannot drift from the output shape.
- LangChain over the raw SDK (option 2) buys a provider-agnostic seam (see
  ADR 0004), retry/callback hooks, and one-line structured-output binding, at an
  acceptable dependency cost. LlamaIndex was considered; it is retrieval-centric,
  which this design deliberately avoids (ADR 0001).

## Consequences

- **Positive:** no text parsing; output re-validated against one source-of-truth
  schema; provider portability retained.
- **Negative:** a heavier dependency than the bare SDK; occasional malformed
  tool calls still occur and must be handled (retries + skip-on-failure).
- **Note:** the same Pydantic schema does triple duty — constrain the model,
  validate the result, and document the JSON contract.
