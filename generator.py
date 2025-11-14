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


def get_file_hash(filepath):
    """Generate MD5 hash of file for change detection."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def parse_episode_metadata(json_path):
    """Parse episode metadata from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)


def get_mp3_size(mp3_path):
    """Get MP3 file size in bytes."""
    return os.path.getsize(mp3_path)


def find_episodes(input_dir):
    """
    Scan input directory for episode folders containing .mp3 and .json files.
    Returns list of episode data dictionaries.
    """
    episodes = []
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"Input directory {input_dir} does not exist")
        return episodes

    # Look for folders containing both .mp3 and .json files
    for folder in sorted(input_path.iterdir()):
        if not folder.is_dir():
            continue

        mp3_files = list(folder.glob("*.mp3"))
        json_files = list(folder.glob("*.json"))

        if mp3_files and json_files:
            # Take first mp3 and json found in folder
            mp3_file = mp3_files[0]
            json_file = json_files[0]

            try:
                metadata = parse_episode_metadata(json_file)
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
                print(f"Error processing {folder.name}: {e}")

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
        SubElement(item, 'description').text = meta.get('description', '')

        # Episode URL
        episode_url = f"{base_url}/episodes/{episode['mp3_filename']}"
        SubElement(item, 'link').text = episode_url

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
</head>
<body>
    <h1>{podcast_info.get('title', 'My Podcast')}</h1>
    <p>{podcast_info.get('description', 'A podcast feed')}</p>

    <h2>Subscribe</h2>
    <p>RSS Feed: <a href="/feed.xml">/feed.xml</a></p>

    <h2>Episodes</h2>
    <ul>
"""

    for episode in sorted_episodes:
        meta = episode['metadata']
        title = meta.get('title', episode['folder_name'])
        description = meta.get('description', '')
        pub_date = meta.get('pub_date', '')

        html += f"""        <li>
            <h3>{title}</h3>
            <p><strong>Published:</strong> {pub_date}</p>
            <p>{description}</p>
            <audio controls>
                <source src="/episodes/{episode['mp3_filename']}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
        </li>
"""

    html += """    </ul>
</body>
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

    # Copy MP3 files to output directory
    print("Copying MP3 files...")
    for episode in episodes:
        dest = episodes_dir / episode['mp3_filename']
        if not dest.exists() or get_file_hash(episode['mp3_path']) != get_file_hash(dest):
            shutil.copy2(episode['mp3_path'], dest)
            print(f"  Copied {episode['mp3_filename']}")

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
