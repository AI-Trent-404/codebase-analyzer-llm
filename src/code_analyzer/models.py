"""
Pydantic data models that define the *contract* for the analyzer's output.

Design intent
-------------
These schemas serve three jobs at once:

1. **LLM structured-output target.** LangChain's ``with_structured_output`` binds
   a schema to the model so Claude is forced to return valid, typed JSON — no
   brittle regex/text parsing.
2. **Validation gate.** Anything the model returns is re-validated here before it
   is written to disk, so the final artifact is guaranteed to match the schema.
3. **Public JSON contract.** ``CodebaseAnalysis`` is the top-level object that is
   serialized to the deliverable JSON file. Field names and descriptions are the
   documentation for downstream consumers.

Keeping the schema in one place is what makes the output *consistent and
machine-readable* — a core requirement of the assignment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class ComplexityBand(str, Enum):
    """Human-readable bucket for cyclomatic complexity."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


# --------------------------------------------------------------------------- #
# LLM-produced models (the "map" step fills these in per file)
# --------------------------------------------------------------------------- #
class MethodInfo(BaseModel):
    """A single method / function of interest within a source file."""

    name: str = Field(..., description="Method or function name.")
    signature: str = Field(
        ...,
        description="Full signature including modifiers, return type, name, and "
        "parameter list, e.g. 'public ResponseEntity<FilmDto> getFilm(Integer id)'.",
    )
    description: str = Field(
        ...,
        description="One or two sentences on what the method does and why it exists.",
    )
    parameters: list[str] = Field(
        default_factory=list,
        description="Parameter declarations, e.g. ['Integer filmId', 'Pageable pageable'].",
    )
    returns: str | None = Field(
        None, description="Return type and a short note on what is returned."
    )
    visibility: str | None = Field(
        None, description="Access modifier if applicable (public/private/protected/package)."
    )


class LLMFileInsight(BaseModel):
    """
    The portion of a file's analysis that the LLM is responsible for.

    This is the exact schema bound to Claude via ``with_structured_output`` — it
    intentionally excludes anything we can compute deterministically (line counts,
    cyclomatic complexity), so we never pay tokens for facts a static analyzer
    already knows.
    """

    summary: str = Field(
        ..., description="A concise, high-signal summary of the file's responsibility."
    )
    role: str = Field(
        ...,
        description="Architectural role, e.g. 'REST controller', 'JPA entity', "
        "'service implementation', 'MapStruct mapper', 'configuration'.",
    )
    key_methods: list[MethodInfo] = Field(
        default_factory=list,
        description="The most important methods. Omit trivial getters/setters and "
        "Lombok-generated accessors.",
    )
    external_dependencies: list[str] = Field(
        default_factory=list,
        description="Notable frameworks/libraries this file leans on "
        "(e.g. 'Spring HATEOAS', 'QueryDSL', 'MapStruct').",
    )
    noteworthy: list[str] = Field(
        default_factory=list,
        description="Design patterns, security annotations, gotchas, or anything a "
        "reviewer should know.",
    )


class ComplexityMetrics(BaseModel):
    """Deterministic metrics computed by a static analyzer (lizard), not the LLM."""

    nloc: int = Field(0, description="Non-comment lines of code.")
    function_count: int = Field(0, description="Number of functions/methods detected.")
    average_cyclomatic_complexity: float = Field(
        0.0, description="Mean cyclomatic complexity across functions."
    )
    max_cyclomatic_complexity: int = Field(
        0, description="Highest cyclomatic complexity of any single function."
    )
    most_complex_function: str | None = Field(
        None, description="Name of the function with the highest complexity."
    )
    band: ComplexityBand = Field(
        ComplexityBand.LOW, description="Bucketed complexity for quick scanning."
    )


class FileAnalysis(BaseModel):
    """Complete per-file record: deterministic metrics + LLM insight, merged."""

    path: str = Field(..., description="Repo-relative path of the file.")
    language: str = Field(..., description="Detected source language.")
    package: str | None = Field(
        None, description="Logical package/module the file belongs to."
    )
    size_bytes: int = Field(0, description="File size in bytes.")
    complexity: ComplexityMetrics = Field(default_factory=ComplexityMetrics)
    insight: LLMFileInsight
    analyzed_with_chunking: bool = Field(
        False, description="True if the file was split to respect token limits."
    )
    from_cache: bool = Field(
        False, description="True if this record was served from the content-hash cache."
    )


class ProjectOverview(BaseModel):
    """The 'reduce' step: a synthesized, high-level view of the whole project."""

    name: str = Field(..., description="Best-guess project name.")
    purpose: str = Field(
        ..., description="What the project is for, in plain language (2-4 sentences)."
    )
    architecture_summary: str = Field(
        ..., description="How the code is organized and the main architectural style."
    )
    primary_language: str = Field(..., description="Dominant programming language.")
    frameworks: list[str] = Field(
        default_factory=list, description="Major frameworks and libraries in use."
    )
    key_components: list[str] = Field(
        default_factory=list,
        description="The most important modules/packages and what each does.",
    )
    entry_points: list[str] = Field(
        default_factory=list,
        description="Application entry points (main class, controllers, etc.).",
    )
    notable_patterns: list[str] = Field(
        default_factory=list,
        description="Cross-cutting design patterns and conventions observed.",
    )
    potential_risks: list[str] = Field(
        default_factory=list,
        description="Complexity hotspots, coupling, or maintenance risks worth flagging.",
    )


# --------------------------------------------------------------------------- #
# Envelope / statistics
# --------------------------------------------------------------------------- #
class LanguageStat(BaseModel):
    language: str
    file_count: int
    line_count: int


class RunStatistics(BaseModel):
    """Operational metadata — useful for cost review and reproducibility."""

    files_discovered: int = 0
    files_analyzed: int = 0
    files_skipped: int = 0
    files_from_cache: int = 0
    total_source_lines: int = 0
    languages: list[LanguageStat] = Field(default_factory=list)
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    wall_time_seconds: float = 0.0


class AnalysisMetadata(BaseModel):
    schema_version: str = SCHEMA_VERSION
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    target: str = Field(..., description="Path or URL of the analyzed codebase.")
    model: str = Field(..., description="LLM used for comprehension.")
    tool_version: str = "1.0.0"


class CodebaseAnalysis(BaseModel):
    """
    Top-level deliverable. This is what gets serialized to the output JSON file.
    """

    metadata: AnalysisMetadata
    overview: ProjectOverview
    statistics: RunStatistics
    files: list[FileAnalysis]

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)
