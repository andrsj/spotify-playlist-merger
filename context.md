# Context

1) I get client id & secret in `.example.env` / `.env` (the actual values) files

2) I have setup the UV virtual env (no installed packages)

```plaintext
> tree -a

.
├── .env // actual values [do not read]
├── .example.env // use as reference
├── .gitignore
├── .venv
│   ├── .gitignore
│   ├── bin
│   │   ├── activate
│   │   ├── activate_this.py
│   │   ├── activate.bat
│   │   ├── activate.csh
│   │   ├── activate.fish
│   │   ├── activate.nu
│   │   ├── activate.ps1
│   │   ├── deactivate.bat
│   │   ├── pydoc.bat
│   │   ├── python -> /opt/homebrew/opt/python@3.14/bin/python3.14
│   │   ├── python3 -> python
│   │   └── python3.14 -> python
│   ├── CACHEDIR.TAG
│   ├── lib
│   │   └── python3.14
│   │       └── site-packages
│   │           ├── _virtualenv.pth
│   │           └── _virtualenv.py
│   └── pyvenv.cfg
├── 2026-01-02-read-the-task-and-execute.txt // our previous converstation [do not read]
├── album_response_example.json
├── context.md
├── data
│   ├── checkpoints
│   └── exports
├── docs // read these files for context
│   ├── preparing_context.png
│   ├── preparing_usage.png
│   ├── stage-1-tooling-analysis.md
│   ├── stage-2-storage-strategy.md
│   ├── stage-3-analytics-deduplication.md
│   └── stage-4-execution-plan.md
├── playlist_response_example.json
└── task.md // the initial task
```

Let's keep the IDs as list in textfile, which we will read line by line (each line - playlist ID)

3) Have tried the Spotify API:

## Track

Endpoint: `https://api.spotify.com/v1/tracks/{id}`
`id`: `0rap6gzHGp4r2TlIeiulwf`
`market`: `ES` (have no clue what is that)

Example:

```bash
curl --request GET \
  --url https://api.spotify.com/v1/tracks/0rap6gzHGp4r2TlIeiulwf \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

Response:

```json
{
  "album": {
    "album_type": "album",
    "artists": [
      {
        "external_urls": {
          "spotify": "https://open.spotify.com/artist/3r40SMXcvhhDUE1xhU8MSB"
        },
        "href": "https://api.spotify.com/v1/artists/3r40SMXcvhhDUE1xhU8MSB",
        "id": "3r40SMXcvhhDUE1xhU8MSB",
        "name": "Deluzion",
        "type": "artist",
        "uri": "spotify:artist:3r40SMXcvhhDUE1xhU8MSB"
      }
    ],
    "available_markets": [
      "AR",
      "AU",
      "AT",
      "BE",
      "BO",
      "BR",
      "BG",
      "CA",
      "CL",
      "CO",
      "CR",
      "CY",
      "CZ",
      "DK",
      "DO",
      "DE",
      "EC",
      "EE",
      "SV",
      "FI",
      "FR",
      "GR",
      "GT",
      "HN",
      "HK",
      "HU",
      "IS",
      "IE",
      "IT",
      "LV",
      "LT",
      "LU",
      "MY",
      "MT",
      "MX",
      "NL",
      "NZ",
      "NI",
      "NO",
      "PA",
      "PY",
      "PE",
      "PH",
      "PL",
      "PT",
      "SG",
      "SK",
      "ES",
      "SE",
      "CH",
      "TW",
      "TR",
      "UY",
      "US",
      "GB",
      "AD",
      "LI",
      "MC",
      "ID",
      "JP",
      "TH",
      "VN",
      "RO",
      "IL",
      "ZA",
      "SA",
      "AE",
      "BH",
      "QA",
      "OM",
      "KW",
      "EG",
      "MA",
      "DZ",
      "TN",
      "LB",
      "JO",
      "PS",
      "IN",
      "BY",
      "KZ",
      "MD",
      "UA",
      "AL",
      "BA",
      "HR",
      "ME",
      "MK",
      "RS",
      "SI",
      "KR",
      "BD",
      "PK",
      "LK",
      "GH",
      "KE",
      "NG",
      "TZ",
      "UG",
      "AG",
      "AM",
      "BS",
      "BB",
      "BZ",
      "BT",
      "BW",
      "BF",
      "CV",
      "CW",
      "DM",
      "FJ",
      "GM",
      "GE",
      "GD",
      "GW",
      "GY",
      "HT",
      "JM",
      "KI",
      "LS",
      "LR",
      "MW",
      "MV",
      "ML",
      "MH",
      "FM",
      "NA",
      "NR",
      "NE",
      "PW",
      "PG",
      "PR",
      "WS",
      "SM",
      "ST",
      "SN",
      "SC",
      "SL",
      "SB",
      "KN",
      "LC",
      "VC",
      "SR",
      "TL",
      "TO",
      "TT",
      "TV",
      "VU",
      "AZ",
      "BN",
      "BI",
      "KH",
      "CM",
      "TD",
      "KM",
      "GQ",
      "SZ",
      "GA",
      "GN",
      "KG",
      "LA",
      "MO",
      "MR",
      "MN",
      "NP",
      "RW",
      "TG",
      "UZ",
      "ZW",
      "BJ",
      "MG",
      "MU",
      "MZ",
      "AO",
      "CI",
      "DJ",
      "ZM",
      "CD",
      "CG",
      "IQ",
      "LY",
      "TJ",
      "VE",
      "ET",
      "XK"
    ],
    "external_urls": {
      "spotify": "https://open.spotify.com/album/2zMlApVsuczyP3YbENEyVC"
    },
    "href": "https://api.spotify.com/v1/albums/2zMlApVsuczyP3YbENEyVC",
    "id": "2zMlApVsuczyP3YbENEyVC",
    "images": [
      {
        "url": "https://i.scdn.co/image/ab67616d0000b2735ccc43128fd76a849c3b328c",
        "width": 640,
        "height": 640
      },
      {
        "url": "https://i.scdn.co/image/ab67616d00001e025ccc43128fd76a849c3b328c",
        "width": 300,
        "height": 300
      },
      {
        "url": "https://i.scdn.co/image/ab67616d000048515ccc43128fd76a849c3b328c",
        "width": 64,
        "height": 64
      }
    ],
    "name": "Point Zero",
    "release_date": "2025-11-21",
    "release_date_precision": "day",
    "total_tracks": 19,
    "type": "album",
    "uri": "spotify:album:2zMlApVsuczyP3YbENEyVC"
  },
  "artists": [
    {
      "external_urls": {
        "spotify": "https://open.spotify.com/artist/3r40SMXcvhhDUE1xhU8MSB"
      },
      "href": "https://api.spotify.com/v1/artists/3r40SMXcvhhDUE1xhU8MSB",
      "id": "3r40SMXcvhhDUE1xhU8MSB",
      "name": "Deluzion",
      "type": "artist",
      "uri": "spotify:artist:3r40SMXcvhhDUE1xhU8MSB"
    }
  ],
  "available_markets": [
    "AR",
    "AU",
    "AT",
    "BE",
    "BO",
    "BR",
    "BG",
    "CA",
    "CL",
    "CO",
    "CR",
    "CY",
    "CZ",
    "DK",
    "DO",
    "DE",
    "EC",
    "EE",
    "SV",
    "FI",
    "FR",
    "GR",
    "GT",
    "HN",
    "HK",
    "HU",
    "IS",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MY",
    "MT",
    "MX",
    "NL",
    "NZ",
    "NI",
    "NO",
    "PA",
    "PY",
    "PE",
    "PH",
    "PL",
    "PT",
    "SG",
    "SK",
    "ES",
    "SE",
    "CH",
    "TW",
    "TR",
    "UY",
    "US",
    "GB",
    "AD",
    "LI",
    "MC",
    "ID",
    "JP",
    "TH",
    "VN",
    "RO",
    "IL",
    "ZA",
    "SA",
    "AE",
    "BH",
    "QA",
    "OM",
    "KW",
    "EG",
    "MA",
    "DZ",
    "TN",
    "LB",
    "JO",
    "PS",
    "IN",
    "BY",
    "KZ",
    "MD",
    "UA",
    "AL",
    "BA",
    "HR",
    "ME",
    "MK",
    "RS",
    "SI",
    "KR",
    "BD",
    "PK",
    "LK",
    "GH",
    "KE",
    "NG",
    "TZ",
    "UG",
    "AG",
    "AM",
    "BS",
    "BB",
    "BZ",
    "BT",
    "BW",
    "BF",
    "CV",
    "CW",
    "DM",
    "FJ",
    "GM",
    "GE",
    "GD",
    "GW",
    "GY",
    "HT",
    "JM",
    "KI",
    "LS",
    "LR",
    "MW",
    "MV",
    "ML",
    "MH",
    "FM",
    "NA",
    "NR",
    "NE",
    "PW",
    "PG",
    "PR",
    "WS",
    "SM",
    "ST",
    "SN",
    "SC",
    "SL",
    "SB",
    "KN",
    "LC",
    "VC",
    "SR",
    "TL",
    "TO",
    "TT",
    "TV",
    "VU",
    "AZ",
    "BN",
    "BI",
    "KH",
    "CM",
    "TD",
    "KM",
    "GQ",
    "SZ",
    "GA",
    "GN",
    "KG",
    "LA",
    "MO",
    "MR",
    "MN",
    "NP",
    "RW",
    "TG",
    "UZ",
    "ZW",
    "BJ",
    "MG",
    "MU",
    "MZ",
    "AO",
    "CI",
    "DJ",
    "ZM",
    "CD",
    "CG",
    "IQ",
    "LY",
    "TJ",
    "VE",
    "ET",
    "XK"
  ],
  "disc_number": 1,
  "duration_ms": 187500,
  "explicit": false,
  "external_ids": {
    "isrc": "NLFL72500435"
  },
  "external_urls": {
    "spotify": "https://open.spotify.com/track/0rap6gzHGp4r2TlIeiulwf"
  },
  "href": "https://api.spotify.com/v1/tracks/0rap6gzHGp4r2TlIeiulwf",
  "id": "0rap6gzHGp4r2TlIeiulwf",
  "is_local": false,
  "name": "Bring It Raw",
  "popularity": 21,
  "preview_url": null,
  "track_number": 5,
  "type": "track",
  "uri": "spotify:track:0rap6gzHGp4r2TlIeiulwf"
}
```

## Playlist

Endpoint: `https://api.spotify.com/v1/playlists/{playlist_id}`
`playlist_id`: `491WiUqmbpuCtUs6xwXRaB` (My playlist "TOP-100 2025")
`market`: `ES`
`fields`: `items(added_by.id,track(name,href,album(name,href)))`
`additional_types` `<empty>`

Example:

```bash
curl --request GET \
  --url https://api.spotify.com/v1/playlists/491WiUqmbpuCtUs6xwXRaB \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

Response

```json
{
  "collaborative": false,
  "description": "",
  "external_urls": {
    "spotify": "https://open.spotify.com/playlist/491WiUqmbpuCtUs6xwXRaB"
  },
  "followers": {
    "href": null,
    "total": 0
  },
  "href": "https://api.spotify.com/v1/playlists/491WiUqmbpuCtUs6xwXRaB?locale=en-US%2Cen%3Bq%3D0.9%2Cuk%3Bq%3D0.8",
  "id": "491WiUqmbpuCtUs6xwXRaB",
  "images": [
    {
      "height": 640,
      "url": "https://mosaic.scdn.co/640/ab67616d00001e0217942a547902fb9e5ce69b13ab67616d00001e023b10a643d18e134d39d00bc0ab67616d00001e02513e26f5f3efc12b3b0aa695ab67616d00001e02f957f90e390bf30b33d7c81e",
      "width": 640
    },
    {
      "height": 300,
      "url": "https://mosaic.scdn.co/300/ab67616d00001e0217942a547902fb9e5ce69b13ab67616d00001e023b10a643d18e134d39d00bc0ab67616d00001e02513e26f5f3efc12b3b0aa695ab67616d00001e02f957f90e390bf30b33d7c81e",
      "width": 300
    },
    {
      "height": 60,
      "url": "https://mosaic.scdn.co/60/ab67616d00001e0217942a547902fb9e5ce69b13ab67616d00001e023b10a643d18e134d39d00bc0ab67616d00001e02513e26f5f3efc12b3b0aa695ab67616d00001e02f957f90e390bf30b33d7c81e",
      "width": 60
    }
  ],
  "name": "TOP-100 2025",
  "owner": {
    "display_name": "andrsj",
    "external_urls": {
      "spotify": "https://open.spotify.com/user/2u85lbaamkz66rxcspb1hpv2f"
    },
    "href": "https://api.spotify.com/v1/users/2u85lbaamkz66rxcspb1hpv2f",
    "id": "2u85lbaamkz66rxcspb1hpv2f",
    "type": "user",
    "uri": "spotify:user:2u85lbaamkz66rxcspb1hpv2f"
  },
  "primary_color": null,
  "public": true,
  "snapshot_id": "AAAAA+6rnZbqZu7VvfT+P33pemXgx4gX",
  "tracks": {
    "href": "https://api.spotify.com/v1/playlists/491WiUqmbpuCtUs6xwXRaB/tracks?offset=0&limit=100&locale=en-US,en;q%3D0.9,uk;q%3D0.8",
    "items": [...] // very looong list (48 611 lines for this playlist) `array of PlaylistTrackObject Required`
    ],
    "limit": 100,
    "next": null,
    "offset": 0,
    "previous": null,
    "total": 100
  },
  "type": "playlist",
  "uri": "spotify:playlist:491WiUqmbpuCtUs6xwXRaB"
}
```

## Album (not for task)

Endpoint: `https://api.spotify.com/v1/albums/{id}`
`id`: `2zMlApVsuczyP3YbENEyVC`
`market`: `ES`

Example:

```bash
curl --request GET \
  --url https://api.spotify.com/v1/albums/2zMlApVsuczyP3YbENEyVC \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

Response:

```json
{
  "album_type": "album",
  "total_tracks": 19,
  "available_markets": [
    "AR",
    "AU",
    "AT",
    "BE",
    "BO",
    "BR",
    "BG",
    "CA",
    "CL",
    "CO",
    "CR",
    "CY",
    "CZ",
    "DK",
    "DO",
    "DE",
    "EC",
    "EE",
    "SV",
    "FI",
    "FR",
    "GR",
    "GT",
    "HN",
    "HK",
    "HU",
    "IS",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MY",
    "MT",
    "MX",
    "NL",
    "NZ",
    "NI",
    "NO",
    "PA",
    "PY",
    "PE",
    "PH",
    "PL",
    "PT",
    "SG",
    "SK",
    "ES",
    "SE",
    "CH",
    "TW",
    "TR",
    "UY",
    "US",
    "GB",
    "AD",
    "LI",
    "MC",
    "ID",
    "JP",
    "TH",
    "VN",
    "RO",
    "IL",
    "ZA",
    "SA",
    "AE",
    "BH",
    "QA",
    "OM",
    "KW",
    "EG",
    "MA",
    "DZ",
    "TN",
    "LB",
    "JO",
    "PS",
    "IN",
    "BY",
    "KZ",
    "MD",
    "UA",
    "AL",
    "BA",
    "HR",
    "ME",
    "MK",
    "RS",
    "SI",
    "KR",
    "BD",
    "PK",
    "LK",
    "GH",
    "KE",
    "NG",
    "TZ",
    "UG",
    "AG",
    "AM",
    "BS",
    "BB",
    "BZ",
    "BT",
    "BW",
    "BF",
    "CV",
    "CW",
    "DM",
    "FJ",
    "GM",
    "GE",
    "GD",
    "GW",
    "GY",
    "HT",
    "JM",
    "KI",
    "LS",
    "LR",
    "MW",
    "MV",
    "ML",
    "MH",
    "FM",
    "NA",
    "NR",
    "NE",
    "PW",
    "PG",
    "PR",
    "WS",
    "SM",
    "ST",
    "SN",
    "SC",
    "SL",
    "SB",
    "KN",
    "LC",
    "VC",
    "SR",
    "TL",
    "TO",
    "TT",
    "TV",
    "VU",
    "AZ",
    "BN",
    "BI",
    "KH",
    "CM",
    "TD",
    "KM",
    "GQ",
    "SZ",
    "GA",
    "GN",
    "KG",
    "LA",
    "MO",
    "MR",
    "MN",
    "NP",
    "RW",
    "TG",
    "UZ",
    "ZW",
    "BJ",
    "MG",
    "MU",
    "MZ",
    "AO",
    "CI",
    "DJ",
    "ZM",
    "CD",
    "CG",
    "IQ",
    "LY",
    "TJ",
    "VE",
    "ET",
    "XK"
  ],
  "external_urls": {
    "spotify": "https://open.spotify.com/album/2zMlApVsuczyP3YbENEyVC"
  },
  "href": "https://api.spotify.com/v1/albums/2zMlApVsuczyP3YbENEyVC?locale=en-US%2Cen%3Bq%3D0.9%2Cuk%3Bq%3D0.8",
  "id": "2zMlApVsuczyP3YbENEyVC",
  "images": [
    {
      "url": "https://i.scdn.co/image/ab67616d0000b2735ccc43128fd76a849c3b328c",
      "height": 640,
      "width": 640
    },
    {
      "url": "https://i.scdn.co/image/ab67616d00001e025ccc43128fd76a849c3b328c",
      "height": 300,
      "width": 300
    },
    {
      "url": "https://i.scdn.co/image/ab67616d000048515ccc43128fd76a849c3b328c",
      "height": 64,
      "width": 64
    }
  ],
  "name": "Point Zero",
  "release_date": "2025-11-21",
  "release_date_precision": "day",
  "type": "album",
  "uri": "spotify:album:2zMlApVsuczyP3YbENEyVC",
  "artists": [
    {
      "external_urls": {
        "spotify": "https://open.spotify.com/artist/3r40SMXcvhhDUE1xhU8MSB"
      },
      "href": "https://api.spotify.com/v1/artists/3r40SMXcvhhDUE1xhU8MSB",
      "id": "3r40SMXcvhhDUE1xhU8MSB",
      "name": "Deluzion",
      "type": "artist",
      "uri": "spotify:artist:3r40SMXcvhhDUE1xhU8MSB"
    }
  ],
  "tracks": {
    "href": "https://api.spotify.com/v1/albums/2zMlApVsuczyP3YbENEyVC/tracks?offset=0&limit=50&locale=en-US,en;q%3D0.9,uk;q%3D0.8",
    "limit": 50,
    "next": null,
    "offset": 0,
    "previous": null,
    "total": 19,
    "items": [...] // a lot of items
    },
  "copyrights": [
    {
      "text": "2025 Minus is More",
      "type": "C"
    },
    {
      "text": "2025 Minus is More",
      "type": "P"
    }
  ],
  "external_ids": {
    "upc": "8721416438318"
  },
  "genres": [],
  "label": "Minus is More",
  "popularity": 41
}
```

## Track's audio features

Example:

```bash
curl --request GET \
  --url https://api.spotify.com/v1/audio-features/11dFghVXANMlKmJXsNCbNl \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

> MARKED AS `DEPRECATED`

Response:

```json
{
  "acousticness": 0.00242,
  "analysis_url": "https://api.spotify.com/v1/audio-analysis/2takcwOaAZWiXQijPHIx7B",
  "danceability": 0.585,
  "duration_ms": 237040,
  "energy": 0.842,
  "id": "2takcwOaAZWiXQijPHIx7B",
  "instrumentalness": 0.00686,
  "key": 9,
  "liveness": 0.0866,
  "loudness": -5.883,
  "mode": 0,
  "speechiness": 0.0556,
  "tempo": 118.211,
  "time_signature": 4,
  "track_href": "https://api.spotify.com/v1/tracks/2takcwOaAZWiXQijPHIx7B",
  "type": "audio_features",
  "uri": "spotify:track:2takcwOaAZWiXQijPHIx7B",
  "valence": 0.428
}
```

## Track's audio analysis

Example:

```bash
curl --request GET \
  --url https://api.spotify.com/v1/audio-analysis/11dFghVXANMlKmJXsNCbNl \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

> MARKED AS `DEPRECATED`

Response:

```json
{
  "meta": {
    "analyzer_version": "4.0.0",
    "platform": "Linux",
    "detailed_status": "OK",
    "status_code": 0,
    "timestamp": 1495193577,
    "analysis_time": 6.93906,
    "input_process": "libvorbisfile L+R 44100->22050"
  },
  "track": {
    "num_samples": 4585515,
    "duration": 207.95985,
    "sample_md5": "string",
    "offset_seconds": 0,
    "window_seconds": 0,
    "analysis_sample_rate": 22050,
    "analysis_channels": 1,
    "end_of_fade_in": 0,
    "start_of_fade_out": 201.13705,
    "loudness": -5.883,
    "tempo": 118.211,
    "tempo_confidence": 0.73,
    "time_signature": 4,
    "time_signature_confidence": 0.994,
    "key": 9,
    "key_confidence": 0.408,
    "mode": 0,
    "mode_confidence": 0.485,
    "codestring": "string",
    "code_version": 3.15,
    "echoprintstring": "string",
    "echoprint_version": 4.15,
    "synchstring": "string",
    "synch_version": 1,
    "rhythmstring": "string",
    "rhythm_version": 1
  },
  "bars": [
    {
      "start": 0.49567,
      "duration": 2.18749,
      "confidence": 0.925
    }
  ],
  "beats": [
    {
      "start": 0.49567,
      "duration": 2.18749,
      "confidence": 0.925
    }
  ],
  "sections": [
    {
      "start": 0,
      "duration": 6.97092,
      "confidence": 1,
      "loudness": -14.938,
      "tempo": 113.178,
      "tempo_confidence": 0.647,
      "key": 9,
      "key_confidence": 0.297,
      "mode": -1,
      "mode_confidence": 0.471,
      "time_signature": 4,
      "time_signature_confidence": 1
    }
  ],
  "segments": [
    {
      "start": 0.70154,
      "duration": 0.19891,
      "confidence": 0.435,
      "loudness_start": -23.053,
      "loudness_max": -14.25,
      "loudness_max_time": 0.07305,
      "loudness_end": 0,
      "pitches": [
        0.212,
        0.141,
        0.294
      ],
      "timbre": [
        42.115,
        64.373,
        -0.233
      ]
    }
  ],
  "tatums": [
    {
      "start": 0.49567,
      "duration": 2.18749,
      "confidence": 0.925
    }
  ]
}
```

## Several track's audio features

Example:

```bash
curl --request GET \
  --url 'https://api.spotify.com/v1/audio-features?ids=7ouMYWpwJ422jRcDASZB7P%2C4VqPOruhp5EdPBeR92t6lQ%2C2takcwOaAZWiXQijPHIx7B' \
  --header 'Authorization: Bearer 1POdFZRZbvb...qqillRxMr2z'
```

> MARKED AS `DEPRECATED`

Response:

```json
{
  "audio_features": [
    {
      "acousticness": 0.00242,
      "analysis_url": "https://api.spotify.com/v1/audio-analysis/2takcwOaAZWiXQijPHIx7B",
      "danceability": 0.585,
      "duration_ms": 237040,
      "energy": 0.842,
      "id": "2takcwOaAZWiXQijPHIx7B",
      "instrumentalness": 0.00686,
      "key": 9,
      "liveness": 0.0866,
      "loudness": -5.883,
      "mode": 0,
      "speechiness": 0.0556,
      "tempo": 118.211,
      "time_signature": 4,
      "track_href": "https://api.spotify.com/v1/tracks/2takcwOaAZWiXQijPHIx7B",
      "type": "audio_features",
      "uri": "spotify:track:2takcwOaAZWiXQijPHIx7B",
      "valence": 0.428
    }
  ]
}
```
