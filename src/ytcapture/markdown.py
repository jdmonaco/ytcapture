"""Markdown generation for Obsidian output."""

from datetime import datetime
from pathlib import Path

import yaml

from ytcapture.frames import FrameInfo
from ytcapture.transcript import TranscriptSegment
from ytcapture.utils import format_date, format_timestamp, sanitize_title
from ytcapture.video import VideoMetadata


def align_transcript_to_frames(
    transcript: list[TranscriptSegment] | None,
    frames: list[FrameInfo],
) -> list[tuple[FrameInfo, list[TranscriptSegment]]]:
    """Group transcript segments under the closest preceding frame.

    For each frame, collects all transcript segments that occur between
    that frame's timestamp and the next frame's timestamp.

    Args:
        transcript: List of transcript segments, or None.
        frames: List of frame info objects.

    Returns:
        List of (frame, segments) tuples, where segments is a list of
        transcript segments that belong to that frame's time window.
    """
    if not frames:
        return []

    if not transcript:
        # No transcript - return frames with empty segments
        return [(frame, []) for frame in frames]

    grouped: list[tuple[FrameInfo, list[TranscriptSegment]]] = []

    for i, frame in enumerate(frames):
        # Determine the time window for this frame
        frame_start = frame.timestamp
        if i + 1 < len(frames):
            frame_end = frames[i + 1].timestamp
        else:
            frame_end = float('inf')

        # Collect segments in this time window
        segments = [
            s for s in transcript
            if frame_start <= s.start < frame_end
        ]

        grouped.append((frame, segments))

    return grouped


def generate_frontmatter(
    metadata: VideoMetadata,
    url: str,
) -> str:
    """Generate YAML frontmatter for Obsidian.

    Args:
        metadata: Video metadata object.
        url: Original YouTube URL.

    Returns:
        YAML frontmatter string including delimiters.
    """
    # Truncate description if too long
    description = metadata.description
    if len(description) > 200:
        description = description[:197] + '...'

    # Build frontmatter dict
    frontmatter = {
        'title': metadata.title,
        'source': url,
        'author': [metadata.channel],
        'created': datetime.now().strftime('%Y-%m-%d'),
        'published': format_date(metadata.upload_date),
        'description': description,
        'tags': ['youtube'],
    }

    # Remove empty values
    frontmatter = {k: v for k, v in frontmatter.items() if v}

    # Generate YAML
    yaml_str = yaml.dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )

    return f'---\n{yaml_str}---\n'


def generate_markdown_body(
    grouped_data: list[tuple[FrameInfo, list[TranscriptSegment]]],
) -> str:
    """Generate markdown body with embedded frames and transcript.

    Args:
        grouped_data: List of (frame, segments) tuples from align_transcript_to_frames.

    Returns:
        Markdown body string.
    """
    sections = []

    for frame, segments in grouped_data:
        # Timestamp heading
        timestamp_str = format_timestamp(frame.timestamp)
        section = f'\n## {timestamp_str}\n\n'

        # Frame embed (Obsidian syntax)
        relative_path = f'images/{frame.path.name}'
        section += f'![[{relative_path}]]\n\n'

        # Transcript text for this frame's time window
        if segments:
            text = ' '.join(s.text for s in segments)
            section += f'{text}\n'

        sections.append(section)

    return ''.join(sections)


def generate_frames_only(
    frames: list[FrameInfo],
) -> str:
    """Generate markdown body with frames only (no transcript).

    Args:
        frames: List of frame info objects.

    Returns:
        Markdown body string.
    """
    sections = []

    for frame in frames:
        timestamp_str = format_timestamp(frame.timestamp)
        relative_path = f'images/{frame.path.name}'

        section = f'\n## {timestamp_str}\n\n![[{relative_path}]]\n'
        sections.append(section)

    return ''.join(sections)


def generate_markdown_file(
    metadata: VideoMetadata,
    url: str,
    transcript: list[TranscriptSegment] | None,
    frames: list[FrameInfo],
    output_dir: Path,
) -> Path:
    """Generate complete markdown file.

    Args:
        metadata: Video metadata object.
        url: Original YouTube URL.
        transcript: List of transcript segments, or None.
        frames: List of frame info objects.
        output_dir: Directory to save the markdown file.

    Returns:
        Path to the generated markdown file.
    """
    # Generate frontmatter
    frontmatter = generate_frontmatter(metadata, url)

    # Generate body
    if transcript and frames:
        grouped = align_transcript_to_frames(transcript, frames)
        body = generate_markdown_body(grouped)
    elif frames:
        body = generate_frames_only(frames)
    else:
        # No frames or transcript
        body = '\n*No frames or transcript available.*\n'

    # Generate description blockquote (first paragraph only)
    description_section = ''
    if metadata.description:
        first_para = metadata.description.strip().split('\n\n')[0]
        desc_lines = first_para.strip().split('\n')
        desc_blockquote = '\n'.join(f'> {line}' for line in desc_lines if line.strip())
        if desc_blockquote:
            description_section = f'\n{desc_blockquote}\n'

    # Combine: frontmatter + H1 title + description + body
    title_heading = f'\n# {metadata.title}\n'
    content = frontmatter + title_heading + description_section + body

    # Generate filename
    sanitized_title = sanitize_title(metadata.title)
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f'{sanitized_title} {date_str}.md'

    filepath = output_dir / filename
    filepath.write_text(content, encoding='utf-8')

    return filepath
