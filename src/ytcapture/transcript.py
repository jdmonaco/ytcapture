"""Transcript fetching and parsing using youtube-transcript-api."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from youtube_transcript_api import TranscriptsDisabled, YouTubeTranscriptApi


@dataclass
class TranscriptSegment:
    """A single segment of a transcript."""

    text: str
    start: float
    duration: float


class TranscriptError(Exception):
    """Exception raised for transcript-related errors."""

    pass


def get_transcript(
    video_id: str,
    language: str = 'en',
    prefer_manual: bool = True,
) -> list[TranscriptSegment] | None:
    """Fetch transcript for a YouTube video.

    Attempts to get a manual transcript first (if prefer_manual is True),
    then falls back to auto-generated transcript.

    Args:
        video_id: YouTube video ID.
        language: Language code (e.g., 'en', 'es', 'fr').
        prefer_manual: If True, prefer manual transcripts over auto-generated.

    Returns:
        List of TranscriptSegment objects, or None if no transcript available.
    """
    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = list(ytt.list(video_id))
    except TranscriptsDisabled:
        return None
    except Exception:
        return None

    if not transcript_list:
        return None

    # Separate manual and auto-generated transcripts
    manual_transcripts = [t for t in transcript_list if not t.is_generated]
    generated_transcripts = [t for t in transcript_list if t.is_generated]

    transcript = None

    # Try to find transcript in preferred language
    if prefer_manual:
        # Try manual first in preferred language
        for t in manual_transcripts:
            if t.language_code.startswith(language):
                transcript = t
                break

    # Try generated in preferred language if no manual found
    if transcript is None:
        for t in generated_transcripts:
            if t.language_code.startswith(language):
                transcript = t
                break

    # Fall back to any manual transcript
    if transcript is None and manual_transcripts:
        transcript = manual_transcripts[0]

    # Fall back to any generated transcript
    if transcript is None and generated_transcripts:
        transcript = generated_transcripts[0]

    # Fall back to first available
    if transcript is None and transcript_list:
        transcript = transcript_list[0]

    if transcript is None:
        return None

    # Fetch and parse the transcript
    try:
        raw_transcript = transcript.fetch()
        return [
            TranscriptSegment(
                text=segment.text,
                start=float(segment.start),
                duration=float(segment.duration),
            )
            for segment in raw_transcript
        ]
    except Exception:
        return None


def save_transcript_json(
    transcript: list[TranscriptSegment],
    path: Path,
) -> None:
    """Save transcript to a JSON file.

    Args:
        transcript: List of TranscriptSegment objects.
        path: Path to save the JSON file.
    """
    data = [asdict(segment) for segment in transcript]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
