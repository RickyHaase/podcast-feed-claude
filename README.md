# Podcast Feed Generator

A self-contained Docker solution for generating podcast RSS feeds and a simple static website from MP3 files and JSON metadata.

## Features

- Automatically generates RSS 2.0 podcast feed from MP3 files
- **Automatic transcription using OpenAI Whisper**
- Creates a simple HTML page for browsing episodes
- Serves everything with Caddy web server
- Self-contained Docker container
- Optional automatic regeneration when new episodes are added
- iTunes-compatible podcast feed

## Quick Start

### 1. Prepare Your Directory Structure

Create a directory for your podcast files with this structure:

```
podcast-files/
├── T3 Playlist/
│   ├── 2025-09-26_Episode Title/
│   │   ├── 2025-09-26.mp3
│   │   ├── 2025-09-26.info.json
│   │   └── 2025-09-26-thumb.jpg
│   ├── 2025-09-27_Another Episode/
│   │   ├── 2025-09-27.mp3
│   │   ├── 2025-09-27.info.json
│   │   └── 2025-09-27-thumb.jpg
└── ...
```

Each episode folder should contain:
- One `.mp3` file (your podcast episode) - named with date: `YYYY-MM-DD.mp3`
- One `.info.json` file (YouTube-style metadata) - named: `YYYY-MM-DD.info.json`
- One thumbnail file (optional) - named: `YYYY-MM-DD-thumb.jpg`
- One transcript file (optional) - named: `YYYY-MM-DD.txt` (auto-generated if not present)

### 2. Episode Metadata Format

This generator is designed to work with YouTube-downloaded podcast episodes (using yt-dlp or similar tools). The `.info.json` files follow the YouTube metadata format.

**Key fields used from the JSON:**
- `title`: Episode title
- `description`: Episode description (will include timestamps and source link in feed)
- `upload_date`: Publication date in YYYYMMDD format (e.g., "20250926")
- `duration`: Episode duration in seconds (automatically converted to HH:MM:SS)
- `webpage_url`: Original YouTube URL (added to episode descriptions)
- `chapters`: Array of chapter objects with `start_time` and `title` (formatted as timestamps in show notes)
- `uploader` or `channel`: Episode author/channel name
- `id`: YouTube video ID (used for GUID)
- `thumbnail`: Episode thumbnail URL

**Example snippet from info.json:**
```json
{
  "id": "6HTU2DrROyg",
  "title": "Episode Title",
  "description": "Episode description with show notes...",
  "upload_date": "20250926",
  "duration": 2109,
  "webpage_url": "https://www.youtube.com/watch?v=6HTU2DrROyg",
  "uploader": "Channel Name",
  "chapters": [
    {
      "start_time": 0.0,
      "title": "Intro",
      "end_time": 21.0
    },
    {
      "start_time": 21.0,
      "title": "Topic 1",
      "end_time": 69.0
    }
  ]
}
```

The generator will automatically:
- Convert upload_date to proper RSS date format
- Convert duration from seconds to HH:MM:SS
- Format chapters as timestamps in the description
- Add the original YouTube link to show notes
- Generate unique GUIDs from video IDs

### 3. Run with Docker Compose

Edit `docker-compose.yml` to customize your podcast metadata and paths, then:

```bash
docker-compose up -d
```

Or build and run manually:

```bash
docker build -t podcast-feed .

docker run -d \
  -p 80:80 \
  -v /path/to/your/podcast-files:/input:ro \
  -v /path/to/output:/output \
  -e PODCAST_TITLE="My Podcast" \
  -e PODCAST_DESCRIPTION="Weekly episodes" \
  -e PODCAST_AUTHOR="Your Name" \
  -e BASE_URL="http://yourserver.com" \
  -e REGEN_INTERVAL=300 \
  --name podcast-feed \
  podcast-feed
```

### 4. Access Your Podcast

- Website: `http://localhost/`
- RSS Feed: `http://localhost/feed.xml`
- Episodes: `http://localhost/episodes/episode.mp3`

## Configuration

### Environment Variables

Configure your podcast using environment variables:

**Podcast Metadata:**
- `PODCAST_TITLE`: Podcast title (default: "My Podcast")
- `PODCAST_DESCRIPTION`: Podcast description
- `PODCAST_AUTHOR`: Podcast author name
- `PODCAST_LANGUAGE`: Language code (default: "en-us")
- `PODCAST_EXPLICIT`: "yes" or "no" (default: "no")
- `PODCAST_IMAGE_URL`: URL to podcast cover art image

**System Configuration:**
- `BASE_URL`: Base URL where podcast is hosted (default: "http://localhost")
- `INPUT_DIR`: Input directory path (default: "/input")
- `OUTPUT_DIR`: Output directory path (default: "/output")
- `REGEN_INTERVAL`: Auto-regenerate interval in seconds (default: 0 = run once)

**Transcription Configuration:**
- `ENABLE_TRANSCRIPTION`: Enable automatic transcription (default: "true")
- `WHISPER_MODEL`: Whisper model to use - "tiny", "base", "small", "medium", "large" (default: "base")
  - **tiny**: Fastest, lower quality (~1GB RAM, ~32x realtime)
  - **base**: Balanced speed and quality (~1GB RAM, ~16x realtime) - **recommended**
  - **small**: Better quality (~2GB RAM, ~6x realtime)
  - **medium**: High quality (~5GB RAM, ~2x realtime)
  - **large**: Best quality (~10GB RAM, ~1x realtime)

### Alternative: podcast_info.json

Instead of environment variables, you can place a `podcast_info.json` file in your input directory:

```json
{
  "title": "My Awesome Podcast",
  "description": "Weekly episodes about interesting topics",
  "author": "Your Name",
  "language": "en-us",
  "explicit": "no",
  "image_url": "https://example.com/podcast-cover.jpg"
}
```

This file takes precedence over environment variables.

## Volume Mounts

The container expects two volume mounts:

1. `/input` - Your podcast files directory (read-only recommended)
2. `/output` - Generated website files (read-write, can be backed up)

The output directory will contain:
```
output/
├── index.html          # Website homepage
├── feed.xml           # RSS podcast feed
└── episodes/          # Copied MP3 files
    ├── episode1.mp3
    └── episode2.mp3
```

## Auto-Regeneration

Set `REGEN_INTERVAL` to automatically regenerate the feed at regular intervals. This is useful if you're adding new episodes while the container is running:

```yaml
environment:
  - REGEN_INTERVAL=300  # Regenerate every 5 minutes
```

Set to `0` (default) to only generate on container startup.

## Transcription

The podcast feed generator includes automatic transcription using OpenAI's Whisper model.

### How It Works

1. **Automatic Transcription**: When processing episodes, the generator checks for existing transcript files (`.txt`)
2. **Cache System**: If a transcript exists, it's loaded from the file. Otherwise, Whisper transcribes the audio
3. **Storage**: Transcripts are saved as `.txt` files alongside your MP3s for reuse
4. **Integration**: Transcripts appear in both the RSS feed description and HTML page

### Transcription Workflow

```
Episode Processing
├─ Check for YYYY-MM-DD.txt
├─ If exists: Load existing transcript
├─ If not exists and ENABLE_TRANSCRIPTION=true:
│   ├─ Load Whisper model
│   ├─ Transcribe audio
│   └─ Save to YYYY-MM-DD.txt
└─ Add transcript to RSS feed and HTML
```

### Configuring Transcription

**Enable/Disable:**
```yaml
environment:
  - ENABLE_TRANSCRIPTION=true  # Enable (default)
  # or
  - ENABLE_TRANSCRIPTION=false  # Disable
```

**Choose Model:**
```yaml
environment:
  - WHISPER_MODEL=base  # Recommended for most use cases
  # Options: tiny, base, small, medium, large
```

**Model Selection Guide:**
- Use **tiny** for quick testing or low-resource environments
- Use **base** (default) for good balance of speed and quality
- Use **small** or **medium** for better accuracy with longer processing time
- Use **large** only if you need maximum accuracy and have powerful hardware

### Performance Notes

- First transcription downloads the Whisper model (~140MB for base model)
- Processing time varies by model and episode length
- Transcripts are cached, so subsequent runs are instant
- Transcription happens during feed generation, not while serving

### Manual Transcripts

You can provide your own transcripts by creating `.txt` files:

```
2025-09-26/
├── 2025-09-26.mp3
├── 2025-09-26.info.json
└── 2025-09-26.txt  ← Your custom transcript
```

If a `.txt` file exists, Whisper transcription is skipped for that episode.

## Publishing Your Podcast

### To iTunes/Apple Podcasts:

1. Set `BASE_URL` to your public domain
2. Ensure your feed is accessible at `https://yourdomain.com/feed.xml`
3. Submit your feed URL to Apple Podcasts Connect

### To Spotify:

1. Use the same feed URL
2. Submit through Spotify for Podcasters

### To Other Platforms:

Most podcast platforms accept standard RSS 2.0 feeds. Use your feed URL: `https://yourdomain.com/feed.xml`

## Example Setup

See the `examples/` directory for:
- Sample episode JSON format
- Recommended directory structure

## Backups

The `/output` directory contains all generated files including copied MP3s. To backup your podcast:

```bash
# Backup the output directory
tar -czf podcast-backup.tar.gz /path/to/output

# Or use your bind-mount location
tar -czf podcast-backup.tar.gz ./public
```

For a complete backup, also save your input directory with original files and metadata.

## Troubleshooting

**No episodes showing up?**
- Check that each episode folder has both an `.mp3` and `.json` file
- Verify JSON files are valid (use a JSON validator)
- Check container logs: `docker logs podcast-feed`

**Feed not updating?**
- If using `REGEN_INTERVAL`, wait for the next regeneration cycle
- Or restart the container: `docker restart podcast-feed`
- Check that the input directory is properly mounted

**Permission errors?**
- Ensure the container can read from `/input`
- Ensure the container can write to `/output`
- Check volume mount permissions

## Technical Details

- Built on Alpine Linux
- Uses Caddy 2 web server
- Python 3 for feed generation
- Generates RSS 2.0 with iTunes extensions
- Supports all standard podcast players

## License

This project is provided as-is for personal and commercial use.
