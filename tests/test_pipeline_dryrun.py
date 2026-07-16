"""
End-to-end and unit coverage for the orchestration path — exercised via the
dry-run stand-in so it needs no API key or network. This is what lets CI cover
the pipeline, extractor merge logic, aggregator (including the hierarchical
reduce), the mock client, and the usage tracker.
"""
from pathlib import Path

from code_analyzer.config import Settings
from code_analyzer.extractors import _merge_insights
from code_analyzer.llm import UsageTracker
from code_analyzer.mock import MockLLMClient
from code_analyzer.models import LLMFileInsight, MethodInfo, ProjectOverview
from code_analyzer.pipeline import AnalysisPipeline


def _make_repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src/main/java/com/acme/web"
    pkg.mkdir(parents=True)
    (pkg / "FooController.java").write_text(
        "package com.acme.web;\n"
        "public class FooController {\n"
        "  public int ping() { return 1; }\n"
        "  public String hello(String name) { return name; }\n"
        "}\n"
    )
    (tmp_path / "src/main/java/com/acme").joinpath("App.java").write_text(
        "package com.acme;\npublic class App { public static void main(String[] a){} }\n"
    )
    return tmp_path


def test_pipeline_end_to_end_dry_run(tmp_path):
    root = _make_repo(tmp_path)
    settings = Settings(dry_run=True, max_concurrency=2)
    result = AnalysisPipeline(settings).run(root, "acme/demo")

    assert result.statistics.files_analyzed == 2
    assert result.metadata.target == "acme/demo"
    assert result.overview.primary_language == "Java"
    # every file produced a record with its deterministic + heuristic parts
    paths = {f.path for f in result.files}
    assert any(p.endswith("FooController.java") for p in paths)
    foo = next(f for f in result.files if f.path.endswith("FooController.java"))
    assert foo.complexity.function_count >= 2          # from lizard, not the mock
    assert any(m.name == "ping" for m in foo.insight.key_methods)


def test_pipeline_triggers_hierarchical_reduce(tmp_path):
    # A tiny input budget forces the reduce step down the per-package path.
    root = _make_repo(tmp_path)
    settings = Settings(dry_run=True, max_input_tokens=10)
    result = AnalysisPipeline(settings).run(root, "acme/demo")
    assert result.overview.name  # synthesis still succeeds via the hierarchical fold


def test_merge_insights_dedups_and_unions():
    m1 = MethodInfo(name="x", signature="sig-1", description="d")
    m2 = MethodInfo(name="y", signature="sig-2", description="d")
    part_a = LLMFileInsight(summary="a", role="controller", key_methods=[m1],
                            external_dependencies=["A"], noteworthy=["n1"])
    part_b = LLMFileInsight(summary="b", role="controller", key_methods=[m1, m2],
                            external_dependencies=["A", "B"], noteworthy=["n2"])
    merged = _merge_insights([part_a, part_b])
    assert len(merged.key_methods) == 2                 # deduped by signature
    assert merged.external_dependencies == ["A", "B"]   # unioned, order-preserving
    assert set(merged.noteworthy) == {"n1", "n2"}


def test_usage_tracker_cost_math():
    u = UsageTracker(price_in=3.0, price_out=15.0)
    u.record(1_000_000, 0)
    assert u.estimated_cost_usd == 3.0
    u.record(0, 1_000_000)
    assert u.estimated_cost_usd == 18.0
    assert u.calls == 2


def test_mock_client_parses_methods_and_overview():
    c = MockLLMClient(settings=None)
    user = "File: web/FooController.java\n```\npublic int ping() { return 1; }\n```"
    insight = c.structured(LLMFileInsight, "sys", user)
    assert insight.role == "REST controller"
    assert any(m.name == "ping" for m in insight.key_methods)
    overview = c.structured(ProjectOverview, "sys", "anything")
    assert overview.primary_language == "Java"
