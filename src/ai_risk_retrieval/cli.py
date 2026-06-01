"""CLI entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.table import Table

from .config import load_config, load_taxonomy
from .pipeline import run_full
from .storage import write_run

app = typer.Typer(
    add_completion=False,
    help="Intelligent retrieval of AI risk research papers.",
)
console = Console()


def _setup_logging(level: str) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level)),
    )


@app.command()
def run(
    config_path: Path = typer.Option(
        Path("config/local.yaml"), "--config", "-c", help="Path to config YAML."
    ),
    taxonomy_path: Path = typer.Option(
        Path("config/taxonomy.yaml"), "--taxonomy", "-t", help="Path to taxonomy YAML."
    ),
    subcategory: str | None = typer.Option(
        None, "--subcategory", "-s", help="Run a single subcategory by exact name."
    ),
    all_categories: bool = typer.Option(False, "--all", help="Run the entire taxonomy."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Load config and taxonomy but do not call sources/LLM."
    ),
) -> None:
    """Run the retrieval pipeline."""
    if not subcategory and not all_categories:
        console.print(
            "[yellow]Specify --subcategory or --all.[/yellow] "
            "Use --subcategory for testing; --all for production."
        )
        raise typer.Exit(2)

    config = load_config(config_path)
    taxonomy = load_taxonomy(taxonomy_path)
    _setup_logging(config.runtime.log_level)

    console.print(f"[green]Loaded taxonomy version {taxonomy.version}[/green]")
    console.print(
        f"  {len(taxonomy.categories)} categories, "
        f"{sum(len(c.subcategories) for c in taxonomy.categories)} subcategories"
    )

    if dry_run:
        _print_summary(taxonomy, subcategory)
        return

    result = asyncio.run(run_full(taxonomy, config, subcategory_filter=subcategory))
    path = write_run(result, config.output)

    console.print(f"\n[green]✓ Written:[/green] {path}")
    _print_results_table(result)


@app.command()
def show_taxonomy(
    taxonomy_path: Path = typer.Option(Path("config/taxonomy.yaml"), "--taxonomy", "-t"),
) -> None:
    """Print the loaded taxonomy as a tree."""
    taxonomy = load_taxonomy(taxonomy_path)
    for cat in taxonomy.categories:
        console.print(f"[bold cyan]{cat.name}[/bold cyan]  [dim]({cat.id})[/dim]")
        for sub in cat.subcategories:
            kw = f" [dim]+{len(sub.keywords)} kw[/dim]" if sub.keywords else ""
            console.print(f"  • {sub.name}{kw}")


@app.command()
def validate_config(
    config_path: Path = typer.Option(Path("config/local.yaml"), "--config", "-c"),
    taxonomy_path: Path = typer.Option(Path("config/taxonomy.yaml"), "--taxonomy", "-t"),
) -> None:
    """Validate config and taxonomy without running anything."""
    try:
        load_config(config_path)
        console.print(f"[green]✓ config OK:[/green] {config_path}")
    except Exception as e:
        console.print(f"[red]✗ config:[/red] {e}")
        raise typer.Exit(1) from e
    try:
        load_taxonomy(taxonomy_path)
        console.print(f"[green]✓ taxonomy OK:[/green] {taxonomy_path}")
    except Exception as e:
        console.print(f"[red]✗ taxonomy:[/red] {e}")
        raise typer.Exit(1) from e


def _print_summary(taxonomy, subcategory_filter: str | None) -> None:
    if subcategory_filter:
        found = taxonomy.find_subcategory(subcategory_filter)
        if found:
            cat, sub = found
            console.print(f"[yellow]Would run:[/yellow] {cat.name} → {sub.name}")
        else:
            console.print(f"[red]Subcategory not found:[/red] {subcategory_filter}")
    else:
        total = sum(len(c.subcategories) for c in taxonomy.categories)
        console.print(f"[yellow]Would run {total} subcategories[/yellow]")


def _print_results_table(result) -> None:
    table = Table(title="Retrieval results", show_lines=False)
    table.add_column("Subcategory", style="cyan")
    table.add_column("Selected", justify="right")
    table.add_column("Candidates", justify="right")
    table.add_column("Top score", justify="right")
    for r in result.results:
        top = max((sp.composite_score for sp in r.selected_papers), default=0.0)
        table.add_row(
            r.subcategory_name,
            str(len(r.selected_papers)),
            str(r.candidate_count),
            f"{top:.2f}",
        )
    console.print(table)


if __name__ == "__main__":
    app()
