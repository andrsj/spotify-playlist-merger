"""Step 2: Analyze fetched tracks.

Usage:
    python -m src.02_analyze
"""

import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .analyze import SpotifyAnalyzer

# Use wide console for file output (no truncation)
if sys.stdout.isatty():
    console = Console()
else:
    console = Console(width=300, force_terminal=False)

SPOTIFY_TRACK_URL = "https://open.spotify.com/track/"
SPOTIFY_ARTIST_URL = "https://open.spotify.com/artist/"


def format_duration(ms: int) -> str:
    """Format milliseconds as HH:MM:SS or MM:SS."""
    seconds = ms // 1000
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_total_duration(ms: int) -> str:
    """Format total duration as Xh Ym."""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    return f"{hours}h {minutes}m"


def main():
    console.print(Panel.fit(
        "[bold cyan]STEP 2: ANALYZE TRACKS[/bold cyan]\n"
        "Statistics and duplicate analysis",
        border_style="cyan"
    ))

    analyzer = SpotifyAnalyzer()

    # ═══════════════════════════════════════════════════════════════
    # PLAYLIST SUMMARY
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold]═══ PLAYLIST SUMMARY ═══[/bold]")
    counts = analyzer.conn.execute("""
        SELECT
            playlist_source,
            COUNT(*) as entries,
            COUNT(DISTINCT id) as unique_tracks
        FROM tracks
        GROUP BY playlist_source
    """).fetchdf()

    summary_table = Table(show_header=True)
    summary_table.add_column("Playlist ID", style="cyan")
    summary_table.add_column("Entries", style="green", justify="right")
    summary_table.add_column("Unique", style="yellow", justify="right")
    summary_table.add_column("Duplicates", style="red", justify="right")
    summary_table.add_column("Dup %", style="red", justify="right")

    for _, row in counts.iterrows():
        dups = row['entries'] - row['unique_tracks']
        dup_pct = (dups / row['entries'] * 100) if row['entries'] > 0 else 0
        summary_table.add_row(
            row['playlist_source'],
            str(row['entries']),
            str(row['unique_tracks']),
            str(dups),
            f"{dup_pct:.1f}%"
        )

    total_entries = counts['entries'].sum()
    total_unique_global = analyzer.conn.execute("SELECT COUNT(DISTINCT id) FROM tracks").fetchone()[0]
    total_dups = total_entries - total_unique_global
    total_dup_pct = (total_dups / total_entries * 100) if total_entries > 0 else 0

    summary_table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_entries}[/bold]",
        f"[bold]{total_unique_global}[/bold]",
        f"[bold]{total_dups}[/bold]",
        f"[bold]{total_dup_pct:.1f}%[/bold]"
    )
    console.print(summary_table)

    # ═══════════════════════════════════════════════════════════════
    # DETAILED STATISTICS
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold]═══ DETAILED STATISTICS ═══[/bold]")

    stats = analyzer.conn.execute("""
        SELECT
            COUNT(DISTINCT id) as unique_tracks,
            COUNT(DISTINCT artist_id) as unique_artists,
            COUNT(DISTINCT album_id) as unique_albums,
            SUM(duration_ms) as total_duration_all,
            AVG(duration_ms) as avg_duration,
            MIN(duration_ms) as min_duration,
            MAX(duration_ms) as max_duration,
            AVG(popularity) as avg_popularity,
            SUM(CASE WHEN explicit THEN 1 ELSE 0 END) as explicit_count
        FROM (SELECT DISTINCT id, artist_id, album_id, duration_ms, popularity, explicit FROM tracks)
    """).fetchdf().iloc[0]

    stats_table = Table(show_header=False, box=None)
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")

    stats_table.add_row("Unique tracks", str(int(stats['unique_tracks'])))
    stats_table.add_row("Unique artists", str(int(stats['unique_artists'])))
    stats_table.add_row("Unique albums", str(int(stats['unique_albums'])))
    stats_table.add_row("Total duration", format_total_duration(int(stats['total_duration_all'])))
    stats_table.add_row("Avg track length", format_duration(int(stats['avg_duration'])))
    stats_table.add_row("Shortest track", format_duration(int(stats['min_duration'])))
    stats_table.add_row("Longest track", format_duration(int(stats['max_duration'])))
    stats_table.add_row("Avg popularity", f"{stats['avg_popularity']:.1f}/100")
    stats_table.add_row("Explicit tracks", f"{int(stats['explicit_count'])} ({int(stats['explicit_count'])/int(stats['unique_tracks'])*100:.1f}%)")

    console.print(stats_table)

    # ═══════════════════════════════════════════════════════════════
    # PLAYLIST OVERLAP (clearer explanation)
    # ═══════════════════════════════════════════════════════════════
    if len(counts) > 1:
        console.print("\n[bold]═══ PLAYLIST OVERLAP ═══[/bold]")
        console.print("[dim]Shows how many tracks appear in multiple playlists[/dim]\n")

        overlap_df = analyzer.conn.execute("""
            WITH track_playlists AS (
                SELECT
                    id,
                    name,
                    artist,
                    COUNT(DISTINCT playlist_source) as playlist_count
                FROM tracks
                GROUP BY id, name, artist
            )
            SELECT
                playlist_count,
                COUNT(*) as track_count
            FROM track_playlists
            GROUP BY playlist_count
            ORDER BY playlist_count
        """).fetchdf()

        overlap_table = Table(show_header=True)
        overlap_table.add_column("Appears in", style="cyan")
        overlap_table.add_column("Track Count", style="green", justify="right")
        overlap_table.add_column("Description", style="dim")

        for _, row in overlap_df.iterrows():
            n = int(row['playlist_count'])
            if n == 1:
                desc = "Only in one playlist"
            elif n == len(counts):
                desc = "In ALL playlists"
            else:
                desc = f"In {n} playlists"
            overlap_table.add_row(
                f"{n} playlist(s)",
                str(row['track_count']),
                desc
            )
        console.print(overlap_table)

        # Show ALL overlapping tracks
        shared_tracks = analyzer.conn.execute("""
            SELECT id, name, artist
            FROM tracks
            GROUP BY id, name, artist
            HAVING COUNT(DISTINCT playlist_source) > 1
            ORDER BY name
        """).fetchdf()

        if len(shared_tracks) > 0:
            console.print(f"\n[bold]All shared tracks ({len(shared_tracks)} total):[/bold]")
            shared_table = Table(show_header=True, show_lines=False)
            shared_table.add_column("#", style="dim", width=4)
            shared_table.add_column("Track", style="white", no_wrap=True)
            shared_table.add_column("Artist", style="cyan", no_wrap=True)
            shared_table.add_column("URL", style="dim", no_wrap=True)

            for idx, row in shared_tracks.iterrows():
                shared_table.add_row(
                    str(idx + 1),
                    str(row['name']),
                    str(row['artist']),
                    f"{SPOTIFY_TRACK_URL}{row['id']}"
                )
            console.print(shared_table)

    # ═══════════════════════════════════════════════════════════════
    # ALL DUPLICATED TRACKS
    # ═══════════════════════════════════════════════════════════════
    weight_df = analyzer.conn.execute("""
        SELECT
            id,
            name,
            artist,
            COUNT(*) as weight
        FROM tracks
        GROUP BY id, name, artist
        HAVING COUNT(*) > 1
        ORDER BY weight DESC
    """).fetchdf()

    console.print(f"\n[bold]═══ ALL DUPLICATED TRACKS ({len(weight_df)} total) ═══[/bold]")
    console.print("[dim]Tracks that appear multiple times (your 'weighted' favorites)[/dim]\n")

    if len(weight_df) > 0:
        weight_table = Table(show_header=True, show_lines=False)
        weight_table.add_column("#", style="dim", width=4)
        weight_table.add_column("Track", style="white", no_wrap=True)
        weight_table.add_column("Artist", style="cyan", no_wrap=True)
        weight_table.add_column("Weight", style="yellow", justify="right")
        weight_table.add_column("URL", style="dim", no_wrap=True)

        for idx, row in weight_df.iterrows():
            weight_table.add_row(
                str(idx + 1),
                str(row['name']),
                str(row['artist']),
                str(row['weight']),
                f"{SPOTIFY_TRACK_URL}{row['id']}"
            )
        console.print(weight_table)
    else:
        console.print("[dim]No duplicates found[/dim]")

    # ═══════════════════════════════════════════════════════════════
    # ALL ARTISTS (with 2+ tracks)
    # ═══════════════════════════════════════════════════════════════
    artists_df = analyzer.conn.execute("""
        SELECT
            artist,
            artist_id,
            COUNT(DISTINCT id) as unique_tracks,
            COUNT(*) as total_entries
        FROM tracks
        GROUP BY artist, artist_id
        HAVING COUNT(DISTINCT id) >= 2
        ORDER BY unique_tracks DESC
    """).fetchdf()

    console.print(f"\n[bold]═══ ALL ARTISTS with 2+ tracks ({len(artists_df)} total) ═══[/bold]")

    artists_table = Table(show_header=True, show_lines=False)
    artists_table.add_column("#", style="dim", width=4)
    artists_table.add_column("Artist", style="cyan", no_wrap=True)
    artists_table.add_column("Tracks", style="green", justify="right")
    artists_table.add_column("Entries", style="yellow", justify="right")
    artists_table.add_column("URL", style="dim", no_wrap=True)

    for idx, row in artists_df.iterrows():
        artists_table.add_row(
            str(idx + 1),
            str(row['artist']),
            str(row['unique_tracks']),
            str(row['total_entries']),
            f"{SPOTIFY_ARTIST_URL}{row['artist_id']}" if row['artist_id'] else ""
        )
    console.print(artists_table)

    # ═══════════════════════════════════════════════════════════════
    # RELEASE YEAR DISTRIBUTION (ALL YEARS)
    # ═══════════════════════════════════════════════════════════════
    console.print("\n[bold]═══ RELEASE YEAR DISTRIBUTION ═══[/bold]")

    years_df = analyzer.get_release_year_distribution()

    years_table = Table(show_header=True)
    years_table.add_column("Year", style="cyan")
    years_table.add_column("Tracks", style="green", justify="right")
    years_table.add_column("Bar", style="yellow")

    max_count = years_df['track_count'].max() if len(years_df) > 0 else 1

    for _, row in years_df.iterrows():
        bar_len = int((row['track_count'] / max_count) * 30)
        bar = "█" * bar_len
        years_table.add_row(
            str(row['year']),
            str(row['track_count']),
            bar
        )
    console.print(years_table)

    analyzer.close()

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]ANALYSIS COMPLETE[/bold green]\n\n"
        f"Total unique tracks: [cyan]{total_unique_global}[/cyan]\n"
        f"Duplicates removed: [yellow]{total_dups}[/yellow] ({total_dup_pct:.1f}%)\n\n"
        "[dim]Next step: python -m src.03_merge[/dim]",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
