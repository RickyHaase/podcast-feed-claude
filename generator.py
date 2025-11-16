#!/usr/bin/env python3
"""
Podcast Feed Generator
Scans a directory of podcast episodes and generates an RSS feed and HTML page.
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree, tostring
from xml.dom import minidom
import hashlib

# Configure logging
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_file_hash(filepath):
    """Generate MD5 hash of file for change detection."""
    logger.debug(f"Computing hash for {filepath}")
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    hash_value = hash_md5.hexdigest()
    logger.debug(f"Hash for {filepath}: {hash_value}")
    return hash_value


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


def parse_episode_metadata(json_path):
    """Parse episode metadata from JSON file (YouTube format)."""
    logger.debug(f"Parsing metadata from {json_path}")
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Convert YouTube JSON format to our internal format
    metadata = {
        'title': data.get('title', ''),
        'description': data.get('description', ''),
        'webpage_url': data.get('webpage_url', ''),
        'chapters': data.get('chapters', []),
    }

    logger.debug(f"  Title: {metadata['title']}")
    logger.debug(f"  Chapters: {len(metadata['chapters'])} found")

    # Convert upload_date (YYYYMMDD) to ISO 8601 format
    if 'upload_date' in data:
        try:
            date_str = data['upload_date']
            dt = datetime.strptime(date_str, '%Y%m%d')
            metadata['pub_date'] = dt.isoformat() + 'Z'
            logger.debug(f"  Pub date: {metadata['pub_date']}")
        except Exception as e:
            logger.warning(f"  Failed to parse upload_date: {e}")

    # Convert duration from seconds to HH:MM:SS
    if 'duration' in data:
        metadata['duration'] = seconds_to_duration(data['duration'])
        logger.debug(f"  Duration: {metadata['duration']}")

    # Extract other useful fields
    metadata['author'] = data.get('uploader', data.get('channel', ''))
    metadata['thumbnail'] = data.get('thumbnail', '')

    # Generate a unique GUID from the video ID
    if 'id' in data:
        metadata['guid'] = f"youtube-{data['id']}"
        logger.debug(f"  GUID: {metadata['guid']}")

    return metadata


def get_mp3_size(mp3_path):
    """Get MP3 file size in bytes."""
    return os.path.getsize(mp3_path)


def find_episodes(input_dir):
    """
    Scan input directory for episode folders containing .mp3 and .info.json files.
    Expects files named like: YYYY-MM-DD.mp3, YYYY-MM-DD.info.json, YYYY-MM-DD-thumb.jpg
    Returns list of episode data dictionaries.
    """
    episodes = []
    input_path = Path(input_dir)

    if not input_path.exists():
        logger.error(f"Input directory {input_dir} does not exist")
        return episodes

    logger.debug(f"Scanning {input_path} for episode folders")

    # Look for folders containing both .mp3 and .info.json files
    for folder in sorted(input_path.iterdir()):
        if not folder.is_dir():
            logger.debug(f"Skipping non-directory: {folder.name}")
            continue

        logger.debug(f"Scanning folder: {folder.name}")

        # Look for .info.json files (YouTube format)
        info_json_files = list(folder.glob("*.info.json"))
        logger.debug(f"  Found {len(info_json_files)} .info.json file(s)")

        if info_json_files:
            # Process each info.json file
            for json_file in info_json_files:
                # Extract the base date from the filename (e.g., "2025-09-26" from "2025-09-26.info.json")
                base_name = json_file.stem.replace('.info', '')
                logger.debug(f"  Processing: {json_file.name} (base: {base_name})")

                # Look for corresponding MP3 file
                mp3_file = folder / f"{base_name}.mp3"

                # Look for thumbnail
                thumb_file = folder / f"{base_name}-thumb.jpg"

                if mp3_file.exists():
                    logger.debug(f"    MP3 found: {mp3_file.name}")
                    if thumb_file.exists():
                        logger.debug(f"    Thumbnail found: {thumb_file.name}")
                    else:
                        logger.debug(f"    No thumbnail found")

                    try:
                        metadata = parse_episode_metadata(json_file)

                        # Add thumbnail path if it exists
                        if thumb_file.exists():
                            metadata['thumbnail_file'] = thumb_file

                        mp3_size = get_mp3_size(mp3_file)
                        episode = {
                            'folder_name': folder.name,
                            'mp3_path': mp3_file,
                            'mp3_filename': mp3_file.name,
                            'mp3_size': mp3_size,
                            'metadata': metadata
                        }
                        episodes.append(episode)
                        logger.info(f"Found episode: {metadata.get('title', folder.name)}")
                        logger.debug(f"    MP3 size: {mp3_size} bytes")
                    except Exception as e:
                        logger.error(f"Error processing {json_file.name}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning(f"    MP3 file not found: {mp3_file.name}")

    return episodes


def generate_rss_feed(episodes, podcast_info, base_url):
    """Generate RSS 2.0 podcast feed XML."""
    logger.debug(f"Generating RSS feed with {len(episodes)} episodes")
    logger.debug(f"  Podcast title: {podcast_info.get('title')}")
    logger.debug(f"  Base URL: {base_url}")

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

        # Build description with chapters and source link
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
    rough_string = tostring(elem, encoding='unicode')
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

    logger.info("=== Podcast Feed Generator ===")
    logger.info(f"Debug mode: {'ENABLED' if DEBUG else 'DISABLED'}")
    logger.debug(f"Configuration:")
    logger.debug(f"  INPUT_DIR: {INPUT_DIR}")
    logger.debug(f"  OUTPUT_DIR: {OUTPUT_DIR}")
    logger.debug(f"  BASE_URL: {BASE_URL}")

    # Podcast metadata (can be overridden with env vars or config file)
    podcast_info = {
        'title': os.getenv('PODCAST_TITLE', 'My Podcast'),
        'description': os.getenv('PODCAST_DESCRIPTION', 'A podcast feed'),
        'author': os.getenv('PODCAST_AUTHOR', 'Podcast Author'),
        'language': os.getenv('PODCAST_LANGUAGE', 'en-us'),
        'explicit': os.getenv('PODCAST_EXPLICIT', 'no'),
    }

    logger.debug(f"Podcast metadata:")
    logger.debug(f"  Title: {podcast_info['title']}")
    logger.debug(f"  Author: {podcast_info['author']}")
    logger.debug(f"  Language: {podcast_info['language']}")

    # Optional image URL
    if os.getenv('PODCAST_IMAGE_URL'):
        podcast_info['image_url'] = os.getenv('PODCAST_IMAGE_URL')
        logger.debug(f"  Image URL: {podcast_info['image_url']}")

    # Check for podcast_info.json in input directory
    podcast_info_file = Path(INPUT_DIR) / 'podcast_info.json'
    if podcast_info_file.exists():
        logger.debug(f"Loading podcast info from {podcast_info_file}")
        with open(podcast_info_file, 'r') as f:
            podcast_info.update(json.load(f))

    logger.info(f"Scanning {INPUT_DIR} for episodes...")
    episodes = find_episodes(INPUT_DIR)

    if not episodes:
        logger.warning("No episodes found!")
        return

    logger.info(f"Found {len(episodes)} episode(s)")

    # Create output directory structure
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(exist_ok=True)
    episodes_dir = output_path / 'episodes'
    episodes_dir.mkdir(exist_ok=True)
    logger.debug(f"Output directories created: {output_path}, {episodes_dir}")

    # Copy MP3 files and thumbnails to output directory
    logger.info("Copying MP3 files and thumbnails...")
    copied_files = 0
    skipped_files = 0
    for episode in episodes:
        # Copy MP3
        dest = episodes_dir / episode['mp3_filename']
        if not dest.exists() or get_file_hash(episode['mp3_path']) != get_file_hash(dest):
            logger.debug(f"  Copying {episode['mp3_filename']}")
            shutil.copy2(episode['mp3_path'], dest)
            logger.info(f"  Copied {episode['mp3_filename']}")
            copied_files += 1
        else:
            logger.debug(f"  Skipping {episode['mp3_filename']} (unchanged)")
            skipped_files += 1

        # Copy thumbnail if it exists
        if 'thumbnail_file' in episode['metadata']:
            thumb_src = episode['metadata']['thumbnail_file']
            thumb_dest = episodes_dir / thumb_src.name
            if not thumb_dest.exists() or get_file_hash(thumb_src) != get_file_hash(thumb_dest):
                logger.debug(f"  Copying thumbnail {thumb_src.name}")
                shutil.copy2(thumb_src, thumb_dest)
                logger.info(f"  Copied {thumb_src.name}")
                copied_files += 1
            else:
                logger.debug(f"  Skipping thumbnail {thumb_src.name} (unchanged)")
                skipped_files += 1

    logger.info(f"File copy complete: {copied_files} copied, {skipped_files} skipped")

    # Generate RSS feed
    logger.info("Generating RSS feed...")
    rss = generate_rss_feed(episodes, podcast_info, BASE_URL)
    logger.debug("Converting RSS to XML string")
    xml_str = prettify_xml(rss)

    feed_path = output_path / 'feed.xml'
    logger.debug(f"Writing RSS feed to {feed_path}")
    with open(feed_path, 'w') as f:
        f.write(xml_str)
    logger.info(f"  RSS feed written to {feed_path}")

    # Generate HTML page
    logger.info("Generating HTML page...")
    html = generate_html_page(episodes, podcast_info)

    index_path = output_path / 'index.html'
    logger.debug(f"Writing HTML page to {index_path}")
    with open(index_path, 'w') as f:
        f.write(html)
    logger.info(f"  HTML page written to {index_path}")

    logger.info("Done!")


if __name__ == '__main__':
    main()
