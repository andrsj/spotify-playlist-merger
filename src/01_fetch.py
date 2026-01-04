"""Step 1: Fetch tracks from playlists and store in DuckDB.

Usage:
    python -m src.01_fetch playlists.txt

Where playlists.txt contains one playlist ID per line.
"""

import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from .auth import authenticate
from .fetch import fetch_playlist_tracks
from .storage import SpotifyStorage

console = Console()


def load_playlist_ids(filepath: str) -> list[str]:
    """Load playlist IDs from a text file (one per line)."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]Error: File not found: {filepath}[/red]")
        sys.exit(1)

    ids = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                ids.append(line)

    return ids


def main():
    if len(sys.argv) < 2:
        console.print("[red]Usage: python -m src.01_fetch <playlists_file>[/red]")
        console.print("\nExample playlists.txt:")
        console.print("  491WiUqmbpuCtUs6xwXRaB")
        console.print("  37i9dQZF1DXcBWIGoYBM5M")
        console.print("  # comments are ignored")
        sys.exit(1)

    playlist_file = sys.argv[1]

    console.print(Panel.fit(
        "[bold cyan]STEP 1: FETCH PLAYLISTS[/bold cyan]\n"
        "Fetch tracks and store in local database",
        border_style="cyan"
    ))

    # Load playlist IDs
    playlist_ids = load_playlist_ids(playlist_file)
    console.print(f"\nLoaded [green]{len(playlist_ids)}[/green] playlist IDs from {playlist_file}\n")

    # Authenticate
    console.print("[bold]Authenticating...[/bold]")
    sp = authenticate()
    user = sp.current_user()
    console.print(f"Logged in as: [green]{user['display_name']}[/green]\n")

    # Initialize storage
    storage = SpotifyStorage()
    storage.clear_tracks()

    # Fetch each playlist
    for i, playlist_id in enumerate(playlist_ids, 1):
        console.print(f"[bold]Fetching playlist {i}/{len(playlist_ids)}: {playlist_id}[/bold]")

        try:
            # Get playlist name first
            playlist_info = sp.playlist(playlist_id, fields="name")
            playlist_name = playlist_info['name']
            console.print(f"  Name: [cyan]{playlist_name}[/cyan]")

            tracks = fetch_playlist_tracks(sp, playlist_id)
            console.print(f"  Fetched [green]{len(tracks)}[/green] entries")

            # Use playlist ID as source identifier
            storage.store_tracks(tracks, playlist_id)
            console.print(f"  Stored in database\n")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]\n")
            continue

    # Summary
    counts = storage.get_track_count()
    storage.close()

    total_entries = sum(c['count'] for c in counts)
    total_unique = sum(c['unique_count'] for c in counts)

    console.print("\n")
    summary_lines = [
        "[bold green]FETCH COMPLETE[/bold green]\n",
        f"Playlists processed: {len(counts)}",
        f"Total entries: {total_entries}",
        f"Total unique (per playlist): {total_unique}",
        "",
        "Data saved to: data/spotify.duckdb",
        "",
        "[dim]Next step: python -m src.02_analyze[/dim]"
    ]
    console.print(Panel.fit("\n".join(summary_lines), border_style="green"))


if __name__ == "__main__":
    main()
