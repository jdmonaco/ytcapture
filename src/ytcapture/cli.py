"""CLI interface for ytcapture and vidcapture."""

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable, TypeVar

import click
from rich.console import Console

from ytcapture import __version__
from ytcapture.config import (
    config_was_auto_created,
    get_config_for_defaults,
    get_config_path,
    resolve_output_path,
)

# Load config at module level for CLI option defaults
_cfg = get_config_for_defaults()
from ytcapture.frames import FrameExtractionError, extract_frames_fast, extract_frames_from_file
from ytcapture.local import LocalVideoError, LocalVideoMetadata, get_local_video_metadata
from ytcapture.markdown import generate_markdown_file, generate_markdown_filename
from ytcapture.transcript import TranscriptSegment, get_transcript, save_transcript_json
from ytcapture.utils import is_playlist_url, is_video_url
from ytcapture.video import (
    VideoError,
    VideoMetadata,
    download_video,
    expand_playlist,
    get_video_metadata,
)

F = TypeVar('F', bound=Callable[..., None])

console = Console()


def get_clipboard_url() -> str | None:
    """Check clipboard for a YouTube URL (macOS only).

    Returns video or playlist URL from clipboard, or None if not found/available.
    """
    if platform.system() != 'Darwin':
        return None

    if shutil.which('pbpaste') is None:
        return None

    try:
        result = subprocess.run(
            ['pbpaste'],
            capture_output=True,
            text=True,
            timeout=5,
        )
        clipboard = result.stdout.strip()

        # Check if it looks like a YouTube video or playlist URL
        if clipboard and (is_video_url(clipboard) or is_playlist_url(clipboard)):
            return clipboard

    except Exception:
        pass

    return None


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


def common_frame_options(func: F) -> F:
    """Decorator for frame extraction options shared by ytcapture and vidcapture."""
    func = click.option(
        '-o', '--output',
        type=click.Path(),
        help='Output directory (vault-relative unless absolute path)',
    )(func)
    func = click.option(
        '--interval',
        type=int,
        default=_cfg.get("interval", 15),
        show_default=True,
        help='Frame extraction interval in seconds',
    )(func)
    func = click.option(
        '--max-frames',
        type=int,
        default=_cfg.get("max_frames"),
        help='Maximum number of frames to extract',
    )(func)
    func = click.option(
        '--frame-format',
        type=click.Choice(['jpg', 'png']),
        default=_cfg.get("frame_format", "jpg"),
        show_default=True,
        help='Frame image format',
    )(func)
    func = click.option(
        '--dedup-threshold',
        type=float,
        default=_cfg.get("dedup_threshold", 0.85),
        show_default=True,
        help='Similarity threshold for frame deduplication (0.0-1.0)',
    )(func)
    func = click.option(
        '--no-dedup',
        is_flag=True,
        help='Disable frame deduplication',
    )(func)
    func = click.option(
        '-v', '--verbose',
        is_flag=True,
        help='Verbose output',
    )(func)
    return func  # type: ignore[return-value]


def process_video(
    url: str,
    output_dir: Path,
    interval: int,
    max_frames: int | None,
    frame_format: str,
    language: str,
    prefer_manual: bool,
    dedup_threshold: float,
    no_dedup: bool,
    keep_video: bool,
) -> Path:
    """Process a single video URL.

    Args:
        url: YouTube video URL.
        output_dir: Output directory.
        interval: Frame extraction interval in seconds.
        max_frames: Maximum number of frames to extract.
        frame_format: Frame image format (jpg or png).
        language: Transcript language code.
        prefer_manual: Only use manual transcripts.
        dedup_threshold: Similarity threshold for frame deduplication.
        no_dedup: Disable frame deduplication.
        keep_video: Keep downloaded video file.

    Returns:
        Path to the generated markdown file.

    Raises:
        VideoError: If video processing fails.
        FrameExtractionError: If frame extraction fails.
    """
    # 1. Get video metadata
    with console.status("[bold blue]Fetching video metadata...", spinner="dots"):
        metadata: VideoMetadata = get_video_metadata(url)

    console.print("[green]✓[/] Fetched video metadata")
    console.print(f"  [dim]Title:[/] {metadata.title}")
    console.print(f"  [dim]Channel:[/] {metadata.channel}")

    # 2. Create directory structure
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / 'images' / metadata.video_id
    frames_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir = output_dir / 'transcripts'
    transcripts_dir.mkdir(exist_ok=True)
    videos_dir = output_dir / 'videos'
    videos_dir.mkdir(exist_ok=True)

    # 3. Get transcript
    with console.status("[bold blue]Fetching transcript...", spinner="dots"):
        transcript: list[TranscriptSegment] | None = get_transcript(
            metadata.video_id,
            language=language,
            prefer_manual=prefer_manual,
        )

    if transcript:
        console.print(f"[green]✓[/] Found {len(transcript)} transcript segments")
        save_transcript_json(
            transcript,
            transcripts_dir / f'raw-transcript-{metadata.video_id}.json',
        )
    else:
        console.print("[yellow]⚠[/] No transcript available, proceeding with frames only")

    # 4. Download video
    with console.status("[bold blue]Downloading video...", spinner="dots"):
        video_path = download_video(url, videos_dir)

    video_size = format_size(video_path.stat().st_size)
    console.print(f"[green]✓[/] Downloaded video ({video_size})")

    # 5. Extract frames (with integrated dedup)
    with console.status("[bold blue]Extracting frames...", spinner="dots"):
        frames = extract_frames_from_file(
            video_path,
            frames_dir,
            interval=interval,
            max_frames=max_frames,
            frame_format=frame_format,
            dedup_threshold=None if no_dedup else dedup_threshold,
        )

    dedup_msg = "" if no_dedup else " (deduplicated)"
    console.print(f"[green]✓[/] Extracted {len(frames)} frames{dedup_msg}")

    # 6. Handle video file (keep or delete)
    final_video_path: Path | None = None
    if keep_video:
        # Rename video to match markdown filename (for readability)
        md_filename = generate_markdown_filename(metadata)
        md_basename = md_filename.rsplit('.', 1)[0]  # Remove .md extension
        video_ext = video_path.suffix  # .mp4, .webm, etc.
        final_video_path = videos_dir / f'{md_basename}{video_ext}'

        if video_path != final_video_path:
            video_path.rename(final_video_path)

        console.print(f"  [dim]Video saved:[/] {final_video_path}")
    else:
        try:
            video_path.unlink()
            videos_dir.rmdir()
        except Exception:
            pass  # Ignore cleanup errors

    # 7. Generate markdown
    with console.status("[bold blue]Generating markdown...", spinner="dots"):
        md_file = generate_markdown_file(
            metadata,
            url,
            transcript,
            frames,
            output_dir,
            video_path=final_video_path,
        )

    console.print("[green]✓[/] Generated markdown")

    # 8. Format markdown (if mdformat available)
    if format_markdown(md_file):
        console.print("  [dim]Formatted with mdformat[/]")

    return md_file


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument('urls', nargs=-1)
@click.option(
    '-o', '--output',
    type=click.Path(),
    help='Output directory (vault-relative unless absolute path)',
)
@click.option(
    '--interval',
    type=int,
    default=_cfg.get("interval", 15),
    show_default=True,
    help='Frame extraction interval in seconds',
)
@click.option(
    '--max-frames',
    type=int,
    default=_cfg.get("max_frames"),
    help='Maximum number of frames to extract',
)
@click.option(
    '--frame-format',
    type=click.Choice(['jpg', 'png']),
    default=_cfg.get("frame_format", "jpg"),
    show_default=True,
    help='Frame image format',
)
@click.option(
    '--language',
    default=_cfg.get("language", "en"),
    show_default=True,
    help='Transcript language code',
)
@click.option(
    '--prefer-manual',
    is_flag=True,
    default=_cfg.get("prefer_manual", False),
    help='Only use manual transcripts (fail if unavailable)',
)
@click.option(
    '--dedup-threshold',
    type=float,
    default=_cfg.get("dedup_threshold", 0.85),
    show_default=True,
    help='Similarity threshold for frame deduplication (0.0-1.0)',
)
@click.option(
    '--no-dedup',
    is_flag=True,
    help='Disable frame deduplication',
)
@click.option(
    '--keep-video',
    is_flag=True,
    default=_cfg.get("keep_video", False),
    help='Keep downloaded video file after frame extraction',
)
@click.option(
    '-y', '--yes',
    is_flag=True,
    help='Skip confirmation prompt for large batches (>10 videos)',
)
@click.option(
    '-v', '--verbose',
    is_flag=True,
    help='Verbose output',
)
@click.version_option(version=__version__)
def main(
    urls: tuple[str, ...],
    output: str | None,
    interval: int,
    max_frames: int | None,
    frame_format: str,
    language: str,
    prefer_manual: bool,
    dedup_threshold: float,
    no_dedup: bool,
    keep_video: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """Extract frames and transcript from YouTube videos.

    Creates Obsidian-compatible markdown files with embedded frames
    and timestamped transcript segments.

    URLS can be video URLs or playlist URLs. Playlists are automatically
    expanded. If no URLs provided, checks clipboard (macOS only).

    Examples:

    \b
        ytcapture "https://www.youtube.com/watch?v=VIDEO_ID"
        ytcapture URL1 URL2 URL3
        ytcapture "https://www.youtube.com/playlist?list=PLAYLIST_ID"
    """
    # Show message if config was auto-created on this run
    if config_was_auto_created():
        console.print(f"[dim]Created config:[/] {get_config_path()}")

    # 1. Collect URLs from arguments and/or clipboard
    url_list = list(urls)
    if not url_list:
        clipboard_url = get_clipboard_url()
        if clipboard_url:
            console.print(f"[dim]Using URL from clipboard:[/] {clipboard_url}")
            url_list = [clipboard_url]
        else:
            raise click.ClickException(
                "No URLs provided. Pass YouTube URLs as arguments or copy one to clipboard."
            )

    # 2. Determine output directory (vault-relative path handling)
    vault = Path(_cfg.get("vault", ".")).expanduser()
    if output:
        # CLI --output provided: resolve relative to vault
        output_dir = resolve_output_path(output, vault)
    elif _cfg.get("output"):
        # Config output setting: resolve relative to vault
        output_dir = resolve_output_path(_cfg["output"], vault)
    else:
        # Default to vault root
        output_dir = vault
        output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[dim]Output directory:[/] {output_dir.resolve()}/")

    # 3. Classify and expand URLs
    video_urls: list[str] = []
    for url in url_list:
        if is_playlist_url(url):
            console.print(f"\n[dim]Expanding playlist:[/] {url}")
            with console.status("[bold blue]Fetching playlist...", spinner="dots"):
                try:
                    playlist_videos = expand_playlist(url)
                except VideoError as e:
                    console.print(f"[red]✗[/] Failed to expand playlist: {e}")
                    continue
            console.print(f"[green]✓[/] Found {len(playlist_videos)} videos in playlist")
            video_urls.extend(playlist_videos)
        elif is_video_url(url):
            video_urls.append(url)
        else:
            console.print(f"[yellow]⚠[/] Skipping invalid URL: {url}")

    if not video_urls:
        raise click.ClickException("No valid video URLs found.")

    # 4. Deduplicate video URLs
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in video_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    video_urls = unique_urls

    # 5. Confirm if >10 videos (unless -y/--yes)
    if len(video_urls) > 10 and not yes:
        console.print(f"\n[bold]Found {len(video_urls)} videos to process.[/]")
        if not click.confirm("Continue?", default=True):
            raise click.ClickException("Cancelled by user.")

    # 6. Process each video
    console.print(f"\n[bold]Processing {len(video_urls)} video(s)...[/]\n")

    success_count = 0
    error_count = 0

    for i, video_url in enumerate(video_urls, 1):
        console.print(f"[bold blue][{i}/{len(video_urls)}][/] {video_url}")
        try:
            md_file = process_video(
                video_url,
                output_dir,
                interval,
                max_frames,
                frame_format,
                language,
                prefer_manual,
                dedup_threshold,
                no_dedup,
                keep_video,
            )
            console.print(f"[green]✓[/] {md_file.name}\n")
            success_count += 1
        except (VideoError, FrameExtractionError) as e:
            console.print(f"[red]✗[/] Failed: {e}\n")
            error_count += 1

    # 7. Summary
    if error_count > 0:
        console.print(
            f"\n[bold yellow]Complete![/] {success_count} succeeded, {error_count} failed"
        )
    else:
        console.print(f"\n[bold green]Complete![/] {success_count} video(s) processed")


def process_local_video(
    video_path: Path,
    output_dir: Path,
    interval: int,
    max_frames: int | None,
    frame_format: str,
    dedup_threshold: float,
    no_dedup: bool,
    fast: bool = False,
    json_output: bool = False,
) -> dict | Path:
    """Process a single local video file.

    Args:
        video_path: Path to the local video file.
        output_dir: Output directory.
        interval: Frame extraction interval in seconds.
        max_frames: Maximum number of frames to extract.
        frame_format: Frame image format (jpg or png).
        dedup_threshold: Similarity threshold for frame deduplication.
        no_dedup: Disable frame deduplication.
        fast: Use fast keyframe-seeking extraction (less accurate timestamps).
        json_output: If True, return dict instead of Path and suppress console output.

    Returns:
        Path to the generated markdown file, or dict with status/metadata if json_output.

    Raises:
        LocalVideoError: If video processing fails.
        FrameExtractionError: If frame extraction fails.
    """
    # Use quiet console for JSON output
    out_console = Console(quiet=True) if json_output else console

    # 1. Get video metadata
    with out_console.status("[bold blue]Extracting video metadata...", spinner="dots"):
        metadata: LocalVideoMetadata = get_local_video_metadata(video_path)

    out_console.print("[green]✓[/] Extracted video metadata")
    out_console.print(f"  [dim]Title:[/] {metadata.title}")
    out_console.print(f"  [dim]Duration:[/] {metadata.duration:.1f}s")

    # 2. Create directory structure (with collision handling)
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / 'images' / metadata.identifier
    if frames_dir.exists():
        # Find next available suffix
        suffix = 2
        while (output_dir / 'images' / f"{metadata.file_path.stem}-{suffix}").exists():
            suffix += 1
        metadata._identifier_suffix = suffix
        frames_dir = output_dir / 'images' / metadata.identifier
        out_console.print(f"  [dim]Using identifier:[/] {metadata.identifier} (collision avoided)")
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 3. Extract frames (with integrated dedup)
    extraction_mode = "fast seek" if fast else "full decode"
    with out_console.status(f"[bold blue]Extracting frames ({extraction_mode})...", spinner="dots"):
        if fast:
            frames = extract_frames_fast(
                video_path,
                frames_dir,
                duration=metadata.duration,
                interval=interval,
                max_frames=max_frames,
                frame_format=frame_format,
                dedup_threshold=None if no_dedup else dedup_threshold,
            )
        else:
            frames = extract_frames_from_file(
                video_path,
                frames_dir,
                interval=interval,
                max_frames=max_frames,
                frame_format=frame_format,
                dedup_threshold=None if no_dedup else dedup_threshold,
            )

    dedup_msg = "" if no_dedup else " (deduplicated)"
    out_console.print(f"[green]✓[/] Extracted {len(frames)} frames{dedup_msg}")

    # 4. Generate markdown (no transcript for local videos)
    with out_console.status("[bold blue]Generating markdown...", spinner="dots"):
        md_file = generate_markdown_file(
            metadata,
            url=None,  # No source URL for local files
            transcript=None,  # No transcript support yet
            frames=frames,
            output_dir=output_dir,
            video_path=None,  # Don't embed video
        )

    out_console.print("[green]✓[/] Generated markdown")

    # 5. Format markdown (if mdformat available)
    if format_markdown(md_file):
        out_console.print("  [dim]Formatted with mdformat[/]")

    # Return dict for JSON output, or Path for normal output
    if json_output:
        return {
            "status": "success",
            "video": str(video_path.resolve()),
            "frames_dir": str(frames_dir.resolve()),
            "frame_count": len(frames),
            "markdown": str(md_file.resolve()),
        }
    return md_file


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.argument('files', nargs=-1, type=click.Path(exists=True))
@common_frame_options
@click.option(
    '--fast',
    is_flag=True,
    default=_cfg.get("fast", False),
    help='Fast extraction using keyframe seeking (recommended for long videos)',
)
@click.option(
    '--json',
    'json_output',
    is_flag=True,
    help='Output JSON instead of rich console output (for programmatic use)',
)
@click.version_option(version=__version__)
def vidcapture_main(
    files: tuple[str, ...],
    output: str | None,
    interval: int,
    max_frames: int | None,
    frame_format: str,
    dedup_threshold: float,
    no_dedup: bool,
    verbose: bool,
    fast: bool,
    json_output: bool,
) -> None:
    """Extract frames from local video files.

    Creates Obsidian-compatible markdown files with embedded frames.

    FILES are paths to local video files (mp4, mkv, webm, mov, etc.).

    Examples:

    \b
        vidcapture meeting.mp4
        vidcapture video1.mp4 video2.mkv -o notes/
        vidcapture recording.mov --interval 30 --max-frames 50
        vidcapture long-workshop.mp4 --fast --interval 60
    """
    # Use quiet console for JSON output
    out_console = Console(quiet=True) if json_output else console

    # Show message if config was auto-created on this run
    if config_was_auto_created() and not json_output:
        out_console.print(f"[dim]Created config:[/] {get_config_path()}")

    if not files:
        if json_output:
            print(json.dumps({"status": "error", "error": "No video files provided"}))
            return
        raise click.ClickException(
            "No video files provided. Pass paths to video files as arguments."
        )

    # Determine output directory (vault-relative path handling)
    vault = Path(_cfg.get("vault", ".")).expanduser()
    if output:
        # CLI --output provided: resolve relative to vault
        output_dir = resolve_output_path(output, vault)
    elif _cfg.get("output"):
        # Config output setting: resolve relative to vault
        output_dir = resolve_output_path(_cfg["output"], vault)
    else:
        # Default to vault root
        output_dir = vault
        output_dir.mkdir(parents=True, exist_ok=True)

    out_console.print(f"[dim]Output directory:[/] {output_dir.resolve()}/")

    # Process each video file
    out_console.print(f"\n[bold]Processing {len(files)} video file(s)...[/]\n")

    success_count = 0
    error_count = 0
    results: list[dict] = []

    for i, file_path in enumerate(files, 1):
        video_path = Path(file_path)
        out_console.print(f"[bold blue][{i}/{len(files)}][/] {video_path.name}")
        try:
            result = process_local_video(
                video_path,
                output_dir,
                interval,
                max_frames,
                frame_format,
                dedup_threshold,
                no_dedup,
                fast,
                json_output,
            )
            if json_output:
                results.append(result)  # type: ignore[arg-type]
            else:
                out_console.print(f"[green]✓[/] {result.name}\n")  # type: ignore[union-attr]
            success_count += 1
        except (LocalVideoError, FrameExtractionError) as e:
            if json_output:
                results.append({
                    "status": "error",
                    "video": str(video_path.resolve()),
                    "error": str(e),
                })
            else:
                out_console.print(f"[red]✗[/] Failed: {e}\n")
            error_count += 1

    # JSON output
    if json_output:
        # Single file: return single result; multiple files: return array
        if len(files) == 1:
            print(json.dumps(results[0], indent=2))
        else:
            print(json.dumps({
                "status": "success" if error_count == 0 else "partial",
                "succeeded": success_count,
                "failed": error_count,
                "results": results,
            }, indent=2))
        return

    # Summary
    if error_count > 0:
        out_console.print(
            f"\n[bold yellow]Complete![/] {success_count} succeeded, {error_count} failed"
        )
    else:
        out_console.print(f"\n[bold green]Complete![/] {success_count} video(s) processed")


def ytcapture_entry() -> None:
    """Entry point for ytcapture command.

    Handles completion subcommand before Click processing.

    Shell completion:
        ytcapture completion bash            Output completion script
        ytcapture completion bash --install  Install to user completions directory
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "completion":
        from ytcapture.completion import completion_command

        sys.exit(completion_command("ytcapture", sys.argv[2:]))
    main()


def vidcapture_entry() -> None:
    """Entry point for vidcapture command.

    Handles completion subcommand before Click processing.

    Shell completion:
        vidcapture completion bash            Output completion script
        vidcapture completion bash --install  Install to user completions directory
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "completion":
        from ytcapture.completion import completion_command

        sys.exit(completion_command("vidcapture", sys.argv[2:]))
    vidcapture_main()


if __name__ == '__main__':
    main()
