from pathlib import Path

from code_analyzer.config import Settings
from code_analyzer.ingestion import discover, language_breakdown


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src/main/java/com/acme/web").mkdir(parents=True)
    (tmp_path / "src/main/java/com/acme/web/FooController.java").write_text(
        "package com.acme.web;\npublic class FooController { public int ping(){return 1;} }\n"
    )
    (tmp_path / "src/test/java/com/acme/web").mkdir(parents=True)
    (tmp_path / "src/test/java/com/acme/web/FooControllerTest.java").write_text(
        "class FooControllerTest {}\n"
    )
    (tmp_path / "build").mkdir()
    (tmp_path / "build/Generated.java").write_text("class Generated {}\n")
    (tmp_path / "README.md").write_text("# not source\n")
    return tmp_path


def test_discover_filters_tests_build_and_nonsource(tmp_path):
    root = _make_repo(tmp_path)
    settings = Settings(anthropic_api_key="x")
    files = discover(root, settings)
    rels = {f.rel_path for f in files}
    assert "src/main/java/com/acme/web/FooController.java" in rels
    assert not any("test" in r.lower() for r in rels)      # tests excluded
    assert not any(r.startswith("build/") for r in rels)   # build excluded
    assert not any(r.endswith(".md") for r in rels)        # non-source excluded


def test_include_tests_flag(tmp_path):
    root = _make_repo(tmp_path)
    settings = Settings(anthropic_api_key="x", include_tests=True)
    files = discover(root, settings)
    assert any("Test.java" in f.rel_path for f in files)


def test_package_derivation_and_breakdown(tmp_path):
    root = _make_repo(tmp_path)
    settings = Settings(anthropic_api_key="x")
    files = discover(root, settings)
    foo = next(f for f in files if f.rel_path.endswith("FooController.java"))
    assert foo.package == "com.acme.web"
    assert foo.language == "Java"
    breakdown = language_breakdown(files)
    assert breakdown["Java"]["file_count"] == 1


def test_max_files_cap(tmp_path):
    root = _make_repo(tmp_path)
    settings = Settings(anthropic_api_key="x", max_files=0)
    assert discover(root, settings) == []
