#!/usr/bin/env python3
"""
Podcast Feed Generator
Scans a directory of podcast episodes and generates an RSS feed and HTML page.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
from xml.dom import minidom
import hashlib

# Import Whisper for transcription (will be None if not available)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("Warning: Whisper not available. Transcription will be disabled.")

# Import WhisperX for speaker diarization (optional)
try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    print("Warning: WhisperX not available. Speaker diarization will be disabled.")


def get_file_hash(filepath):
    """Generate MD5 hash of file for change detection."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def seconds_to_duration(seconds):
    """Convert seconds to HH:MM:SS format."""
    if not seconds:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_chapters_as_text(chapters):
    """Format chapters array into readable timestamp text."""
    if not chapters:
        return ""

    lines = []
    for chapter in chapters:
        start = int(chapter.get('start_time', 0))
        hours = start // 3600
        minutes = (start % 3600) // 60
        secs = start % 60

        if hours > 0:
            timestamp = f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            timestamp = f"{minutes:02d}:{secs:02d}"

        title = chapter.get('title', '')
        lines.append(f"{timestamp} {title}")

    return "\n".join(lines)


def format_transcript_for_html(transcript_data):
    """
    Format transcript data into HTML paragraphs with speaker labels.

    Args:
        transcript_data: Dictionary with 'segments' from WhisperX

    Returns:
        HTML string with formatted transcript
    """
    if not transcript_data or 'segments' not in transcript_data:
        return ""

    segments = transcript_data['segments']
    if not segments:
        return ""

    html_parts = []
    current_speaker = None
    current_paragraph = []

    for segment in segments:
        speaker = segment.get('speaker', None)
        text = segment.get('text', '').strip()

        if not text:
            continue

        # If speaker changed, start a new paragraph
        if speaker != current_speaker:
            # Save previous paragraph if it exists
            if current_paragraph:
                paragraph_text = ' '.join(current_paragraph)
                if current_speaker:
                    html_parts.append(f'<p><strong>{current_speaker}:</strong> {paragraph_text}</p>')
                else:
                    html_parts.append(f'<p>{paragraph_text}</p>')
                current_paragraph = []

            current_speaker = speaker

        current_paragraph.append(text)

    # Add final paragraph
    if current_paragraph:
        paragraph_text = ' '.join(current_paragraph)
        if current_speaker:
            html_parts.append(f'<p><strong>{current_speaker}:</strong> {paragraph_text}</p>')
        else:
            html_parts.append(f'<p>{paragraph_text}</p>')

    return '\n'.join(html_parts)


def parse_episode_metadata(json_path):
    """Parse episode metadata from JSON file (YouTube format)."""
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Convert YouTube JSON format to our internal format
    metadata = {
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'webpage_url': data.get('webpage_url', ''),
        'chapters': data.get('chapters', []),
    }

    # Convert upload_date (YYYYMMDD) to ISO 8601 format
    if 'upload_date' in data:
        try:
            date_str = data['upload_date']
            dt = datetime.strptime(date_str, '%Y%m%d')
            metadata['pub_date'] = dt.isoformat() + 'Z'
        except:
            pass

    # Convert duration from seconds to HH:MM:SS
    if 'duration' in data:
        metadata['duration'] = seconds_to_duration(data['duration'])

    # Extract other useful fields
    metadata['author'] = data.get('uploader', data.get('channel', ''))
    metadata['thumbnail'] = data.get('thumbnail', '')

    # Generate a unique GUID from the video ID
    if 'id' in data:
        metadata['guid'] = f"youtube-{data['id']}"

    return metadata


def get_mp3_size(mp3_path):
    """Get MP3 file size in bytes."""
    return os.path.getsize(mp3_path)


def transcribe_audio(audio_path, transcript_path=None, model_name="base", initial_prompt=""):
    """
    Transcribe audio file using Whisper.

    Args:
        audio_path: Path to the audio file (MP3, WAV, etc.)
        transcript_path: Optional path to save transcript to. If None, returns transcript text only.
        model_name: Whisper model to use (tiny, base, small, medium, large)
        initial_prompt: Optional text to guide the model (speaker names, technical terms, etc.)

    Returns:
        Transcript text string
    """
    if not WHISPER_AVAILABLE:
        print(f"  Skipping transcription for {audio_path.name} (Whisper not available)")
        return None

    try:
        print(f"  Loading Whisper model '{model_name}'...")
        model = whisper.load_model(model_name)

        print(f"  Transcribing {audio_path.name}...")

        # Build transcribe options
        transcribe_options = {}
        if initial_prompt:
            transcribe_options['initial_prompt'] = initial_prompt
            print(f"  Using custom prompt: {initial_prompt[:50]}...")

        result = model.transcribe(str(audio_path), **transcribe_options)

        transcript_text = result["text"].strip()

        # Save to file if path provided
        if transcript_path:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            print(f"  Transcript saved to {transcript_path.name}")

        return transcript_text

    except Exception as e:
        print(f"  Error transcribing {audio_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def transcribe_with_whisperx(audio_path, model_name="base", initial_prompt="", hf_token=None, min_speakers=None, max_speakers=None):
    """
    Transcribe audio file using WhisperX with speaker diarization.

    Args:
        audio_path: Path to the audio file
        model_name: Whisper model to use (tiny, base, small, medium, large)
        initial_prompt: Optional text to guide the model
        hf_token: HuggingFace token for speaker diarization (required for diarization)
        min_speakers: Minimum number of speakers (optional)
        max_speakers: Maximum number of speakers (optional)

    Returns:
        Dictionary with 'text', 'segments', and structured data for JSON/HTML
    """
    if not WHISPERX_AVAILABLE:
        print(f"  WhisperX not available, falling back to regular Whisper")
        return None

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "float32"

        print(f"  Loading WhisperX model '{model_name}' on {device}...")
        model = whisperx.load_model(model_name, device, compute_type=compute_type)

        # Load audio
        print(f"  Loading audio from {audio_path.name}...")
        audio = whisperx.load_audio(str(audio_path))

        # Transcribe
        print(f"  Transcribing with WhisperX...")
        transcribe_options = {}
        if initial_prompt:
            transcribe_options['initial_prompt'] = initial_prompt
            print(f"  Using custom prompt: {initial_prompt[:50]}...")

        result = model.transcribe(audio, batch_size=16, **transcribe_options)

        # Align whisper output
        print(f"  Aligning timestamps...")
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

        # Perform speaker diarization if token provided
        if hf_token:
            print(f"  Performing speaker diarization...")
            try:
                diarize_model = whisperx.DiarizationPipeline(use_auth_token=hf_token, device=device)

                diarize_segments = diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                print(f"  Speaker diarization completed")
            except Exception as e:
                print(f"  Warning: Speaker diarization failed: {e}")
                print(f"  Continuing without speaker labels...")
        else:
            print(f"  Skipping speaker diarization (no HuggingFace token provided)")

        # Build structured result
        full_text = " ".join([seg.get("text", "").strip() for seg in result["segments"]])

        return {
            'text': full_text,
            'segments': result["segments"],
            'language': result.get("language", "unknown")
        }

    except Exception as e:
        print(f"  Error transcribing with WhisperX {audio_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def find_episodes(input_dir):
    """
    Scan input directory for episode folders containing .mp3 and .info.json files.
    Expects files named like: YYYY-MM-DD.mp3, YYYY-MM-DD.info.json, YYYY-MM-DD-thumb.jpg
    Optionally generates or loads transcripts using Whisper.
    Returns list of episode data dictionaries.
    """
    episodes = []
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"Input directory {input_dir} does not exist")
        return episodes

    # Get transcription settings from environment
    enable_transcription = os.getenv('ENABLE_TRANSCRIPTION', 'false').lower() == 'true'
    whisper_model = os.getenv('WHISPER_MODEL', 'base')  # tiny, base, small, medium, large
    whisper_prompt = os.getenv('WHISPER_PROMPT', '')  # Optional initial prompt for context

    # Speaker diarization settings
    enable_diarization = os.getenv('ENABLE_SPEAKER_DIARIZATION', 'false').lower() == 'true'
    hf_token = os.getenv('HUGGINGFACE_TOKEN', '')
    min_speakers = os.getenv('MIN_SPEAKERS', None)
    max_speakers = os.getenv('MAX_SPEAKERS', None)

    # Convert speaker counts to integers if provided
    if min_speakers:
        try:
            min_speakers = int(min_speakers)
        except ValueError:
            min_speakers = None
    if max_speakers:
        try:
            max_speakers = int(max_speakers)
        except ValueError:
            max_speakers = None

    # Look for folders containing both .mp3 and .info.json files
    for folder in sorted(input_path.iterdir()):
        if not folder.is_dir():
            continue

        # Look for .info.json files (YouTube format)
        info_json_files = list(folder.glob("*.info.json"))

        if info_json_files:
            # Process each info.json file
            for json_file in info_json_files:
                # Extract the base date from the filename (e.g., "2025-09-26" from "2025-09-26.info.json")
                base_name = json_file.stem.replace('.info', '')

                # Look for corresponding MP3 file
                mp3_file = folder / f"{base_name}.mp3"

                # Look for thumbnail
                thumb_file = folder / f"{base_name}-thumb.jpg"

                # Look for transcript files
                transcript_file = folder / f"{base_name}.txt"
                transcript_json_file = folder / f"{base_name}.transcript.json"

                if mp3_file.exists():
                    try:
                        metadata = parse_episode_metadata(json_file)

                        # Add thumbnail path if it exists
                        if thumb_file.exists():
                            metadata['thumbnail_file'] = thumb_file

                        # Handle transcription
                        transcript_data = None
                        transcript_text = None

                        # Check for existing JSON transcript (WhisperX format)
                        if transcript_json_file.exists():
                            print(f"  Loading existing transcript from {transcript_json_file.name}")
                            with open(transcript_json_file, 'r', encoding='utf-8') as f:
                                transcript_data = json.load(f)
                                transcript_text = transcript_data.get('text', '')
                        # Check for existing plain text transcript
                        elif transcript_file.exists():
                            print(f"  Loading existing transcript from {transcript_file.name}")
                            with open(transcript_file, 'r', encoding='utf-8') as f:
                                transcript_text = f.read().strip()
                        # Generate new transcript if enabled
                        elif enable_transcription:
                            # Use WhisperX if diarization is enabled
                            if enable_diarization and WHISPERX_AVAILABLE and hf_token:
                                print(f"  Generating transcript with speaker diarization for {mp3_file.name}...")
                                transcript_data = transcribe_with_whisperx(
                                    mp3_file,
                                    model_name=whisper_model,
                                    initial_prompt=whisper_prompt,
                                    hf_token=hf_token,
                                    min_speakers=min_speakers,
                                    max_speakers=max_speakers
                                )
                                if transcript_data:
                                    transcript_text = transcript_data['text']
                                    # Save JSON transcript
                                    with open(transcript_json_file, 'w', encoding='utf-8') as f:
                                        json.dump(transcript_data, f, indent=2, ensure_ascii=False)
                                    print(f"  Transcript JSON saved to {transcript_json_file.name}")
                                    # Also save plain text version
                                    with open(transcript_file, 'w', encoding='utf-8') as f:
                                        f.write(transcript_text)
                            # Fall back to regular Whisper
                            elif WHISPER_AVAILABLE:
                                print(f"  Generating transcript for {mp3_file.name}...")
                                transcript_text = transcribe_audio(mp3_file, transcript_file, whisper_model, whisper_prompt)

                        # Add transcript data to metadata
                        if transcript_data:
                            metadata['transcript_data'] = transcript_data  # Full structured data
                        if transcript_text:
                            metadata['transcript'] = transcript_text  # Plain text for backward compat

                        episode = {
                            'folder_name': folder.name,
                            'mp3_path': mp3_file,
                            'mp3_filename': mp3_file.name,
                            'mp3_size': get_mp3_size(mp3_file),
                            'metadata': metadata
                        }
                        episodes.append(episode)
                        print(f"Found episode: {metadata.get('title', folder.name)}")
                    except Exception as e:
                        print(f"Error processing {json_file.name}: {e}")
                        import traceback
                        traceback.print_exc()

    return episodes


def generate_rss_feed(episodes, podcast_info, base_url):
    """Generate RSS 2.0 podcast feed XML."""
    rss = Element('rss')
    rss.set('version', '2.0')
    rss.set('xmlns:itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd')
    rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')

    channel = SubElement(rss, 'channel')

    # Podcast-level metadata
    SubElement(channel, 'title').text = podcast_info.get('title', 'My Podcast')
    SubElement(channel, 'description').text = podcast_info.get('description', 'A podcast feed')
    SubElement(channel, 'link').text = base_url
    SubElement(channel, 'language').text = podcast_info.get('language', 'en-us')

    # Self-referencing link
    atom_link = SubElement(channel, 'atom:link')
    atom_link.set('href', f"{base_url}/feed.xml")
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')

    # iTunes-specific tags
    SubElement(channel, 'itunes:author').text = podcast_info.get('author', 'Unknown')
    SubElement(channel, 'itunes:explicit').text = podcast_info.get('explicit', 'no')

    if 'image_url' in podcast_info:
        image = SubElement(channel, 'image')
        SubElement(image, 'url').text = podcast_info['image_url']
        SubElement(image, 'title').text = podcast_info.get('title', 'My Podcast')
        SubElement(image, 'link').text = base_url

        itunes_image = SubElement(channel, 'itunes:image')
        itunes_image.set('href', podcast_info['image_url'])

    # Add episodes as items (sort by pub_date, newest first)
    sorted_episodes = sorted(
        episodes,
        key=lambda e: e['metadata'].get('pub_date', '1970-01-01T00:00:00Z'),
        reverse=True
    )

    for episode in sorted_episodes:
        item = SubElement(channel, 'item')
        meta = episode['metadata']

        SubElement(item, 'title').text = meta.get('title', episode['folder_name'])

        # Build description with chapters and source link (NO transcripts in RSS)
        description = meta.get('description', '')

        # Add chapters/timestamps if available
        chapters = meta.get('chapters', [])
        if chapters:
            chapters_text = format_chapters_as_text(chapters)
            if chapters_text:
                description += f"\n\nTimestamps:\n{chapters_text}"

        # Add source link if available
        if meta.get('webpage_url'):
            description += f"\n\nOriginal source: {meta['webpage_url']}"

        SubElement(item, 'description').text = description

        # Episode URL
        episode_url = f"{base_url}/episodes/{episode['mp3_filename']}"
        SubElement(item, 'link').text = meta.get('webpage_url', episode_url)

        # Enclosure (the actual MP3 file)
        enclosure = SubElement(item, 'enclosure')
        enclosure.set('url', episode_url)
        enclosure.set('length', str(episode['mp3_size']))
        enclosure.set('type', 'audio/mpeg')

        # GUID
        guid = SubElement(item, 'guid')
        guid.set('isPermaLink', 'false')
        guid.text = meta.get('guid', f"{episode['folder_name']}-{episode['mp3_filename']}")

        # Publication date (RFC 2822 format)
        if 'pub_date' in meta:
            try:
                dt = datetime.fromisoformat(meta['pub_date'].replace('Z', '+00:00'))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S %z')
                SubElement(item, 'pubDate').text = pub_date
            except:
                pass

        # iTunes-specific
        if 'duration' in meta:
            SubElement(item, 'itunes:duration').text = meta['duration']

        if 'episode_number' in meta:
            SubElement(item, 'itunes:episode').text = str(meta['episode_number'])

        if 'author' in meta:
            SubElement(item, 'itunes:author').text = meta['author']

        SubElement(item, 'itunes:explicit').text = meta.get('explicit', 'no')

    return rss


def prettify_xml(elem):
    """Return a pretty-printed XML string."""
    rough_string = ElementTree.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def generate_html_page(episodes, podcast_info):
    """Generate a simple HTML page listing episodes."""
    sorted_episodes = sorted(
        episodes,
        key=lambda e: e['metadata'].get('pub_date', '1970-01-01T00:00:00Z'),
        reverse=True
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{podcast_info.get('title', 'My Podcast')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        .episode {{
            margin-bottom: 40px;
            padding-bottom: 40px;
            border-bottom: 1px solid #ccc;
        }}
        .episode:last-child {{
            border-bottom: none;
        }}
        .episode h3 {{
            margin-top: 0;
        }}
        .description {{
            white-space: pre-wrap;
            margin: 15px 0;
        }}
        .transcript {{
            background-color: #e8f4f8;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
            border-left: 4px solid #0066cc;
        }}
        .transcript h4 {{
            margin-top: 0;
            color: #0066cc;
        }}
        .transcript-text {{
            line-height: 1.8;
            font-size: 0.95em;
        }}
        .transcript-text p {{
            margin: 10px 0;
        }}
        .transcript-text strong {{
            color: #0066cc;
        }}
        .chapters {{
            background-color: #f5f5f5;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .chapters h4 {{
            margin-top: 0;
        }}
        .chapters-list {{
            white-space: pre-wrap;
            font-family: monospace;
            font-size: 0.9em;
        }}
        .metadata {{
            color: #666;
            font-size: 0.9em;
        }}
        audio {{
            width: 100%;
            margin: 15px 0;
        }}
    </style>
</head>
<body>
    <h1>{podcast_info.get('title', 'My Podcast')}</h1>
    <p>{podcast_info.get('description', 'A podcast feed')}</p>

    <h2>Subscribe</h2>
    <p>RSS Feed: <a href="/feed.xml">/feed.xml</a></p>

    <h2>Episodes</h2>
"""

    for episode in sorted_episodes:
        meta = episode['metadata']
        title = meta.get('title', episode['folder_name'])
        description = meta.get('description', '')
        pub_date = meta.get('pub_date', '')
        webpage_url = meta.get('webpage_url', '')
        chapters = meta.get('chapters', [])
        transcript_data = meta.get('transcript_data', None)
        transcript = meta.get('transcript', '')

        html += f"""    <div class="episode">
        <h3>{title}</h3>
        <div class="metadata">
            <strong>Published:</strong> {pub_date}
"""

        if webpage_url:
            html += f"""            | <strong>Source:</strong> <a href="{webpage_url}" target="_blank">View Original</a>
"""

        html += """        </div>

        <audio controls>
            <source src="/episodes/{}" type="audio/mpeg">
            Your browser does not support the audio element.
        </audio>
""".format(episode['mp3_filename'])

        if description:
            html += f"""
        <div class="description">{description}</div>
"""

        # Display formatted transcript with speakers if available
        if transcript_data:
            formatted_transcript = format_transcript_for_html(transcript_data)
            if formatted_transcript:
                html += f"""
        <div class="transcript">
            <h4>Transcript</h4>
            <div class="transcript-text">{formatted_transcript}</div>
        </div>
"""
        # Fall back to plain text transcript
        elif transcript:
            html += f"""
        <div class="transcript">
            <h4>Transcript</h4>
            <div class="transcript-text"><p>{transcript}</p></div>
        </div>
"""

        if chapters:
            chapters_text = format_chapters_as_text(chapters)
            if chapters_text:
                html += f"""
        <div class="chapters">
            <h4>Timestamps</h4>
            <div class="chapters-list">{chapters_text}</div>
        </div>
"""

        html += """    </div>
"""

    html += """</body>
</html>
"""

    return html


def main():
    """Main generator function."""
    # Configuration
    INPUT_DIR = os.getenv('INPUT_DIR', '/input')
    OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/output')
    BASE_URL = os.getenv('BASE_URL', 'http://localhost')

    # Podcast metadata (can be overridden with env vars or config file)
    podcast_info = {
        'title': os.getenv('PODCAST_TITLE', 'My Podcast'),
        'description': os.getenv('PODCAST_DESCRIPTION', 'A podcast feed'),
        'author': os.getenv('PODCAST_AUTHOR', 'Podcast Author'),
        'language': os.getenv('PODCAST_LANGUAGE', 'en-us'),
        'explicit': os.getenv('PODCAST_EXPLICIT', 'no'),
    }

    # Optional image URL
    if os.getenv('PODCAST_IMAGE_URL'):
        podcast_info['image_url'] = os.getenv('PODCAST_IMAGE_URL')

    # Check for podcast_info.json in input directory
    podcast_info_file = Path(INPUT_DIR) / 'podcast_info.json'
    if podcast_info_file.exists():
        with open(podcast_info_file, 'r') as f:
            podcast_info.update(json.load(f))

    print(f"Scanning {INPUT_DIR} for episodes...")
    episodes = find_episodes(INPUT_DIR)

    if not episodes:
        print("No episodes found!")
        return

    print(f"Found {len(episodes)} episode(s)")

    # Create output directory structure
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    episodes_dir = output_path / 'episodes'
    episodes_dir.mkdir(exist_ok=True)

    # Copy MP3 files and thumbnails to output directory
    print("Copying MP3 files...")
    for episode in episodes:
        # Copy MP3
        dest = episodes_dir / episode['mp3_filename']
        if not dest.exists() or get_file_hash(episode['mp3_path']) != get_file_hash(dest):
            shutil.copy2(episode['mp3_path'], dest)
            print(f"  Copied {episode['mp3_filename']}")

        # Copy thumbnail if it exists
        if 'thumbnail_file' in episode['metadata']:
            thumb_src = episode['metadata']['thumbnail_file']
            thumb_dest = episodes_dir / thumb_src.name
            if not thumb_dest.exists() or get_file_hash(thumb_src) != get_file_hash(thumb_dest):
                shutil.copy2(thumb_src, thumb_dest)
                print(f"  Copied {thumb_src.name}")

    # Generate RSS feed
    print("Generating RSS feed...")
    rss = generate_rss_feed(episodes, podcast_info, BASE_URL)
    xml_str = prettify_xml(rss)

    feed_path = output_path / 'feed.xml'
    with open(feed_path, 'w') as f:
        f.write(xml_str)
    print(f"  RSS feed written to {feed_path}")

    # Generate HTML page
    print("Generating HTML page...")
    html = generate_html_page(episodes, podcast_info)

    index_path = output_path / 'index.html'
    with open(index_path, 'w') as f:
        f.write(html)
    print(f"  HTML page written to {index_path}")

    print("Done!")


if __name__ == '__main__':
    main()
