"""Markdown generation for Obsidian output."""

from datetime import datetime
from pathlib import Path

import yaml

from ytcapture.frames import FrameInfo
from ytcapture.metadata import VideoMetadataProtocol
from ytcapture.transcript import TranscriptSegment
from ytcapture.utils import format_date, format_timestamp, sanitize_title, truncate_title_words


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
    metadata: VideoMetadataProtocol,
    url: str | None = None,
) -> str:
    """Generate YAML frontmatter for Obsidian.

    Args:
        metadata: Any object implementing VideoMetadataProtocol.
        url: Optional source URL (for YouTube videos).

    Returns:
        YAML frontmatter string including delimiters.
    """
    # Build frontmatter dict with required fields
    frontmatter: dict[str, str | list[str]] = {
        'title': metadata.title,
        'created': datetime.now().strftime('%Y-%m-%d'),
        'published': format_date(metadata.source_date),
        'tags': [metadata.source_type],
    }

    # Add optional source URL
    if url:
        frontmatter['source'] = url

    # Add optional author
    if metadata.author:
        frontmatter['author'] = [metadata.author]

    # Add optional description (truncated)
    if metadata.description:
        description = metadata.description
        if len(description) > 200:
            description = description[:197] + '...'
        frontmatter['description'] = description

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
    identifier: str,
) -> str:
    """Generate markdown body with embedded frames and transcript.

    Args:
        grouped_data: List of (frame, segments) tuples from align_transcript_to_frames.
        identifier: Unique identifier for constructing embed paths (video_id or filename stem).

    Returns:
        Markdown body string.
    """
    sections = []

    for frame, segments in grouped_data:
        # Timestamp heading
        timestamp_str = format_timestamp(frame.timestamp)
        section = f'\n## {timestamp_str}\n\n'

        # Frame embed (Obsidian syntax)
        relative_path = f'images/{identifier}/{frame.path.name}'
        section += f'![[{relative_path}]]\n\n'

        # Transcript text for this frame's time window
        if segments:
            text = ' '.join(s.text for s in segments)
            section += f'{text}\n'

        sections.append(section)

    return ''.join(sections)


def generate_frames_only(
    frames: list[FrameInfo],
    identifier: str,
) -> str:
    """Generate markdown body with frames only (no transcript).

    Args:
        frames: List of frame info objects.
        identifier: Unique identifier for constructing embed paths (video_id or filename stem).

    Returns:
        Markdown body string.
    """
    sections = []

    for frame in frames:
        timestamp_str = format_timestamp(frame.timestamp)
        relative_path = f'images/{identifier}/{frame.path.name}'

        section = f'\n## {timestamp_str}\n\n![[{relative_path}]]\n'
        sections.append(section)

    return ''.join(sections)


def generate_markdown_filename(metadata: VideoMetadataProtocol) -> str:
    """Generate the markdown filename from video metadata.

    Args:
        metadata: Any object implementing VideoMetadataProtocol.

    Returns:
        Filename string (without directory path).
    """
    short_title = sanitize_title(truncate_title_words(metadata.title, 6))
    date_str = metadata.source_date  # YYYYMMDD format

    if metadata.author:
        author = sanitize_title(metadata.author)
        return f'{short_title} ({author}) {date_str}.md'
    else:
        return f'{short_title} {date_str}.md'


def generate_markdown_file(
    metadata: VideoMetadataProtocol,
    url: str | None,
    transcript: list[TranscriptSegment] | None,
    frames: list[FrameInfo],
    output_dir: Path,
    video_path: Path | None = None,
) -> Path:
    """Generate complete markdown file.

    Args:
        metadata: Any object implementing VideoMetadataProtocol.
        url: Optional source URL (for YouTube videos).
        transcript: List of transcript segments, or None.
        frames: List of frame info objects.
        output_dir: Directory to save the markdown file.
        video_path: Path to saved video file (if --keep-video was used).

    Returns:
        Path to the generated markdown file.
    """
    identifier = metadata.identifier

    # Generate frontmatter
    frontmatter = generate_frontmatter(metadata, url)

    # Generate body
    if transcript and frames:
        grouped = align_transcript_to_frames(transcript, frames)
        body = generate_markdown_body(grouped, identifier)
    elif frames:
        body = generate_frames_only(frames, identifier)
    else:
        # No frames or transcript
        body = '\n*No frames or transcript available.*\n'

    # Generate video embed (if video was saved)
    video_embed = ''
    if video_path and video_path.exists():
        # Use relative path from output_dir (where markdown will be)
        relative_video_path = f'videos/{video_path.name}'
        video_embed = f'\n<video src="{relative_video_path}" controls width="100%"></video>\n'

    # Generate description blockquote (first paragraph only)
    description_section = ''
    if metadata.description:
        first_para = metadata.description.strip().split('\n\n')[0]
        desc_lines = first_para.strip().split('\n')
        desc_blockquote = '\n'.join(f'> {line}' for line in desc_lines if line.strip())
        if desc_blockquote:
            description_section = f'\n{desc_blockquote}\n'

    # Combine: frontmatter + H1 title + video embed + description + body
    title_heading = f'\n# {metadata.title}\n'
    content = frontmatter + title_heading + video_embed + description_section + body

    # Generate filename
    filename = generate_markdown_filename(metadata)

    filepath = output_dir / filename
    filepath.write_text(content, encoding='utf-8')

    return filepath
