"""
The 'reduce' step: synthesize a project-wide ``ProjectOverview`` from per-file
insights.

Token-limit strategy (hierarchical map-reduce):
    Sending every file's full analysis to one prompt would blow the context window
    on a large repo. Instead we build compact one-line digests, and if the combined
    digest still exceeds the input budget we first summarize *per package* and then
    combine those package summaries. This keeps the final synthesis call safely
    within limits regardless of repo size.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import List

from . import prompts
from .config import Settings
from .llm import LLMClient
from .models import FileAnalysis, ProjectOverview
from .tokens import count_tokens

log = logging.getLogger("code_analyzer.aggregate")


def _digest_line(fa: FileAnalysis) -> str:
    return f"[{fa.insight.role}] {fa.path} — {fa.insight.summary}"


def _package_tree(files: List[FileAnalysis]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for fa in files:
        counts[fa.package or "(root)"] += 1
    lines = [f"  {pkg} ({n} files)" for pkg, n in sorted(counts.items())]
    return "\n".join(lines)


class OverviewAggregator:
    def __init__(self, client: LLMClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    def build(self, target: str, files: List[FileAnalysis]) -> ProjectOverview:
        tree = _package_tree(files)
        digests = [_digest_line(fa) for fa in files]
        combined = "\n".join(digests)

        # Budget for the digest portion of the reduce prompt.
        budget = self.settings.max_input_tokens - 4000
        if count_tokens(combined) > budget:
            log.info("Digest exceeds budget; summarizing per-package first (hierarchical reduce).")
            combined = self._hierarchical_digest(files, budget)

        return self.client.structured(
            ProjectOverview,
            prompts.OVERVIEW_SYSTEM,
            prompts.overview_user_prompt(target, tree, combined),
        )

    def _hierarchical_digest(self, files: List[FileAnalysis], budget: int) -> str:
        """Collapse files into per-package digests until the whole thing fits."""
        by_pkg: dict[str, List[FileAnalysis]] = defaultdict(list)
        for fa in files:
            by_pkg[fa.package or "(root)"].append(fa)

        package_summaries: List[str] = []
        for pkg, pkg_files in sorted(by_pkg.items()):
            pkg_digest = "\n".join(_digest_line(fa) for fa in pkg_files)
            summary = self.client.structured(
                ProjectOverview,  # reuse schema; we only keep the prose fields
                prompts.PARTIAL_OVERVIEW_SYSTEM,
                f"Package: {pkg}\n\nFiles:\n{pkg_digest}\n\n"
                "Summarize this package's responsibility and key components.",
            )
            package_summaries.append(
                f"[package {pkg}] {summary.purpose} "
                f"Components: {', '.join(summary.key_components[:6])}"
            )

        combined = "\n".join(package_summaries)
        # In the (rare) event package-level is still too big, truncate defensively.
        while count_tokens(combined) > budget and len(package_summaries) > 1:
            package_summaries = package_summaries[: len(package_summaries) // 2 + 1]
            combined = "\n".join(package_summaries) + "\n… (truncated for token budget)"
        return combined
