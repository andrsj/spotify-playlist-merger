# Stage 2: Storage Strategy (The "Source of Truth")

## Executive Summary

This document evaluates storage approaches for persisting 18,000+ Spotify tracks. After analyzing flat files (JSON/CSV), relational databases (SQLite/DuckDB), and document stores (TinyDB), **DuckDB** emerges as the optimal choice for its unique combination of analytical power, pandas integration, and zero-configuration setup.

---

## Table of Contents

1. [Why We Need Persistent Storage](#why-we-need-persistent-storage)
2. [Data Volume Analysis](#data-volume-analysis)
3. [Storage Option Deep Dive](#storage-option-deep-dive)
4. [Benchmark: Query Patterns](#benchmark-query-patterns)
5. [Integration with Analytics Stage](#integration-with-analytics-stage)
6. [Final Recommendation](#final-recommendation)
7. [Deep Dive: Raw JSON vs Structured Storage](#deep-dive-raw-json-vs-structured-storage)

---

## Why We Need Persistent Storage

### Problem: API Fragility

```
18,000 tracks × (1 base call + potential 429 retries) = 360+ API calls
360 calls × 150ms average = 54+ seconds minimum fetch time
```

If anything fails mid-fetch (network drop, token expiry, rate limit storm):
- Without storage: Start from scratch
- With storage: Resume from checkpoint

### Problem: Analysis Iterations

The analytics stage will involve:
- Multiple exploratory queries
- Refining deduplication logic
- Generating various reports

Re-fetching from Spotify API for each iteration:
- Wastes time (54+ seconds each time)
- Risks rate limit exhaustion
- Is unnecessary once data is captured

### Requirements for Storage

| Requirement | Weight | Rationale |
|-------------|--------|-----------|
| Query speed for analytics | High | Will run many aggregations |
| Schema flexibility | Medium | Spotify API may return unexpected fields |
| Resume/checkpoint support | High | Handle failed fetches |
| Export capabilities | Medium | Generate reports in various formats |
| Zero config | High | One-time project, no setup overhead |

---

## Data Volume Analysis

### Track Object Structure (Simplified)

```json
{
  "added_at": "2023-05-15T10:30:00Z",
  "added_by": {"id": "user123"},
  "track": {
    "id": "4iV5W9uYEdYUVa79Axb7Rh",
    "name": "Take On Me",
    "artists": [{"id": "...", "name": "a-ha"}],
    "album": {
      "id": "...",
      "name": "Hunting High and Low",
      "release_date": "1985-06-01",
      "images": [{"url": "...", "height": 640, "width": 640}]
    },
    "duration_ms": 225280,
    "explicit": false,
    "popularity": 85,
    "external_ids": {"isrc": "USRC18500250"},
    "external_urls": {"spotify": "..."}
  }
}
```

### Storage Size Estimates

| Data Type | Size per Track | Total (18,000) |
|-----------|---------------|----------------|
| Raw JSON (full response) | ~2-3 KB | 36-54 MB |
| Normalized (essential fields) | ~500 bytes | 9 MB |
| With audio features | +200 bytes | +3.6 MB |

**Conclusion**: All storage options can easily handle this volume.

---

## Storage Option Deep Dive

### Option 1: Flat Files (JSON/CSV)

#### JSON Approach

```python
import json

# Save raw API responses
def save_checkpoint(tracks, filename="tracks.json"):
    with open(filename, 'w') as f:
        json.dump(tracks, f, indent=2)

# Load for analysis
def load_tracks(filename="tracks.json"):
    with open(filename, 'r') as f:
        return json.load(f)

# Checkpoint during fetch
def fetch_with_checkpoint(playlist_id):
    tracks = []
    offset = 0

    while True:
        batch = fetch_batch(playlist_id, offset)
        tracks.extend(batch)

        # Checkpoint every 500 tracks
        if len(tracks) % 500 == 0:
            save_checkpoint(tracks, f"checkpoint_{len(tracks)}.json")

        if not batch:
            break
        offset += 100

    save_checkpoint(tracks, "final.json")
    return tracks
```

#### CSV Approach

```python
import csv
import pandas as pd

# Flatten nested structure for CSV
def track_to_row(item):
    track = item['track']
    return {
        'id': track['id'],
        'name': track['name'],
        'artist': track['artists'][0]['name'],
        'album': track['album']['name'],
        'added_at': item['added_at'],
        'duration_ms': track['duration_ms'],
        'popularity': track['popularity'],
        'isrc': track.get('external_ids', {}).get('isrc'),
    }

# Write to CSV
with open('tracks.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[...])
    writer.writeheader()
    writer.writerows(track_to_row(t) for t in tracks)

# Load into pandas
df = pd.read_csv('tracks.csv')
```

#### Pros
- Zero dependencies
- Human-readable
- Easy to version control (JSON)
- Simple to share

#### Cons
- **No query optimization** - every analysis reads entire file
- **JSON**: Slow for repeated queries on large files
- **CSV**: Loses nested structure (artists, albums)
- No indexing for duplicate detection
- Manual checkpoint management

#### Query Performance

```python
# Every query loads entire dataset
df = pd.read_csv('tracks.csv')  # ~500ms for 18k rows

# Want to find one track? Still loads everything
df = pd.read_csv('tracks.csv')
result = df[df['id'] == 'abc123']
```

#### Scalability: 18,000 Records
- **Load time**: ~0.5-1 second for full read
- **Memory**: Entire dataset in RAM
- **Acceptable**: Yes, but not optimal for iterative analysis

---

### Option 2: SQLite

#### Schema Design

```sql
-- Normalized schema for efficient queries
CREATE TABLE artists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE albums (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    release_date TEXT,
    artist_id TEXT REFERENCES artists(id)
);

CREATE TABLE tracks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    album_id TEXT REFERENCES albums(id),
    duration_ms INTEGER,
    popularity INTEGER,
    explicit BOOLEAN,
    isrc TEXT
);

CREATE TABLE playlist_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id TEXT NOT NULL,
    track_id TEXT REFERENCES tracks(id),
    added_at TEXT,
    added_by TEXT
);

-- Indexes for common queries
CREATE INDEX idx_playlist_track ON playlist_tracks(playlist_id, track_id);
CREATE INDEX idx_track_isrc ON tracks(isrc);
```

#### Python Integration

```python
import sqlite3
import pandas as pd

# Create connection
conn = sqlite3.connect('spotify.db')

# Insert with upsert (handle duplicates)
def insert_track(conn, track_data):
    conn.execute("""
        INSERT OR REPLACE INTO tracks (id, name, album_id, duration_ms, popularity, isrc)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        track_data['id'],
        track_data['name'],
        track_data['album']['id'],
        track_data['duration_ms'],
        track_data['popularity'],
        track_data.get('external_ids', {}).get('isrc')
    ))

# Query directly into pandas
df = pd.read_sql_query("""
    SELECT
        t.id,
        t.name,
        a.name as artist,
        COUNT(*) as duplicate_count
    FROM playlist_tracks pt
    JOIN tracks t ON pt.track_id = t.id
    JOIN artists a ON t.artist_id = a.id
    GROUP BY t.id
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC
""", conn)
```

#### Pros
- **Zero configuration** - single file database
- **SQL power** - complex queries, JOINs, aggregations
- **Indexing** - fast lookups by ID or ISRC
- **ACID compliance** - safe checkpoint/resume
- **pd.read_sql_query()** - direct pandas integration
- **Widely understood** - SQL is universal

#### Cons
- **Schema rigidity** - must define tables upfront
- **Normalized schema overhead** - more complex inserts
- **Not optimized for analytics** - row-based storage

#### Query Performance

```python
# Only reads what's needed
df = pd.read_sql_query("""
    SELECT id, name FROM tracks WHERE id = 'abc123'
""", conn)  # ~1-5ms with index

# Aggregation pushes compute to SQLite
df = pd.read_sql_query("""
    SELECT track_id, COUNT(*) as cnt
    FROM playlist_tracks
    GROUP BY track_id
    HAVING cnt > 1
""", conn)  # ~10-50ms for 18k rows
```

#### Scalability: 18,000 Records
- **Query time**: 1-50ms depending on complexity
- **Memory**: Only loads query results
- **Excellent**: Indexes make it fast

---

### Option 3: DuckDB

#### What is DuckDB?

DuckDB is an embedded analytical database (like SQLite, but column-oriented). It's designed for data science workloads:
- **Columnar storage** - efficient for aggregations
- **Vectorized execution** - processes data in batches
- **Direct pandas integration** - query DataFrames with SQL
- **Zero configuration** - single file, pip install

#### Schema Design

```sql
-- DuckDB supports semi-structured data
CREATE TABLE raw_tracks (
    data JSON,  -- Store full API response
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Or structured for analytics
CREATE TABLE tracks (
    id VARCHAR PRIMARY KEY,
    name VARCHAR,
    artist_names VARCHAR[],  -- DuckDB supports arrays!
    album_name VARCHAR,
    album_release_date DATE,
    duration_ms INTEGER,
    popularity INTEGER,
    isrc VARCHAR,
    added_at TIMESTAMP,
    playlist_source VARCHAR
);
```

#### Python Integration

```python
import duckdb
import pandas as pd

# Connect (creates file if not exists)
conn = duckdb.connect('spotify.duckdb')

# Insert from pandas DataFrame directly
tracks_df = pd.DataFrame(tracks_data)
conn.execute("INSERT INTO tracks SELECT * FROM tracks_df")

# Query with SQL, get pandas DataFrame
result = conn.execute("""
    SELECT
        id,
        name,
        artist_names[1] as primary_artist,
        COUNT(*) OVER (PARTITION BY id) as duplicate_count
    FROM tracks
    QUALIFY duplicate_count > 1
    ORDER BY duplicate_count DESC
""").fetchdf()

# Or query a pandas DataFrame directly without storing
conn.execute("""
    SELECT id, COUNT(*) as cnt
    FROM df  -- 'df' is a Python variable!
    GROUP BY id
    HAVING cnt > 1
""")
```

#### Killer Feature: Query pandas DataFrames Directly

```python
# No need to insert into database first!
import duckdb
import pandas as pd

# Your pandas DataFrame
tracks_df = pd.DataFrame(...)

# Query it with SQL immediately
result = duckdb.query("""
    SELECT
        artist_names[1] as artist,
        AVG(popularity) as avg_popularity,
        COUNT(*) as track_count
    FROM tracks_df
    GROUP BY artist
    ORDER BY track_count DESC
    LIMIT 20
""").to_df()
```

#### Pros
- **Analytics-optimized** - columnar storage for fast aggregations
- **pandas native** - query DataFrames with SQL, zero friction
- **Modern SQL** - window functions, QUALIFY, array types
- **Zero configuration** - `pip install duckdb`, single file
- **Fast** - 10-100x faster than SQLite for analytical queries
- **Flexible schema** - supports JSON columns and arrays

#### Cons
- **Newer** - less battle-tested than SQLite (but stable)
- **Not for OLTP** - row updates are slower than SQLite
- **Learning curve** - advanced SQL features may be unfamiliar

#### Query Performance

```python
# Analytical query - DuckDB shines
result = conn.execute("""
    SELECT
        date_trunc('year', album_release_date) as year,
        COUNT(*) as tracks,
        AVG(popularity) as avg_pop,
        AVG(duration_ms) / 60000.0 as avg_minutes
    FROM tracks
    GROUP BY year
    ORDER BY year
""").fetchdf()  # ~5-10ms for 18k rows

# Duplicate analysis
result = conn.execute("""
    SELECT id, name, COUNT(*) as weight
    FROM tracks
    GROUP BY id, name
    ORDER BY weight DESC
""").fetchdf()  # ~3-5ms
```

#### Scalability: 18,000 Records
- **Query time**: 1-20ms for most analytics
- **Memory**: Efficient columnar processing
- **Excellent**: Purpose-built for this use case

---

### Option 4: TinyDB (Document Store)

#### What is TinyDB?

A lightweight document-oriented database in pure Python:
- Stores JSON documents
- No server, no configuration
- Python-native query syntax

#### Usage

```python
from tinydb import TinyDB, Query

db = TinyDB('spotify.json')
Track = Query()

# Insert
db.insert({
    'id': 'abc123',
    'name': 'Take On Me',
    'artist': 'a-ha',
    'added_at': '2023-05-15T10:30:00Z'
})

# Query
results = db.search(Track.artist == 'a-ha')

# Complex query
duplicates = db.search(Track.id.one_of(['id1', 'id2', 'id3']))
```

#### Pros
- Pure Python - no binary dependencies
- Flexible schema - just store JSON
- Simple API
- Human-readable storage file

#### Cons
- **No aggregations** - must load all data for groupby
- **Slow for analytics** - linear scan for every query
- **No SQL** - custom query language
- **Not designed for 18k records** - intended for small datasets

#### Query Performance

```python
# Finding duplicates requires loading everything
all_tracks = db.all()  # Load 18k documents
counts = {}
for t in all_tracks:
    counts[t['id']] = counts.get(t['id'], 0) + 1
# ~200-500ms for 18k records
```

#### Scalability: 18,000 Records
- **Query time**: 100-500ms for any non-trivial query
- **Memory**: Must load significant portions into RAM
- **Marginal**: Works but not recommended for analytics

---

## Benchmark: Query Patterns

### Common Analytics Queries

| Query | JSON/CSV | SQLite | DuckDB | TinyDB |
|-------|----------|--------|--------|--------|
| Load all tracks | 500ms | N/A | N/A | 400ms |
| Find track by ID | 500ms | 2ms | 1ms | 100ms |
| Count duplicates | 600ms | 30ms | 5ms | 500ms |
| Group by artist | 700ms | 50ms | 10ms | 600ms |
| Avg popularity by year | 800ms | 80ms | 15ms | 700ms |
| Top 10 weighted tracks | 650ms | 40ms | 8ms | 550ms |

*Estimates for 18,000 records on typical hardware*

### Winner by Query Pattern

| Use Case | Best Option |
|----------|-------------|
| Simple key-value lookup | SQLite |
| Aggregations & groupby | DuckDB |
| Flexible schema exploration | DuckDB (JSON columns) |
| Raw API response storage | JSON file + DuckDB |

---

## Integration with Analytics Stage

### Stage 3 Requirements

The Analytics stage needs to answer:
1. Which tracks were duplicated most? (GROUP BY + COUNT)
2. What's the genre distribution? (GROUP BY genres array)
3. BPM/energy analysis (numerical aggregations)
4. Release year trends (date functions)

### How Each Storage Supports Analytics

#### JSON/CSV
```python
# Every analysis starts with full load
df = pd.read_csv('tracks.csv')

# Then pandas operations
top_weighted = df.groupby('id').size().sort_values(ascending=False)
```
**Verdict**: Works, but loads full dataset for every notebook cell.

#### SQLite
```python
# Push aggregations to database
df = pd.read_sql_query("""
    SELECT track_id, COUNT(*) as weight
    FROM playlist_tracks
    GROUP BY track_id
    ORDER BY weight DESC
    LIMIT 50
""", conn)
```
**Verdict**: Good - SQL handles aggregation, only results returned.

#### DuckDB
```python
# Best of both worlds
import duckdb

# Query pandas DataFrame with SQL!
raw_df = pd.read_json('raw_tracks.json')

result = duckdb.query("""
    SELECT
        json_extract_string(data, '$.track.id') as id,
        json_extract_string(data, '$.track.name') as name,
        COUNT(*) as weight
    FROM raw_df
    GROUP BY id, name
    ORDER BY weight DESC
""").to_df()

# Or persist and query even faster
conn.execute("CREATE TABLE tracks AS SELECT * FROM raw_df")
```
**Verdict**: Optimal - flexible schema + fast analytics + pandas integration.

---

## Final Recommendation

### Primary: DuckDB

**Reasoning:**

1. **Analytics-First**: Columnar storage makes aggregations 10-100x faster than SQLite for our query patterns (GROUP BY, COUNT, AVG).

2. **pandas Symbiosis**: Unique ability to query pandas DataFrames directly with SQL eliminates friction between fetching (pandas) and analyzing (SQL).

3. **Flexible Schema**: Can store raw JSON responses and query with `json_extract()`, then create structured tables as needed.

4. **Modern SQL**: Window functions (`COUNT(*) OVER`), `QUALIFY` clause, array types - powerful for duplicate detection.

5. **Zero Configuration**: `pip install duckdb` and you're done. Single `.duckdb` file.

### Storage Architecture

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
│  After successful fetch, import to DuckDB:                    │
│  - raw_playlist_items table (stores FULL JSON responses)      │
│  - tracks view (extracted fields for fast queries)            │
│  - audio_features table (from separate API call)              │
│                                                               │
│  DuckDB is the SOURCE OF TRUTH (raw JSON preserved)           │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                    ANALYTICS PHASE                             │
├───────────────────────────────────────────────────────────────┤
│  DuckDB queries → pandas DataFrames → visualizations          │
│                                                               │
│  Can query:                                                   │
│  - Extracted columns (fast, indexed)                          │
│  - Raw JSON (flexible, any field)                             │
└───────────────────────────────────────────────────────────────┘
```

### Key Design Decision: Store Raw JSON in DuckDB

```sql
-- DuckDB stores COMPLETE API responses
CREATE TABLE raw_playlist_items (
    playlist_source VARCHAR,
    raw_json JSON,              -- Full Spotify response
    fetched_at TIMESTAMP
);

-- Query extracted fields (fast)
SELECT id, name, artist FROM tracks WHERE popularity > 80;

-- Query raw JSON (flexible, any field)
SELECT raw_json->>'$.track.preview_url' FROM tracks WHERE id = 'xyz';
```

---

## Deep Dive: Raw JSON vs Structured Storage

### Query Syntax Comparison

```sql
-- STRUCTURED: Direct column access (fast, clean)
SELECT id, name, artist
FROM tracks
WHERE popularity > 80;

-- RAW JSON: JSON path extraction (flexible, verbose)
SELECT
    raw_json->>'$.track.id' as id,
    raw_json->>'$.track.name' as name,
    raw_json->>'$.track.artists[0].name' as artist
FROM raw_playlist_items
WHERE CAST(raw_json->>'$.track.popularity' AS INTEGER) > 80;
```

### Performance Comparison

| Aspect | Structured Columns | Raw JSON Column |
|--------|-------------------|-----------------|
| **Read speed** | Fast (columnar, indexed) | Slower (parse JSON each query) |
| **Filter/WHERE** | Uses indexes | Full scan + JSON parse |
| **Aggregations** | Optimized | Must cast types first |
| **GROUP BY** | Fast | Slower (string operations) |

**Benchmark estimate for 18k rows:**

| Query | Structured | Raw JSON |
|-------|------------|----------|
| `SELECT artist, COUNT(*) GROUP BY artist` | ~5ms | ~50-100ms |
| `SELECT * WHERE id = 'xyz'` | ~1ms | ~20ms |
| `AVG(popularity) GROUP BY decade` | ~10ms | ~80ms |

### Storage Size Comparison

| Approach | Size for 18k tracks | Notes |
|----------|---------------------|-------|
| Raw JSON only | ~50 MB | Complete API responses |
| Structured only | ~10 MB | Extracted fields only |
| **Hybrid (both)** | **~60 MB** | Best of both worlds |

**Note**: 60 MB is trivial. Storage is not a concern here.

### Pros & Cons Analysis

#### Raw JSON Storage

```sql
CREATE TABLE raw_playlist_items (
    playlist_source VARCHAR,
    raw_json JSON,
    fetched_at TIMESTAMP
);
```

| Pros | Cons |
|------|------|
| **Future-proof**: Query any field later | **Slower queries**: Parse JSON on every access |
| **No schema migration**: API changes don't break storage | **No type safety**: Everything is string until cast |
| **Complete data**: Nothing lost from API response | **Verbose syntax**: Long JSON path expressions |
| **Debug-friendly**: See exactly what Spotify returned | **No indexes**: Can't index JSON paths efficiently |
| **Exploration**: "What other fields exist?" | **No constraints**: Can't enforce referential integrity |

#### Structured Storage

```sql
CREATE TABLE tracks (
    id VARCHAR PRIMARY KEY,
    name VARCHAR,
    artist VARCHAR,
    popularity INTEGER,
    ...
);
```

| Pros | Cons |
|------|------|
| **Fast queries**: Columnar storage, indexes work | **Schema rigidity**: Must define columns upfront |
| **Type safety**: `popularity` is INTEGER, enforced | **Data loss risk**: Non-extracted fields are gone |
| **Clean syntax**: `SELECT name FROM tracks` | **Migration needed**: Schema changes require ALTER |
| **Indexable**: `CREATE INDEX idx ON tracks(artist)` | **Upfront decisions**: Must know what you need |
| **Smaller storage**: No JSON overhead | **API changes**: New Spotify fields won't appear |

### The Hybrid Approach (Recommended)

```sql
-- 1. Raw storage table (source of truth, never loses data)
CREATE TABLE raw_playlist_items (
    id INTEGER PRIMARY KEY,
    playlist_source VARCHAR NOT NULL,
    raw_json JSON NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Materialized table for fast analytics
CREATE TABLE tracks AS
SELECT
    ROW_NUMBER() OVER () as row_id,
    raw_json->>'$.track.id' as id,
    raw_json->>'$.track.name' as name,
    raw_json->>'$.track.artists[0].name' as artist,
    raw_json->>'$.track.album.name' as album,
    raw_json->>'$.track.album.release_date' as release_date,
    CAST(raw_json->>'$.track.duration_ms' AS INTEGER) as duration_ms,
    CAST(raw_json->>'$.track.popularity' AS INTEGER) as popularity,
    CAST(raw_json->>'$.track.explicit' AS BOOLEAN) as explicit,
    raw_json->>'$.track.external_ids.isrc' as isrc,
    raw_json->>'$.added_at' as added_at,
    playlist_source,
    raw_json  -- Keep raw for ad-hoc queries
FROM raw_playlist_items;

-- 3. Indexes for common queries
CREATE INDEX idx_tracks_id ON tracks(id);
CREATE INDEX idx_tracks_artist ON tracks(artist);
CREATE INDEX idx_tracks_playlist ON tracks(playlist_source);
```

### Why Materialized Table, Not View?

| Approach | Query Speed | Storage | When Data Changes |
|----------|-------------|---------|-------------------|
| **VIEW** | Slow (parses JSON every query) | 0 MB | Always current |
| **TABLE** | Fast (pre-parsed, indexed) | +10 MB | Must recreate |

For our use case (one-time import, many queries), **TABLE is better**.

### Real-World Query Examples

#### Common Analytics (use structured columns)

```sql
-- Fast: uses extracted columns with indexes
SELECT
    artist,
    COUNT(DISTINCT id) as tracks,
    AVG(popularity) as avg_pop
FROM tracks
GROUP BY artist
ORDER BY tracks DESC
LIMIT 20;
-- Execution time: ~5ms
```

#### Exploration (use raw JSON)

```sql
-- "What does preview_url look like?"
SELECT
    raw_json->>'$.track.preview_url' as preview,
    raw_json->>'$.track.name' as name
FROM raw_playlist_items
LIMIT 5;

-- "What fields exist in external_ids?"
SELECT DISTINCT json_keys(raw_json->'$.track.external_ids')
FROM raw_playlist_items;

-- "What's in the album images array?"
SELECT raw_json->'$.track.album.images'
FROM raw_playlist_items
LIMIT 1;

-- "Does Spotify include any fields I didn't know about?"
SELECT json_keys(raw_json->'$.track')
FROM raw_playlist_items
LIMIT 1;
```

### DuckDB JSON Functions Reference

```sql
-- Extract string value
raw_json->>'$.track.name'

-- Extract as JSON (for nested objects)
raw_json->'$.track.album'

-- Array access (0-indexed)
raw_json->>'$.track.artists[0].name'

-- Array unnesting
SELECT unnest(raw_json->'$.track.artists') as artist_obj
FROM raw_playlist_items;

-- Get all keys at a path
SELECT json_keys(raw_json->'$.track')
FROM raw_playlist_items LIMIT 1;

-- Type conversion
CAST(raw_json->>'$.track.duration_ms' AS INTEGER)
CAST(raw_json->>'$.track.explicit' AS BOOLEAN)
```

### When to Query Which

| Use Case | Query From | Why |
|----------|------------|-----|
| Weight analysis (COUNT, GROUP BY) | Structured `tracks` | Fast aggregations |
| Popularity/duration stats | Structured `tracks` | Pre-cast types |
| "What fields does API return?" | Raw `raw_playlist_items` | Exploration |
| "Does this track have preview_url?" | Raw `raw_playlist_items` | Field we didn't extract |
| Join with audio_features | Structured (both tables) | Indexed join |
| Export for visualization | Structured `tracks` | Cleaner output |
| Debug "why is this track weird?" | Raw `raw_playlist_items` | See original data |

### Summary: Why Hybrid Wins

| Approach | Speed | Flexibility | Data Safety | Recommended |
|----------|-------|-------------|-------------|-------------|
| Raw JSON only | Slow | Maximum | Complete | No - too slow for analytics |
| Structured only | Fast | Limited | Data loss risk | No - loses API fields |
| **Hybrid** | **Fast** | **Both** | **Complete** | **Yes** |

The hybrid approach costs ~10 MB extra storage but gives:
- Fast analytics on known fields (extracted columns)
- Raw JSON for "what if" queries (exploration)
- No data loss from Spotify's API response
- Future-proof: can extract more fields later without re-fetching

---

### Hybrid Approach Details

1. **Fetching**: Save raw JSON for checkpoint/resume
   ```python
   # Checkpoint every 500 tracks
   with open(f'checkpoint_{offset}.json', 'w') as f:
       json.dump(batch, f)
   ```

2. **Processing**: Load into DuckDB for analytics
   ```python
   import duckdb
   conn = duckdb.connect('spotify.duckdb')

   # Create table from JSON
   conn.execute("""
       CREATE TABLE tracks AS
       SELECT
           json_extract_string(data, '$.track.id') as id,
           json_extract_string(data, '$.track.name') as name,
           -- ... more fields
       FROM read_json_auto('raw_tracks.json')
   """)
   ```

3. **Analytics**: Query with SQL, visualize with pandas/matplotlib
   ```python
   # In Jupyter
   weight_analysis = conn.execute("""
       SELECT id, name, artist, COUNT(*) as weight
       FROM tracks
       GROUP BY id, name, artist
       ORDER BY weight DESC
   """).fetchdf()

   weight_analysis['weight'].hist(bins=50)
   ```

### Why Not SQLite?

SQLite would work, but DuckDB is superior for this specific project:

| Aspect | SQLite | DuckDB |
|--------|--------|--------|
| Aggregation speed | Good | 10x better |
| pandas integration | `read_sql_query()` | Native DataFrame queries |
| JSON support | Limited | Full `json_extract()` |
| Array columns | No | Yes |
| Window functions | Limited | Full support |

### Why Not Just pandas?

pandas alone:
- Loads entire dataset into memory
- No persistence between notebook sessions (unless you re-read JSON each time)
- Complex queries require verbose chained methods

DuckDB + pandas:
- Query subsets without loading everything
- Persist processed data between sessions
- SQL for complex queries, pandas for visualization

---

## Implementation Example

```python
# fetch.py - Fetching with JSON checkpoint
import json
import spotipy

def fetch_all_tracks(sp, playlist_id):
    all_tracks = []
    offset = 0

    while True:
        response = sp.playlist_tracks(playlist_id, offset=offset, limit=100)
        all_tracks.extend(response['items'])

        # Checkpoint every 500 tracks
        if len(all_tracks) % 500 == 0:
            with open(f'data/checkpoint_{playlist_id}_{len(all_tracks)}.json', 'w') as f:
                json.dump(all_tracks, f)

        if not response['next']:
            break
        offset += 100

    # Final save
    with open(f'data/playlist_{playlist_id}.json', 'w') as f:
        json.dump(all_tracks, f)

    return all_tracks


# analyze.py - DuckDB analytics
import duckdb

conn = duckdb.connect('data/spotify.duckdb')

# Load raw JSON into structured table
conn.execute("""
    CREATE OR REPLACE TABLE tracks AS
    SELECT
        unnest(data).track.id as id,
        unnest(data).track.name as name,
        unnest(data).track.artists[1].name as artist,
        unnest(data).track.album.name as album,
        unnest(data).track.album.release_date as release_date,
        unnest(data).track.duration_ms as duration_ms,
        unnest(data).track.popularity as popularity,
        unnest(data).added_at as added_at,
        ? as playlist_source
    FROM read_json_auto('data/playlist_*.json')
""", ['source_playlist'])

# Weight analysis
weights = conn.execute("""
    SELECT id, name, artist, COUNT(*) as weight
    FROM tracks
    GROUP BY id, name, artist
    HAVING weight > 1
    ORDER BY weight DESC
""").fetchdf()

print(f"Found {len(weights)} tracks with duplicates")
print(weights.head(20))
```

---

## Decision Log

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Primary storage | JSON, CSV, SQLite, DuckDB, TinyDB | DuckDB | Best analytics performance, pandas integration |
| Checkpoint format | JSON, SQLite | JSON | Human-readable, easy resume |
| Schema approach | Strict normalized, flexible JSON | Hybrid | JSON for raw, structured for analytics |

---

## Next Steps

Pending your approval:

1. **Stage 3**: Analytics & Deduplication Logic document
2. **Stage 4**: High-Performance Execution plan
3. **Begin implementation** once all stages approved
