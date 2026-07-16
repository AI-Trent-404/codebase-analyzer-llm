"""
Codebase ingestion: discover and load source files efficiently.

Responsibilities
----------------
* Walk a local directory (the repo is cloned first — see ``scripts/clone_target.sh``
  or the ``--repo-url`` CLI option).
* Filter aggressively so we only spend tokens on files that matter: by extension,
  by excluded directory, by size, and (optionally) by skipping test sources.
* Attach lightweight metadata (language, package, size) used downstream.

Efficiency note: filtering happens *before* any file is read into memory or sent
to the LLM. This is the cheapest and most important lever for staying within
token and cost budgets.
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .config import Settings

_LANGUAGE_BY_EXT = {
    ".java": "Java", ".kt": "Kotlin", ".py": "Python", ".js": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript", ".go": "Go",
    ".rb": "Ruby", ".cs": "C#", ".cpp": "C++", ".c": "C", ".h": "C/C++ header",
    ".hpp": "C++ header", ".rs": "Rust", ".php": "PHP", ".scala": "Scala",
    ".swift": "Swift",
}


@dataclass
class SourceFile:
    path: Path                 # absolute path on disk
    rel_path: str              # repo-relative path (stable identifier)
    language: str
    size_bytes: int
    package: str | None = None
    _content: str | None = field(default=None, repr=False)

    def content(self) -> str:
        if self._content is None:
            self._content = self.path.read_text(encoding="utf-8", errors="replace")
        return self._content

    def line_count(self) -> int:
        return self.content().count("\n") + 1


def _looks_like_test(rel_path: str) -> bool:
    lowered = rel_path.lower()
    return (
        "/test/" in lowered
        or lowered.endswith("test.java")
        or lowered.endswith("tests.java")
        or lowered.endswith("_test.py")
        or lowered.endswith("test.py")
        or ".test." in lowered
        or ".spec." in lowered
    )


def _derive_package(rel_path: str, language: str) -> str | None:
    """
    Best-effort logical package: for JVM languages under ``src/main/<lang>``,
    return the dotted package; otherwise the parent directory.
    """
    p = rel_path.replace("\\", "/")
    for marker in ("src/main/java/", "src/main/kotlin/", "src/"):
        if marker in p:
            pkg_path = p.split(marker, 1)[1]
            parent = "/".join(pkg_path.split("/")[:-1])
            return parent.replace("/", ".") if parent else None
    parent = "/".join(p.split("/")[:-1])
    return parent or None


def discover(root: Path, settings: Settings) -> list[SourceFile]:
    """Return the filtered, ordered list of source files to analyze."""
    root = root.resolve()
    exclude_dirs = set(settings.exclude_dirs)
    if settings.include_tests:
        exclude_dirs.discard("test")
        exclude_dirs.discard("tests")

    allowed_ext = set(settings.source_extensions)
    found: list[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded directories in-place so os.walk never descends into them.
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for name in filenames:
            ext = Path(name).suffix.lower()
            if ext not in allowed_ext:
                continue
            abs_path = Path(dirpath) / name
            try:
                size = abs_path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > settings.max_file_bytes:
                continue

            rel = os.path.relpath(abs_path, root).replace("\\", "/")
            if not settings.include_tests and _looks_like_test(rel):
                continue

            language = _LANGUAGE_BY_EXT.get(ext, ext.lstrip("."))
            found.append(
                SourceFile(
                    path=abs_path,
                    rel_path=rel,
                    language=language,
                    size_bytes=size,
                    package=_derive_package(rel, language),
                )
            )

    # Deterministic ordering keeps runs reproducible and diffs stable.
    found.sort(key=lambda f: f.rel_path)
    if settings.max_files is not None:
        found = found[: settings.max_files]
    return found


def language_breakdown(files: Iterable[SourceFile]) -> dict[str, dict[str, int]]:
    stats: dict[str, dict[str, int]] = {}
    for f in files:
        entry = stats.setdefault(f.language, {"file_count": 0, "line_count": 0})
        entry["file_count"] += 1
        entry["line_count"] += f.line_count()
    return stats
