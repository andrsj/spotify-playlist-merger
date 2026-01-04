"""Spotify OAuth authentication."""

import os
from pathlib import Path
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv()

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
    client_id = os.environ.get("SPOTIFY_CLIENT_ID") or os.environ.get("CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or os.environ.get("CLIENT_SECRET")
    redirect_uri = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8080/callback")

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
