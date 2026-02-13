# dl-video - Twitter/X Video Downloader Bot

Telegram bot that downloads videos from Twitter/X and sends them directly to users. Features a freemium model with Telegram Stars payments.

## Features

- Download videos from Twitter/X by pasting a tweet link
- Free tier: 3 downloads per day
- Premium tier: unlimited downloads (250 Stars/month)
- Payments via Telegram Stars (native, no external payment provider needed)
- Lightweight SQLite database (no external DB server required)
- Auto-cleanup of downloaded files after sending
- Concurrent download management (global + per-user limits)

## Requirements

- Python 3.11+
- ffmpeg (for video processing)

## Setup

1. Clone this repository:
```bash
git clone <repo-url>
cd dl-video
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file (see `.env.example`):
```bash
cp .env.example .env
# Edit .env with your Telegram bot token
```

4. Run the bot:
```bash
python main.py
```

## Docker

```bash
docker-compose up --build
```

The SQLite database is persisted in `./data/bot.db` via a Docker volume.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and get a welcome message |
| `/help` | Show available commands |
| `/status` | Check your plan, downloads remaining, subscription expiry |
| `/subscribe` | Purchase premium with Telegram Stars |

To download a video, just paste a Twitter/X link in the chat.

## Configuration

All configuration is done via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKEN` | - | Telegram bot token (required) |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/bot.db` | Database connection string |
| `FREE_DAILY_LIMIT` | `3` | Max downloads/day for free users |
| `PREMIUM_PRICE_STARS` | `250` | Price in Telegram Stars for premium |
| `PREMIUM_DURATION_DAYS` | `30` | Duration of premium subscription |
| `MAX_CONCURRENT_DOWNLOADS` | `5` | Global max concurrent downloads |

## Project Structure

```
dl-video/
├── main.py              # Bot entry point
├── src/
│   ├── config.py        # Settings (env vars)
│   ├── models.py        # SQLAlchemy ORM models
│   ├── db.py            # Database operations
│   ├── handlers.py      # Telegram command/message handlers
│   └── downloader.py    # yt-dlp video download wrapper
├── data/                # SQLite database (gitignored)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Tech Stack

- **python-telegram-bot** 22.6 (async, Stars support)
- **yt-dlp** (video downloading)
- **SQLAlchemy** 2.0 + aiosqlite (async SQLite)
- **Pydantic** (settings management)
- **Docker** (deployment)

## License

MIT
