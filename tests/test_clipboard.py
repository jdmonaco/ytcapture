"""Tests for clipboard URL extraction and confirmation."""

from unittest.mock import MagicMock, patch

import pytest

from ytcapture.utils import extract_youtube_urls


class TestExtractYoutubeUrls:
    """Tests for extract_youtube_urls()."""

    def test_plain_urls(self):
        text = (
            "https://www.youtube.com/watch?v=abc123\n"
            "https://youtu.be/def456\n"
        )
        result = extract_youtube_urls(text)
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    def test_markdown_links(self):
        text = (
            "[Video Title](https://www.youtube.com/watch?v=abc123)\n"
            "[Another](https://youtu.be/def456)\n"
        )
        result = extract_youtube_urls(text)
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    def test_csv_format(self):
        text = (
            "Title,URL\n"
            "My Video,https://www.youtube.com/watch?v=abc123\n"
            "Other,https://youtu.be/def456\n"
        )
        result = extract_youtube_urls(text)
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    def test_mixed_text(self):
        text = (
            "Check out this video: https://www.youtube.com/watch?v=abc123 and also\n"
            "this one [here](https://youtu.be/def456) for more info.\n"
        )
        result = extract_youtube_urls(text)
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    def test_deduplication(self):
        text = (
            "https://www.youtube.com/watch?v=abc123\n"
            "https://www.youtube.com/watch?v=abc123\n"
            "https://youtu.be/def456\n"
        )
        result = extract_youtube_urls(text)
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    def test_no_urls(self):
        assert extract_youtube_urls("no urls here") == []
        assert extract_youtube_urls("") == []

    def test_playlist_urls(self):
        text = "https://www.youtube.com/playlist?list=PLabc123"
        result = extract_youtube_urls(text)
        assert result == ["https://www.youtube.com/playlist?list=PLabc123"]

    def test_urls_with_tracking_params(self):
        text = "https://www.youtube.com/watch?v=abc123&t=120&si=xyz"
        result = extract_youtube_urls(text)
        assert len(result) == 1
        assert "abc123" in result[0]

    def test_non_youtube_urls_ignored(self):
        text = (
            "https://vimeo.com/12345\n"
            "https://www.youtube.com/watch?v=abc123\n"
            "https://example.com/video\n"
        )
        result = extract_youtube_urls(text)
        assert result == ["https://www.youtube.com/watch?v=abc123"]

    def test_embed_url(self):
        text = "https://www.youtube.com/embed/abc123"
        result = extract_youtube_urls(text)
        assert result == ["https://www.youtube.com/embed/abc123"]

    def test_mobile_url(self):
        text = "https://m.youtube.com/watch?v=abc123"
        result = extract_youtube_urls(text)
        assert result == ["https://m.youtube.com/watch?v=abc123"]

    def test_url_in_angle_brackets(self):
        text = "<https://www.youtube.com/watch?v=abc123>"
        result = extract_youtube_urls(text)
        assert result == ["https://www.youtube.com/watch?v=abc123"]

    def test_single_url_no_newline(self):
        text = "https://www.youtube.com/watch?v=abc123"
        result = extract_youtube_urls(text)
        assert result == ["https://www.youtube.com/watch?v=abc123"]


class TestGetClipboardUrls:
    """Tests for get_clipboard_urls()."""

    @patch("ytcapture.cli.platform.system", return_value="Darwin")
    @patch("ytcapture.cli.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("ytcapture.cli.subprocess.run")
    def test_multi_url_clipboard(self, mock_run, mock_which, mock_system):
        from ytcapture.cli import get_clipboard_urls

        mock_run.return_value = MagicMock(
            stdout=(
                "https://www.youtube.com/watch?v=abc123\n"
                "https://youtu.be/def456\n"
            ),
        )
        result = get_clipboard_urls()
        assert result == [
            "https://www.youtube.com/watch?v=abc123",
            "https://youtu.be/def456",
        ]

    @patch("ytcapture.cli.platform.system", return_value="Darwin")
    @patch("ytcapture.cli.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("ytcapture.cli.subprocess.run")
    def test_empty_clipboard(self, mock_run, mock_which, mock_system):
        from ytcapture.cli import get_clipboard_urls

        mock_run.return_value = MagicMock(stdout="")
        result = get_clipboard_urls()
        assert result == []

    @patch("ytcapture.cli.platform.system", return_value="Darwin")
    @patch("ytcapture.cli.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("ytcapture.cli.subprocess.run")
    def test_no_youtube_urls(self, mock_run, mock_which, mock_system):
        from ytcapture.cli import get_clipboard_urls

        mock_run.return_value = MagicMock(stdout="just some text")
        result = get_clipboard_urls()
        assert result == []

    @patch("ytcapture.cli.platform.system", return_value="Linux")
    def test_non_macos(self, mock_system):
        from ytcapture.cli import get_clipboard_urls

        result = get_clipboard_urls()
        assert result == []

    @patch("ytcapture.cli.platform.system", return_value="Darwin")
    @patch("ytcapture.cli.shutil.which", return_value=None)
    def test_no_pbpaste(self, mock_which, mock_system):
        from ytcapture.cli import get_clipboard_urls

        result = get_clipboard_urls()
        assert result == []

    @patch("ytcapture.cli.platform.system", return_value="Darwin")
    @patch("ytcapture.cli.shutil.which", return_value="/usr/bin/pbpaste")
    @patch("ytcapture.cli.subprocess.run", side_effect=Exception("timeout"))
    def test_subprocess_error(self, mock_run, mock_which, mock_system):
        from ytcapture.cli import get_clipboard_urls

        result = get_clipboard_urls()
        assert result == []


class TestConfirmClipboardUrls:
    """Tests for confirm_clipboard_urls()."""

    @patch("ytcapture.cli.click.confirm", return_value=True)
    @patch("ytcapture.cli.get_video_metadata")
    def test_confirm_accepted(self, mock_metadata, mock_confirm):
        from rich.console import Console

        from ytcapture.cli import confirm_clipboard_urls
        from ytcapture.video import VideoMetadata

        mock_metadata.return_value = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            channel="Test Channel",
            upload_date="20240101",
            description="Test",
            duration=120.0,
        )
        con = Console(quiet=True)
        result = confirm_clipboard_urls(
            ["https://www.youtube.com/watch?v=abc123"], con
        )
        assert result is True
        mock_confirm.assert_called_once_with("Proceed with capture?", default=True)

    @patch("ytcapture.cli.click.confirm", return_value=False)
    @patch("ytcapture.cli.get_video_metadata")
    def test_confirm_rejected(self, mock_metadata, mock_confirm):
        from rich.console import Console

        from ytcapture.cli import confirm_clipboard_urls
        from ytcapture.video import VideoMetadata

        mock_metadata.return_value = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            channel="Test Channel",
            upload_date="20240101",
            description="Test",
            duration=120.0,
        )
        con = Console(quiet=True)
        result = confirm_clipboard_urls(
            ["https://www.youtube.com/watch?v=abc123"], con
        )
        assert result is False

    @patch("ytcapture.cli.click.confirm", return_value=True)
    @patch("ytcapture.cli.get_video_metadata")
    def test_metadata_unavailable(self, mock_metadata, mock_confirm):
        from rich.console import Console

        from ytcapture.cli import confirm_clipboard_urls
        from ytcapture.video import VideoError

        mock_metadata.side_effect = VideoError("not found")
        con = Console(quiet=True)
        result = confirm_clipboard_urls(
            ["https://www.youtube.com/watch?v=abc123"], con
        )
        assert result is True

    @patch("ytcapture.cli.click.confirm", return_value=True)
    @patch("ytcapture.cli.get_video_metadata")
    def test_multiple_urls(self, mock_metadata, mock_confirm):
        from rich.console import Console

        from ytcapture.cli import confirm_clipboard_urls
        from ytcapture.video import VideoMetadata

        mock_metadata.return_value = VideoMetadata(
            video_id="abc123",
            title="Test Video",
            channel="Test Channel",
            upload_date="20240101",
            description="Test",
            duration=60.0,
        )
        con = Console(quiet=True)
        urls = [
            "https://www.youtube.com/watch?v=abc123",
            "https://www.youtube.com/watch?v=def456",
            "https://www.youtube.com/watch?v=ghi789",
        ]
        result = confirm_clipboard_urls(urls, con)
        assert result is True
        assert mock_metadata.call_count == 3
