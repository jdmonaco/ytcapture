"""Frame deduplication using perceptual hashing."""

from pathlib import Path

import imagehash
from PIL import Image

from ytcapture.frames import FrameInfo


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
    # Hamming distance: 0 = identical, 64 = completely different (for 8x8 hash)
    distance = hash1 - hash2
    return 1.0 - (distance / 64.0)


def deduplicate_frames(
    frames: list[FrameInfo],
    threshold: float = 0.90,
    delete_files: bool = True,
) -> list[FrameInfo]:
    """Remove consecutive frames that are too similar.

    Compares each frame to the previous kept frame using perceptual hashing.
    Frames with similarity above the threshold are considered duplicates
    and removed.

    Args:
        frames: List of FrameInfo objects (should be sorted by timestamp).
        threshold: Similarity threshold (0.0-1.0). Frames with similarity
            above this value are removed. Default 0.90 (90% similar).
        delete_files: If True, delete the image files of duplicate frames.

    Returns:
        Filtered list of FrameInfo with duplicates removed.
    """
    if not frames:
        return []

    if len(frames) == 1:
        return frames

    kept: list[FrameInfo] = []
    prev_hash: imagehash.ImageHash | None = None

    for frame in frames:
        # Compute hash for current frame
        try:
            current_hash = compute_phash(frame.path)
        except Exception:
            # If we can't read the image, keep it anyway
            kept.append(frame)
            prev_hash = None
            continue

        # First frame is always kept
        if prev_hash is None:
            kept.append(frame)
            prev_hash = current_hash
            continue

        # Compare to previous kept frame
        similarity = hash_similarity(prev_hash, current_hash)

        if similarity < threshold:
            # Different enough - keep this frame
            kept.append(frame)
            prev_hash = current_hash
        elif delete_files:
            # Too similar - delete the file
            try:
                frame.path.unlink()
            except Exception:
                pass  # Ignore deletion errors

    return kept
