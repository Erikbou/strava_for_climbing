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
    """Print instructions for applying the Supabase schema migrations."""
    migrations = P.REPO_ROOT / "supabase" / "migrations"
    typer.echo(
        "Supabase schema is applied out-of-band. Run each migration in order "
        "in the Supabase Dashboard → SQL Editor:\n"
    )
    for m in sorted(migrations.glob("*.sql")):
        typer.echo(f"  {m}")
    typer.echo("\nOr, if you use the Supabase CLI:\n  supabase db push")


@app.command("pull-raw")
def pull_raw(
    dest: Path = typer.Option(
        P.RAW_DIR, "--dest", help="Where to write the downloaded files."
    ),
    prefix: str = typer.Option("", "--prefix", help="Only pull keys with this prefix."),
) -> None:
    """Mirror the raw-uploads bucket to a local directory before running ingest.

    Use when climbers upload through the frontend (which writes to the raw
    bucket) and the pipeline operator wants to run ``strava ingest`` against
    those files. Existing local files are NOT overwritten; the file is
    skipped if a same-named file already exists.
    """
    from . import storage

    if not storage.bucket_configured("raw"):
        typer.echo(
            "SUPABASE_STORAGE_RAW_BUCKET is not set — nothing to pull.", err=True
        )
        raise typer.Exit(2)

    dest.mkdir(parents=True, exist_ok=True)
    keys = storage.list_keys("raw", prefix=prefix)
    pulled = skipped = 0
    for key in keys:
        local = dest / Path(key).name
        if local.exists():
            skipped += 1
            continue
        storage.download_file(key, local, kind="raw")
        typer.echo(f"pulled {key} -> {local}")
        pulled += 1
    typer.echo(f"pull-raw done: pulled={pulled} skipped={skipped} total={len(keys)}")


@app.command("signed-url")
def signed_url_cmd(
    key: str = typer.Argument(..., help="Object key inside the bucket."),
    kind: str = typer.Option(
        "normalized",
        "--kind",
        help="Which bucket: raw, normalized, or overlays.",
    ),
    expires_in: int = typer.Option(3600, "--expires-in", help="Seconds before expiry."),
) -> None:
    """Print a time-limited signed URL for a Storage object. Handy for poking at uploads."""
    from . import storage as storage_mod

    if kind not in ("raw", "normalized", "overlays"):
        typer.echo(f"--kind must be raw|normalized|overlays, got {kind!r}", err=True)
        raise typer.Exit(2)
    typer.echo(storage_mod.signed_url(key, kind=kind, expires_in=expires_in))  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: no cover
    app()
