"""Video metadata protocol for abstracting different video sources."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class VideoMetadataProtocol(Protocol):
    """Protocol defining required metadata fields for any video source.

    This protocol allows the markdown generation code to work with
    both YouTube videos and local video files.
    """

    @property
    def identifier(self) -> str:
        """Unique identifier for organizing output files.

        For YouTube: video_id
        For local files: filename stem (without extension)
        """
        ...

    @property
    def title(self) -> str:
        """Video title."""
        ...

    @property
    def author(self) -> str | None:
        """Author or channel name.

        Returns None for local files without author metadata.
        """
        ...

    @property
    def source_date(self) -> str:
        """Date in YYYYMMDD format.

        For YouTube: upload date
        For local files: file modification time
        """
        ...

    @property
    def description(self) -> str:
        """Video description. Empty string if not available."""
        ...

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        ...

    @property
    def source_type(self) -> str:
        """Source type identifier: 'youtube' or 'local'."""
        ...
