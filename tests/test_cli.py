"""
CLI coverage via Typer's test runner — drives the real command wiring through
the dry-run path, so no API key or network is needed.
"""
from pathlib import Path

from typer.testing import CliRunner

from code_analyzer.cli import app

runner = CliRunner()


def _make_repo(tmp_path: Path) -> Path:
    pkg = tmp_path / "src/main/java/com/acme"
    pkg.mkdir(parents=True)
    (pkg / "App.java").write_text(
        "package com.acme;\npublic class App { public int add(int a,int b){return a+b;} }\n"
    )
    return tmp_path


def test_cli_analyze_dry_run(tmp_path):
    repo = _make_repo(tmp_path)
    out = tmp_path / "out.json"
    result = runner.invoke(
        app, ["analyze", "--repo", str(repo), "--dry-run", "--out", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert '"files"' in out.read_text()


def test_cli_analyze_requires_a_source():
    # Neither --repo nor --repo-url provided -> usage error, exit code 2.
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 2


def test_cli_schema_command():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    assert "properties" in result.output or "CodebaseAnalysis" in result.output
