<div align="center">
  <img src="lucida_flow.png" alt="Lucida Flow Logo" width="600"/>
  
  # Lucida-Sync
  
  A Python CLI tool and REST API for downloading high-quality music from various streaming services using [Lucida.to](https://lucida.to), with Amazon Music as the default service.
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
  [![GitHub Stars](https://img.shields.io/github/stars/ryanlong1004/lucida-flow.svg)](https://github.com/ryanlong1004/lucida-flow/stargazers)
  
</div>

## Features

- 🎵 **Amazon Music Focus**: Optimized for Amazon Music with fallback support for other services
- 🔍 **Search Functionality**: Search for tracks across multiple services
- 💻 **CLI Tool**: Easy-to-use command-line interface with beautiful output
- 🌐 **REST API**: FastAPI-based HTTP API for integration
- 🕷️ **Web Scraping**: No service credentials required - uses Lucida.to's web interface
- 📦 **High Quality**: Download in FLAC, MP3, AAC, and other formats
- 🎨 **Beautiful Output**: Rich terminal formatting with colored tables

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Quick Start

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

2. **Install Playwright browsers (required for downloads):**

```bash
playwright install chromium
```

3. **Try the CLI:**

```bash
# Search uses Amazon Music by default
python cli.py search "hotel california"
python cli.py search "daft punk" --limit 5

# List available services
python cli.py services
```

4. **Start the API:**

```bash
python api_server.py
# Visit http://localhost:8000/docs for interactive API documentation
```

## CLI Usage

### Search for Music

```bash
# Search Amazon Music (default)
python cli.py search "hotel california"
python cli.py search "shape of you" --limit 5

# Search other services
python cli.py search "daft punk get lucky" --service tidal
python cli.py search "album name" -s qobuz
```

### Download Music

```bash
python cli.py download "https://tidal.com/browse/track/123456"
python cli.py download "https://open.qobuz.com/track/123456" -o ./my-music/song.flac
```

### Get Track Information

```bash
python cli.py info "https://tidal.com/browse/track/123456"
```

### List Available Services

```bash
python cli.py services
```

## API Usage

### Start Server

```bash
python api_server.py
```

API docs: `http://localhost:8000/docs`

### Example Requests

**Search:**

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "daft punk", "service": "tidal", "limit": 5}'
```

**Download:**

```bash
curl -X POST http://localhost:8000/download-file \
  -H "Content-Type: application/json" \
  -d '{"url": "https://tidal.com/browse/track/123456"}' \
  --output track.flac
```

See full documentation in [DOCUMENTATION.md](DOCUMENTATION.md)

## Project Structure

```
lucida_flow/
├── lucida_client.py        # Core web scraping client
├── cli.py                  # CLI application
├── api_server.py           # FastAPI server
├── requirements.txt        # Dependencies
├── .env                    # Configuration (optional)
└── downloads/              # Default download directory
```

### Spotify Playlist Sync (New)

The most advanced feature of this tool is the **Interactively Parallel Sync**. It can download an entire Spotify playlist by searching Amazon Music for each track and downloading them 3-at-a-time in separate browser tabs.

```bash
python spotify_sync.py
```

- **Interactive Setup**: On first run, it will guide you through adding your Spotify credentials and download directory.
- **Async Concurrency**: Optimized to run 3 tabs simultaneously for maximum speed without browser crashes.
- **Fail-Safe**: Includes automatic retry loops for both searching and downloading.

## Configuration (.env)

The tool uses a `.env` file to store sensitive credentials and settings. **Make sure to never commit this file to GitHub.**

1. Create a `.env` file in the root directory:
2. Add your Spotify API credentials (get them from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)):

```env
# Spotify API
SPOTIPY_CLIENT_ID=your_client_id
SPOTIPY_CLIENT_SECRET=your_client_secret

# Project Settings
DOWNLOAD_DIR=C:\Musics\FLAC
LUCIDA_BASE_URL=https://lucida.to
```

## Security for Public Repositories

If you plan to push this to a public repository:
- **.env**: This file is already in `.gitignore` and must stay there.
- **lucida_session/**: This directory contains browser cookies/state. It is ignored by `.gitignore` to prevent leaking your session.
- **.cache**: Contains your Spotify authentication token. It is also ignored.

## How It Works

This tool implements a high-speed, parallelized music acquisition pipeline. Instead of requiring complex API integrations with every streaming service, it leverages the power of **browser automation** and **asynchronous processing**.

### The Parallel Pipeline:
1. **Spotify Extraction**: The tool uses `spotipy` to fetch the metadata (Artist, Title) of every track in your playlist.
2. **Amazon Search**: It opens up to **3 concurrent Chromium tabs** (via Playwright) to search Amazon Music for direct song links. 
3. **Lucida Processing**: Once a link is found, the same tab navigates to [Lucida.to](https://lucida.to), handles the backend processing, and triggers the high-quality (FLAC) download.
4. **Async Coordination**: The entire flow is managed by Python's `asyncio` event loop. As soon as one song finishes downloading and its tab closes, a new tab instantly takes its place for the next song.

## Setup & Usage

### 1. Installation
```bash
# Clone the repo
git clone https://github.com/your-username/lucida-sync.git
cd lucida-sync

# Install dependencies
pip install -r requirements.txt

# Install the browser engine
playwright install chromium
```

### 2. Configuration
Create a `.env` file and add your Spotify API credentials. You can get these for free at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).

```env
SPOTIPY_CLIENT_ID=your_id
SPOTIPY_CLIENT_SECRET=your_secret
DOWNLOAD_DIR=C:\Musics\FLAC
```

### 3. Running the Sync
Simply run the script and paste your Spotify Playlist URL:
```bash
python lucida_sync.py
```

## Security for Public Repositories
- **.env**: Your credentials are safe. `.env` is blocked by `.gitignore`.
- **Session Data**: The `lucida_session/` folder (where browser cookies are stored) is also ignored to prevent session hijacking.
- **Tokens**: Spotify `.cache` tokens are never uploaded.

## Disclaimer
For educational and personal use only. Please respect the copyright of the artists and the Terms of Service of the platforms involved.

## Credits
- **Original Service**: This tool is a wrapper for the incredible work done by the creators of **[Lucida.to](https://lucida.to)**.
- **Original Repository**: Credit to **[ryanlong1004](https://github.com/ryanlong1004/lucida-flow)** for the initial development of the Lucida Flow project.
- **Core Library**: Credit to **[hazycora](https://hazy.gay/)** for the underlying Lucida logic and service integrations.
- **Optimization**: This version features a custom **Async Parallel Engine** designed for maximum speed and stability on Windows systems.

## License
MIT License
