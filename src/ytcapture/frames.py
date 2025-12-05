"""Frame extraction from local video files using ffmpeg."""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image


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


def compute_phash(image_path: Path) -> imagehash.ImageHash:
    """Compute perceptual hash for an image.

    Args:
        image_path: Path to the image file.

    Returns:
        Perceptual hash of the image.
    """
    with Image.open(image_path) as img:
        return imagehash.phash(img)


def hash_similarity(hash1: imagehash.ImageHash, hash2: imagehash.ImageHash) -> float:
    """Compute similarity between two perceptual hashes.

    Args:
        hash1: First image hash.
        hash2: Second image hash.

    Returns:
        Similarity score between 0.0 (different) and 1.0 (identical).
    """
    distance = hash1 - hash2
    return 1.0 - (distance / 64.0)


def extract_frames_from_file(
    video_path: Path,
    output_dir: Path,
    interval: int = 15,
    max_frames: int | None = None,
    frame_format: str = 'jpg',
    dedup_threshold: float | None = 0.85,
) -> list[FrameInfo]:
    """Extract frames from a local video file with integrated deduplication.

    Extracts frames to a temp directory first, then iterates through them
    applying perceptual hash deduplication before moving to the final location.

    Args:
        video_path: Path to the local video file.
        output_dir: Directory to save extracted frames.
        interval: Interval between frames in seconds.
        max_frames: Maximum number of frames to extract.
        frame_format: Output format ('jpg' or 'png').
        dedup_threshold: Similarity threshold for deduplication (0.0-1.0).
            Frames with similarity above this value are removed.
            Set to None to disable deduplication.

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

    if not video_path.exists():
        raise FrameExtractionError(f"Video file not found: {video_path}")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create temp directory for initial extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        temp_pattern = temp_path / f'frame-%04d.{frame_format}'

        # Build ffmpeg command
        cmd = ['ffmpeg', '-y', '-i', str(video_path)]

        # Build video filter
        vf_parts = [f'fps=1/{interval}']

        if max_frames and dedup_threshold is None:
            # Only apply max_frames in ffmpeg if dedup is disabled
            # Otherwise we need to extract more to account for duplicates
            vf_parts.append(f"select='lt(n,{max_frames})'")

        if vf_parts:
            cmd.extend(['-vf', ','.join(vf_parts)])

        # Output settings
        cmd.extend([
            '-vsync', 'vfr',
            '-frame_pts', '1',
            str(temp_pattern),
        ])

        # Run ffmpeg
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                raise FrameExtractionError(
                    f"ffmpeg failed with code {result.returncode}:\n{result.stderr}"
                )

        except subprocess.TimeoutExpired:
            raise FrameExtractionError("Frame extraction timed out (10 minutes)")
        except FileNotFoundError:
            raise FrameExtractionError("ffmpeg not found")
        except FrameExtractionError:
            raise
        except Exception as e:
            raise FrameExtractionError(f"Frame extraction failed: {e}") from e

        # Collect temp frames
        temp_frames = sorted(temp_path.glob(f'frame-*.{frame_format}'))

        if not temp_frames:
            raise FrameExtractionError("No frames were extracted from video")

        # Process frames with deduplication
        frames: list[FrameInfo] = []
        prev_hash: imagehash.ImageHash | None = None
        frame_index = 0

        for i, temp_frame in enumerate(temp_frames):
            # Calculate timestamp
            timestamp = float(i * interval)

            # Check max_frames limit
            if max_frames and len(frames) >= max_frames:
                break

            # Compute hash if dedup is enabled
            if dedup_threshold is not None:
                try:
                    current_hash = compute_phash(temp_frame)
                except Exception:
                    # Can't compute hash, keep the frame anyway
                    current_hash = None

                if current_hash is not None and prev_hash is not None:
                    similarity = hash_similarity(prev_hash, current_hash)
                    if similarity >= dedup_threshold:
                        # Too similar, skip this frame
                        continue

                prev_hash = current_hash

            # Move frame to final location with sequential numbering
            final_name = f'frame-{frame_index:04d}.{frame_format}'
            final_path = output_dir / final_name
            shutil.move(str(temp_frame), str(final_path))

            frames.append(FrameInfo(path=final_path, timestamp=timestamp))
            frame_index += 1

    return frames
