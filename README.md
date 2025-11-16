# Podcast Feed Generator

A self-contained Docker solution for generating podcast RSS feeds and a simple static website from MP3 files and JSON metadata.

## Features

- Automatically generates RSS 2.0 podcast feed from MP3 files
- Creates a simple HTML page for browsing episodes
- Serves everything with Caddy web server
- Self-contained Docker container
- Optional automatic regeneration when new episodes are added
- iTunes-compatible podcast feed
- Comprehensive debug logging for troubleshooting

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
- `PRIMARY_COLOR`: Primary color for website theme in hex format (default: "#1a73e8")
- `SECONDARY_COLOR`: Secondary color for website theme in hex format (default: "#34a853")

**System Configuration:**
- `BASE_URL`: Base URL where podcast is hosted (default: "http://localhost")
- `INPUT_DIR`: Input directory path (default: "/input")
- `OUTPUT_DIR`: Output directory path (default: "/output")
- `REGEN_INTERVAL`: Auto-regenerate interval in seconds (default: 0 = run once)
- `DEBUG`: Enable verbose debug logging - set to `true`, `1`, or `yes` (default: "false")

### Alternative: podcast_info.json

Instead of environment variables, you can place a `podcast_info.json` file in your input directory:

```json
{
  "title": "My Awesome Podcast",
  "description": "Weekly episodes about interesting topics",
  "author": "Your Name",
  "language": "en-us",
  "explicit": "no",
  "image_url": "https://example.com/podcast-cover.jpg",
  "primary_color": "#1a73e8",
  "secondary_color": "#34a853"
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

## Debug Logging

Enable detailed debug logging to troubleshoot issues or understand what the generator is doing:

```yaml
environment:
  - DEBUG=true  # Enable debug mode
```

**Logging Levels:**

- **INFO (default)**: Shows high-level progress and important events
  ```
  2025-11-15 00:15:30 [INFO] === Podcast Feed Generator ===
  2025-11-15 00:15:30 [INFO] Found episode: Episode Title
  2025-11-15 00:15:31 [INFO] Found 37 episode(s)
  2025-11-15 00:15:32 [INFO] File copy complete: 37 copied, 0 skipped
  ```

- **DEBUG (when enabled)**: Shows detailed operation information
  ```
  2025-11-15 00:15:30 [DEBUG] Configuration:
  2025-11-15 00:15:30 [DEBUG]   INPUT_DIR: /input
  2025-11-15 00:15:30 [DEBUG]   OUTPUT_DIR: /output
  2025-11-15 00:15:30 [DEBUG] Scanning folder: 2024-10-25
  2025-11-15 00:15:30 [DEBUG]   Found 1 .info.json file(s)
  2025-11-15 00:15:30 [DEBUG]   Processing: 2024-10-25.info.json
  2025-11-15 00:15:30 [DEBUG]     MP3 found: 2024-10-25.mp3
  2025-11-15 00:15:30 [DEBUG]     Thumbnail found: 2024-10-25-thumb.jpg
  2025-11-15 00:15:30 [DEBUG]   Title: Episode Title
  2025-11-15 00:15:30 [DEBUG]   Chapters: 5 found
  2025-11-15 00:15:30 [DEBUG]   Duration: 00:35:09
  ```

**What Debug Mode Shows:**
- Configuration values at startup
- Directory scanning operations
- File discovery and matching (MP3, JSON, thumbnails)
- Episode metadata parsing details
- File hash computations for change detection
- File copy operations (including skipped files)
- RSS feed generation details

**Usage:**
```bash
# View logs in real-time
docker logs -f podcast-feed

# View last 100 lines
docker logs --tail 100 podcast-feed
```

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

**First Step: Enable Debug Logging**

For any issue, start by enabling debug mode to see detailed information:

```yaml
environment:
  - DEBUG=true
```

Then restart the container and check the logs:
```bash
docker-compose down
docker-compose up -d
docker logs -f podcast-feed
```

**No episodes showing up?**
- Enable `DEBUG=true` to see which folders and files are being scanned
- Check that each episode folder has both an `.mp3` and `.info.json` file with matching date prefixes
- Verify JSON files are valid (use a JSON validator)
- Check container logs: `docker logs podcast-feed`
- Debug logs will show exactly which files are found and why others are skipped

**Feed not updating?**
- If using `REGEN_INTERVAL`, wait for the next regeneration cycle
- Or restart the container: `docker restart podcast-feed`
- Check that the input directory is properly mounted
- Enable debug logging to see if files are being detected

**Files not being copied?**
- Enable `DEBUG=true` to see file copy operations
- Debug logs show: "Copying filename" vs "Skipping filename (unchanged)"
- Files are only copied if they don't exist or their hash has changed

**Permission errors?**
- Ensure the container can read from `/input`
- Ensure the container can write to `/output`
- Check volume mount permissions
- Debug logs will show specific file access errors

## Technical Details

- Built on Alpine Linux
- Uses Caddy 2 web server
- Python 3 for feed generation
- Generates RSS 2.0 with iTunes extensions
- Supports all standard podcast players

## License

This project is provided as-is for personal and commercial use.
