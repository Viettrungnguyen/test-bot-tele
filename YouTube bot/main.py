"""
================================================================
  Telegram YouTube MP3 Downloader Bot
  Libraries: pyTelegramBotAPI, yt-dlp, python-dotenv
================================================================
  Workflow:
    1. User sends a YouTube URL
    2. Bot replies "Downloading audio, please wait..."
    3. Bot downloads MP3 using yt-dlp
    4. Bot checks file size (Telegram limit: 50 MB)
    5. Bot sends the MP3 file back to the user
    6. Bot deletes the local temp file to save disk space

  Supported URLs: youtube.com/watch, youtu.be short links
================================================================
"""

import os
import re
import uuid
import tempfile

import telebot
import yt_dlp
from dotenv import load_dotenv

# ================================================================
#  STEP 1: LOAD ENVIRONMENT VARIABLES
# ================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(SCRIPT_DIR, ".env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env file!")

# ================================================================
#  STEP 2: INITIALIZE BOT
# ================================================================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Telegram's maximum file upload size is 50 MB
TELEGRAM_MAX_BYTES = 50 * 1024 * 1024  # 50 MB in bytes

# Temp folder to store downloaded files before sending
TEMP_DIR = os.path.join(SCRIPT_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)  # create temp/ folder if not exists

# Regex to detect YouTube URLs (supports youtube.com and youtu.be)
YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/(watch\?.*v=|shorts/)|youtu\.be/)"
    r"[\w\-]+"
)


# ================================================================
#  STEP 3: CORE FUNCTION — Download YouTube audio as MP3
# ================================================================
def download_audio(url: str) -> dict:
    """
    Download the audio from a YouTube URL and convert to MP3.

    Args:
        url: YouTube video URL

    Returns:
        dict with keys:
            success  (bool)
            filepath (str)  — path to downloaded MP3, if success
            title    (str)  — video title, if success
            duration (int)  — duration in seconds, if success
            error    (str)  — error message, if not success
    """
    # Unique filename to avoid conflicts when multiple users download at once
    unique_id = uuid.uuid4().hex[:8]
    output_template = os.path.join(TEMP_DIR, f"{unique_id}_%(title)s.%(ext)s")

    # yt-dlp options
    ydl_opts = {
        "format": "bestaudio/best",  # pick best audio quality
        "outtmpl": output_template,  # output filename template
        "quiet": True,  # suppress console output
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",  # extract audio track
                "preferredcodec": "mp3",  # convert to MP3
                "preferredquality": "192",  # 192 kbps quality
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first (without downloading) to get title & duration
            info = ydl.extract_info(url, download=True)

            title = info.get("title", "Unknown Title")
            duration = info.get("duration", 0)

            # Find the downloaded .mp3 file in TEMP_DIR with our unique_id prefix
            mp3_file = None
            for fname in os.listdir(TEMP_DIR):
                if fname.startswith(unique_id) and fname.endswith(".mp3"):
                    mp3_file = os.path.join(TEMP_DIR, fname)
                    break

            if not mp3_file or not os.path.exists(mp3_file):
                return {"success": False, "error": "Downloaded file not found."}

            return {
                "success": True,
                "filepath": mp3_file,
                "title": title,
                "duration": duration,
            }

    except yt_dlp.utils.DownloadError as e:
        # Handles: private video, age-restricted, unavailable, bad URL
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}


def format_duration(seconds: int) -> str:
    """Convert seconds to mm:ss or hh:mm:ss string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ================================================================
#  /start COMMAND
# ================================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name
    welcome = (
        f"👋 Hello, *{name}*!\n\n"
        "🎵 I'm your *YouTube MP3 Downloader Bot*.\n"
        "Send me any YouTube link and I'll send back the audio!\n\n"
        "Type /help for instructions."
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


# ================================================================
#  /help COMMAND
# ================================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *How to use:*\n\n"
        "Just send a YouTube link and I'll download the audio as MP3.\n\n"
        "📌 *Supported formats:*\n"
        "• `https://www.youtube.com/watch?v=...`\n"
        "• `https://youtu.be/...`\n"
        "• `https://youtube.com/shorts/...`\n\n"
        "⚠️ *Limitations:*\n"
        "• Max file size: 50 MB (Telegram API limit)\n"
        "• Private or age-restricted videos are not supported\n\n"
        "🎵 *Audio quality:* 192 kbps MP3"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


# ================================================================
#  HANDLE ALL TEXT — Detect YouTube URL or guide user
# ================================================================
@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text.strip()

    # Skip commands (handled above)
    if text.startswith("/"):
        return

    # Check if the message contains a YouTube URL
    if not YOUTUBE_URL_PATTERN.search(text):
        bot.reply_to(
            message,
            "🔗 Please send a valid *YouTube URL*.\n\n"
            "Example: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`\n\n"
            "Type /help for more info.",
            parse_mode="Markdown",
        )
        return

    # Extract the URL from the message (user might send extra text)
    url_match = YOUTUBE_URL_PATTERN.search(text)
    url = url_match.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    # Step 1: Tell user we're working on it
    wait_msg = bot.reply_to(
        message,
        "⏳ *Downloading audio, please wait...*\n"
        "_This may take a few seconds depending on video length._",
        parse_mode="Markdown",
    )

    mp3_path = None  # track file path for cleanup in finally block

    try:
        # Step 2: Download the audio
        result = download_audio(url)

        if not result["success"]:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wait_msg.message_id,
                text=(
                    "❌ *Download failed.*\n\n"
                    f"`{result['error']}`\n\n"
                    "Possible reasons:\n"
                    "• Video is private or age-restricted\n"
                    "• URL is invalid or video was removed\n"
                    "• Geographic restriction"
                ),
                parse_mode="Markdown",
            )
            return

        mp3_path = result["filepath"]
        title = result["title"]
        duration = result["duration"]
        filesize = os.path.getsize(mp3_path)

        # Step 3: Check file size against Telegram's 50 MB limit
        if filesize > TELEGRAM_MAX_BYTES:
            size_mb = filesize / (1024 * 1024)
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=wait_msg.message_id,
                text=(
                    f"⚠️ *File too large!*\n\n"
                    f"Downloaded: *{size_mb:.1f} MB*\n"
                    f"Telegram limit: *50 MB*\n\n"
                    "Please try a shorter video."
                ),
                parse_mode="Markdown",
            )
            return

        # Step 4: Delete the "please wait" message, then send the audio file
        bot.delete_message(message.chat.id, wait_msg.message_id)

        size_mb = filesize / (1024 * 1024)

        with open(mp3_path, "rb") as audio_file:
            # send_audio displays the file with a music player UI in Telegram
            bot.send_audio(
                chat_id=message.chat.id,
                audio=audio_file,
                title=title,
                duration=duration,
                caption=(
                    f"🎵 *{title}*\n"
                    f"⏱ {format_duration(duration)}  |  💾 {size_mb:.1f} MB"
                ),
                parse_mode="Markdown",
                reply_to_message_id=message.message_id,
            )

    except Exception as err:
        print(f"[ERROR] {err}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=wait_msg.message_id,
            text="⚠️ *An unexpected error occurred.* Please try again later.",
            parse_mode="Markdown",
        )

    finally:
        # Step 5: Always delete the temp MP3 file to free disk space
        if mp3_path and os.path.exists(mp3_path):
            os.remove(mp3_path)
            print(f"[INFO] Deleted temp file: {os.path.basename(mp3_path)}")


# ================================================================
#  MAIN LOOP
# ================================================================
if __name__ == "__main__":
    print("🎵 YouTube MP3 Downloader Bot is starting...")
    print(f"   Temp folder: {TEMP_DIR}")
    print("✅ Bot is running! Send a YouTube link to test. Press Ctrl+C to stop.\n")

    bot.infinity_polling(
        none_stop=True, interval=0, timeout=20, long_polling_timeout=20
    )
