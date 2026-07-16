"""
Command-line interface.

Examples
--------
    # Analyze a cloned repo with Claude
    code-analyzer analyze --repo ./target-repo --out out/analysis.json

    # Clone + analyze in one step
    code-analyzer analyze --repo-url https://github.com/codejsha/spring-rest-sakila

    # Cheap smoke test with no API key
    code-analyzer analyze --repo ./target-repo --dry-run --max-files 15
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from .config import Settings
from .logging_setup import configure_logging
from .models import CodebaseAnalysis
from .pipeline import AnalysisPipeline

app = typer.Typer(add_completion=False, help="Analyze a codebase with an LLM into structured JSON.")
console = Console()


def _clone(repo_url: str, dest: Path) -> Path:
    console.print(f"[cyan]Cloning[/cyan] {repo_url} …")
    subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, str(dest)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return dest


def _render_summary(analysis: CodebaseAnalysis) -> None:
    s = analysis.statistics
    table = Table(title="Analysis summary", show_header=False, title_style="bold green")
    table.add_row("Project", analysis.overview.name)
    table.add_row("Primary language", analysis.overview.primary_language)
    table.add_row("Files analyzed", f"{s.files_analyzed} / {s.files_discovered}")
    table.add_row("From cache", str(s.files_from_cache))
    table.add_row("Source lines", f"{s.total_source_lines:,}")
    table.add_row("LLM calls", str(s.llm_calls))
    table.add_row(
        "Tokens (in/out)", f"{s.prompt_tokens:,} / {s.completion_tokens:,}"
    )
    table.add_row("Est. cost (USD)", f"${s.estimated_cost_usd:.4f}")
    table.add_row("Wall time", f"{s.wall_time_seconds:.1f}s")
    console.print(table)


@app.command()
def analyze(
    repo: Path | None = typer.Option(None, help="Path to a local codebase to analyze."),
    repo_url: str | None = typer.Option(None, help="Git URL to clone, then analyze."),
    out: Path = typer.Option(Path("out/analysis.json"), help="Output JSON path."),
    config: Path | None = typer.Option(None, help="Optional YAML config file."),
    model: str | None = typer.Option(None, help="Override the Claude model id."),
    max_files: int | None = typer.Option(None, help="Analyze at most N files (cheap runs)."),
    max_concurrency: int | None = typer.Option(None, help="Parallel LLM calls."),
    include_tests: bool = typer.Option(False, help="Include test sources."),
    no_cache: bool = typer.Option(False, help="Disable the content-hash cache."),
    dry_run: bool = typer.Option(False, help="Run with a heuristic stand-in; no API key needed."),
    log_level: str = typer.Option("INFO", help="Logging verbosity."),
) -> None:
    """Analyze a codebase and write structured JSON knowledge to disk."""
    load_dotenv()
    logger = configure_logging(log_level)

    overrides = dict(
        model=model,
        max_files=max_files,
        max_concurrency=max_concurrency,
        include_tests=include_tests or None,
        dry_run=dry_run or None,
        cache_enabled=(False if no_cache else None),
        log_level=log_level,
        output_path=out,
    )
    settings = Settings.load(config_file=config, **overrides)

    # Resolve the codebase location (local path or freshly cloned).
    tmp_dir: tempfile.TemporaryDirectory | None = None
    if repo_url:
        tmp_dir = tempfile.TemporaryDirectory(prefix="analyzer_")
        root = _clone(repo_url, Path(tmp_dir.name) / "repo")
        target_label = repo_url
    elif repo:
        root = repo
        target_label = str(repo)
    else:
        console.print("[red]Provide --repo <path> or --repo-url <git-url>.[/red]")
        raise typer.Exit(code=2)

    if not root.exists():
        console.print(f"[red]Path not found:[/red] {root}")
        raise typer.Exit(code=2)

    try:
        pipeline = AnalysisPipeline(settings)
        analysis = pipeline.run(root, target_label)
    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        raise typer.Exit(code=1) from exc
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(analysis.to_json())
    console.print(f"[green]✓ Wrote[/green] {out}")
    _render_summary(analysis)


@app.command()
def schema(out: Path | None = typer.Option(None, help="Write JSON Schema here.")) -> None:
    """Emit the JSON Schema of the output contract (for consumers/validators)."""
    import json

    schema_json = json.dumps(CodebaseAnalysis.model_json_schema(), indent=2)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(schema_json)
        console.print(f"[green]✓ Wrote schema to[/green] {out}")
    else:
        console.print_json(schema_json)


if __name__ == "__main__":
    app()
