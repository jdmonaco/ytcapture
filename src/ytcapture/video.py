"""Video metadata extraction using yt-dlp."""

import json
import subprocess
from dataclasses import dataclass

from ytcapture.utils import extract_video_id


@dataclass
class VideoMetadata:
    """Metadata extracted from a YouTube video."""

    video_id: str
    title: str
    channel: str
    upload_date: str
    description: str
    duration: float


class VideoError(Exception):
    """Exception raised for video-related errors."""

    pass


def get_video_metadata(url: str) -> VideoMetadata:
    """Extract metadata from a YouTube video.

    Uses yt-dlp CLI for better JS challenge handling.

    Args:
        url: YouTube video URL.

    Returns:
        VideoMetadata object with video information.

    Raises:
        VideoError: If the video is unavailable or metadata extraction fails.
    """
    cmd = [
        'yt-dlp',
        '--dump-json',
        '--skip-download',
        '--no-warnings',
        '--remote-components', 'ejs:github',
        url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            error_msg = result.stderr
            if 'Private video' in error_msg:
                raise VideoError(f"Video is private: {url}")
            if 'Video unavailable' in error_msg:
                raise VideoError(f"Video is unavailable: {url}")
            if 'Sign in' in error_msg:
                raise VideoError(f"Video requires authentication: {url}")
            raise VideoError(f"Failed to get video metadata: {error_msg}")

        info = json.loads(result.stdout)
        video_id = extract_video_id(url) or info.get('id', '')

        return VideoMetadata(
            video_id=video_id,
            title=info.get('title', 'Untitled'),
            channel=info.get('channel', info.get('uploader', 'Unknown')),
            upload_date=info.get('upload_date', ''),
            description=info.get('description', ''),
            duration=float(info.get('duration', 0)),
        )

    except subprocess.TimeoutExpired:
        raise VideoError("Metadata extraction timed out")
    except json.JSONDecodeError as e:
        raise VideoError(f"Failed to parse video metadata: {e}") from e
    except FileNotFoundError:
        raise VideoError(
            "yt-dlp not found. Please install yt-dlp:\n"
            "  pip install yt-dlp\n"
            "  or: brew install yt-dlp"
        )
    except Exception as e:
        raise VideoError(f"Unexpected error getting metadata: {e}") from e


def get_stream_url(url: str) -> str:
    """Get the direct stream URL for a YouTube video (video stream only).

    Uses yt-dlp CLI for better JS challenge handling.

    Args:
        url: YouTube video URL.

    Returns:
        Direct URL to the video stream.

    Raises:
        VideoError: If stream URL cannot be obtained.
    """
    # Format spec that ensures we get a combined video+audio stream
    # Format 18 is a reliable 360p mp4, fallback to best combined format
    format_spec = '18/22/best'

    cmd = [
        'yt-dlp',
        '--format', format_spec,
        '--get-url',
        '--no-warnings',
        '--remote-components', 'ejs:github',
        url,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise VideoError(f"Failed to get stream URL: {result.stderr}")

        stream_url = result.stdout.strip()
        if not stream_url:
            raise VideoError("No stream URL returned")

        return stream_url

    except subprocess.TimeoutExpired:
        raise VideoError("Stream URL extraction timed out")
    except FileNotFoundError:
        raise VideoError("yt-dlp not found. Please install yt-dlp.")
    except Exception as e:
        raise VideoError(f"Unexpected error getting stream URL: {e}") from e
