# Stage 4: High-Performance Execution

## Executive Summary

This document covers the technical execution plan for handling 18,000+ Spotify tracks efficiently and safely. We address rate limit management, batch operations, checkpoint/resume mechanisms, and a comprehensive "dry run" safety protocol before any write operations.

---

## Table of Contents

1. [Spotify API Constraints](#spotify-api-constraints)
2. [Fetching Strategy](#fetching-strategy)
3. [Writing Strategy](#writing-strategy)
4. [Dry Run Safety Protocol](#dry-run-safety-protocol)
5. [Local Setup](#local-setup)
6. [Complete Implementation](#complete-implementation)

---

## Spotify API Constraints

### Rate Limits

Spotify's API uses a rolling window rate limit:

| Limit Type | Value | Recovery |
|------------|-------|----------|
| Requests per 30 seconds | ~30-50 (varies) | Wait for `Retry-After` header |
| HTTP 429 Response | Too Many Requests | Mandatory pause |
| Token Expiry | 1 hour | Automatic refresh via spotipy |

### Endpoint-Specific Limits

| Endpoint | Max per Request | Notes |
|----------|-----------------|-------|
| Get Playlist Tracks | 100 items | Pagination required |
| Get Audio Features | 100 IDs | Batch endpoint |
| Add Items to Playlist | 100 URIs | Batch endpoint |
| Get Artist | 50 IDs | Batch endpoint |

### Our Workload Estimate

```
Playlist 1: ~9,000 entries → 90 API calls
Playlist 2: ~9,000 entries → 90 API calls
Audio Features: ~15,000 unique tracks → 150 API calls
─────────────────────────────────────────────────
Total Read Operations: ~330 API calls

New Playlist Creation: 1 API call
Add Tracks: ~15,000 / 100 = 150 API calls
─────────────────────────────────────────────────
Total Write Operations: ~151 API calls

GRAND TOTAL: ~481 API calls
```

At ~30 requests per 30 seconds without hitting limits:
- **Best case**: ~8 minutes
- **With rate limit pauses**: ~15-20 minutes

---

## Fetching Strategy

### Spotipy's Built-in Rate Limit Handling

```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# spotipy automatically handles 429 errors with exponential backoff
sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id="...",
        client_secret="...",
        redirect_uri="http://localhost:8888/callback",
        scope="playlist-read-private playlist-modify-public playlist-modify-private"
    ),
    retries=5,  # Number of retries on 429
    status_retries=3,  # Retries on 5xx errors
    backoff_factor=0.5  # Exponential backoff multiplier
)
```

### Fetch All Tracks with Checkpointing

```python
import json
from pathlib import Path
from datetime import datetime
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

def fetch_playlist_tracks(sp, playlist_id: str, checkpoint_dir: str = "data/checkpoints"):
    """
    Fetch all tracks from a playlist with checkpoint support.

    Args:
        sp: Authenticated Spotipy client
        playlist_id: Spotify playlist ID
        checkpoint_dir: Directory to store checkpoints

    Returns:
        List of track items
    """
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    checkpoint_file = checkpoint_path / f"playlist_{playlist_id}.json"

    # Try to resume from checkpoint
    all_tracks = []
    start_offset = 0

    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            all_tracks = checkpoint_data.get('tracks', [])
            start_offset = checkpoint_data.get('next_offset', 0)
            print(f"Resuming from checkpoint: {len(all_tracks)} tracks already fetched")

    # Get total count first
    initial = sp.playlist_tracks(playlist_id, limit=1)
    total = initial['total']

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    ) as progress:
        task = progress.add_task(
            f"Fetching playlist {playlist_id[:8]}...",
            total=total,
            completed=len(all_tracks)
        )

        offset = start_offset
        while offset < total:
            try:
                response = sp.playlist_tracks(playlist_id, offset=offset, limit=100)
                batch = response['items']
                all_tracks.extend(batch)

                # Update progress
                progress.update(task, completed=len(all_tracks))

                # Checkpoint every 500 tracks
                if len(all_tracks) % 500 < 100:  # Just crossed a 500 boundary
                    save_checkpoint(checkpoint_file, all_tracks, offset + 100)

                offset += 100

            except Exception as e:
                # On any error, save checkpoint and re-raise
                save_checkpoint(checkpoint_file, all_tracks, offset)
                raise e

    # Final save and cleanup
    save_checkpoint(checkpoint_file, all_tracks, offset, final=True)

    return all_tracks


def save_checkpoint(filepath: Path, tracks: list, next_offset: int, final: bool = False):
    """Save progress checkpoint."""
    data = {
        'tracks': tracks,
        'next_offset': next_offset,
        'timestamp': datetime.now().isoformat(),
        'complete': final
    }
    with open(filepath, 'w') as f:
        json.dump(data, f)
```

### Fetch Audio Features in Batches

```python
def fetch_audio_features(sp, track_ids: list[str], checkpoint_dir: str = "data/checkpoints"):
    """
    Fetch audio features for multiple tracks with checkpointing.

    Args:
        sp: Authenticated Spotipy client
        track_ids: List of Spotify track IDs
        checkpoint_dir: Directory for checkpoints

    Returns:
        Dict mapping track_id to audio features
    """
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_file = checkpoint_path / "audio_features.json"

    # Resume from checkpoint
    features = {}
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            features = checkpoint_data.get('features', {})
            print(f"Resuming: {len(features)} tracks already have features")

    # Filter out already-fetched IDs
    remaining_ids = [tid for tid in track_ids if tid not in features]

    if not remaining_ids:
        print("All audio features already fetched!")
        return features

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Fetching audio features...", total=len(remaining_ids))

        # Batch requests (100 IDs max per request)
        for i in range(0, len(remaining_ids), 100):
            batch = remaining_ids[i:i+100]

            try:
                response = sp.audio_features(batch)

                # Map results (some tracks may return None if not available)
                for track_id, feature in zip(batch, response):
                    if feature:
                        features[track_id] = feature

                progress.update(task, advance=len(batch))

                # Checkpoint every 500 tracks
                if len(features) % 500 < 100:
                    with open(checkpoint_file, 'w') as f:
                        json.dump({'features': features, 'timestamp': datetime.now().isoformat()}, f)

            except Exception as e:
                # Save checkpoint on error
                with open(checkpoint_file, 'w') as f:
                    json.dump({'features': features, 'timestamp': datetime.now().isoformat()}, f)
                raise e

    # Final save
    with open(checkpoint_file, 'w') as f:
        json.dump({'features': features, 'complete': True, 'timestamp': datetime.now().isoformat()}, f)

    return features
```

### Handling 429 Errors Explicitly (Beyond spotipy's auto-retry)

```python
import time
from spotipy.exceptions import SpotifyException

def robust_api_call(func, *args, max_retries=5, **kwargs):
    """
    Wrapper for API calls with explicit 429 handling.

    Use this for critical operations where you want more control
    than spotipy's built-in retry.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 429:
                # Get retry-after header (spotipy includes it in the exception)
                retry_after = int(e.headers.get('Retry-After', 5))
                print(f"Rate limited. Waiting {retry_after} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_after + 1)  # Add 1 second buffer
            elif e.http_status >= 500:
                # Server error - exponential backoff
                wait_time = (2 ** attempt) + 1
                print(f"Server error {e.http_status}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise  # Re-raise non-retryable errors
        except Exception as e:
            # Network errors, etc.
            wait_time = (2 ** attempt) + 1
            print(f"Error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise Exception(f"Max retries ({max_retries}) exceeded")
```

---

## Writing Strategy

### Creating the Master Playlist

```python
def create_master_playlist(sp, user_id: str, name: str, description: str = None):
    """
    Create a new playlist for the deduplicated tracks.

    Args:
        sp: Authenticated Spotipy client
        user_id: Spotify user ID
        name: Playlist name
        description: Optional description

    Returns:
        Created playlist object
    """
    desc = description or f"Master playlist created on {datetime.now().strftime('%Y-%m-%d')}"

    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,  # Start as private for safety
        description=desc
    )

    print(f"Created playlist: {playlist['name']} ({playlist['id']})")
    return playlist
```

### Adding Tracks in Batches

```python
def add_tracks_to_playlist(
    sp,
    playlist_id: str,
    track_ids: list[str],
    checkpoint_dir: str = "data/checkpoints"
):
    """
    Add tracks to playlist in batches of 100 with checkpointing.

    Args:
        sp: Authenticated Spotipy client
        playlist_id: Target playlist ID
        track_ids: List of track IDs to add
        checkpoint_dir: Directory for checkpoints

    Returns:
        Number of tracks added
    """
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_file = checkpoint_path / f"write_playlist_{playlist_id}.json"

    # Resume from checkpoint
    start_index = 0
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            start_index = checkpoint_data.get('tracks_added', 0)
            print(f"Resuming: {start_index} tracks already added")

    # Convert IDs to URIs if needed
    uris = [f"spotify:track:{tid}" if not tid.startswith("spotify:") else tid for tid in track_ids]
    remaining_uris = uris[start_index:]

    if not remaining_uris:
        print("All tracks already added!")
        return len(track_ids)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    ) as progress:
        task = progress.add_task("Adding tracks to playlist...", total=len(track_ids), completed=start_index)

        tracks_added = start_index
        for i in range(0, len(remaining_uris), 100):
            batch = remaining_uris[i:i+100]

            try:
                sp.playlist_add_items(playlist_id, batch)
                tracks_added += len(batch)
                progress.update(task, completed=tracks_added)

                # Checkpoint every 500 tracks
                if tracks_added % 500 < 100:
                    with open(checkpoint_file, 'w') as f:
                        json.dump({
                            'playlist_id': playlist_id,
                            'tracks_added': tracks_added,
                            'timestamp': datetime.now().isoformat()
                        }, f)

                # Small delay to be nice to the API
                time.sleep(0.1)

            except Exception as e:
                # Save checkpoint on error
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'playlist_id': playlist_id,
                        'tracks_added': tracks_added,
                        'timestamp': datetime.now().isoformat(),
                        'error': str(e)
                    }, f)
                raise e

    # Final checkpoint
    with open(checkpoint_file, 'w') as f:
        json.dump({
            'playlist_id': playlist_id,
            'tracks_added': tracks_added,
            'complete': True,
            'timestamp': datetime.now().isoformat()
        }, f)

    return tracks_added
```

---

## Dry Run Safety Protocol

### The Dry Run Philosophy

**NEVER modify Spotify data without user confirmation.**

Before any write operation:
1. Show exactly what will happen
2. Display statistics and impact
3. Require explicit "yes" confirmation
4. Provide a preview export

### Dry Run Implementation

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()

def generate_dry_run_report(analyzer, output_file: str = "data/exports/dry_run_report.json"):
    """
    Generate a comprehensive preview of what the write operation will do.

    Args:
        analyzer: SpotifyAnalyzer instance with loaded data
        output_file: Path to save the report

    Returns:
        Dict containing the full report
    """
    report = analyzer.generate_dry_run_report()
    deduped = analyzer.get_deduplicated_tracks()
    top_weighted = analyzer.get_weight_analysis('playlist_1').head(10)

    # Console output
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]DRY RUN REPORT[/bold cyan]\n"
        "[dim]No changes have been made. Review carefully before proceeding.[/dim]",
        border_style="cyan"
    ))

    # Summary table
    summary = Table(title="Operation Summary", show_header=True)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", style="green")
    summary.add_column("Notes", style="dim")

    summary.add_row(
        "Playlist 1 entries",
        str(report['before']['playlist_1_entries']),
        "With duplicates"
    )
    summary.add_row(
        "Playlist 2 entries",
        str(report['before']['playlist_2_entries']),
        "Clean (no duplicates)"
    )
    summary.add_row(
        "Total entries",
        str(report['before']['total_entries']),
        ""
    )
    summary.add_row(
        "Unique tracks (after dedup)",
        str(report['after']['unique_tracks']),
        "[bold green]← Final count[/bold green]"
    )
    summary.add_row(
        "Duplicates to remove",
        str(report['impact']['duplicates_removed']),
        f"{report['impact']['duplicates_removed'] / report['before']['total_entries'] * 100:.1f}% reduction"
    )
    summary.add_row(
        "Cross-playlist overlap",
        str(report['overlap']['in_both']),
        "Tracks in both playlists"
    )

    console.print(summary)
    console.print("\n")

    # Weight stats (Playlist 1)
    weight_table = Table(title="Weight Analysis (Playlist 1)", show_header=True)
    weight_table.add_column("Metric", style="cyan")
    weight_table.add_column("Value", style="yellow")

    weight_table.add_row("Highest weight", str(report['weight_stats']['highest_weight_p1']))
    weight_table.add_row("Average weight", str(report['weight_stats']['avg_weight_p1']))
    weight_table.add_row("Tracks with duplicates", str(report['weight_stats']['tracks_with_duplicates_p1']))

    console.print(weight_table)
    console.print("\n")

    # Top 10 weighted tracks
    if len(top_weighted) > 0:
        top_table = Table(title="Top 10 Most Weighted Tracks (Playlist 1)", show_header=True)
        top_table.add_column("#", style="dim")
        top_table.add_column("Track", style="white")
        top_table.add_column("Artist", style="cyan")
        top_table.add_column("Weight", style="yellow")

        for idx, row in top_weighted.iterrows():
            top_table.add_row(
                str(idx + 1),
                row['name'][:40] + "..." if len(row['name']) > 40 else row['name'],
                row['artist'][:25] + "..." if len(row['artist']) > 25 else row['artist'],
                str(row['weight'])
            )

        console.print(top_table)
        console.print("\n")

    # Overlap analysis
    overlap_table = Table(title="Playlist Overlap Analysis", show_header=True)
    overlap_table.add_column("Category", style="cyan")
    overlap_table.add_column("Count", style="green")

    overlap_table.add_row("Only in Playlist 1", str(report['overlap']['only_p1']))
    overlap_table.add_row("Only in Playlist 2", str(report['overlap']['only_p2']))
    overlap_table.add_row("In both playlists", str(report['overlap']['in_both']))

    console.print(overlap_table)

    # Save to file
    import json
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            'report': report,
            'top_weighted': top_weighted.to_dict('records'),
            'sample_deduplicated': deduped.head(20).to_dict('records'),
            'generated_at': datetime.now().isoformat()
        }, f, indent=2, default=str)

    console.print(f"\n[dim]Full report saved to: {output_file}[/dim]")

    return report


def confirm_write_operation(report: dict) -> bool:
    """
    Ask user to confirm the write operation.

    Args:
        report: Dry run report dict

    Returns:
        True if user confirms, False otherwise
    """
    console.print("\n")
    console.print(Panel.fit(
        f"[bold yellow]WRITE OPERATION PREVIEW[/bold yellow]\n\n"
        f"This will create a new playlist with [bold green]{report['after']['unique_tracks']}[/bold green] tracks.\n"
        f"[dim](Removing {report['impact']['duplicates_removed']} duplicates from {report['before']['total_entries']} total entries)[/dim]",
        border_style="yellow"
    ))

    console.print("\n[bold red]This action will:[/bold red]")
    console.print("  1. Create a NEW playlist (original playlists remain untouched)")
    console.print(f"  2. Add {report['after']['unique_tracks']} unique tracks")
    console.print("  3. Take approximately 2-3 minutes\n")

    return Confirm.ask("[bold]Do you want to proceed?[/bold]", default=False)
```

### Full Execution Flow

```python
def main():
    """Main execution flow with safety checks."""

    console.print(Panel.fit(
        "[bold cyan]SPOTIFY LIBRARY MERGER[/bold cyan]\n"
        "Deep Analytics & Smart Deduplication",
        border_style="cyan"
    ))

    # Step 1: Authentication
    console.print("\n[bold]Step 1: Authentication[/bold]")
    sp = authenticate()
    user = sp.current_user()
    console.print(f"Authenticated as: [green]{user['display_name']}[/green]\n")

    # Step 2: Fetch data
    console.print("[bold]Step 2: Fetching Playlists[/bold]")
    playlist1_tracks = fetch_playlist_tracks(sp, PLAYLIST_1_ID)
    playlist2_tracks = fetch_playlist_tracks(sp, PLAYLIST_2_ID)
    console.print(f"Fetched {len(playlist1_tracks)} + {len(playlist2_tracks)} entries\n")

    # Step 3: Store in DuckDB
    console.print("[bold]Step 3: Processing Data[/bold]")
    store_tracks(playlist1_tracks, 'playlist_1')
    store_tracks(playlist2_tracks, 'playlist_2')

    # Step 4: Optional - Fetch audio features
    if Confirm.ask("Fetch audio features for enhanced analysis?", default=True):
        unique_ids = get_unique_track_ids()
        fetch_audio_features(sp, unique_ids)

    # Step 5: Analysis
    console.print("\n[bold]Step 4: Analysis[/bold]")
    analyzer = SpotifyAnalyzer()
    report = generate_dry_run_report(analyzer)

    # Step 6: Confirmation
    if not confirm_write_operation(report):
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        console.print("Your data has been saved. You can:")
        console.print("  - Review the dry run report: data/exports/dry_run_report.json")
        console.print("  - Explore the data in Jupyter: notebooks/")
        console.print("  - Run this script again when ready")
        return

    # Step 7: Create playlist
    console.print("\n[bold]Step 5: Creating Master Playlist[/bold]")
    deduped = analyzer.get_deduplicated_tracks()

    master = create_master_playlist(
        sp,
        user_id=user['id'],
        name=f"Master Library {datetime.now().strftime('%Y-%m-%d')}",
        description="Merged & deduplicated from weighted shuffle playlists"
    )

    # Step 8: Add tracks
    track_ids = deduped['id'].tolist()
    added = add_tracks_to_playlist(sp, master['id'], track_ids)

    # Step 9: Success
    console.print("\n")
    console.print(Panel.fit(
        f"[bold green]SUCCESS![/bold green]\n\n"
        f"Created playlist: [cyan]{master['name']}[/cyan]\n"
        f"Tracks added: [green]{added}[/green]\n"
        f"Playlist URL: [link]{master['external_urls']['spotify']}[/link]",
        border_style="green"
    ))
```

---

## Local Setup

Since we're using DuckDB (embedded database) and this is a one-time execution, there's no need for Docker. We'll use `uv` for fast dependency management.

### requirements.txt

```
# Core
spotipy>=2.23.0
duckdb>=0.9.0
pandas>=2.0.0

# Visualization
matplotlib>=3.7.0
seaborn>=0.12.0

# CLI
rich>=13.0.0

# Jupyter (optional, for interactive exploration)
jupyterlab>=4.0.0

# Environment management
python-dotenv>=1.0.0
```

### .env.example

```bash
# .env.example
# Copy this to .env and fill in your Spotify credentials

SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8080/callback

# Optional: Playlist IDs (can also be provided interactively)
PLAYLIST_1_ID=
PLAYLIST_2_ID=
```

### Setup Instructions (using uv)

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 3. Copy and configure environment
cp .env.example .env
# Edit .env with your Spotify credentials

# 4. Create data directories
mkdir -p data/checkpoints data/exports

# 5. Run the script
python -m src.main

# Or launch Jupyter for interactive exploration
jupyter lab
```

### Alternative: Using pip

```bash
# If you prefer traditional pip
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Why No Docker?

| Aspect | Docker | Local venv + uv |
|--------|--------|-----------------|
| DuckDB | Embedded, no server | Embedded, no server |
| Dependencies | Isolated in container | Isolated in venv |
| Install speed | Build image (~1 min) | uv install (~5 sec) |
| Setup complexity | Dockerfile + compose | Just `uv pip install` |
| One-time script | Overkill | Perfect fit |
| OAuth callback | Port mapping needed | Works directly |

**Conclusion**: For a one-time script with an embedded database, `uv` + virtual environment is faster and simpler than Docker.

---

## Complete Implementation

### Project Structure

```
spotify-analyzer/
├── requirements.txt
├── .env.example
├── .env                  # Your credentials (git-ignored)
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py           # CLI entry point
│   ├── auth.py           # Spotify OAuth
│   ├── fetch.py          # Data fetching
│   ├── storage.py        # DuckDB operations
│   └── analyze.py        # Analytics queries
├── notebooks/
│   ├── 01_setup.ipynb
│   ├── 02_weight_analysis.ipynb
│   ├── 03_musical_dna.ipynb
│   └── 04_merge_execute.ipynb
├── data/
│   ├── .gitkeep
│   ├── checkpoints/
│   └── exports/
└── docs/
    ├── stage-1-tooling-analysis.md
    ├── stage-2-storage-strategy.md
    ├── stage-3-analytics-deduplication.md
    └── stage-4-execution-plan.md
```

### src/auth.py

```python
"""Spotify OAuth authentication."""

import os
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Required scopes for our operations
SCOPES = [
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
]

def authenticate(cache_path: str = ".cache-spotify") -> spotipy.Spotify:
    """
    Authenticate with Spotify OAuth.

    Uses environment variables:
    - SPOTIFY_CLIENT_ID
    - SPOTIFY_CLIENT_SECRET
    - SPOTIFY_REDIRECT_URI (default: http://localhost:8080/callback)

    Args:
        cache_path: Path to store the OAuth token cache

    Returns:
        Authenticated Spotipy client
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing Spotify credentials. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET "
            "environment variables or create a .env file."
        )

    auth_manager = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=" ".join(SCOPES),
        cache_path=cache_path,
        open_browser=True,
    )

    return spotipy.Spotify(
        auth_manager=auth_manager,
        retries=5,
        status_retries=3,
        backoff_factor=0.5,
    )


def get_user_playlists(sp: spotipy.Spotify, limit: int = 50) -> list[dict]:
    """
    Get user's playlists for selection.

    Args:
        sp: Authenticated Spotipy client
        limit: Maximum playlists to fetch

    Returns:
        List of playlist objects
    """
    playlists = []
    offset = 0

    while True:
        response = sp.current_user_playlists(limit=50, offset=offset)
        playlists.extend(response['items'])

        if not response['next'] or len(playlists) >= limit:
            break
        offset += 50

    return playlists[:limit]
```

### src/storage.py

```python
"""DuckDB storage operations."""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

class SpotifyStorage:
    """Handles all DuckDB storage operations."""

    def __init__(self, db_path: str = "data/spotify.duckdb"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id VARCHAR,
                name VARCHAR,
                artist VARCHAR,
                artist_id VARCHAR,
                album VARCHAR,
                album_id VARCHAR,
                release_date VARCHAR,
                duration_ms INTEGER,
                popularity INTEGER,
                explicit BOOLEAN,
                isrc VARCHAR,
                added_at TIMESTAMP,
                playlist_source VARCHAR,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS audio_features (
                track_id VARCHAR PRIMARY KEY,
                danceability FLOAT,
                energy FLOAT,
                key INTEGER,
                loudness FLOAT,
                mode INTEGER,
                speechiness FLOAT,
                acousticness FLOAT,
                instrumentalness FLOAT,
                liveness FLOAT,
                valence FLOAT,
                tempo FLOAT,
                duration_ms INTEGER,
                time_signature INTEGER,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    def store_tracks(self, tracks: list[dict], playlist_source: str):
        """
        Store fetched tracks in the database.

        Args:
            tracks: List of track items from Spotify API
            playlist_source: Identifier for source playlist
        """
        rows = []
        for item in tracks:
            track = item.get('track')
            if not track or not track.get('id'):
                continue  # Skip invalid entries

            rows.append({
                'id': track['id'],
                'name': track['name'],
                'artist': track['artists'][0]['name'] if track['artists'] else None,
                'artist_id': track['artists'][0]['id'] if track['artists'] else None,
                'album': track['album']['name'] if track.get('album') else None,
                'album_id': track['album']['id'] if track.get('album') else None,
                'release_date': track['album'].get('release_date') if track.get('album') else None,
                'duration_ms': track.get('duration_ms'),
                'popularity': track.get('popularity'),
                'explicit': track.get('explicit', False),
                'isrc': track.get('external_ids', {}).get('isrc'),
                'added_at': item.get('added_at'),
                'playlist_source': playlist_source,
            })

        if rows:
            df = pd.DataFrame(rows)
            self.conn.execute("INSERT INTO tracks SELECT * FROM df")

    def store_audio_features(self, features: dict[str, dict]):
        """
        Store audio features in the database.

        Args:
            features: Dict mapping track_id to feature dict
        """
        rows = []
        for track_id, feat in features.items():
            if feat:
                rows.append({
                    'track_id': track_id,
                    'danceability': feat.get('danceability'),
                    'energy': feat.get('energy'),
                    'key': feat.get('key'),
                    'loudness': feat.get('loudness'),
                    'mode': feat.get('mode'),
                    'speechiness': feat.get('speechiness'),
                    'acousticness': feat.get('acousticness'),
                    'instrumentalness': feat.get('instrumentalness'),
                    'liveness': feat.get('liveness'),
                    'valence': feat.get('valence'),
                    'tempo': feat.get('tempo'),
                    'duration_ms': feat.get('duration_ms'),
                    'time_signature': feat.get('time_signature'),
                })

        if rows:
            df = pd.DataFrame(rows)
            # Upsert - replace if exists
            self.conn.execute("""
                INSERT OR REPLACE INTO audio_features
                SELECT * FROM df
            """)

    def get_unique_track_ids(self) -> list[str]:
        """Get list of unique track IDs."""
        result = self.conn.execute("SELECT DISTINCT id FROM tracks").fetchall()
        return [row[0] for row in result]

    def get_track_count(self) -> dict:
        """Get track counts by source."""
        result = self.conn.execute("""
            SELECT
                playlist_source,
                COUNT(*) as count,
                COUNT(DISTINCT id) as unique_count
            FROM tracks
            GROUP BY playlist_source
        """).fetchdf()
        return result.to_dict('records')

    def clear_tracks(self):
        """Clear all track data (for re-import)."""
        self.conn.execute("DELETE FROM tracks")

    def close(self):
        """Close database connection."""
        self.conn.close()
```

---

## Spotify Developer App Setup

### If You Don't Have an App Yet

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Log in with your Spotify account
3. Click "Create App"
4. Fill in:
   - **App name**: "Library Merger" (or anything you like)
   - **App description**: "Personal tool for playlist management"
   - **Website**: Leave blank or use `http://localhost`
   - **Redirect URI**: `http://localhost:8080/callback`
5. Check the terms and click "Save"
6. Click "Settings" to view your Client ID and Client Secret

### Finding Your Existing App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Look for any existing apps
3. Click on the app to view credentials
4. Make sure the Redirect URI is set to `http://localhost:8080/callback`

---

## Decision Log

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Rate limit handling | Manual, spotipy built-in | spotipy + explicit wrapper | Best of both: auto-retry + visibility |
| Checkpoint format | SQLite, JSON | JSON | Human-readable, easy debugging |
| Batch size | 50, 100, 200 | 100 | Spotify's maximum per request |
| Environment | Docker, venv + pip, venv + uv | venv + uv | Fastest install, simplest for one-time script |
| Dry run output | JSON only, CLI, Both | Both | JSON for export, CLI for UX |

---

## Next Steps

With all 4 stages documented, you can:

1. **Review** these documents
2. **Provide playlist IDs** when you find them
3. **Set up Spotify Developer App** (if needed)
4. **Approve** to begin implementation

I will not write any code that modifies your Spotify account until you explicitly approve after reviewing the dry run report.
