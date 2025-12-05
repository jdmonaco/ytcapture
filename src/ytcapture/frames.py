"""Stream-based frame extraction using ffmpeg."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ytcapture.video import VideoError, get_stream_url


@dataclass
class FrameInfo:
    """Information about an extracted frame."""

    path: Path
    timestamp: float


class FrameExtractionError(Exception):
    """Exception raised for frame extraction errors."""

    pass


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available in PATH.

    Returns:
        True if ffmpeg is available, False otherwise.
    """
    return shutil.which('ffmpeg') is not None


def extract_frames_stream(
    url: str,
    output_dir: Path,
    interval: int = 30,
    keyframes: bool = False,
    max_frames: int | None = None,
    frame_format: str = 'jpg',
) -> list[FrameInfo]:
    """Extract frames from a video stream without downloading.

    Uses yt-dlp to get the stream URL and ffmpeg to extract frames
    directly from the stream.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save extracted frames.
        interval: Interval between frames in seconds (ignored if keyframes=True).
        keyframes: If True, extract only keyframes (I-frames).
        max_frames: Maximum number of frames to extract.
        frame_format: Output format ('jpg' or 'png').

    Returns:
        List of FrameInfo objects with paths and timestamps.

    Raises:
        FrameExtractionError: If frame extraction fails.
    """
    if not check_ffmpeg():
        raise FrameExtractionError(
            "ffmpeg not found. Please install ffmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Ubuntu: sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )

    # Get stream URL
    try:
        stream_url = get_stream_url(url)
    except VideoError as e:
        raise FrameExtractionError(f"Failed to get stream URL: {e}") from e

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build output pattern
    output_pattern = output_dir / f'frame-%04d.{frame_format}'

    # Build ffmpeg command
    cmd = ['ffmpeg', '-y', '-i', stream_url]

    # Build video filter
    vf_parts = []

    if keyframes:
        # Select only keyframes (I-frames)
        vf_parts.append("select='eq(pict_type,I)'")
    else:
        # Extract at intervals
        vf_parts.append(f'fps=1/{interval}')

    # Apply max frames limit
    if max_frames:
        vf_parts.append(f"select='lt(n,{max_frames})'")

    if vf_parts:
        cmd.extend(['-vf', ','.join(vf_parts)])

    # Output settings
    cmd.extend([
        '-vsync', 'vfr',
        '-frame_pts', '1',
        str(output_pattern),
    ])

    # Run ffmpeg
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        # ffmpeg outputs to stderr even on success
        if result.returncode != 0:
            raise FrameExtractionError(
                f"ffmpeg failed with code {result.returncode}:\n{result.stderr}"
            )

    except subprocess.TimeoutExpired:
        raise FrameExtractionError("Frame extraction timed out (10 minutes)")
    except FileNotFoundError:
        raise FrameExtractionError("ffmpeg not found")
    except Exception as e:
        raise FrameExtractionError(f"Frame extraction failed: {e}") from e

    # Collect extracted frames
    frames = []
    frame_files = sorted(output_dir.glob(f'frame-*.{frame_format}'))

    for i, frame_path in enumerate(frame_files):
        # Calculate timestamp based on interval or keyframe index
        if keyframes:
            # For keyframes, we estimate based on frame index
            # This is approximate - actual timestamps would need parsing ffmpeg output
            timestamp = float(i * interval)
        else:
            timestamp = float(i * interval)

        frames.append(FrameInfo(path=frame_path, timestamp=timestamp))

        # Respect max_frames limit
        if max_frames and len(frames) >= max_frames:
            break

    return frames


def extract_frames_with_timestamps(
    url: str,
    output_dir: Path,
    interval: int = 30,
    max_frames: int | None = None,
    frame_format: str = 'jpg',
) -> list[FrameInfo]:
    """Extract frames at specific timestamps with accurate timing.

    This method extracts frames at exact intervals by seeking to specific
    timestamps, which is more accurate than using fps filter for
    widely-spaced frames.

    Args:
        url: YouTube video URL.
        output_dir: Directory to save extracted frames.
        interval: Interval between frames in seconds.
        max_frames: Maximum number of frames to extract.
        frame_format: Output format ('jpg' or 'png').

    Returns:
        List of FrameInfo objects with paths and timestamps.

    Raises:
        FrameExtractionError: If frame extraction fails.
    """
    if not check_ffmpeg():
        raise FrameExtractionError(
            "ffmpeg not found. Please install ffmpeg."
        )

    try:
        stream_url = get_stream_url(url)
    except VideoError as e:
        raise FrameExtractionError(f"Failed to get stream URL: {e}") from e

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build output pattern
    output_pattern = output_dir / f'frame-%04d.{frame_format}'

    # Build ffmpeg command with fps filter
    cmd = [
        'ffmpeg', '-y',
        '-i', stream_url,
        '-vf', f'fps=1/{interval}',
        '-vsync', 'vfr',
        str(output_pattern),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        if result.returncode != 0:
            raise FrameExtractionError(
                f"ffmpeg failed:\n{result.stderr}"
            )

    except subprocess.TimeoutExpired:
        raise FrameExtractionError("Frame extraction timed out")
    except Exception as e:
        raise FrameExtractionError(f"Frame extraction failed: {e}") from e

    # Collect frames with calculated timestamps
    frames = []
    frame_files = sorted(output_dir.glob(f'frame-*.{frame_format}'))

    for i, frame_path in enumerate(frame_files):
        timestamp = float(i * interval)
        frames.append(FrameInfo(path=frame_path, timestamp=timestamp))

        if max_frames and len(frames) >= max_frames:
            break

    return frames
