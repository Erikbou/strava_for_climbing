"""Typer CLI — single entry point. ``strava ingest``, ``strava process``, ``strava demo``."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import typer

from . import ingest as ingest_mod
from . import orchestrate
from .config import paths as P

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
    help="Strava-for-climbing pipeline CLI.",
)


@app.callback()
def _root(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )


@app.command()
def ingest(
    raw_dir: Path = typer.Option(P.RAW_DIR, "--raw-dir", help="Directory of source videos."),
    dry_run: bool = typer.Option(False, "--dry-run", help="List videos but do not normalize."),
) -> None:
    """Normalize raw videos via ffmpeg, dedup by source SHA-256, write ingest_report.json."""
    if not ingest_mod.have_ffmpeg():
        typer.echo("ffmpeg/ffprobe not found on PATH", err=True)
        raise typer.Exit(2)
    if dry_run:
        for src in sorted(raw_dir.iterdir()):
            if src.suffix.lower() in ingest_mod.VIDEO_EXTENSIONS:
                typer.echo(f"would ingest: {src}")
        return
    stats = ingest_mod.ingest_directory(raw_dir)
    typer.echo(f"ingest done: {stats}")


@app.command()
def process(
    force: bool = typer.Option(False, "--force", help="Re-process even if manifest matches."),
) -> None:
    """Run pose -> boundaries -> metrics -> overlay over all successfully ingested videos."""
    from .config import runtime as R

    stats = orchestrate.process_all(force=force)
    typer.echo(f"process done: {stats}")
    if not R.stage2_enabled():
        typer.echo("(stage 2 disabled via STRAVA_CLIMBING_DISABLE_STAGE2)")


@app.command()
def demo(
    port: int = typer.Option(8501, "--port"),
) -> None:
    """Launch the Streamlit dashboard. Sets STRAVA_CLIMBING_MODE=demo for read-only UX."""
    import os

    env = os.environ.copy()
    env["STRAVA_CLIMBING_MODE"] = "demo"
    typer.echo("demo mode: read-only against Supabase")
    app_file = P.REPO_ROOT / "apps" / "streamlit" / "main.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_file), "--server.port", str(port)]
    subprocess.run(cmd, env=env, check=False)


@app.command("verify-demo")
def verify_demo() -> None:
    """Walk the DB and stat() every referenced overlay/frame. Run before plugging in the projector."""
    missing = orchestrate.verify_demo()
    if not missing:
        typer.echo("verify-demo: OK — all referenced files exist")
        return
    typer.echo(f"verify-demo: {len(missing)} missing files:", err=True)
    for p in missing:
        typer.echo(f"  - {p}", err=True)
    raise typer.Exit(1)


@app.command("init-db")
def init_db_cmd() -> None:
    """Print instructions for applying the Supabase schema migration."""
    migration = P.REPO_ROOT / "supabase" / "migrations" / "0001_initial_schema.sql"
    typer.echo(
        "Supabase schema is applied out-of-band. Paste this file into the "
        "Supabase Dashboard → SQL Editor and run it:\n"
        f"  {migration}\n"
        "Or, if you use the Supabase CLI:\n"
        "  supabase db push"
    )


if __name__ == "__main__":  # pragma: no cover
    app()
