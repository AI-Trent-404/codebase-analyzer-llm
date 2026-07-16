"""
Offline / dry-run LLM stand-in.

This lets the *entire* pipeline run end-to-end with no API key and no network —
useful for CI, for unit tests, and for demonstrating the data flow. It produces
deterministic, heuristic insight derived from lightweight source parsing. It is
explicitly NOT a substitute for real LLM comprehension; it exists so the plumbing
can be exercised and reviewed without spending tokens.

The class mirrors ``LLMClient.structured`` and the ``.usage`` attribute so it is
a drop-in replacement inside the pipeline.
"""
from __future__ import annotations

import re
from typing import Type, TypeVar

from pydantic import BaseModel

from .llm import UsageTracker
from .models import LLMFileInsight, MethodInfo, ProjectOverview

T = TypeVar("T", bound=BaseModel)

# Java/Kotlin-ish method matcher (good enough for a heuristic demo).
_METHOD_RE = re.compile(
    r"(?P<vis>public|private|protected)?\s*"
    r"(?:static\s+|final\s+|synchronized\s+|abstract\s+)*"
    r"(?P<ret>[\w<>\[\],.\s?]+?)\s+"
    r"(?P<name>\w+)\s*\((?P<params>[^)]*)\)\s*(?:throws [\w.,\s]+)?\{",
)

_ROLE_HINTS = [
    ("Controller", "REST controller"),
    ("ServiceImpl", "service implementation"),
    ("Service", "service interface"),
    ("RepositoryImpl", "repository implementation"),
    ("Repository", "data repository"),
    ("Entity", "JPA entity"),
    ("Dto", "data transfer object"),
    ("Mapper", "object mapper"),
    ("Assembler", "HATEOAS representation assembler"),
    ("Config", "configuration"),
    ("Converter", "attribute converter"),
]

_FRAMEWORK_HINTS = {
    "org.springframework.web": "Spring Web",
    "hateoas": "Spring HATEOAS",
    "data.jpa": "Spring Data JPA",
    "querydsl": "QueryDSL",
    "mapstruct": "MapStruct",
    "lombok": "Lombok",
    "security": "Spring Security",
    "redis": "Spring Data Redis",
    "validation": "Jakarta Validation",
}


def _guess_role(path: str) -> str:
    for needle, role in _ROLE_HINTS:
        if needle in path:
            return role
    return "source file"


class MockLLMClient:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.usage = UsageTracker(0.0, 0.0)  # cost is always zero in dry-run

    def structured(self, schema: Type[T], system: str, user: str) -> T:
        self.usage.record(0, 0)
        if schema is LLMFileInsight:
            return self._file_insight(user)  # type: ignore[return-value]
        if schema is ProjectOverview:
            return self._overview(user)  # type: ignore[return-value]
        # Fallback: construct with minimal placeholder values.
        return schema.model_construct()  # type: ignore[return-value]

    # --- heuristic builders -------------------------------------------------
    def _file_insight(self, user: str) -> LLMFileInsight:
        path = _extract_field(user, "File:")
        code = _extract_code(user)
        role = _guess_role(path)

        methods: list[MethodInfo] = []
        for m in _METHOD_RE.finditer(code):
            name = m.group("name")
            if name in {"if", "for", "while", "switch", "catch"}:
                continue
            ret = (m.group("ret") or "").strip()
            params = m.group("params").strip()
            vis = (m.group("vis") or "package").strip()
            methods.append(
                MethodInfo(
                    name=name,
                    signature=f"{vis} {ret} {name}({params})".strip(),
                    description=f"[dry-run heuristic] {name} in a {role}.",
                    parameters=[p.strip() for p in params.split(",") if p.strip()],
                    returns=ret or None,
                    visibility=vis,
                )
            )
            if len(methods) >= 12:
                break

        frameworks = sorted({name for hint, name in _FRAMEWORK_HINTS.items() if hint in code})
        return LLMFileInsight(
            summary=f"[dry-run] A {role} ({path.split('/')[-1]}).",
            role=role,
            key_methods=methods,
            external_dependencies=frameworks,
            noteworthy=(["Secured endpoints present"] if "@Secured" in code else []),
        )

    def _overview(self, user: str) -> ProjectOverview:
        return ProjectOverview(
            name="spring-rest-sakila (dry-run)",
            purpose="[dry-run heuristic overview] A Spring Boot REST API over the "
            "Sakila sample database. Run without --dry-run for a real LLM synthesis.",
            architecture_summary="Package-by-feature layered architecture "
            "(controller → service → repository → entity) with DTO mapping.",
            primary_language="Java",
            frameworks=["Spring Boot", "Spring Data JPA", "Spring HATEOAS", "QueryDSL", "MapStruct", "Lombok"],
            key_components=["catalog", "customer", "rental", "payment", "location", "auth"],
            entry_points=["REST controllers under /api/v1", "Spring Boot main application"],
            notable_patterns=["Layered architecture", "DTO/assembler pattern", "Custom repository fragments"],
            potential_risks=["Custom QueryDSL repositories may concentrate complexity"],
        )


def _extract_field(text: str, label: str) -> str:
    for line in text.splitlines():
        if line.startswith(label):
            return line[len(label):].strip()
    return "unknown"


def _extract_code(text: str) -> str:
    if "```" in text:
        return text.split("```", 2)[1] if text.count("```") >= 2 else text
    return text
