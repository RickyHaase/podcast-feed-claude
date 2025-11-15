# Podcast Feed Generator

A self-contained Docker solution for generating podcast RSS feeds and a simple static website from MP3 files and JSON metadata.

## Features

- Automatically generates RSS 2.0 podcast feed from MP3 files
- **Automatic transcription using OpenAI Whisper**
- **Speaker diarization (identification) using WhisperX**
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
- One transcript file (optional) - named: `YYYY-MM-DD.txt` (auto-generated if transcription enabled)
- One JSON transcript (optional) - named: `YYYY-MM-DD.transcript.json` (auto-generated with speaker diarization)

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
- `ENABLE_TRANSCRIPTION`: Enable automatic transcription (default: "false" - must be enabled explicitly)
- `WHISPER_MODEL`: Whisper model to use - "tiny", "base", "small", "medium", "large" (default: "base")
  - **tiny**: Fastest, lower quality (~1GB RAM, ~32x realtime)
  - **base**: Balanced speed and quality (~1GB RAM, ~16x realtime) - **recommended**
  - **small**: Better quality (~2GB RAM, ~6x realtime)
  - **medium**: High quality (~5GB RAM, ~2x realtime)
  - **large**: Best quality (~10GB RAM, ~1x realtime)
- `WHISPER_PROMPT`: Optional custom prompt to guide transcription with context (speaker names, technical terms, etc.)

**Speaker Diarization Configuration:**
- `ENABLE_SPEAKER_DIARIZATION`: Enable speaker identification (default: "false")
- `HUGGINGFACE_TOKEN`: Required HuggingFace token for speaker diarization models ([Get free token here](https://huggingface.co/settings/tokens))
- `MIN_SPEAKERS`: Minimum expected number of speakers (optional, e.g., "2")
- `MAX_SPEAKERS`: Maximum expected number of speakers (optional, e.g., "4")

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
  - ENABLE_TRANSCRIPTION=true  # Enable transcription
  # Transcription is disabled by default to save resources
```

**Choose Model:**
```yaml
environment:
  - WHISPER_MODEL=base  # Recommended for most use cases
  # Options: tiny, base, small, medium, large
```

**Custom Prompt (Improve Accuracy):**
```yaml
environment:
  - WHISPER_PROMPT=This podcast features John and Sarah discussing technology topics like Kubernetes, Docker, and API development.
```

The custom prompt helps Whisper:
- Correctly spell technical terms, product names, and jargon
- Identify speaker names and context
- Maintain consistency with your podcast's terminology
- Improve accuracy for domain-specific content

**Example prompts:**
- `"Hosts: Dr. Jane Smith and Mike Chen. Topics: machine learning, neural networks, TensorFlow, PyTorch."`
- `"Medical podcast discussing cardiology, oncology, pharmaceuticals."`
- `"True crime podcast about the FBI, forensics, and criminal investigations."`

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
- **CPU vs GPU**: By default, Whisper runs on CPU which is sufficient for most use cases

### GPU Acceleration (Optional)

Whisper can use GPU acceleration for significantly faster transcription:

**Do you need GPU?**
- **No, if**: You're transcribing occasionally or have time to wait (CPU works fine)
- **Yes, if**: You're batch-processing many episodes or need faster turnaround

**CPU Performance** (approximate for 1-hour episode):
- tiny: ~2 minutes
- base: ~4 minutes
- small: ~10 minutes
- medium: ~30 minutes
- large: ~60 minutes

**GPU Performance** (with NVIDIA GPU):
- All models: 2-5x faster than CPU

**To enable GPU support:**

1. Ensure you have NVIDIA GPU and nvidia-docker installed on host
2. Update `docker-compose.yml`:

```yaml
services:
  podcast-feed:
    # ... existing config ...
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

3. The container will automatically use GPU if available

**Note**: The current Docker image uses CPU-only PyTorch from Alpine packages. For GPU support, you would need to modify the Dockerfile to install CUDA-enabled PyTorch, which significantly increases image size (~4GB vs ~500MB).

### Manual Transcripts

You can provide your own transcripts by creating `.txt` files:

```
2025-09-26/
├── 2025-09-26.mp3
├── 2025-09-26.info.json
└── 2025-09-26.txt  ← Your custom transcript
```

If a `.txt` file exists, Whisper transcription is skipped for that episode.

## Speaker Diarization

Speaker diarization identifies "who spoke when" in your podcast episodes. This feature uses WhisperX to combine transcription with speaker identification.

### How It Works

1. **Transcription**: WhisperX transcribes the audio (like Whisper)
2. **Alignment**: Improves timestamp accuracy at the word level
3. **Diarization**: Identifies different speakers and labels segments
4. **Output**: Creates formatted transcripts with speaker labels

### Requirements

- **HuggingFace Token**: Free token from https://huggingface.co/settings/tokens
  - Used to download pyannote speaker diarization models
  - One-time model download (~200MB), then cached locally

### Setup

1. **Get HuggingFace Token:**
   - Visit https://huggingface.co/settings/tokens
   - Create a new token (read access is sufficient)
   - Copy the token

2. **Enable in docker-compose.yml:**
```yaml
environment:
  - ENABLE_TRANSCRIPTION=true
  - ENABLE_SPEAKER_DIARIZATION=true
  - HUGGINGFACE_TOKEN=hf_your_token_here
  - MIN_SPEAKERS=2  # Optional: expected minimum speakers
  - MAX_SPEAKERS=4  # Optional: expected maximum speakers
```

3. **Run the generator:**
```bash
docker-compose up -d
```

### Output Formats

**JSON Transcript** (`YYYY-MM-DD.transcript.json`):
```json
{
  "text": "Full transcript text...",
  "language": "en",
  "segments": [
    {
      "start": 0.5,
      "end": 3.2,
      "text": "Welcome to the podcast!",
      "speaker": "SPEAKER_00"
    },
    {
      "start": 3.5,
      "end": 7.8,
      "text": "Thanks for having me.",
      "speaker": "SPEAKER_01"
    }
  ]
}
```

**HTML Display:**
- Formatted paragraphs with speaker labels
- Automatic paragraph breaks when speaker changes
- Speaker names highlighted in blue

**Example HTML output:**
> **SPEAKER_00:** Welcome to the podcast! I'm really excited to talk about this topic today.
>
> **SPEAKER_01:** Thanks for having me. I've been looking forward to this conversation.
>
> **SPEAKER_00:** Let's dive right in...

**Plain Text** (`YYYY-MM-DD.txt`):
- Simple text version without speaker labels
- For backward compatibility

### Speaker Count Hints

Providing `MIN_SPEAKERS` and `MAX_SPEAKERS` helps the diarization model:

```yaml
# For a two-person interview
- MIN_SPEAKERS=2
- MAX_SPEAKERS=2

# For a panel discussion with 3-5 people
- MIN_SPEAKERS=3
- MAX_SPEAKERS=5
```

If not specified, the model will automatically detect the number of speakers.

### Performance Impact

Speaker diarization adds processing time:
- **Without diarization**: ~4 minutes for 1-hour episode (base model, CPU)
- **With diarization**: ~8-10 minutes for 1-hour episode (base model, CPU)

The extra time is for:
- Word-level alignment
- Speaker detection analysis
- Speaker assignment to segments

### Limitations

- Speaker labels are generic: `SPEAKER_00`, `SPEAKER_01`, etc.
- Does not identify speakers by name automatically
- Works best with clear audio and distinct voices
- Accuracy varies with audio quality and speaker overlap

### Transcript Location

**Important:** Transcripts are NOT included in the RSS feed XML to keep feed sizes manageable.

**Where transcripts appear:**
- ✅ **HTML page** - Formatted with speaker labels
- ✅ **JSON file** - Full data with timestamps and speakers
- ✅ **TXT file** - Plain text version
- ❌ **RSS feed** - Not included

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
