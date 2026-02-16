import logging
import os

import yt_dlp
from yt_dlp.utils import DownloadError

logger = logging.getLogger(__name__)

# Telegram bot API limit for file uploads
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

DEFAULT_OPTS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'quiet': True,
    'no_warnings': True,
    # TODO: Workaround temporal para yt-dlp issue #15963 — Twitter GraphQL API
    # devuelve "Dependency: Unspecified". Revertir cuando yt-dlp publique fix.
    # https://github.com/yt-dlp/yt-dlp/issues/15963
    'extractor_args': {'twitter': {'api': ['syndication']}},
}


class FileTooLargeError(Exception):
    """Raised when the downloaded file exceeds the Telegram size limit."""

    def __init__(self, file_size: int, max_size: int = MAX_FILE_SIZE):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(
            f"File size {file_size / 1024 / 1024:.1f}MB exceeds "
            f"limit of {max_size / 1024 / 1024:.0f}MB"
        )


def download_video(url: str, output_filename: str) -> str:
    """Download a video from a supported URL using yt-dlp.

    Args:
        url: The URL of the tweet/post containing the video.
        output_filename: Path where the video file will be saved.

    Returns:
        The path to the downloaded file.

    Raises:
        DownloadError: If the video cannot be downloaded.
        FileTooLargeError: If the downloaded file exceeds MAX_FILE_SIZE.
    """
    opts = {
        **DEFAULT_OPTS,
        'outtmpl': output_filename,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        logger.info(f"Downloading video from: {url}")
        ydl.download([url])

    if not os.path.exists(output_filename):
        raise DownloadError(f"Download completed but file not found: {output_filename}")

    file_size = os.path.getsize(output_filename)
    logger.info(f"Downloaded {output_filename} ({file_size / 1024 / 1024:.1f} MB)")

    if file_size > MAX_FILE_SIZE:
        os.remove(output_filename)
        raise FileTooLargeError(file_size)

    return output_filename
