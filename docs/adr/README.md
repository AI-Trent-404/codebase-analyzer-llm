# Architecture Decision Records

These ADRs capture the *why* behind the significant choices in this project —
the alternatives considered and the trade-offs accepted. They use a lightweight
[Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
format: Context → Decision → Consequences.

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-map-reduce-over-rag.md) | Map-reduce over the file set, not retrieval (RAG) | Accepted |
| [0002](0002-langchain-structured-output.md) | LangChain with schema-bound structured output | Accepted |
| [0003](0003-deterministic-metrics-vs-llm.md) | Deterministic metrics via a static analyzer, not the LLM | Accepted |
| [0004](0004-provider-agnostic-endpoint.md) | Provider-agnostic endpoint via an optional base URL | Accepted |
