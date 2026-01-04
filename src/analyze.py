"""Analytics and deduplication logic."""

import pandas as pd
import duckdb
from pathlib import Path
from datetime import datetime


class SpotifyAnalyzer:
    """Analytics engine for Spotify library data."""

    def __init__(self, db_path: str = "data/spotify.duckdb"):
        self.conn = duckdb.connect(db_path, read_only=True)

    def get_weight_analysis(self, playlist_source: str = None) -> pd.DataFrame:
        """
        Analyze track weights (duplicate counts) in playlists.

        Args:
            playlist_source: Filter by specific playlist, or None for all

        Returns:
            DataFrame with track weights sorted by weight descending
        """
        where_clause = f"WHERE playlist_source = '{playlist_source}'" if playlist_source else ""

        query = f"""
            SELECT
                id,
                name,
                artist,
                album,
                COUNT(*) as weight,
                MAX(added_at) as last_added,
                MIN(added_at) as first_added
            FROM tracks
            {where_clause}
            GROUP BY id, name, artist, album
            ORDER BY weight DESC, name
        """
        return self.conn.execute(query).fetchdf()

    def get_deduplicated_tracks(self) -> pd.DataFrame:
        """
        Get unique tracks across all playlists.

        Returns:
            DataFrame with unique tracks (by ID)
        """
        query = """
            SELECT DISTINCT ON (id)
                id,
                name,
                artist,
                artist_id,
                album,
                album_id,
                release_date,
                duration_ms,
                popularity,
                explicit,
                isrc,
                MAX(added_at) as added_at
            FROM tracks
            GROUP BY id, name, artist, artist_id, album, album_id,
                     release_date, duration_ms, popularity, explicit, isrc
            ORDER BY name, artist
        """
        return self.conn.execute(query).fetchdf()

    def get_overlap_analysis(self) -> dict:
        """
        Analyze overlap between playlists.

        Returns:
            Dict with overlap statistics
        """
        query = """
            WITH playlist_ids AS (
                SELECT
                    id,
                    ARRAY_AGG(DISTINCT playlist_source) as sources
                FROM tracks
                GROUP BY id
            )
            SELECT
                CASE
                    WHEN ARRAY_LENGTH(sources) > 1 THEN 'both'
                    WHEN sources[1] = 'playlist_1' THEN 'only_p1'
                    ELSE 'only_p2'
                END as location,
                COUNT(*) as count
            FROM playlist_ids
            GROUP BY location
        """
        result = self.conn.execute(query).fetchdf()

        overlap = {'only_p1': 0, 'only_p2': 0, 'in_both': 0}
        for _, row in result.iterrows():
            if row['location'] == 'both':
                overlap['in_both'] = row['count']
            elif row['location'] == 'only_p1':
                overlap['only_p1'] = row['count']
            else:
                overlap['only_p2'] = row['count']

        return overlap

    def get_musical_dna(self) -> pd.DataFrame:
        """
        Get aggregated audio features statistics.

        Returns:
            DataFrame with feature statistics
        """
        query = """
            SELECT
                AVG(tempo) as avg_tempo,
                AVG(energy) as avg_energy,
                AVG(danceability) as avg_danceability,
                AVG(valence) as avg_valence,
                AVG(acousticness) as avg_acousticness,
                AVG(instrumentalness) as avg_instrumentalness,
                AVG(speechiness) as avg_speechiness,
                AVG(liveness) as avg_liveness,
                MIN(tempo) as min_tempo,
                MAX(tempo) as max_tempo,
                COUNT(*) as tracks_with_features
            FROM audio_features
        """
        return self.conn.execute(query).fetchdf()

    def get_release_year_distribution(self) -> pd.DataFrame:
        """
        Get distribution of tracks by release year.

        Returns:
            DataFrame with year counts
        """
        query = """
            SELECT
                SUBSTR(release_date, 1, 4) as year,
                COUNT(DISTINCT id) as track_count
            FROM tracks
            WHERE release_date IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """
        return self.conn.execute(query).fetchdf()

    def get_top_artists(self, limit: int = 20) -> pd.DataFrame:
        """
        Get most frequent artists.

        Returns:
            DataFrame with artist counts
        """
        query = f"""
            SELECT
                artist,
                artist_id,
                COUNT(DISTINCT id) as unique_tracks,
                COUNT(*) as total_entries
            FROM tracks
            GROUP BY artist, artist_id
            ORDER BY unique_tracks DESC
            LIMIT {limit}
        """
        return self.conn.execute(query).fetchdf()

    def generate_dry_run_report(self) -> dict:
        """
        Generate a comprehensive dry run report.

        Returns:
            Dict with all statistics for the dry run
        """
        # Basic counts
        counts_query = """
            SELECT
                playlist_source,
                COUNT(*) as entries,
                COUNT(DISTINCT id) as unique_tracks
            FROM tracks
            GROUP BY playlist_source
        """
        counts = self.conn.execute(counts_query).fetchdf()

        p1_entries = counts[counts['playlist_source'] == 'playlist_1']['entries'].iloc[0] if len(counts[counts['playlist_source'] == 'playlist_1']) > 0 else 0
        p2_entries = counts[counts['playlist_source'] == 'playlist_2']['entries'].iloc[0] if len(counts[counts['playlist_source'] == 'playlist_2']) > 0 else 0

        # Total unique
        total_unique = self.conn.execute("SELECT COUNT(DISTINCT id) FROM tracks").fetchone()[0]

        # Overlap
        overlap = self.get_overlap_analysis()

        # Weight stats for playlist 1
        weight_p1 = self.get_weight_analysis('playlist_1')
        highest_weight_p1 = weight_p1['weight'].max() if len(weight_p1) > 0 else 0
        avg_weight_p1 = round(weight_p1['weight'].mean(), 2) if len(weight_p1) > 0 else 0
        tracks_with_dups_p1 = len(weight_p1[weight_p1['weight'] > 1]) if len(weight_p1) > 0 else 0

        return {
            'before': {
                'playlist_1_entries': int(p1_entries),
                'playlist_2_entries': int(p2_entries),
                'total_entries': int(p1_entries + p2_entries),
            },
            'after': {
                'unique_tracks': int(total_unique),
            },
            'impact': {
                'duplicates_removed': int(p1_entries + p2_entries - total_unique),
            },
            'overlap': overlap,
            'weight_stats': {
                'highest_weight_p1': int(highest_weight_p1),
                'avg_weight_p1': float(avg_weight_p1),
                'tracks_with_duplicates_p1': int(tracks_with_dups_p1),
            },
            'generated_at': datetime.now().isoformat(),
        }

    def close(self):
        """Close database connection."""
        self.conn.close()
