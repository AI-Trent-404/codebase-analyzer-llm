"""
The 'map' step: turn one source file into a validated ``FileAnalysis``.

Token-limit handling lives here: if a file is larger than the per-file budget we
split it into chunks (on line boundaries), analyze each chunk, and merge the
results — deduplicating methods and unioning the qualitative fields. This is how
we analyze arbitrarily large files without ever exceeding the context window.
"""
from __future__ import annotations

import logging

from . import prompts
from .cache import InsightCache
from .complexity import analyze_source
from .config import Settings
from .ingestion import SourceFile
from .llm import LLMClient
from .models import FileAnalysis, LLMFileInsight, MethodInfo
from .tokens import split_to_budget

log = logging.getLogger("code_analyzer.extract")


def _merge_insights(parts: list[LLMFileInsight]) -> LLMFileInsight:
    """Combine chunk-level insights into one, deduping methods by signature."""
    if len(parts) == 1:
        return parts[0]

    seen_sigs: set[str] = set()
    methods: list[MethodInfo] = []
    for p in parts:
        for m in p.key_methods:
            if m.signature not in seen_sigs:
                seen_sigs.add(m.signature)
                methods.append(m)

    def _union(attr: str) -> list[str]:
        out: list[str] = []
        for p in parts:
            for item in getattr(p, attr):
                if item not in out:
                    out.append(item)
        return out

    return LLMFileInsight(
        summary=" ".join(p.summary for p in parts if p.summary)[:2000],
        role=parts[0].role,
        key_methods=methods,
        external_dependencies=_union("external_dependencies"),
        noteworthy=_union("noteworthy"),
    )


class FileExtractor:
    def __init__(self, client: LLMClient, cache: InsightCache, settings: Settings) -> None:
        self.client = client
        self.cache = cache
        self.settings = settings

    def extract(self, sf: SourceFile) -> FileAnalysis:
        code = sf.content()
        complexity = analyze_source(sf.rel_path, code)  # deterministic, no tokens

        cached = self.cache.get(code, self.settings.model)
        if cached is not None:
            return self._assemble(sf, cached, complexity, chunked=False, cached=True)

        chunks = split_to_budget(code, self.settings.chunk_token_budget)
        chunked = len(chunks) > 1

        if not chunked:
            insight = self.client.structured(
                LLMFileInsight,
                prompts.FILE_SYSTEM,
                prompts.file_user_prompt(sf.rel_path, sf.language, code),
            )
        else:
            log.info("Splitting %s into %d chunks (token budget)", sf.rel_path, len(chunks))
            parts = [
                self.client.structured(
                    LLMFileInsight,
                    prompts.FILE_SYSTEM,
                    prompts.file_chunk_prompt(
                        sf.rel_path, sf.language, i + 1, len(chunks), chunk
                    ),
                )
                for i, chunk in enumerate(chunks)
            ]
            insight = _merge_insights(parts)

        self.cache.put(code, self.settings.model, insight)
        return self._assemble(sf, insight, complexity, chunked=chunked, cached=False)

    @staticmethod
    def _assemble(sf, insight, complexity, chunked, cached) -> FileAnalysis:
        return FileAnalysis(
            path=sf.rel_path,
            language=sf.language,
            package=sf.package,
            size_bytes=sf.size_bytes,
            complexity=complexity,
            insight=insight,
            analyzed_with_chunking=chunked,
            from_cache=cached,
        )
