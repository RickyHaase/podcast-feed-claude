# Podcast Feed Generator

A self-contained Docker solution for generating podcast RSS feeds and a simple static website from MP3 files and JSON metadata.

## Features

- Automatically generates RSS 2.0 podcast feed from MP3 files
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
├── episode-001/
│   ├── episode.mp3
│   └── episode.json
├── episode-002/
│   ├── episode.mp3
│   └── episode.json
└── ...
```

Each episode folder should contain:
- One `.mp3` file (your podcast episode)
- One `.json` file (episode metadata)

### 2. Create Episode Metadata

Each episode needs a JSON file with metadata. See `examples/episode-001/episode.json` for a template.

Required and optional fields:

```json
{
  "title": "Episode Title",
  "description": "Episode description. Can be longer and more detailed.",
  "pub_date": "2024-01-15T12:00:00Z",
  "duration": "00:45:30",
  "author": "Author Name",
  "episode_number": 1,
  "explicit": "no",
  "guid": "unique-episode-identifier"
}
```

**Field descriptions:**
- `title` (required): Episode title
- `description` (required): Episode description
- `pub_date` (required): Publication date in ISO 8601 format
- `duration` (optional): Episode duration in HH:MM:SS format
- `author` (optional): Episode author (overrides podcast-level author)
- `episode_number` (optional): Episode number for iTunes
- `explicit` (optional): "yes" or "no" for explicit content warning
- `guid` (optional): Unique identifier (auto-generated if not provided)

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
