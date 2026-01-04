# Stage 1: Tooling & Paradigm Selection

## Executive Summary

This document evaluates Python, Go, Node.js, and Elixir/Gleam for building a Spotify playlist deduplication and analytics system handling 18,000+ tracks. After thorough analysis, **Python with spotipy + pandas + Jupyter** emerges as the optimal choice for this specific use case.

---

## Table of Contents

1. [Problem Constraints](#problem-constraints)
2. [Language-by-Language Deep Dive](#language-by-language-deep-dive)
3. [SDK vs Direct API Analysis](#sdk-vs-direct-api-analysis)
4. [Functional Programming Exploration](#functional-programming-exploration)
5. [Concurrency Models Comparison](#concurrency-models-comparison)
6. [Final Recommendation](#final-recommendation)

---

## Problem Constraints

Before evaluating tools, let's establish what we're optimizing for:

| Constraint | Impact on Tooling |
|------------|-------------------|
| **18,000+ tracks** | Need efficient memory handling and batch processing |
| **Spotify API Rate Limits** | 429 responses require exponential backoff; SDK support valuable |
| **One-time execution** | Deployment simplicity less important than development speed |
| **Rich analytics needed** | Data manipulation and visualization capabilities critical |
| **Local machine (macOS)** | No cloud-specific considerations |
| **User knows Python + Go** | Learning curve factor reduced for these two |

### API-Bound vs CPU-Bound

This workload is **heavily API-bound**:
- Fetching 18,000 tracks at 50/request = 360 API calls minimum
- Each call has ~100-300ms network latency
- Rate limits may add delays
- **Raw language speed is irrelevant** - we're waiting on Spotify, not computing

This insight shifts our evaluation criteria toward:
1. Quality of Spotify SDK
2. Data manipulation capabilities
3. Developer experience for analytics

---

## Language-by-Language Deep Dive

### Python

#### Spotify Ecosystem

```python
# spotipy example - handles OAuth, pagination, rate limits automatically
import spotipy
from spotipy.oauth2 import SpotifyOAuth

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="...",
    client_secret="...",
    redirect_uri="http://localhost:8888/callback",
    scope="playlist-read-private playlist-modify-public"
))

# Automatic pagination with offset handling
def get_all_tracks(playlist_id):
    results = []
    offset = 0
    while True:
        response = sp.playlist_tracks(playlist_id, offset=offset, limit=100)
        results.extend(response['items'])
        if not response['next']:
            break
        offset += 100
    return results
```

**spotipy advantages:**
- Automatic retry on 429 with configurable backoff
- Built-in pagination helpers
- Token refresh handling
- Well-documented, actively maintained (500+ GitHub stars)

#### Data Analysis Capabilities

```python
import pandas as pd

# Convert tracks to DataFrame for analysis
df = pd.DataFrame([{
    'id': t['track']['id'],
    'name': t['track']['name'],
    'artist': t['track']['artists'][0]['name'],
    'added_at': t['added_at'],
    'duration_ms': t['track']['duration_ms']
} for t in tracks])

# Duplicate analysis - one line
weight_analysis = df.groupby('id').size().sort_values(ascending=False)

# Genre distribution (after fetching artist data)
genre_counts = df.explode('genres').groupby('genres').size()
```

**pandas advantages for 18k records:**
- Vectorized operations (C-level speed)
- SQL-like groupby, merge, pivot operations
- Memory-efficient with proper dtypes
- 18,000 rows × 20 columns ≈ 3MB memory - trivial

#### Jupyter Notebooks

```python
# Interactive exploration
import matplotlib.pyplot as plt

# Weight distribution histogram
weight_analysis.hist(bins=50)
plt.title("Track Duplication Distribution")
plt.xlabel("Times Duplicated")
plt.ylabel("Number of Tracks")

# Export to HTML for sharing
# jupyter nbconvert --to html analysis.ipynb
```

**Jupyter advantages:**
- Interactive cell-by-cell execution
- Inline visualizations
- Markdown documentation alongside code
- Export to HTML for non-technical stakeholders

#### Pros
- Mature, battle-tested spotipy library
- Best-in-class data analysis ecosystem (pandas, numpy, matplotlib)
- Jupyter provides interactive exploration
- User already proficient
- Extensive community resources for Spotify API

#### Cons
- Slower than compiled languages (irrelevant for API-bound work)
- GIL limits true parallelism (mitigated by asyncio for I/O)
- Virtual environment management can be messy

#### Scalability Assessment
- **18,000 records**: Trivial - pandas handles millions
- **Rate limits**: spotipy handles automatically
- **Memory**: ~10-50MB total footprint with all data loaded

---

### Go

#### Spotify Ecosystem

No official SDK. Community options exist but are less maintained:
- `zmb3/spotify` - Most popular, but last commit 8+ months ago
- Direct HTTP required for reliability

```go
// Manual OAuth + pagination example
package main

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type PlaylistResponse struct {
    Items []struct {
        Track struct {
            ID   string `json:"id"`
            Name string `json:"name"`
        } `json:"track"`
    } `json:"items"`
    Next string `json:"next"`
}

func fetchWithRetry(url string, token string) (*http.Response, error) {
    client := &http.Client{Timeout: 10 * time.Second}

    for retries := 0; retries < 5; retries++ {
        req, _ := http.NewRequest("GET", url, nil)
        req.Header.Set("Authorization", "Bearer "+token)

        resp, err := client.Do(req)
        if err != nil {
            return nil, err
        }

        if resp.StatusCode == 429 {
            retryAfter := resp.Header.Get("Retry-After")
            // Parse and sleep...
            time.Sleep(time.Duration(retries+1) * time.Second)
            continue
        }

        return resp, nil
    }
    return nil, fmt.Errorf("max retries exceeded")
}
```

**This is 50+ lines just for basic retry logic** that spotipy handles in one line.

#### Data Analysis Capabilities

Go lacks a pandas equivalent. Options:
- `gonum/gonum` - Numerical computing, not data wrangling
- `go-gota/gota` - DataFrame-like, but immature
- Manual map/slice manipulation

```go
// Counting duplicates in Go - verbose
duplicateCounts := make(map[string]int)
for _, track := range tracks {
    duplicateCounts[track.ID]++
}

// Sorting by count requires custom code
type kv struct {
    Key   string
    Value int
}
var sorted []kv
for k, v := range duplicateCounts {
    sorted = append(sorted, kv{k, v})
}
sort.Slice(sorted, func(i, j int) bool {
    return sorted[i].Value > sorted[j].Value
})
```

Compare to Python: `df.groupby('id').size().sort_values(ascending=False)`

#### Pros
- Excellent concurrency (goroutines)
- Fast binary, single-file deployment
- Strong typing catches errors at compile time
- User already proficient

#### Cons
- No maintained Spotify SDK
- Weak data analysis ecosystem
- Verbose for data manipulation
- No equivalent to Jupyter for exploration

#### Scalability Assessment
- **18,000 records**: Excellent - Go handles this trivially
- **Rate limits**: Must implement manually (200+ lines)
- **Memory**: Very efficient, ~5-20MB footprint

#### When Go Would Be Better
- Building a long-running service
- CLI tool for distribution to others
- Performance-critical batch processing
- Microservice architecture

---

### Node.js / TypeScript

#### Spotify Ecosystem

```typescript
// spotify-web-api-node example
import SpotifyWebApi from 'spotify-web-api-node';

const spotifyApi = new SpotifyWebApi({
    clientId: '...',
    clientSecret: '...',
    redirectUri: 'http://localhost:8888/callback'
});

async function getAllTracks(playlistId: string) {
    const tracks = [];
    let offset = 0;

    while (true) {
        const response = await spotifyApi.getPlaylistTracks(playlistId, {
            offset,
            limit: 100
        });

        tracks.push(...response.body.items);

        if (!response.body.next) break;
        offset += 100;
    }

    return tracks;
}
```

The SDK exists but:
- Rate limit handling is not automatic
- Less mature than spotipy
- TypeScript types sometimes lag behind API changes

#### Data Analysis Capabilities

JavaScript ecosystem lacks data science focus:
- `danfo.js` - pandas-inspired, but less mature
- `arquero` - Observable's data library, decent
- Most analysis requires manual array methods

```typescript
// Duplicate counting in JS
const counts = tracks.reduce((acc, track) => {
    acc[track.track.id] = (acc[track.track.id] || 0) + 1;
    return acc;
}, {} as Record<string, number>);

// Sorting
const sorted = Object.entries(counts)
    .sort(([, a], [, b]) => b - a);
```

#### Pros
- Native async/await, excellent for API calls
- Good Spotify SDK exists
- Observable notebooks available (Jupyter alternative)
- NPM ecosystem is vast

#### Cons
- Data analysis is not JS's strength
- Type safety requires TypeScript setup
- Not the user's primary language

#### Scalability Assessment
- **18,000 records**: Good - V8 handles arrays efficiently
- **Rate limits**: Manual implementation needed
- **Memory**: Higher than Go, comparable to Python

---

### Elixir / Gleam (Functional Programming)

#### Spotify Ecosystem

No SDK. Must use raw HTTP:

```elixir
# Elixir with HTTPoison and pattern matching
defmodule SpotifyClient do
  use HTTPoison.Base

  def get_all_tracks(playlist_id, token, acc \\ [], offset \\ 0) do
    url = "https://api.spotify.com/v1/playlists/#{playlist_id}/tracks?offset=#{offset}&limit=100"

    case get(url, [{"Authorization", "Bearer #{token}"}]) do
      {:ok, %{status_code: 200, body: body}} ->
        data = Jason.decode!(body)
        new_acc = acc ++ data["items"]

        case data["next"] do
          nil -> {:ok, new_acc}
          _ -> get_all_tracks(playlist_id, token, new_acc, offset + 100)
        end

      {:ok, %{status_code: 429, headers: headers}} ->
        retry_after = get_retry_after(headers)
        Process.sleep(retry_after * 1000)
        get_all_tracks(playlist_id, token, acc, offset)

      {:error, reason} ->
        {:error, reason}
    end
  end
end
```

#### FP Advantages for This Project

**Pattern Matching for Data Transformation:**
```elixir
# Elegant deduplication with pipes
tracks
|> Enum.map(fn item -> item["track"] end)
|> Enum.group_by(fn track -> track["id"] end)
|> Enum.map(fn {id, duplicates} -> {id, length(duplicates)} end)
|> Enum.sort_by(fn {_, count} -> count end, :desc)
```

**Immutability Benefits:**
- No accidental mutations during data cleaning
- Easier to reason about transformations
- Built-in support for concurrent processing

**Livebook (Jupyter Alternative):**
- Interactive notebooks for Elixir
- Good visualization with VegaLite
- Less mature than Jupyter but growing

#### Pros
- Beautiful data transformation syntax
- Excellent concurrency model (OTP)
- Pattern matching is perfect for handling API response variants
- Immutability prevents bugs

#### Cons
- Steep learning curve (new paradigm)
- No Spotify SDK
- Smaller ecosystem
- Debugging unfamiliar errors is slow
- User has no experience

#### Scalability Assessment
- **18,000 records**: Excellent - BEAM VM handles this trivially
- **Rate limits**: GenServer can implement sophisticated backoff
- **Memory**: Efficient with proper streaming

#### When Elixir Would Be Better
- Building a real-time application
- Need fault-tolerant, distributed processing
- Educational project to learn FP
- Long-running service with supervision trees

---

## SDK vs Direct API Analysis

### Effort Comparison

| Task | spotipy (Python) | Direct HTTP (Go/Elixir) |
|------|------------------|-------------------------|
| OAuth2 Flow | 5 lines config | 100+ lines |
| Token Refresh | Automatic | Manual token storage |
| Pagination | Built-in helpers | Manual offset tracking |
| Rate Limiting | Automatic retry | Manual backoff logic |
| Error Handling | Typed exceptions | Manual status code parsing |

### Code Volume Estimate

| Component | Python (spotipy) | Go (direct) | Elixir (direct) |
|-----------|------------------|-------------|-----------------|
| Auth | 10 lines | 150 lines | 100 lines |
| Fetch all tracks | 15 lines | 80 lines | 60 lines |
| Rate limit handling | 0 lines (built-in) | 50 lines | 40 lines |
| **Total boilerplate** | **~25 lines** | **~280 lines** | **~200 lines** |

### Reliability Considerations

**spotipy** has been battle-tested:
- Handles edge cases we won't think of
- Community-reported bugs are fixed
- Spotify API changes are tracked

**Custom implementations** risk:
- Missing edge cases
- Token expiry at inopportune times
- Subtle pagination bugs

---

## Functional Programming Exploration

### Can We Get FP Benefits in Python?

Yes! Python supports FP-style coding:

```python
from functools import reduce
from itertools import groupby
from operator import itemgetter

# Pure function - no side effects
def count_duplicates(tracks):
    return reduce(
        lambda acc, t: {**acc, t['id']: acc.get(t['id'], 0) + 1},
        tracks,
        {}
    )

# Pipeline-style with comprehensions
def analyze_weights(tracks):
    by_id = {}
    for t in tracks:
        by_id[t['id']] = by_id.get(t['id'], []) + [t]

    return sorted(
        ((id, len(dupes), dupes[0]['name']) for id, dupes in by_id.items()),
        key=lambda x: x[1],
        reverse=True
    )
```

### FP Patterns Useful for This Project

| Pattern | Application | Python Support |
|---------|-------------|----------------|
| Map | Transform tracks to analysis format | `map()`, list comprehensions |
| Filter | Remove invalid entries | `filter()`, list comprehensions |
| Reduce | Aggregate statistics | `functools.reduce()` |
| Group By | Count duplicates | `itertools.groupby()`, pandas |
| Pipe | Chain transformations | Method chaining in pandas |

### Conclusion on FP

Pure FP languages (Elixir, Haskell) offer:
- Guaranteed immutability
- Exhaustive pattern matching
- Strong type inference

But for this project:
- Python's FP features are sufficient
- The learning curve isn't justified for one-time use
- pandas provides most benefits with familiar syntax

---

## Concurrency Models Comparison

### API Call Patterns

For 360+ API calls, concurrency helps:

| Language | Concurrency Model | Implementation |
|----------|-------------------|----------------|
| Python | asyncio | `aiohttp` + `asyncio.gather()` |
| Go | Goroutines | `sync.WaitGroup` + channels |
| Node.js | Event Loop | `Promise.all()` |
| Elixir | Processes | `Task.async_stream()` |

### But Consider...

Spotify's rate limits make aggressive concurrency counterproductive:
- Too many parallel requests → 429 → must wait anyway
- Sequential with 3-5 concurrent requests is optimal
- spotipy handles this automatically

**Conclusion**: Concurrency model is not a differentiator here.

---

## Final Recommendation

### Primary: Python + spotipy + pandas + Jupyter

**Reasoning:**

1. **SDK Quality**: spotipy is the most mature, handling OAuth, pagination, and rate limits automatically. This saves ~250 lines of boilerplate.

2. **Analytics Power**: pandas is purpose-built for this exact use case - grouping, counting, sorting, and visualizing 18k records.

3. **Interactive Exploration**: Jupyter notebooks let us explore the "Musical DNA" interactively, adjusting queries as we discover patterns.

4. **User Proficiency**: You know Python. For a one-time execution, this eliminates debugging time.

5. **Community Resources**: Countless tutorials exist for "Spotify + Python + pandas" specifically.

### Secondary Options

**If you want to learn Go deeply:**
- Build the fetcher in Go (good HTTP practice)
- Export to JSON/SQLite
- Analyze with Python pandas
- *Hybrid approach gets Go learning with Python analytics*

**If you want to explore FP:**
- Use Python with explicit FP patterns
- Add type hints for pseudo-static typing
- Consider Elixir for a future project with more time

### Docker Consideration

Since you mentioned Docker Compose and haven't run Docker on the new Mac yet:

```yaml
# docker-compose.yml
version: '3.8'
services:
  spotify-analyzer:
    build: .
    volumes:
      - ./data:/app/data  # Persist fetched data
      - ./notebooks:/app/notebooks  # Jupyter notebooks
    ports:
      - "8888:8888"  # Jupyter
    environment:
      - SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
      - SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
```

This provides:
- Reproducible environment
- No dependency conflicts
- Easy cleanup after one-time use

---

## Next Steps

Pending your approval of this analysis:

1. **Stage 2**: Storage Strategy document (SQLite vs DuckDB vs JSON)
2. **Spotify Setup**: Guide for creating/retrieving Developer App credentials
3. **Implementation**: Begin coding once all stages are approved

---

## Decision Log

| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| Language | Python, Go, Node.js, Elixir | Python | Best SDK, analytics ecosystem |
| SDK | spotipy, direct HTTP | spotipy | Handles rate limits, pagination |
| Notebooks | Jupyter, Observable, Livebook | Jupyter | Mature, best pandas integration |
| FP Approach | Pure Elixir, Python FP | Python FP | Sufficient for task, no learning curve |
