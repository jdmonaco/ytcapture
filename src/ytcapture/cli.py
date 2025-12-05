"""CLI interface for ytcapture."""

import shutil
import subprocess
from pathlib import Path

import click

from ytcapture import __version__
from ytcapture.dedup import deduplicate_frames
from ytcapture.frames import FrameExtractionError, extract_frames_stream
from ytcapture.markdown import generate_markdown_file
from ytcapture.transcript import TranscriptSegment, get_transcript, save_transcript_json
from ytcapture.utils import sanitize_title
from ytcapture.video import VideoError, VideoMetadata, get_video_metadata


def echo_status(message: str, verbose: bool = True) -> None:
    """Print a status message."""
    if verbose:
        click.echo(message)


def format_markdown(filepath: Path) -> bool:
    """Format markdown file with mdformat if available.

    Args:
        filepath: Path to the markdown file.

    Returns:
        True if formatting was applied, False otherwise.
    """
    if shutil.which('mdformat') is None:
        return False

    try:
        subprocess.run(
            ['mdformat', '--wrap', 'no', filepath],
            capture_output=True,
            timeout=30,
        )
        return True
    except Exception:
        return False


@click.command()
@click.argument('url')
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Output directory (default: sanitized video title)',
)
@click.option(
    '--interval',
    type=int,
    default=15,
    help='Frame extraction interval in seconds (default: 15)',
)
@click.option(
    '--keyframes',
    is_flag=True,
    help='Extract only keyframes (I-frames) instead of at intervals',
)
@click.option(
    '--max-frames',
    type=int,
    help='Maximum number of frames to extract',
)
@click.option(
    '--frame-format',
    type=click.Choice(['jpg', 'png']),
    default='jpg',
    help='Frame image format (default: jpg)',
)
@click.option(
    '--images-dir',
    default='images',
    help='Name of images subdirectory (default: images)',
)
@click.option(
    '--language',
    default='en',
    help='Transcript language code (default: en)',
)
@click.option(
    '--prefer-manual',
    is_flag=True,
    help='Only use manual transcripts (fail if unavailable)',
)
@click.option(
    '--dedup-threshold',
    type=float,
    default=0.85,
    help='Similarity threshold for frame deduplication (0.0-1.0, default: 0.85)',
)
@click.option(
    '--no-dedup',
    is_flag=True,
    help='Disable frame deduplication',
)
@click.option(
    '-v', '--verbose',
    is_flag=True,
    help='Verbose output',
)
@click.version_option(version=__version__)
def main(
    url: str,
    output: str | None,
    interval: int,
    keyframes: bool,
    max_frames: int | None,
    frame_format: str,
    images_dir: str,
    language: str,
    prefer_manual: bool,
    dedup_threshold: float,
    no_dedup: bool,
    verbose: bool,
) -> None:
    """Extract frames and transcript from a YouTube video.

    Creates an Obsidian-compatible markdown file with embedded frames
    and timestamped transcript segments.

    URL should be a valid YouTube video URL.

    Example:

        ytcapture "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    """
    verbose = True  # Always show status for now

    # 1. Get video metadata
    echo_status('Fetching video metadata...', verbose)
    try:
        metadata: VideoMetadata = get_video_metadata(url)
    except VideoError as e:
        raise click.ClickException(str(e))

    echo_status(f'  Title: {metadata.title}', verbose)
    echo_status(f'  Channel: {metadata.channel}', verbose)

    # 2. Determine output directory
    if output:
        output_dir = Path(output)
    else:
        output_dir = Path(sanitize_title(metadata.title))

    echo_status(f'  Output: {output_dir}/', verbose)

    # 3. Create directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / images_dir
    frames_dir.mkdir(exist_ok=True)
    transcript_dir = output_dir / 'transcript'
    transcript_dir.mkdir(exist_ok=True)

    # 4. Get transcript
    echo_status('Fetching transcript...', verbose)
    transcript: list[TranscriptSegment] | None = get_transcript(
        metadata.video_id,
        language=language,
        prefer_manual=prefer_manual,
    )

    if transcript:
        echo_status(f'  Found {len(transcript)} segments', verbose)
        save_transcript_json(transcript, transcript_dir / 'raw-transcript.json')
    else:
        echo_status('  No transcript available, proceeding with frames only', verbose)

    # 5. Extract frames
    echo_status('Extracting frames (this may take a while)...', verbose)
    try:
        frames = extract_frames_stream(
            url,
            frames_dir,
            interval=interval,
            keyframes=keyframes,
            max_frames=max_frames,
            frame_format=frame_format,
        )
    except FrameExtractionError as e:
        raise click.ClickException(str(e))

    echo_status(f'  Extracted {len(frames)} frames', verbose)

    # 6. Deduplicate frames
    if not no_dedup and len(frames) > 1:
        original_count = len(frames)
        frames = deduplicate_frames(frames, threshold=dedup_threshold)
        removed = original_count - len(frames)
        if removed > 0:
            echo_status(f'  Removed {removed} duplicate frames', verbose)

    # 7. Generate markdown
    echo_status('Generating markdown...', verbose)
    md_file = generate_markdown_file(
        metadata,
        url,
        transcript,
        frames,
        output_dir,
        images_dir,
    )

    # 8. Format markdown (if mdformat available)
    if format_markdown(md_file):
        echo_status('  Formatted with mdformat', verbose)

    echo_status(f'Complete! Output: {md_file}', verbose)


if __name__ == '__main__':
    main()
