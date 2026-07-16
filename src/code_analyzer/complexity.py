"""
Deterministic complexity metrics via `lizard`.

Design decision (Principal-level): *do not* ask the LLM to count lines or compute
cyclomatic complexity. Those are exact, deterministic facts that a static analyzer
produces for free and reproducibly. Reserving the LLM for genuine *comprehension*
(intent, roles, patterns) is cheaper, faster, and more trustworthy.

`lizard` is language-agnostic and understands Java/Kotlin/Python/C-family/Go and
more, so this works across polyglot repos.
"""
from __future__ import annotations

from .models import ComplexityBand, ComplexityMetrics


def _band(avg: float, mx: int) -> ComplexityBand:
    if mx >= 20 or avg >= 10:
        return ComplexityBand.VERY_HIGH
    if mx >= 11 or avg >= 6:
        return ComplexityBand.HIGH
    if mx >= 6 or avg >= 3:
        return ComplexityBand.MODERATE
    return ComplexityBand.LOW


def analyze_source(path: str, code: str) -> ComplexityMetrics:
    """
    Compute metrics for a single file. Falls back to zeros (LOW band) if lizard
    can't parse the language, so the pipeline never breaks on an odd file type.
    """
    try:
        import lizard
    except Exception:  # pragma: no cover - dependency missing
        return ComplexityMetrics()

    try:
        info = lizard.analyze_file.analyze_source_code(path, code)
    except Exception:
        return ComplexityMetrics()

    functions = info.function_list
    if not functions:
        return ComplexityMetrics(nloc=info.nloc, function_count=0, band=ComplexityBand.LOW)

    ccns = [fn.cyclomatic_complexity for fn in functions]
    avg = sum(ccns) / len(ccns)
    mx = max(ccns)
    most_complex = max(functions, key=lambda fn: fn.cyclomatic_complexity)

    return ComplexityMetrics(
        nloc=info.nloc,
        function_count=len(functions),
        average_cyclomatic_complexity=round(avg, 2),
        max_cyclomatic_complexity=mx,
        most_complex_function=most_complex.name,
        band=_band(avg, mx),
    )
