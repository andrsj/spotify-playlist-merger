# Stage 3: Exhaustive Statistical Analysis & Deduplication Logic

## Executive Summary

This document designs the analytics pipeline for 18,000+ Spotify tracks, covering weight analysis (duplicate frequency), musical DNA profiling (genres, BPM, energy, decades), deduplication strategies, and output format comparisons. The approach prioritizes **ID-based strict matching** as per user requirements while providing comprehensive statistical insights.

### Important Context: Playlist Duplication Patterns

**User clarification**:
- **Playlist 1**: Full of duplicates throughout (entire playlist uses weighted shuffle logic)
- **Playlist 2**: Has duplicates until a certain point, then only unique tracks after Spotify's behavior change

This means:
- **Playlist 1**: Full "weight" analysis applies to the entire playlist
- **Playlist 2**: Mixed - weight analysis for early portion, then unique-only after the cutoff date
- **Timeline detection**: We need to find when Playlist 2's duplication behavior stopped
- **Merge focus**: Cross-playlist duplicates + intra-playlist duplicates in both

The analytics will:
1. Track `playlist_source` to distinguish origins
2. Detect when Playlist 2's duplication stopped (look for `duplication_ratio` dropping to ~1.0)
3. Calculate "weight" for P1 (all) and P2 (early portion)

---

## Table of Contents

1. [The "Weight" Analysis](#the-weight-analysis)
2. [Musical DNA: Deep Statistics](#musical-dna-deep-statistics)
3. [Deduplication Strategy](#deduplication-strategy)
4. [Output Formats Comparison](#output-formats-comparison)
5. [Implementation Blueprint](#implementation-blueprint)

---

## The "Weight" Analysis

### What We're Measuring

"Weight" = how many times a track was intentionally added to playlists for the weighted shuffle effect.

```
Track A appears 5 times in Playlist 1 → Weight = 5 → "Favorite" level HIGH
Track B appears 1 time in Playlist 1  → Weight = 1 → Normal track
Track C appears 1 time in Playlist 2  → Weight = 1 → Post-update addition
```

### Adjusted Analysis for Playlist Asymmetry

Since only Playlist 1 has weighted duplicates, we need to:

1. **Separate weight analysis** for Playlist 1 specifically
2. **Cross-playlist overlap** analysis (tracks in both playlists)
3. **Timeline analysis** to see when the "weighting era" ended

```sql
-- Weight analysis specifically for Playlist 1
WITH playlist1_weights AS (
    SELECT
        id,
        name,
        artist,
        album,
        COUNT(*) as weight,
        MIN(added_at) as first_added,
        MAX(added_at) as last_added
    FROM tracks
    WHERE playlist_source = 'playlist_1'
    GROUP BY id, name, artist, album
)
SELECT * FROM playlist1_weights
ORDER BY weight DESC;

-- Cross-playlist overlap
SELECT
    t1.id,
    t1.name,
    t1.artist,
    t1.weight as playlist1_weight,
    CASE WHEN t2.id IS NOT NULL THEN 'Yes' ELSE 'No' END as in_playlist2
FROM playlist1_weights t1
LEFT JOIN (
    SELECT DISTINCT id FROM tracks WHERE playlist_source = 'playlist_2'
) t2 ON t1.id = t2.id;

-- Timeline: when did weighting behavior stop?
SELECT
    DATE_TRUNC('month', added_at::TIMESTAMP) as month,
    playlist_source,
    COUNT(*) as additions,
    COUNT(DISTINCT id) as unique_tracks,
    ROUND(COUNT(*)::FLOAT / COUNT(DISTINCT id), 2) as avg_duplicates_per_track
FROM tracks
GROUP BY month, playlist_source
ORDER BY month, playlist_source;
```

### Statistical Questions to Answer

1. **Distribution**: What does the weight histogram look like for Playlist 1?
2. **Top Weighted**: Which 50 tracks had highest weights in Playlist 1?
3. **Artist Affinity**: Which artists had most weighted tracks?
4. **Album Patterns**: Were entire albums weighted, or specific tracks?
5. **Temporal Patterns**: When did you stop adding duplicates (timeline)?
6. **Overlap Analysis**: What percentage of Playlist 1 tracks are also in Playlist 2?
7. **Extreme Cases**: What's the maximum weight? Any outliers?

### Query Design

```sql
-- Basic weight calculation (Playlist 1 only)
WITH track_weights AS (
    SELECT
        id,
        name,
        artist,
        album,
        COUNT(*) as weight,
        MIN(added_at) as first_added,
        MAX(added_at) as last_added
    FROM tracks
    WHERE playlist_source = 'playlist_1'
    GROUP BY id, name, artist, album
)
SELECT * FROM track_weights
ORDER BY weight DESC;
```

### Advanced Weight Analytics

```sql
-- Weight distribution buckets (Playlist 1)
WITH track_weights AS (
    SELECT id, COUNT(*) as weight
    FROM tracks
    WHERE playlist_source = 'playlist_1'
    GROUP BY id
)
SELECT
    CASE
        WHEN weight = 1 THEN '1 (unique)'
        WHEN weight BETWEEN 2 AND 3 THEN '2-3'
        WHEN weight BETWEEN 4 AND 6 THEN '4-6'
        WHEN weight BETWEEN 7 AND 10 THEN '7-10'
        WHEN weight BETWEEN 11 AND 20 THEN '11-20'
        ELSE '20+'
    END as weight_bucket,
    COUNT(*) as track_count,
    SUM(weight) as total_occurrences
FROM track_weights
GROUP BY weight_bucket
ORDER BY MIN(weight);

-- Artist weight ranking (Playlist 1)
WITH track_weights AS (
    SELECT
        id,
        artist,
        COUNT(*) as weight
    FROM tracks
    WHERE playlist_source = 'playlist_1'
    GROUP BY id, artist
)
SELECT
    artist,
    COUNT(DISTINCT id) as unique_tracks,
    SUM(weight) as total_weighted_entries,
    ROUND(AVG(weight), 2) as avg_weight_per_track,
    MAX(weight) as highest_weight
FROM track_weights
GROUP BY artist
HAVING COUNT(DISTINCT id) > 1
ORDER BY total_weighted_entries DESC
LIMIT 50;

-- Detect when weighting behavior ended
WITH monthly_stats AS (
    SELECT
        DATE_TRUNC('month', added_at::TIMESTAMP) as month,
        playlist_source,
        COUNT(*) as entries,
        COUNT(DISTINCT id) as unique_tracks
    FROM tracks
    GROUP BY month, playlist_source
)
SELECT
    month,
    playlist_source,
    entries,
    unique_tracks,
    ROUND(entries::FLOAT / NULLIF(unique_tracks, 0), 2) as duplication_ratio
FROM monthly_stats
WHERE playlist_source = 'playlist_1'
ORDER BY month;
-- Look for month where duplication_ratio drops to ~1.0

-- Cross-playlist analysis
WITH p1_tracks AS (
    SELECT DISTINCT id, name, artist FROM tracks WHERE playlist_source = 'playlist_1'
),
p2_tracks AS (
    SELECT DISTINCT id, name, artist FROM tracks WHERE playlist_source = 'playlist_2'
)
SELECT
    (SELECT COUNT(*) FROM p1_tracks) as playlist1_unique,
    (SELECT COUNT(*) FROM p2_tracks) as playlist2_unique,
    (SELECT COUNT(*) FROM p1_tracks WHERE id IN (SELECT id FROM p2_tracks)) as in_both,
    (SELECT COUNT(*) FROM p1_tracks WHERE id NOT IN (SELECT id FROM p2_tracks)) as only_in_p1,
    (SELECT COUNT(*) FROM p2_tracks WHERE id NOT IN (SELECT id FROM p1_tracks)) as only_in_p2;
```

### Visualization Plan

```python
import matplotlib.pyplot as plt
import seaborn as sns

fig, axes = plt.subplots(3, 2, figsize=(14, 15))

# 1. Weight Distribution Histogram (Playlist 1)
axes[0, 0].hist(weights_df['weight'], bins=50, edgecolor='black')
axes[0, 0].set_title('Track Weight Distribution (Playlist 1)')
axes[0, 0].set_xlabel('Weight (times duplicated)')
axes[0, 0].set_ylabel('Number of Tracks')
axes[0, 0].axvline(weights_df['weight'].median(), color='red', linestyle='--', label='Median')

# 2. Top 20 weighted tracks (horizontal bar)
top_20 = weights_df.nlargest(20, 'weight')
axes[0, 1].barh(top_20['name'] + ' - ' + top_20['artist'], top_20['weight'])
axes[0, 1].set_title('Top 20 Most Weighted Tracks')
axes[0, 1].invert_yaxis()

# 3. Duplication ratio over time (detect end of weighting)
axes[1, 0].plot(timeline_df['month'], timeline_df['duplication_ratio'], marker='o')
axes[1, 0].axhline(1.0, color='red', linestyle='--', label='No duplicates')
axes[1, 0].set_title('Duplication Ratio Over Time')
axes[1, 0].set_xlabel('Month')
axes[1, 0].set_ylabel('Entries / Unique Tracks')
axes[1, 0].legend()

# 4. Playlist overlap Venn diagram (conceptual bar chart)
overlap_data = ['Only P1', 'Both', 'Only P2']
overlap_values = [only_in_p1, in_both, only_in_p2]
axes[1, 1].bar(overlap_data, overlap_values, color=['blue', 'purple', 'green'])
axes[1, 1].set_title('Playlist Overlap')
axes[1, 1].set_ylabel('Unique Tracks')

# 5. Top artists by total weight
axes[2, 0].bar(artist_weights['artist'][:15], artist_weights['total_weight'][:15])
axes[2, 0].set_title('Top 15 Artists by Total Weight')
axes[2, 0].tick_params(axis='x', rotation=45)

# 6. Weight vs first_added scatter (did favorites get added early?)
axes[2, 1].scatter(weights_df['first_added'], weights_df['weight'], alpha=0.5)
axes[2, 1].set_title('Weight vs. First Added Date')
axes[2, 1].set_xlabel('First Added')
axes[2, 1].set_ylabel('Weight')

plt.tight_layout()
plt.savefig('weight_analysis.png', dpi=150)
```

---

## Data Storage Strategy

### User Requirement: Store Complete API Responses

We will preserve the **entire JSON objects** that Spotify returns, not just extracted fields.

**Rationale**:
- Don't know which fields will be useful for future analysis
- Spotify may include undocumented or new fields
- Re-fetching 18k+ tracks is expensive
- Raw data enables ad-hoc queries later

### Storage Flow

```
┌───────────────────────────────────────────────────────────────┐
│                      FETCH PHASE                               │
├───────────────────────────────────────────────────────────────┤
│  API Call → Batch (100 tracks) → JSON checkpoint file         │
│                                                               │
│  data/checkpoints/                                            │
│  ├── playlist_1_batch_0.json     (tracks 0-99)               │
│  ├── playlist_1_batch_100.json   (tracks 100-199)            │
│  └── ...                                                      │
│                                                               │
│  Purpose: Resume if fetch fails mid-way                       │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                   IMPORT TO DUCKDB                             │
├───────────────────────────────────────────────────────────────┤
│  After successful fetch:                                       │
│  - Import all batches into DuckDB                             │
│  - Store BOTH raw JSON AND extracted fields                   │
│  - Delete checkpoint files (optional)                         │
└───────────────────────────────────────────────────────────────┘
```

### DuckDB Schema with Raw JSON

```sql
-- Store complete raw API responses
CREATE TABLE raw_playlist_items (
    id INTEGER PRIMARY KEY,
    playlist_source VARCHAR NOT NULL,
    raw_json JSON NOT NULL,           -- FULL API response preserved
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extracted/structured view for fast analytics
CREATE TABLE tracks AS
SELECT
    raw_json->>'$.track.id' as id,
    raw_json->>'$.track.name' as name,
    raw_json->>'$.track.artists[0].name' as artist,
    raw_json->>'$.track.artists[0].id' as artist_id,
    raw_json->>'$.track.album.name' as album,
    raw_json->>'$.track.album.id' as album_id,
    raw_json->>'$.track.album.release_date' as release_date,
    CAST(raw_json->>'$.track.duration_ms' AS INTEGER) as duration_ms,
    CAST(raw_json->>'$.track.popularity' AS INTEGER) as popularity,
    CAST(raw_json->>'$.track.explicit' AS BOOLEAN) as explicit,
    raw_json->>'$.track.external_ids.isrc' as isrc,
    raw_json->>'$.added_at' as added_at,
    playlist_source,
    raw_json  -- Keep raw for ad-hoc queries
FROM raw_playlist_items;

-- Audio features (from separate API call)
CREATE TABLE audio_features (
    track_id VARCHAR PRIMARY KEY,
    raw_json JSON NOT NULL,           -- Full audio features response
    tempo FLOAT,                      -- Extracted BPM
    energy FLOAT,
    danceability FLOAT,
    valence FLOAT,                    -- Mood (0=sad, 1=happy)
    acousticness FLOAT,
    instrumentalness FLOAT,
    key INTEGER,
    mode INTEGER,                     -- 0=minor, 1=major
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Why This Approach

| Aspect | Benefit |
|--------|---------|
| **Checkpoint JSON files** | Resume from failure, human-readable debugging |
| **Raw JSON in DuckDB** | Query any field later, even ones we didn't extract |
| **Extracted columns** | Fast indexed queries for common analytics |
| **Single source of truth** | DuckDB is the permanent storage |

---

## Musical DNA: Deep Statistics

### Data Sources - CRITICAL DISTINCTION

The default track object from playlist fetch does **NOT include BPM, energy, or mood data**.

Spotify provides track information through **SEPARATE API endpoints**:

| Data Type | API Endpoint | What It Returns | Requires Extra API Call? |
|-----------|--------------|-----------------|--------------------------|
| **Basic Track Info** | `GET /playlists/{id}/tracks` | name, artist, album, popularity, duration, ISRC | **NO** - included in playlist fetch |
| **Audio Features** | `GET /audio-features` | BPM, energy, danceability, valence, key, acousticness | **YES** - separate endpoint |
| **Artist Info** | `GET /artists` | genres[], followers | **YES** - separate endpoint |

### Audio Features: A Separate API Call

```python
# Step 1: Get tracks from playlist (basic info only)
tracks = sp.playlist_tracks(playlist_id)
# Returns: name, artist, album, duration, popularity, ISRC
# Does NOT return: BPM, energy, danceability, valence, key

# Step 2: SEPARATE call to get audio features
track_ids = [t['track']['id'] for t in tracks['items']]
features = sp.audio_features(track_ids)  # Batch endpoint, max 100 IDs
# Returns: tempo (BPM), energy, danceability, valence, key, mode, etc.
```

### Audio Features Response Example

```json
{
  "danceability": 0.735,
  "energy": 0.578,
  "key": 5,
  "loudness": -11.840,
  "mode": 0,
  "speechiness": 0.0461,
  "acousticness": 0.514,
  "instrumentalness": 0.0902,
  "liveness": 0.159,
  "valence": 0.624,
  "tempo": 98.002,
  "type": "audio_features",
  "id": "track_id",
  "duration_ms": 255349,
  "time_signature": 4
}
```

### API Call Estimate

| Data Type | API Calls Required | Rate Limit Impact |
|-----------|-------------------|-------------------|
| Playlist 1 tracks | ~90 calls | Low |
| Playlist 2 tracks | ~90 calls | Low |
| **Audio Features** | **~150 calls** | **Medium (+2-3 min)** |
| Artist Genres | ~300+ calls | High - skip initially |

### Recommendation

**YES - Fetch Audio Features** because:
- Enables BPM, energy, mood analysis (the "Musical DNA")
- ~150 extra API calls is manageable
- Significantly enriches analysis
- Store raw JSON for future use

**SKIP Artist Genres** initially (can add later if desired)

### Statistical Questions to Answer

#### From Basic Track Data

1. **Popularity Distribution**: How popular are your saved tracks vs. Spotify average?
2. **Duration Analysis**: Average song length, shortest/longest, decade trends
3. **Release Year Spread**: What decades dominate? Any recent bias?
4. **Explicit Content Ratio**: What percentage is explicit?
5. **Artist Diversity**: How many unique artists? Concentration (Gini coefficient)?
6. **Album Diversity**: Full albums vs. cherry-picked singles?
7. **Playlist Comparison**: How do Playlist 1 and 2 differ in these metrics?

#### From Audio Features (if fetched)

1. **Tempo (BPM)**: Distribution, preferred tempo ranges, workout vs. chill
2. **Energy**: High-energy vs. low-energy balance
3. **Danceability**: Party-ready percentage
4. **Valence (Mood)**: Happy vs. sad distribution
5. **Key/Mode**: Major vs. minor key preferences
6. **Acousticness/Instrumentalness**: Vocal vs. instrumental preferences

### Query Design: Basic Stats

```sql
-- Comprehensive basic statistics (both playlists)
SELECT
    playlist_source,
    COUNT(*) as total_entries,
    COUNT(DISTINCT id) as unique_tracks,
    COUNT(DISTINCT artist) as unique_artists,
    COUNT(DISTINCT album) as unique_albums,

    -- Popularity
    ROUND(AVG(popularity), 2) as avg_popularity,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY popularity) as median_popularity,

    -- Duration
    ROUND(AVG(duration_ms) / 60000, 2) as avg_duration_minutes,

    -- Time span
    MIN(release_date) as oldest_release,
    MAX(release_date) as newest_release,

    -- Explicit
    ROUND(100.0 * SUM(CASE WHEN explicit THEN 1 ELSE 0 END) / COUNT(*), 2) as explicit_percentage

FROM tracks
GROUP BY playlist_source;

-- Combined stats (after deduplication)
SELECT
    COUNT(DISTINCT id) as total_unique_tracks,
    COUNT(DISTINCT artist) as total_unique_artists,
    COUNT(DISTINCT album) as total_unique_albums,
    ROUND(AVG(popularity), 2) as avg_popularity,
    ROUND(AVG(duration_ms) / 60000, 2) as avg_duration_min
FROM tracks;

-- Decade distribution
SELECT
    (EXTRACT(YEAR FROM release_date::DATE) / 10 * 10)::INT as decade,
    COUNT(DISTINCT id) as unique_tracks,
    COUNT(*) as total_occurrences,
    ROUND(AVG(popularity), 2) as avg_popularity,
    ROUND(AVG(duration_ms) / 60000, 2) as avg_duration_min
FROM tracks
WHERE release_date IS NOT NULL
GROUP BY decade
ORDER BY decade;

-- Artist concentration (top N artists account for X% of tracks)
WITH artist_counts AS (
    SELECT
        artist,
        COUNT(DISTINCT id) as track_count,
        SUM(COUNT(DISTINCT id)) OVER () as total_tracks
    FROM tracks
    GROUP BY artist
),
ranked AS (
    SELECT
        artist,
        track_count,
        total_tracks,
        SUM(track_count) OVER (ORDER BY track_count DESC) as cumulative,
        ROW_NUMBER() OVER (ORDER BY track_count DESC) as rank
    FROM artist_counts
)
SELECT
    rank,
    artist,
    track_count,
    ROUND(100.0 * cumulative / total_tracks, 2) as cumulative_percent
FROM ranked
WHERE rank <= 50;
```

### Query Design: Audio Features

```sql
-- Audio feature statistics
SELECT
    -- Tempo (BPM)
    ROUND(AVG(tempo), 1) as avg_bpm,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tempo), 1) as median_bpm,
    MIN(tempo) as min_bpm,
    MAX(tempo) as max_bpm,

    -- Energy (0-1)
    ROUND(AVG(energy), 3) as avg_energy,
    ROUND(100.0 * SUM(CASE WHEN energy > 0.7 THEN 1 ELSE 0 END) / COUNT(*), 1) as high_energy_percent,

    -- Danceability (0-1)
    ROUND(AVG(danceability), 3) as avg_danceability,
    ROUND(100.0 * SUM(CASE WHEN danceability > 0.7 THEN 1 ELSE 0 END) / COUNT(*), 1) as danceable_percent,

    -- Valence/Mood (0-1, higher = happier)
    ROUND(AVG(valence), 3) as avg_valence,
    ROUND(100.0 * SUM(CASE WHEN valence > 0.6 THEN 1 ELSE 0 END) / COUNT(*), 1) as happy_percent,
    ROUND(100.0 * SUM(CASE WHEN valence < 0.4 THEN 1 ELSE 0 END) / COUNT(*), 1) as sad_percent,

    -- Acousticness (0-1)
    ROUND(AVG(acousticness), 3) as avg_acousticness,
    ROUND(100.0 * SUM(CASE WHEN acousticness > 0.7 THEN 1 ELSE 0 END) / COUNT(*), 1) as acoustic_percent,

    -- Instrumentalness (0-1)
    ROUND(AVG(instrumentalness), 3) as avg_instrumentalness,
    ROUND(100.0 * SUM(CASE WHEN instrumentalness > 0.5 THEN 1 ELSE 0 END) / COUNT(*), 1) as instrumental_percent,

    -- Key distribution (0-11, C=0, C#=1, etc.)
    MODE() WITHIN GROUP (ORDER BY key) as most_common_key,

    -- Mode (0=minor, 1=major)
    ROUND(100.0 * SUM(mode) / COUNT(*), 1) as major_key_percent

FROM audio_features af
JOIN tracks t ON af.track_id = t.id;

-- BPM buckets for workout categorization
SELECT
    CASE
        WHEN tempo < 80 THEN 'Very Slow (<80 BPM)'
        WHEN tempo BETWEEN 80 AND 99 THEN 'Slow (80-99 BPM)'
        WHEN tempo BETWEEN 100 AND 119 THEN 'Moderate (100-119 BPM)'
        WHEN tempo BETWEEN 120 AND 139 THEN 'Upbeat (120-139 BPM)'
        WHEN tempo BETWEEN 140 AND 159 THEN 'Fast (140-159 BPM)'
        ELSE 'Very Fast (160+ BPM)'
    END as tempo_category,
    COUNT(*) as track_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage
FROM audio_features
GROUP BY tempo_category
ORDER BY MIN(tempo);

-- Energy vs Valence quadrant analysis (mood mapping)
SELECT
    CASE
        WHEN energy > 0.5 AND valence > 0.5 THEN 'Happy & Energetic'
        WHEN energy > 0.5 AND valence <= 0.5 THEN 'Angry & Intense'
        WHEN energy <= 0.5 AND valence > 0.5 THEN 'Chill & Happy'
        ELSE 'Sad & Calm'
    END as mood_quadrant,
    COUNT(*) as track_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) as percentage,
    ROUND(AVG(tempo), 1) as avg_bpm
FROM audio_features
GROUP BY mood_quadrant
ORDER BY track_count DESC;
```

### Visualization Plan: Musical DNA

```python
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

fig = plt.figure(figsize=(16, 20))

# 1. Decade Distribution (bar chart)
ax1 = fig.add_subplot(4, 2, 1)
decades_df.plot(kind='bar', x='decade', y='unique_tracks', ax=ax1, color='steelblue')
ax1.set_title('Tracks by Decade')
ax1.set_xlabel('Decade')
ax1.set_ylabel('Unique Tracks')

# 2. Popularity Distribution (histogram with KDE)
ax2 = fig.add_subplot(4, 2, 2)
sns.histplot(tracks_df['popularity'], bins=30, kde=True, ax=ax2)
ax2.axvline(tracks_df['popularity'].mean(), color='red', linestyle='--', label=f'Mean: {tracks_df["popularity"].mean():.1f}')
ax2.set_title('Popularity Distribution')
ax2.legend()

# 3. BPM Distribution (histogram)
ax3 = fig.add_subplot(4, 2, 3)
sns.histplot(audio_df['tempo'], bins=40, kde=True, ax=ax3, color='green')
ax3.set_title('Tempo (BPM) Distribution')
ax3.set_xlabel('BPM')

# 4. Energy vs Valence Scatter (mood map)
ax4 = fig.add_subplot(4, 2, 4)
scatter = ax4.scatter(audio_df['valence'], audio_df['energy'],
                      c=audio_df['tempo'], cmap='viridis', alpha=0.5, s=10)
ax4.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
ax4.axvline(0.5, color='gray', linestyle='--', alpha=0.5)
ax4.set_xlabel('Valence (Sad → Happy)')
ax4.set_ylabel('Energy (Calm → Energetic)')
ax4.set_title('Mood Map (color = BPM)')
plt.colorbar(scatter, ax=ax4, label='BPM')
# Quadrant labels
ax4.text(0.75, 0.75, 'Happy & Energetic', fontsize=9, ha='center')
ax4.text(0.25, 0.75, 'Angry & Intense', fontsize=9, ha='center')
ax4.text(0.75, 0.25, 'Chill & Happy', fontsize=9, ha='center')
ax4.text(0.25, 0.25, 'Sad & Calm', fontsize=9, ha='center')

# 5. Top Artists (horizontal bar)
ax5 = fig.add_subplot(4, 2, 5)
top_artists = artist_stats.nlargest(15, 'track_count')
ax5.barh(top_artists['artist'], top_artists['track_count'], color='coral')
ax5.invert_yaxis()
ax5.set_title('Top 15 Artists by Track Count')

# 6. Key Distribution (pie chart)
ax6 = fig.add_subplot(4, 2, 6)
key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
key_counts = audio_df['key'].value_counts().sort_index()
ax6.pie(key_counts.values, labels=[key_names[i] for i in key_counts.index],
        autopct='%1.1f%%', startangle=90)
ax6.set_title('Musical Key Distribution')

# 7. Duration Distribution (box plot by decade)
ax7 = fig.add_subplot(4, 2, 7)
tracks_df['decade'] = (pd.to_datetime(tracks_df['release_date']).dt.year // 10 * 10).astype(str)
tracks_df['duration_min'] = tracks_df['duration_ms'] / 60000
sns.boxplot(data=tracks_df, x='decade', y='duration_min', ax=ax7)
ax7.set_title('Song Duration by Decade')
ax7.set_ylabel('Duration (minutes)')

# 8. Playlist comparison (grouped bar)
ax8 = fig.add_subplot(4, 2, 8)
comparison = playlist_stats.set_index('playlist_source')[['avg_popularity', 'avg_duration_minutes', 'explicit_percentage']]
comparison.plot(kind='bar', ax=ax8)
ax8.set_title('Playlist Comparison')
ax8.set_ylabel('Value')
ax8.legend(loc='upper right')

plt.tight_layout()
plt.savefig('musical_dna.png', dpi=150)
```

---

## Deduplication Strategy

### User Requirements

> "Different track = different item. Remix and original = different tracks!"

This means: **Strict ID-based matching only.**

### Updated Context: Two-Playlist Merge

Given the playlist asymmetry:
1. **Playlist 1**: Has duplicates from weighted shuffle era
2. **Playlist 2**: Clean, no duplicates (post-Spotify update)

Deduplication must handle:
- **Intra-playlist duplicates**: Same track ID multiple times in Playlist 1
- **Cross-playlist duplicates**: Same track ID in both playlists

### Deduplication Methods Compared

| Method | Description | Use Case | Our Project |
|--------|-------------|----------|-------------|
| **Track ID** | Exact Spotify URI match | Strict, literal duplicates | **PRIMARY** |
| **ISRC** | International recording identifier | Same recording, different releases | Optional report |
| **Fuzzy Name** | "Song - Remastered" ≈ "Song" | Merge remasters | **EXCLUDED** |
| **Audio Fingerprint** | Acoustic similarity | Find cover versions | Out of scope |

### Implementation: ID-Based Deduplication

```sql
-- Deduplicate and track source information
CREATE TABLE unique_tracks AS
SELECT
    id,
    name,
    ANY_VALUE(artist) as artist,
    ANY_VALUE(album) as album,
    ANY_VALUE(release_date) as release_date,
    ANY_VALUE(duration_ms) as duration_ms,
    ANY_VALUE(popularity) as popularity,
    ANY_VALUE(isrc) as isrc,
    MIN(added_at) as first_added,
    MAX(added_at) as last_added,
    -- Source tracking
    SUM(CASE WHEN playlist_source = 'playlist_1' THEN 1 ELSE 0 END) as playlist1_count,
    SUM(CASE WHEN playlist_source = 'playlist_2' THEN 1 ELSE 0 END) as playlist2_count,
    COUNT(*) as total_weight
FROM tracks
GROUP BY id, name
ORDER BY first_added;

-- Verification
SELECT
    (SELECT COUNT(*) FROM tracks) as original_entries,
    (SELECT COUNT(*) FROM unique_tracks) as unique_tracks,
    (SELECT COUNT(*) FROM tracks WHERE playlist_source = 'playlist_1') as p1_entries,
    (SELECT COUNT(*) FROM tracks WHERE playlist_source = 'playlist_2') as p2_entries,
    (SELECT SUM(playlist1_count) FROM unique_tracks WHERE playlist2_count > 0) as cross_playlist_overlap,
    (SELECT COUNT(*) FROM tracks) - (SELECT COUNT(*) FROM unique_tracks) as duplicates_removed;
```

### Source Preservation for Analysis

Even after deduplication, we preserve:
- `playlist1_count`: How many times in Playlist 1 (the "weight")
- `playlist2_count`: Whether also in Playlist 2 (0 or 1)
- `first_added`: When you first saved this track
- `total_weight`: Combined count across both playlists

This enables post-hoc analysis like:
- "Show me my Playlist 1 favorites that I didn't add to Playlist 2"
- "Show me tracks I added to both playlists"

### Informational: ISRC-Based Analysis (Not Used for Dedup)

Even though we won't merge by ISRC, it's interesting to report:

```sql
-- Find same recording with different Spotify IDs (re-releases, regional variants)
SELECT
    isrc,
    COUNT(DISTINCT id) as spotify_ids,
    ARRAY_AGG(DISTINCT name) as track_names,
    ARRAY_AGG(DISTINCT album) as albums
FROM tracks
WHERE isrc IS NOT NULL
GROUP BY isrc
HAVING COUNT(DISTINCT id) > 1
ORDER BY COUNT(DISTINCT id) DESC
LIMIT 20;
```

This answers: "Do I have the same song saved from different albums?"

### Fuzzy Matching (Excluded Per Requirements)

For reference only - what we're NOT doing:

```python
# Example of fuzzy matching (NOT USED)
from fuzzywuzzy import fuzz

def normalize_track_name(name):
    # Remove common suffixes
    suffixes = ['remastered', 'remaster', 'deluxe', 'extended', 'radio edit', 'single version']
    name_lower = name.lower()
    for suffix in suffixes:
        name_lower = name_lower.replace(f'- {suffix}', '').replace(f'({suffix})', '')
    return name_lower.strip()

# This would group "Song - 2021 Remaster" with "Song"
# But user said: these are DIFFERENT tracks
```

### Deduplication Report

Before applying deduplication, generate a report:

```sql
-- Deduplication preview report
SELECT
    id,
    name,
    artist,
    COUNT(*) as duplicate_count,
    SUM(CASE WHEN playlist_source = 'playlist_1' THEN 1 ELSE 0 END) as in_p1,
    SUM(CASE WHEN playlist_source = 'playlist_2' THEN 1 ELSE 0 END) as in_p2,
    ARRAY_AGG(added_at ORDER BY added_at) as addition_dates,
    ARRAY_AGG(DISTINCT playlist_source) as source_playlists
FROM tracks
GROUP BY id, name, artist
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

---

## Output Formats Comparison

### Options Evaluated

| Format | Pros | Cons | Best For |
|--------|------|------|----------|
| **CLI Reports** | Quick, scriptable, no dependencies | Limited visualizations | Progress updates, quick checks |
| **JSON Exports** | Machine-readable, portable | Not human-friendly | Integration with other tools |
| **Jupyter Notebook** | Interactive, rich visualizations | Requires Jupyter setup | Exploration, debugging |
| **HTML Dashboard** | Shareable, professional | Static, more dev effort | Final reports, sharing |

### Recommendation: Tiered Approach

```
┌─────────────────────────────────────────────────────────────────┐
│                    Output Strategy                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Development & Exploration:  Jupyter Notebook                   │
│  ├── Interactive cell execution                                 │
│  ├── Inline visualizations                                      │
│  └── Easy iteration on queries                                  │
│                                                                 │
│  Automated Exports:          JSON Files                         │
│  ├── deduplicated_tracks.json                                   │
│  ├── weight_analysis.json                                       │
│  ├── musical_dna_stats.json                                     │
│  └── dedup_preview_report.json                                  │
│                                                                 │
│  Final Report (Optional):    HTML via nbconvert or Plotly       │
│  ├── jupyter nbconvert --to html analysis.ipynb                 │
│  └── Or use Plotly for interactive HTML charts                  │
│                                                                 │
│  CLI Progress:               Rich library for terminal output   │
│  ├── Progress bars during fetch                                 │
│  ├── Summary statistics                                         │
│  └── Dry-run previews                                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### CLI Output Example (using Rich library)

```python
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()

# Progress during fetch
with Progress() as progress:
    task = progress.add_task("[cyan]Fetching tracks...", total=18000)
    for batch in fetch_batches():
        progress.update(task, advance=len(batch))

# Summary table
table = Table(title="Deduplication Summary")
table.add_column("Metric", style="cyan")
table.add_column("Value", style="green")

table.add_row("Playlist 1 entries", "9,234")
table.add_row("Playlist 2 entries", "9,000")
table.add_row("Total entries", "18,234")
table.add_row("Unique tracks (merged)", "15,891")
table.add_row("Duplicates removed", "2,343")
table.add_row("Cross-playlist overlap", "1,200")
table.add_row("Highest weight (P1)", "23 (Track Name - Artist)")

console.print(table)
```

### Jupyter Notebook Structure

```markdown
# Spotify Library Analysis

## 1. Data Loading
- Load from DuckDB
- Verify record counts per playlist

## 2. Weight Analysis (Playlist 1 Focus)
- Distribution histogram
- Top 50 weighted tracks
- Artist weighting patterns
- Timeline: when did weighting end?

## 3. Musical DNA
- Basic stats summary (per playlist & combined)
- Decade distribution
- Popularity analysis
- Audio features (if fetched)
- Mood mapping

## 4. Playlist Comparison
- Overlap analysis (Venn diagram)
- Unique to P1 vs P2
- Cross-playlist favorites

## 5. Deduplication Preview
- Duplicate report
- Same-ISRC analysis (informational)
- Impact summary

## 6. Export
- Generate JSON exports
- Create deduplicated playlist data
```

### JSON Export Schema

```json
{
  "metadata": {
    "generated_at": "2024-01-15T10:30:00Z",
    "source_playlists": {
      "playlist_1": {"id": "...", "entries": 9234},
      "playlist_2": {"id": "...", "entries": 9000}
    },
    "total_entries": 18234,
    "unique_tracks": 15891,
    "cross_playlist_overlap": 1200
  },
  "weight_analysis": {
    "note": "Weight analysis applies to Playlist 1 only (pre-Spotify update)",
    "distribution": {
      "1": 8000,
      "2-3": 800,
      "4-6": 300,
      "7-10": 100,
      "11+": 34
    },
    "top_50": [
      {
        "id": "track_id",
        "name": "Track Name",
        "artist": "Artist Name",
        "weight": 23,
        "also_in_playlist_2": true
      }
    ],
    "weighting_ended_approximately": "2023-06-01"
  },
  "musical_dna": {
    "basic_stats": {
      "avg_popularity": 58.3,
      "median_popularity": 62,
      "avg_duration_minutes": 3.84,
      "explicit_percentage": 34.2,
      "unique_artists": 2341,
      "unique_albums": 4521
    },
    "playlist_comparison": {
      "playlist_1": {"avg_popularity": 56.1, "explicit_pct": 32.0},
      "playlist_2": {"avg_popularity": 60.5, "explicit_pct": 36.4}
    },
    "decade_distribution": {
      "1960": 120,
      "1970": 450,
      "1980": 890
    },
    "audio_features": {
      "avg_bpm": 118.5,
      "avg_energy": 0.654,
      "avg_danceability": 0.612,
      "mood_quadrants": {
        "happy_energetic": 35.2,
        "angry_intense": 22.1,
        "chill_happy": 28.4,
        "sad_calm": 14.3
      }
    }
  },
  "deduplicated_tracks": [
    {
      "id": "track_id",
      "name": "Track Name",
      "artist": "Artist Name",
      "album": "Album Name",
      "playlist1_weight": 5,
      "in_playlist2": true,
      "first_added": "2020-03-15T12:00:00Z"
    }
  ]
}
```

---

## Implementation Blueprint

### File Structure

```
spotify-analyzer/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── auth.py           # Spotify OAuth handling
│   ├── fetch.py          # Data fetching with checkpoints
│   ├── storage.py        # DuckDB operations
│   └── analyze.py        # Analytics queries
├── notebooks/
│   ├── 01_exploration.ipynb
│   ├── 02_weight_analysis.ipynb
│   ├── 03_musical_dna.ipynb
│   └── 04_deduplication.ipynb
├── data/
│   ├── checkpoints/      # JSON fetch checkpoints
│   ├── spotify.duckdb    # Main database
│   └── exports/          # JSON/CSV exports
└── docs/
    └── (these stage documents)
```

### Analytics Pipeline

```python
# analyze.py

import duckdb
import pandas as pd
from pathlib import Path

class SpotifyAnalyzer:
    def __init__(self, db_path: str = "data/spotify.duckdb"):
        self.conn = duckdb.connect(db_path)

    def get_weight_analysis(self, playlist_filter: str = None) -> pd.DataFrame:
        """Calculate track weights (duplicate counts)."""
        where_clause = f"WHERE playlist_source = '{playlist_filter}'" if playlist_filter else ""
        return self.conn.execute(f"""
            SELECT
                id,
                name,
                artist,
                album,
                COUNT(*) as weight,
                MIN(added_at) as first_added,
                MAX(added_at) as last_added
            FROM tracks
            {where_clause}
            GROUP BY id, name, artist, album
            ORDER BY weight DESC
        """).fetchdf()

    def get_weight_distribution(self, playlist_filter: str = None) -> pd.DataFrame:
        """Get weight distribution buckets."""
        where_clause = f"WHERE playlist_source = '{playlist_filter}'" if playlist_filter else ""
        return self.conn.execute(f"""
            WITH weights AS (
                SELECT id, COUNT(*) as weight FROM tracks {where_clause} GROUP BY id
            )
            SELECT
                CASE
                    WHEN weight = 1 THEN '1'
                    WHEN weight BETWEEN 2 AND 3 THEN '2-3'
                    WHEN weight BETWEEN 4 AND 6 THEN '4-6'
                    WHEN weight BETWEEN 7 AND 10 THEN '7-10'
                    ELSE '11+'
                END as bucket,
                COUNT(*) as count
            FROM weights
            GROUP BY bucket
        """).fetchdf()

    def get_basic_stats(self) -> dict:
        """Get basic library statistics."""
        result = self.conn.execute("""
            SELECT
                COUNT(*) as total_entries,
                COUNT(DISTINCT id) as unique_tracks,
                COUNT(DISTINCT artist) as unique_artists,
                COUNT(DISTINCT album) as unique_albums,
                ROUND(AVG(popularity), 2) as avg_popularity,
                ROUND(AVG(duration_ms) / 60000, 2) as avg_duration_min,
                MIN(release_date) as oldest_track,
                MAX(release_date) as newest_track
            FROM tracks
        """).fetchone()
        return dict(zip(
            ['total_entries', 'unique_tracks', 'unique_artists', 'unique_albums',
             'avg_popularity', 'avg_duration_min', 'oldest_track', 'newest_track'],
            result
        ))

    def get_playlist_comparison(self) -> pd.DataFrame:
        """Compare stats between playlists."""
        return self.conn.execute("""
            SELECT
                playlist_source,
                COUNT(*) as entries,
                COUNT(DISTINCT id) as unique_tracks,
                COUNT(DISTINCT artist) as unique_artists,
                ROUND(AVG(popularity), 2) as avg_popularity,
                ROUND(100.0 * SUM(CASE WHEN explicit THEN 1 ELSE 0 END) / COUNT(*), 2) as explicit_pct
            FROM tracks
            GROUP BY playlist_source
        """).fetchdf()

    def get_cross_playlist_analysis(self) -> dict:
        """Analyze overlap between playlists."""
        result = self.conn.execute("""
            WITH p1_ids AS (SELECT DISTINCT id FROM tracks WHERE playlist_source = 'playlist_1'),
                 p2_ids AS (SELECT DISTINCT id FROM tracks WHERE playlist_source = 'playlist_2')
            SELECT
                (SELECT COUNT(*) FROM p1_ids) as p1_unique,
                (SELECT COUNT(*) FROM p2_ids) as p2_unique,
                (SELECT COUNT(*) FROM p1_ids WHERE id IN (SELECT id FROM p2_ids)) as in_both,
                (SELECT COUNT(*) FROM p1_ids WHERE id NOT IN (SELECT id FROM p2_ids)) as only_p1,
                (SELECT COUNT(*) FROM p2_ids WHERE id NOT IN (SELECT id FROM p1_ids)) as only_p2
        """).fetchone()
        return dict(zip(['p1_unique', 'p2_unique', 'in_both', 'only_p1', 'only_p2'], result))

    def get_deduplicated_tracks(self) -> pd.DataFrame:
        """Get unique tracks with source info preserved."""
        return self.conn.execute("""
            SELECT
                id,
                name,
                ANY_VALUE(artist) as artist,
                ANY_VALUE(album) as album,
                ANY_VALUE(release_date) as release_date,
                ANY_VALUE(duration_ms) as duration_ms,
                ANY_VALUE(popularity) as popularity,
                ANY_VALUE(isrc) as isrc,
                MIN(added_at) as first_added,
                SUM(CASE WHEN playlist_source = 'playlist_1' THEN 1 ELSE 0 END) as playlist1_weight,
                SUM(CASE WHEN playlist_source = 'playlist_2' THEN 1 ELSE 0 END) as in_playlist2,
                COUNT(*) as total_weight
            FROM tracks
            GROUP BY id, name
            ORDER BY first_added
        """).fetchdf()

    def generate_dry_run_report(self) -> dict:
        """Generate a preview of what deduplication will do."""
        stats = self.get_basic_stats()
        deduped = self.get_deduplicated_tracks()
        cross = self.get_cross_playlist_analysis()
        p1_weights = self.get_weight_analysis(playlist_filter='playlist_1')

        return {
            'before': {
                'total_entries': stats['total_entries'],
                'playlist_1_entries': len(self.conn.execute(
                    "SELECT 1 FROM tracks WHERE playlist_source = 'playlist_1'").fetchall()),
                'playlist_2_entries': len(self.conn.execute(
                    "SELECT 1 FROM tracks WHERE playlist_source = 'playlist_2'").fetchall()),
            },
            'after': {
                'unique_tracks': len(deduped),
            },
            'overlap': cross,
            'weight_stats': {
                'highest_weight_p1': int(p1_weights['weight'].max()) if len(p1_weights) > 0 else 0,
                'avg_weight_p1': round(p1_weights['weight'].mean(), 2) if len(p1_weights) > 0 else 0,
                'tracks_with_duplicates_p1': len(p1_weights[p1_weights['weight'] > 1]),
            },
            'impact': {
                'duplicates_removed': stats['total_entries'] - len(deduped),
            }
        }

    def export_to_json(self, output_dir: str = "data/exports"):
        """Export all analysis results to JSON."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Export each analysis
        self.get_weight_analysis('playlist_1').to_json(
            output_path / "weight_analysis_p1.json", orient="records")
        self.get_deduplicated_tracks().to_json(
            output_path / "deduplicated_tracks.json", orient="records")
        self.get_playlist_comparison().to_json(
            output_path / "playlist_comparison.json", orient="records")

        # Summary
        import json
        with open(output_path / "summary.json", 'w') as f:
            json.dump({
                'basic_stats': self.get_basic_stats(),
                'cross_playlist': self.get_cross_playlist_analysis(),
                'dry_run_report': self.generate_dry_run_report()
            }, f, indent=2, default=str)
```

---

## Decision Log

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Dedup method | ID, ISRC, Fuzzy | ID-only | User requirement: strict matching |
| Audio features | Skip, Fetch all | Fetch all | Enriches analysis, manageable API cost |
| Primary output | CLI, JSON, Jupyter, HTML | Jupyter + JSON | Best exploration + portability combo |
| Weight scope | Both playlists, P1 only | P1 focus + cross-playlist | Reflects actual duplication history |
| Source tracking | Discard, Preserve | Preserve | Enables rich cross-playlist analysis |

---

## Next Steps

Pending your approval:

1. **Stage 4**: High-Performance Execution plan (rate limits, batching, dry run)
2. **Begin implementation** once all stages approved
