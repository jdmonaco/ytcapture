"""Utility functions for ytcapture."""

import re
from urllib.parse import parse_qs, urlparse

from dateutil import parser as date_parser


def sanitize_title(title: str, max_length: int = 100) -> str:
    """Sanitize a title for use as a filename.

    Removes invalid filename characters and truncates to max_length.
    Preserves original casing (important for acronyms, etc.).

    Args:
        title: The original title string.
        max_length: Maximum length of the output string.

    Returns:
        A sanitized string safe for filenames.
    """
    # Remove invalid filename characters: < > : " / \ | ? *
    sanitized = re.sub(r'[<>:"/\\|?*]', ' ', title)

    # Collapse multiple spaces into one
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length].rsplit(' ', 1)[0]

    return sanitized


def truncate_title_words(title: str, max_words: int = 6) -> str:
    """Truncate title to first N words.

    Args:
        title: The title string.
        max_words: Maximum number of words to keep.

    Returns:
        Title truncated to max_words, or original if fewer words.
    """
    words = title.split()
    if len(words) <= max_words:
        return title
    return ' '.join(words[:max_words])


def format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS format.

    Args:
        seconds: Time in seconds (can be float).

    Returns:
        Formatted string in HH:MM:SS format.
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_date(date_str: str | None) -> str:
    """Parse a date string and return YYYY-MM-DD format.

    Args:
        date_str: A date string in various formats (e.g., "20241215", ISO 8601).

    Returns:
        Date formatted as YYYY-MM-DD, or empty string if parsing fails.
    """
    if not date_str:
        return ""

    try:
        # Handle yt-dlp format: YYYYMMDD
        if re.match(r'^\d{8}$', date_str):
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # Parse other formats using dateutil
        parsed = date_parser.parse(date_str)
        return parsed.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats.

    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID

    Args:
        url: A YouTube URL.

    Returns:
        The video ID string, or None if extraction fails.
    """
    parsed = urlparse(url)

    # youtu.be/VIDEO_ID
    if parsed.netloc in ('youtu.be', 'www.youtu.be'):
        return parsed.path.lstrip('/')

    # youtube.com formats
    if parsed.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        # /watch?v=VIDEO_ID
        if parsed.path == '/watch':
            query = parse_qs(parsed.query)
            if 'v' in query:
                return query['v'][0]

        # /embed/VIDEO_ID or /v/VIDEO_ID
        if parsed.path.startswith(('/embed/', '/v/')):
            parts = parsed.path.split('/')
            if len(parts) >= 3:
                return parts[2]

    return None


def extract_playlist_id(url: str) -> str | None:
    """Extract YouTube playlist ID from various URL formats.

    Supports:
    - https://www.youtube.com/playlist?list=PLAYLIST_ID
    - https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID
    - https://youtu.be/VIDEO_ID?list=PLAYLIST_ID

    Args:
        url: A YouTube URL.

    Returns:
        The playlist ID string, or None if not a playlist URL.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if 'list' in query:
        return query['list'][0]
    return None


def is_video_url(url: str) -> bool:
    """Check if URL is a YouTube video URL.

    Args:
        url: A URL to check.

    Returns:
        True if the URL contains a valid YouTube video ID.
    """
    return extract_video_id(url) is not None


def is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist URL (without a video ID).

    Only returns True for pure playlist URLs like /playlist?list=X.
    URLs with both video ID and playlist (e.g., watch?v=X&list=Y) return False.

    Args:
        url: A URL to check.

    Returns:
        True if the URL is a pure playlist URL.
    """
    # If it has a video ID, treat it as a video URL, not a playlist
    if extract_video_id(url) is not None:
        return False
    return extract_playlist_id(url) is not None
