"""
Orchestration: tie ingestion → per-file extraction (map) → overview (reduce)
into a single, observable run.

Concurrency: per-file extraction is I/O-bound (network calls to the LLM), so a
thread pool gives near-linear speedups up to the configured concurrency. The
``UsageTracker`` and cache are thread-safe, so aggregation of tokens/cost is
correct under parallelism.
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from .aggregator import OverviewAggregator
from .cache import InsightCache
from .config import Settings
from .extractors import FileExtractor
from .ingestion import SourceFile, discover, language_breakdown
from .llm import LLMClient
from .models import (
    AnalysisMetadata,
    CodebaseAnalysis,
    FileAnalysis,
    LanguageStat,
    RunStatistics,
)

log = logging.getLogger("code_analyzer.pipeline")


class AnalysisPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.dry_run:
            from .mock import MockLLMClient

            log.warning("Running in [bold]dry-run[/bold] mode: heuristic stand-in, no LLM calls.")
            self.client = MockLLMClient(settings)
            settings.cache_enabled = False  # heuristic output should not poison the real cache
        else:
            self.client = LLMClient(settings)
        self.cache = InsightCache(settings.cache_dir, settings.cache_enabled)
        self.extractor = FileExtractor(self.client, self.cache, settings)
        self.aggregator = OverviewAggregator(self.client, settings)

    def run(self, root: Path, target_label: str) -> CodebaseAnalysis:
        start = time.time()
        files = discover(root, self.settings)
        log.info("Discovered [bold]%d[/bold] source files to analyze.", len(files))
        if not files:
            raise RuntimeError(
                f"No source files matched under {root}. Check --repo path, "
                "extensions, and exclude rules."
            )

        analyses = self._extract_all(files)
        analyses.sort(key=lambda fa: fa.path)

        log.info("Synthesizing project overview (reduce step)…")
        overview = self.aggregator.build(target_label, analyses)

        stats = self._build_stats(files, analyses, time.time() - start)
        return CodebaseAnalysis(
            metadata=AnalysisMetadata(target=target_label, model=self.settings.model),
            overview=overview,
            statistics=stats,
            files=analyses,
        )

    def _extract_all(self, files: list[SourceFile]) -> list[FileAnalysis]:
        results: list[FileAnalysis] = []
        columns = [
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
        ]
        with Progress(*columns) as progress:
            task = progress.add_task("Analyzing files", total=len(files))
            with ThreadPoolExecutor(max_workers=self.settings.max_concurrency) as pool:
                futures = {pool.submit(self._safe_extract, sf): sf for sf in files}
                for fut in as_completed(futures):
                    fa = fut.result()
                    if fa is not None:
                        results.append(fa)
                    progress.advance(task)
        return results

    def _safe_extract(self, sf: SourceFile) -> FileAnalysis | None:
        try:
            return self.extractor.extract(sf)
        except Exception as exc:  # never let one bad file kill the whole run
            log.warning("Skipping %s: %s", sf.rel_path, exc)
            return None

    def _build_stats(
        self, files: list[SourceFile], analyses: list[FileAnalysis], wall: float
    ) -> RunStatistics:
        breakdown = language_breakdown(files)
        languages = [
            LanguageStat(language=lang, file_count=v["file_count"], line_count=v["line_count"])
            for lang, v in sorted(breakdown.items())
        ]
        from_cache = sum(1 for a in analyses if a.from_cache)
        return RunStatistics(
            files_discovered=len(files),
            files_analyzed=len(analyses),
            files_skipped=len(files) - len(analyses),
            files_from_cache=from_cache,
            total_source_lines=sum(v["line_count"] for v in breakdown.values()),
            languages=languages,
            llm_calls=self.client.usage.calls,
            prompt_tokens=self.client.usage.prompt_tokens,
            completion_tokens=self.client.usage.completion_tokens,
            estimated_cost_usd=self.client.usage.estimated_cost_usd,
            wall_time_seconds=round(wall, 2),
        )
