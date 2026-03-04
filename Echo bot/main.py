"""
==========================================================
  Simple Telegram Chatbot
  Library: pyTelegramBotAPI (telebot)
==========================================================
"""

import os
import telebot
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env file!")

bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
#  /start COMMAND
# ============================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name
    welcome = (
        f"👋 Hello, {name}! Nice to meet you!\n\n"
        "🤖 I'm a simple chatbot built with Python.\n\n"
        "Type /help to see what I can do! 😊"
    )
    bot.reply_to(message, welcome)


# ============================================================
#  /help COMMAND
# ============================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *Available Commands:*\n\n"
        "▶ /start — Start the bot and get a greeting\n"
        "▶ /help  — Show this help message\n\n"
        "💬 *Echo Feature:*\n"
        "Send any text message and I'll repeat it back to you! 😄\n\n"
        "_Built with Python & pyTelegramBotAPI_"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


# ============================================================
#  ECHO FEATURE — Repeat any text message
# ============================================================
@bot.message_handler(content_types=["text"], func=lambda m: not m.text.startswith("/"))
def handle_echo(message):
    text = message.text
    reply = f'🔁 You said: "{text}"'
    bot.reply_to(message, reply)


# ============================================================
#  MAIN LOOP
# ============================================================
if __name__ == "__main__":
    print("🚀 Echo Bot is starting...")
    print("✅ Bot is running! Press Ctrl+C to stop.\n")
    bot.infinity_polling(none_stop=True, interval=0)
