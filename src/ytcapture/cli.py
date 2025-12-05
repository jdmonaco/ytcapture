"""CLI interface for ytcapture."""

import shutil
import subprocess
from pathlib import Path

import click
from rich.console import Console

from ytcapture import __version__
from ytcapture.frames import FrameExtractionError, extract_frames_from_file
from ytcapture.markdown import generate_markdown_file
from ytcapture.transcript import TranscriptSegment, get_transcript, save_transcript_json
from ytcapture.utils import sanitize_title
from ytcapture.video import VideoError, VideoMetadata, download_video, get_video_metadata

console = Console()


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


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"


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
    '--keep-video',
    is_flag=True,
    help='Keep downloaded video file after frame extraction',
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
    max_frames: int | None,
    frame_format: str,
    language: str,
    prefer_manual: bool,
    dedup_threshold: float,
    no_dedup: bool,
    keep_video: bool,
    verbose: bool,
) -> None:
    """Extract frames and transcript from a YouTube video.

    Creates an Obsidian-compatible markdown file with embedded frames
    and timestamped transcript segments.

    URL should be a valid YouTube video URL.

    Example:

        ytcapture "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    """
    # 1. Get video metadata
    with console.status("[bold blue]Fetching video metadata...", spinner="dots"):
        try:
            metadata: VideoMetadata = get_video_metadata(url)
        except VideoError as e:
            console.print(f"[red]✗[/] {e}")
            raise click.ClickException(str(e))

    console.print("[green]✓[/] Fetched video metadata")
    console.print(f"  [dim]Title:[/] {metadata.title}")
    console.print(f"  [dim]Channel:[/] {metadata.channel}")

    # 2. Determine output directory
    if output:
        output_dir = Path(output)
    else:
        output_dir = Path(sanitize_title(metadata.title))

    console.print(f"  [dim]Output:[/] {output_dir}/")

    # 3. Create directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / 'images'
    frames_dir.mkdir(exist_ok=True)
    transcript_dir = output_dir / 'transcript'
    transcript_dir.mkdir(exist_ok=True)
    video_dir = output_dir / 'video'
    video_dir.mkdir(exist_ok=True)

    # 4. Get transcript
    with console.status("[bold blue]Fetching transcript...", spinner="dots"):
        transcript: list[TranscriptSegment] | None = get_transcript(
            metadata.video_id,
            language=language,
            prefer_manual=prefer_manual,
        )

    if transcript:
        console.print(f"[green]✓[/] Found {len(transcript)} transcript segments")
        save_transcript_json(transcript, transcript_dir / 'raw-transcript.json')
    else:
        console.print("[yellow]⚠[/] No transcript available, proceeding with frames only")

    # 5. Download video
    with console.status("[bold blue]Downloading video...", spinner="dots"):
        try:
            video_path = download_video(url, video_dir)
        except VideoError as e:
            console.print(f"[red]✗[/] Download failed: {e}")
            raise click.ClickException(str(e))

    video_size = format_size(video_path.stat().st_size)
    console.print(f"[green]✓[/] Downloaded video ({video_size})")

    # 6. Extract frames (with integrated dedup)
    with console.status("[bold blue]Extracting frames...", spinner="dots"):
        try:
            frames = extract_frames_from_file(
                video_path,
                frames_dir,
                interval=interval,
                max_frames=max_frames,
                frame_format=frame_format,
                dedup_threshold=None if no_dedup else dedup_threshold,
            )
        except FrameExtractionError as e:
            console.print(f"[red]✗[/] Frame extraction failed: {e}")
            raise click.ClickException(str(e))

    dedup_msg = "" if no_dedup else " (deduplicated)"
    console.print(f"[green]✓[/] Extracted {len(frames)} frames{dedup_msg}")

    # 7. Cleanup video (unless --keep-video)
    if keep_video:
        console.print(f"  [dim]Video saved:[/] {video_path}")
    else:
        try:
            video_path.unlink()
            video_dir.rmdir()
        except Exception:
            pass  # Ignore cleanup errors

    # 8. Generate markdown
    with console.status("[bold blue]Generating markdown...", spinner="dots"):
        md_file = generate_markdown_file(
            metadata,
            url,
            transcript,
            frames,
            output_dir,
        )

    console.print("[green]✓[/] Generated markdown")

    # 9. Format markdown (if mdformat available)
    if format_markdown(md_file):
        console.print("  [dim]Formatted with mdformat[/]")

    console.print(f"\n[bold green]Complete![/] Output: {md_file}")


if __name__ == '__main__':
    main()
