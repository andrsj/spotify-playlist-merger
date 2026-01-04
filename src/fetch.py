"""Data fetching with checkpointing and rate limit handling."""

import json
import time
from pathlib import Path
from datetime import datetime
import spotipy
from spotipy.exceptions import SpotifyException
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn


def save_checkpoint(filepath: Path, data: dict):
    """Save progress checkpoint."""
    with open(filepath, 'w') as f:
        json.dump(data, f, default=str)


def fetch_playlist_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    checkpoint_dir: str = "data/checkpoints"
) -> list[dict]:
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

    all_tracks = []
    start_offset = 0

    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            if not checkpoint_data.get('complete', False):
                all_tracks = checkpoint_data.get('tracks', [])
                start_offset = checkpoint_data.get('next_offset', 0)
                print(f"Resuming from checkpoint: {len(all_tracks)} tracks already fetched")
            else:
                print(f"Playlist {playlist_id} already fully fetched, loading from cache")
                return checkpoint_data.get('tracks', [])

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
                progress.update(task, completed=len(all_tracks))

                if len(all_tracks) % 500 < 100:
                    save_checkpoint(checkpoint_file, {
                        'tracks': all_tracks,
                        'next_offset': offset + 100,
                        'timestamp': datetime.now().isoformat(),
                        'complete': False
                    })

                offset += 100

            except Exception as e:
                save_checkpoint(checkpoint_file, {
                    'tracks': all_tracks,
                    'next_offset': offset,
                    'timestamp': datetime.now().isoformat(),
                    'complete': False,
                    'error': str(e)
                })
                raise e

    save_checkpoint(checkpoint_file, {
        'tracks': all_tracks,
        'next_offset': offset,
        'timestamp': datetime.now().isoformat(),
        'complete': True
    })

    return all_tracks


def fetch_audio_features(
    sp: spotipy.Spotify,
    track_ids: list[str],
    checkpoint_dir: str = "data/checkpoints"
) -> dict[str, dict]:
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

    features = {}
    if checkpoint_file.exists():
        with open(checkpoint_file, 'r') as f:
            checkpoint_data = json.load(f)
            features = checkpoint_data.get('features', {})
            print(f"Resuming: {len(features)} tracks already have features")

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

        for i in range(0, len(remaining_ids), 100):
            batch = remaining_ids[i:i+100]

            try:
                response = sp.audio_features(batch)

                for track_id, feature in zip(batch, response):
                    if feature:
                        features[track_id] = feature

                progress.update(task, advance=len(batch))

                if len(features) % 500 < 100:
                    with open(checkpoint_file, 'w') as f:
                        json.dump({
                            'features': features,
                            'timestamp': datetime.now().isoformat()
                        }, f)

            except Exception as e:
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'features': features,
                        'timestamp': datetime.now().isoformat(),
                        'error': str(e)
                    }, f)
                raise e

    with open(checkpoint_file, 'w') as f:
        json.dump({
            'features': features,
            'complete': True,
            'timestamp': datetime.now().isoformat()
        }, f)

    return features


def robust_api_call(func, *args, max_retries=5, **kwargs):
    """
    Wrapper for API calls with explicit 429 handling.
    """
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get('Retry-After', 5))
                print(f"Rate limited. Waiting {retry_after} seconds... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_after + 1)
            elif e.http_status >= 500:
                wait_time = (2 ** attempt) + 1
                print(f"Server error {e.http_status}. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            wait_time = (2 ** attempt) + 1
            print(f"Error: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)

    raise Exception(f"Max retries ({max_retries}) exceeded")
