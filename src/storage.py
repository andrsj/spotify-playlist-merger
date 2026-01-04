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
                continue

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
            self.conn.execute("""
                INSERT INTO tracks (id, name, artist, artist_id, album, album_id,
                    release_date, duration_ms, popularity, explicit, isrc,
                    added_at, playlist_source)
                SELECT * FROM df
            """)

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
