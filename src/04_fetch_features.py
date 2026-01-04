"""Step 4 (optional): Fetch audio features for all tracks.

WARNING: As of January 2026, this API returns HTTP 403 Forbidden.
Spotify has fully deprecated and disabled the audio features endpoint.

This script is kept for historical purposes and in case Spotify
re-enables the API in the future.

Audio features that WOULD have been available:
- tempo (BPM)
- energy (0.0 to 1.0)
- danceability (0.0 to 1.0)
- valence (mood, 0.0 to 1.0)
- acousticness (0.0 to 1.0)
- instrumentalness (0.0 to 1.0)
- speechiness (0.0 to 1.0)
- liveness (0.0 to 1.0)
- loudness (dB)
- key (0-11, pitch class)
- mode (0=minor, 1=major)
- time_signature

See: https://developer.spotify.com/documentation/web-api/reference/get-audio-features

Usage:
    python -m src.04_fetch_features
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from .auth import authenticate
from .fetch import fetch_audio_features
from .storage import SpotifyStorage

console = Console()


def main():
    console.print(Panel.fit(
        "[bold cyan]FETCH AUDIO FEATURES[/bold cyan]\n"
        "[yellow]Note: This API is deprecated by Spotify[/yellow]",
        border_style="cyan"
    ))

    # Get unique track IDs from database
    storage = SpotifyStorage()
    track_ids = storage.get_unique_track_ids()
    console.print(f"\nFound [green]{len(track_ids)}[/green] unique tracks in database")

    # Check how many already have features
    existing = storage.conn.execute("SELECT COUNT(*) FROM audio_features").fetchone()[0]
    console.print(f"Already have features for [yellow]{existing}[/yellow] tracks")

    remaining = len(track_ids) - existing
    if remaining == 0:
        console.print("[green]All tracks already have features![/green]")
        storage.close()
        return

    console.print(f"Need to fetch features for [cyan]{remaining}[/cyan] tracks")
    console.print(f"Estimated API calls: ~{remaining // 100 + 1}")
    console.print("\n[yellow]Warning: This API is deprecated and may fail or return incomplete data[/yellow]\n")

    if not Confirm.ask("Proceed?", default=True):
        console.print("[yellow]Cancelled[/yellow]")
        storage.close()
        return

    # Authenticate
    console.print("\n[bold]Authenticating...[/bold]")
    sp = authenticate()
    console.print("Authenticated\n")

    # Fetch features
    console.print("[bold]Fetching audio features...[/bold]")
    try:
        features = fetch_audio_features(sp, track_ids)

        # Store in database
        console.print(f"\n[bold]Storing {len(features)} features in database...[/bold]")
        storage.store_audio_features(features)

        console.print("\n")
        console.print(Panel.fit(
            f"[bold green]SUCCESS![/bold green]\n\n"
            f"Fetched features for [cyan]{len(features)}[/cyan] tracks\n\n"
            "[dim]Run python -m src.02_analyze to see updated stats[/dim]",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        console.print("[yellow]Partial data may have been saved via checkpoints[/yellow]")

    storage.close()


if __name__ == "__main__":
    main()
