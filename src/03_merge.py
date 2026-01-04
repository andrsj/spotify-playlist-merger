"""Step 3: Create merged playlist with unique tracks.

Usage:
    python -m src.03_merge [playlist_name]
"""

import sys
import time
from datetime import datetime
from pathlib import Path
import json

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from .auth import authenticate
from .analyze import SpotifyAnalyzer

console = Console()

SPOTIFY_PLAYLIST_LIMIT = 10000


def create_master_playlist(sp, user_id: str, name: str, description: str = None):
    """Create a new playlist."""
    desc = description or f"Merged playlist created on {datetime.now().strftime('%Y-%m-%d')}"

    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=False,
        description=desc
    )

    console.print(f"Created playlist: [cyan]{playlist['name']}[/cyan]")
    return playlist


def add_tracks_to_playlist(sp, playlist_id: str, track_ids: list[str], checkpoint_dir: str = "data/checkpoints"):
    """Add tracks to playlist in batches of 100."""
    checkpoint_path = Path(checkpoint_dir)
    checkpoint_path.mkdir(parents=True, exist_ok=True)
    checkpoint_file = checkpoint_path / f"write_{playlist_id}.json"

    start_index = 0
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            if not checkpoint_data.get('complete', False):
                start_index = checkpoint_data.get('tracks_added', 0)
                console.print(f"Resuming: {start_index} tracks already added")

    uris = [f"spotify:track:{tid}" if not tid.startswith("spotify:") else tid for tid in track_ids]
    remaining_uris = uris[start_index:]

    if not remaining_uris:
        console.print("All tracks already added!")
        return len(track_ids)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
    ) as progress:
        task = progress.add_task("Adding tracks...", total=len(track_ids), completed=start_index)

        tracks_added = start_index
        for i in range(0, len(remaining_uris), 100):
            batch = remaining_uris[i:i+100]

            try:
                sp.playlist_add_items(playlist_id, batch)
                tracks_added += len(batch)
                progress.update(task, completed=tracks_added)

                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'playlist_id': playlist_id,
                        'tracks_added': tracks_added,
                        'timestamp': datetime.now().isoformat()
                    }, f)

                time.sleep(0.1)

            except Exception as e:
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'playlist_id': playlist_id,
                        'tracks_added': tracks_added,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    }, f)
                raise e

    with open(checkpoint_file, 'w') as f:
        json.dump({
            'playlist_id': playlist_id,
            'tracks_added': tracks_added,
            'complete': True,
            'timestamp': datetime.now().isoformat()
        }, f)

    return tracks_added


def main():
    # Parse args
    args = sys.argv[1:]
    skip_confirm = '-y' in args or '--yes' in args
    args = [a for a in args if a not in ('-y', '--yes')]
    playlist_name = args[0] if args else None

    console.print(Panel.fit(
        "[bold cyan]STEP 3: CREATE MERGED PLAYLIST[/bold cyan]\n"
        "Create deduplicated playlist on Spotify",
        border_style="cyan"
    ))

    # Load data
    analyzer = SpotifyAnalyzer()
    deduped = analyzer.get_deduplicated_tracks()
    total_unique = len(deduped)
    track_ids = deduped['id'].tolist()

    console.print(f"\n[bold]Unique tracks to add:[/bold] [green]{total_unique}[/green]")

    # Check if we need multiple playlists
    num_playlists = (total_unique + SPOTIFY_PLAYLIST_LIMIT - 1) // SPOTIFY_PLAYLIST_LIMIT

    if num_playlists > 1:
        console.print(f"[yellow]Note: Exceeds {SPOTIFY_PLAYLIST_LIMIT} limit, will create {num_playlists} playlists[/yellow]")

    # Confirm
    console.print("\n[bold yellow]This will:[/bold yellow]")
    console.print(f"  1. Create {num_playlists} NEW playlist(s) (originals untouched)")
    console.print(f"  2. Add {total_unique} unique tracks total")
    console.print(f"  3. Take ~{total_unique // 100 * 2} seconds\n")

    if not skip_confirm:
        if not Confirm.ask("Proceed?", default=False):
            console.print("[yellow]Cancelled[/yellow]")
            analyzer.close()
            return

    # Authenticate
    console.print("\n[bold]Authenticating...[/bold]")
    sp = authenticate()
    user = sp.current_user()
    console.print(f"Logged in as: [green]{user['display_name']}[/green]")

    # Get playlist name
    if not playlist_name:
        default_name = f"Master Library {datetime.now().strftime('%Y-%m-%d')}"
        if skip_confirm:
            playlist_name = default_name
        else:
            playlist_name = Prompt.ask("Playlist name", default=default_name)

    analyzer.close()

    # Create playlist(s) and add tracks
    created_playlists = []

    for part in range(num_playlists):
        start_idx = part * SPOTIFY_PLAYLIST_LIMIT
        end_idx = min((part + 1) * SPOTIFY_PLAYLIST_LIMIT, total_unique)
        batch_ids = track_ids[start_idx:end_idx]

        # Name with part number if multiple playlists
        if num_playlists > 1:
            part_name = f"{playlist_name} (Part {part + 1})"
        else:
            part_name = playlist_name

        console.print(f"\n[bold]Creating playlist: {part_name}[/bold]")
        master = create_master_playlist(sp, user['id'], part_name)

        console.print(f"[bold]Adding {len(batch_ids)} tracks...[/bold]")
        added = add_tracks_to_playlist(sp, master['id'], batch_ids)

        created_playlists.append({
            'name': master['name'],
            'tracks': added,
            'url': master['external_urls']['spotify']
        })

    # Summary
    console.print("\n")
    summary_lines = ["[bold green]SUCCESS![/bold green]\n"]

    for p in created_playlists:
        summary_lines.append(f"Playlist: [cyan]{p['name']}[/cyan]")
        summary_lines.append(f"  Tracks: [green]{p['tracks']}[/green]")
        summary_lines.append(f"  URL: {p['url']}")
        summary_lines.append("")

    console.print(Panel.fit("\n".join(summary_lines), border_style="green"))


if __name__ == "__main__":
    main()
