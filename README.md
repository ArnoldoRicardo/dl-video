# Twitter Video Downloader Bot
## Description
This project is a Telegram bot that allows users to download videos from Twitter. The bot is built using Python and the Telegram library.

https://github.com/inteoryx/twitter-video-dl

## Requirements
Python 3.x
Telegram Library
twitter_video_dl Library
Setup
Clone this repository.

Install the dependencies using pip:

```
pip install -r requirements.txt
```
Configure the environment variables in config/settings.py.

```
TOKEN = "your_telegram_token"
```
## Usage
Run the bot:

```
python main.py
```
Send the /start command to initiate the bot.

Use the /help command for usage instructions.

Paste the tweet link to download the video.

### Available Commands
/start: Initiates the bot and displays your user ID.
/help: Displays a help message.

## Functions
start(update, context): Handles the /start command.
help_command(update, context): Handles the /help command.
download_video(update, context): Downloads a video from Twitter.

## Contributing
If you have any ideas or improvements, feel free to make a Pull Request or open an Issue.

## License
This project is under the MIT License.
