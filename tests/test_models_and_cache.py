from pathlib import Path

from code_analyzer.cache import InsightCache
from code_analyzer.models import (
    AnalysisMetadata,
    CodebaseAnalysis,
    FileAnalysis,
    LLMFileInsight,
    MethodInfo,
    ProjectOverview,
    RunStatistics,
)


def _insight() -> LLMFileInsight:
    return LLMFileInsight(
        summary="A REST controller.",
        role="REST controller",
        key_methods=[MethodInfo(name="getFilm", signature="public FilmDto getFilm(int id)", description="Fetch a film.")],
        external_dependencies=["Spring Web"],
        noteworthy=["Secured"],
    )


def test_top_level_serialization_roundtrip():
    analysis = CodebaseAnalysis(
        metadata=AnalysisMetadata(target="x", model="claude-sonnet-4-20250514"),
        overview=ProjectOverview(
            name="demo", purpose="p", architecture_summary="a", primary_language="Java"
        ),
        statistics=RunStatistics(),
        files=[
            FileAnalysis(path="A.java", language="Java", insight=_insight())
        ],
    )
    js = analysis.to_json()
    restored = CodebaseAnalysis.model_validate_json(js)
    assert restored.files[0].insight.key_methods[0].name == "getFilm"
    assert restored.metadata.schema_version == "1.0"


def test_cache_hit_and_content_addressing(tmp_path: Path):
    cache = InsightCache(tmp_path / "c", enabled=True)
    content = "class A {}"
    assert cache.get(content, "m") is None      # miss
    cache.put(content, "m", _insight())
    assert cache.get(content, "m") is not None   # hit
    assert cache.get(content + " ", "m") is None  # different content -> miss
    assert cache.get(content, "other-model") is None  # model change invalidates


def test_cache_disabled_is_noop(tmp_path: Path):
    cache = InsightCache(tmp_path / "c", enabled=False)
    cache.put("x", "m", _insight())
    assert cache.get("x", "m") is None
