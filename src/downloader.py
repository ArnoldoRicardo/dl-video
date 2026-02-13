import logging
import os

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

logger = logging.getLogger(__name__)

# Telegram bot API limit for file uploads
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

DEFAULT_OPTS = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'quiet': True,
    'no_warnings': True,
    'max_filesize': MAX_FILE_SIZE,
}


def download_video(url: str, output_filename: str) -> str:
    """Download a video from a supported URL using yt-dlp.

    Args:
        url: The URL of the tweet/post containing the video.
        output_filename: Path where the video file will be saved.

    Returns:
        The path to the downloaded file.

    Raises:
        DownloadError: If the video cannot be downloaded.
        ExtractorError: If the video metadata cannot be extracted.
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

    return output_filename


def get_video_info(url: str) -> dict | None:
    """Extract video metadata without downloading.

    Args:
        url: The URL of the tweet/post containing the video.

    Returns:
        A dict with video info or None if extraction fails.
    """
    opts = {
        **DEFAULT_OPTS,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except (DownloadError, ExtractorError) as e:
        logger.error(f"Failed to extract video info: {e}")
        return None
