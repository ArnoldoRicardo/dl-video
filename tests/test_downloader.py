from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

import src.downloader as downloader


def test_download_video_success(monkeypatch, tmp_path):
    output_file = tmp_path / "video.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            output_file.write_bytes(b"ok")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)

    result = downloader.download_video("https://x.com/i/status/123", str(output_file))

    assert result == str(output_file)
    assert output_file.exists()


def test_download_video_raises_when_file_missing(monkeypatch, tmp_path):
    output_file = tmp_path / "video.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            return None

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)

    with pytest.raises(DownloadError):
        downloader.download_video("https://x.com/i/status/123", str(output_file))


def test_download_video_propagates_download_error(monkeypatch, tmp_path):
    output_file = tmp_path / "video.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            raise DownloadError("boom")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)

    with pytest.raises(DownloadError):
        downloader.download_video("https://x.com/i/status/123", str(output_file))


def test_download_video_raises_file_too_large_and_deletes_file(monkeypatch, tmp_path):
    output_file = tmp_path / "video.mp4"

    class FakeYDL:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            output_file.write_bytes(b"small")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(downloader.os.path, "getsize", lambda _path: downloader.MAX_FILE_SIZE + 1)

    with pytest.raises(downloader.FileTooLargeError):
        downloader.download_video("https://x.com/i/status/123", str(output_file))

    assert not output_file.exists()


def test_download_video_passes_expected_ydl_options(monkeypatch, tmp_path):
    output_file = tmp_path / "video.mp4"
    captured_opts = {}

    class FakeYDL:
        def __init__(self, opts):
            captured_opts.update(opts)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, _urls):
            Path(output_file).write_bytes(b"ok")

    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYDL)

    downloader.download_video("https://x.com/i/status/456", str(output_file))

    assert captured_opts["outtmpl"] == str(output_file)
    assert captured_opts["merge_output_format"] == "mp4"
    assert captured_opts["quiet"] is True
    assert captured_opts["no_warnings"] is True
    assert "bestvideo" in captured_opts["format"]
