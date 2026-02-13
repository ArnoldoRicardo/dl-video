import re

from src.downloader import download_video

url = "https://x.com/iRazasdePerros/status/1721331013974937873?s=20"
pattern = r'https:\/\/(twitter|x)\.com\/\w+\/status\/(\d+)'
match = re.match(pattern, url)
if match:
    plataform, tweet_id = match.groups()
    filename = f"video_{tweet_id}.mp4"
    try:
        download_video(url, filename)
        print(f"Video descargado: {filename}")
    except Exception as e:
        print(f"Error: {e}")
        raise e
