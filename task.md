# Project Brief: Spotify Library Engineering, Deep Analytics & Smart Deduplication

## Context

I am managing two massive Spotify playlists (9,000+ tracks each). Historically, I used a "weighted shuffle" technique by adding the same tracks multiple times to increase their playback probability. Since Spotify changed this behavior, I now need to merge these playlists into one "clean" master copy, removing all intentional and unintentional duplicates.

## ⚠️ MANDATORY: Before Execution

The agent must NOT provide a full solution immediately. First, the agent must ask the user clarifying questions to define the scope and technical constraints. Only after receiving answers should the agent proceed to Stage 1.

## Core Objectives

1. Architecture Selection: Choose languages/tools based on technical merit.
2. Stateful Data Acquisition: Fetch 18k+ tracks and store them locally using a robust storage strategy.
3. Deep Data Analytics & Duplicate Profiling: Analyze the "weighted" tracks and general library statistics.
4. Master Merge: Create a clean, deduplicated playlist.

## Instructions for the AI Agent

### 1. Tooling & Paradigm Selection (Stage 1)

Evaluate Python, Go, Node.js, and Elixir/Haskell/Gleam
- SDK vs. Direct API: Analyze if a wrapper (like spotipy) or direct HTTP calls with a custom concurrency model is better for handling 18,000+ records.
- FP Exploration: Evaluate if Functional Programming (immutability, pattern matching) offers advantages for data cleaning and deduplication logic.

### 2. Storage Strategy (The "Source of Truth") (Stage 2)

Since the dataset is large, we cannot rely on memory alone. Compare at least three storage approaches:
- Flat Files: JSON/CSV (simplicity vs. query speed).
- Local Database: SQLite or DuckDB (relational integrity, SQL power for analysis).
- Document Store: TinyDB or similar (NoSQL flexibility for raw API responses).
- Requirement: The agent must explain which storage best supports the "Analytics" stage.

### 3. Exhaustive Statistical Analysis & Deduplication Logic (Stage 3)

The analysis should be split into sub-tasks. I want to see:
- The "Weight" Analysis: Identify tracks that were duplicated the most. What was my "favorite" music based on the frequency of duplicates?
- Musical DNA: Detailed stats on genres, BPM, energy, and release years across 18k tracks (not just top 10).
- Deduplication Strategy: Propose methods to identify duplicates (Track ID vs. ISRC vs. Fuzzy Matching for "Remastered" vs. "Original" versions).
- Output Formats: Compare CLI reports, JSON exports, Interactive Notebooks (Jupyter/Livebook), or HTML dashboards.

### 4. High-Performance Execution (Stage 4)

- Fetching: How to bypass/handle rate limits (429) during massive fetches.
- Writing: How to efficiently create a playlist of ~15,000 unique tracks (Spotify allows 100 per request).
- Safety: Provide a "Dry Run" report before any write operations occur.

## Deliverable Requirements

For every proposed solution, the Agent must provide:
- Thinking Process: "I considered X, but chose Y because..."
- Pros & Cons: Clear comparison of different paths.
- Scalability: Specifically address how the choice handles 18,000+ records.
- Learning Context: If a new language or FP is suggested, explain the core benefit for this specific task.

## Proposed Clarifying Questions (for the Agent to ask the User)

To the Agent: Please use these as a starting point for your first response.
- API Auth: Do you already have a Spotify Developer App (Client ID/Secret) ready?
  - The answer is: I don't remember to be honest. I haven't touched the API for years 
- Environment: Where will this run? (Local machine, Docker, or a specific cloud environment).
  - The answer: one time execution on local machine. We can consider the docker-compose, because I haven't run the Docker on my new Mac 
- Deduplication Strictness: Should "Track A - Remastered" and "Track A" be considered the same track (Fuzzy) or different (ID-based)?
  - The answer: different track - different item. The remix and original - different tracks! 
- Analytics Depth: Do you need just the data Spotify provides in the track object, or should we also fetch audio-features (BPM, Mood, etc.) for all 18k tracks? (Note: This requires extra API calls).
  - The answer: consider on the limitations. I'd like to see as much as we can
- FP Curiosity: On a scale of 1-10, how "deep" into the FP rabbit hole (Haskell/Elixir) are you willing to go for this project?
  - Answer: I'm totally noob in this question, so I can't answer, to be honset
