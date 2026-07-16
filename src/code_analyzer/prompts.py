"""
Prompt templates, kept in one place so they can be versioned and reviewed.

Prompt-engineering choices that matter here:
* A tight, role-specific system prompt anchors the model as a senior code analyst.
* We ask for *signal, not prose*: skip trivial getters/setters, focus on intent.
* Because output is bound to a Pydantic schema, the prompt does NOT describe JSON
  formatting — the schema does. This keeps prompts short and avoids drift between
  the instructions and the actual contract.
"""
from __future__ import annotations

FILE_SYSTEM = (
    "You are a senior software engineer performing precise static code review. "
    "You extract accurate, high-signal facts about a single source file: its "
    "responsibility, architectural role, the important methods (with exact "
    "signatures), notable frameworks, and anything a reviewer should know. "
    "Be faithful to the code — never invent methods or behaviour. Ignore trivial "
    "boilerplate such as getters, setters, equals/hashCode, and Lombok-generated "
    "accessors."
)


def file_user_prompt(rel_path: str, language: str, code: str) -> str:
    return (
        f"File: {rel_path}\n"
        f"Language: {language}\n\n"
        "Analyze the file below and extract the structured insight.\n"
        "```\n"
        f"{code}\n"
        "```"
    )


def file_chunk_prompt(rel_path: str, language: str, part: int, total: int, code: str) -> str:
    return (
        f"File: {rel_path} (part {part} of {total} — the file was split to fit the "
        f"context window; analyze only what is present in this part)\n"
        f"Language: {language}\n\n"
        "```\n"
        f"{code}\n"
        "```"
    )


OVERVIEW_SYSTEM = (
    "You are a principal software architect. Given per-file summaries and the "
    "package layout of a codebase, synthesize an accurate, high-level overview: "
    "the project's purpose, its architecture and conventions, the major "
    "components, entry points, notable patterns, and real maintenance risks. "
    "Base every statement on the evidence provided; do not speculate beyond it."
)


def overview_user_prompt(target: str, tree: str, file_digests: str) -> str:
    return (
        f"Target: {target}\n\n"
        f"Package / directory layout:\n{tree}\n\n"
        f"Per-file summaries (role — path — summary):\n{file_digests}\n\n"
        "Produce the structured project overview."
    )


PARTIAL_OVERVIEW_SYSTEM = (
    "You are a software architect. Summarize a group of related source files into "
    "a compact digest capturing the package's responsibility, its key components, "
    "and any notable patterns. This digest will be combined with others to describe "
    "the whole system, so be concise but information-dense."
)
