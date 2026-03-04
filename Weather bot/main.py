"""
================================================================
  Telegram Weather Bot - OpenWeatherMap Integration
  Library: pyTelegramBotAPI, requests, python-dotenv
================================================================
  Commands:
    /start              - Welcome message
    /help               - Show instructions
    /thoitiet [city]    - Get current weather for a city

  Example: /thoitiet Hanoi
================================================================
"""

import os
import requests
import telebot
from dotenv import load_dotenv

# ================================================================
#  STEP 1: LOAD ENVIRONMENT VARIABLES
# ================================================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env file!")
if not OPENWEATHER_API_KEY:
    raise ValueError("Missing OPENWEATHER_API_KEY in .env file!")

# ================================================================
#  STEP 2: INITIALIZE BOT
# ================================================================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# OpenWeatherMap API endpoint (free tier)
OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


# ================================================================
#  STEP 3: WEATHER CONDITION → EMOJI MAPPING
#  OpenWeatherMap returns a "main" weather group (e.g. "Rain", "Clear")
#  We map each group to an emoji for a better user experience
# ================================================================
WEATHER_EMOJI = {
    "Thunderstorm": "⛈️",
    "Drizzle": "🌦️",
    "Rain": "🌧️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Smoke": "🌫️",
    "Haze": "🌫️",
    "Dust": "💨",
    "Fog": "🌫️",
    "Sand": "💨",
    "Ash": "🌋",
    "Squall": "💨",
    "Tornado": "🌪️",
    "Clear": "☀️",
    "Clouds": "☁️",
}


# ================================================================
#  STEP 4: FUNCTION TO FETCH WEATHER DATA
# ================================================================
def get_weather(city: str) -> dict | None:
    """
    Call OpenWeatherMap API to get current weather for a city.

    Args:
        city: City name (e.g. "Hanoi", "Ho Chi Minh City")

    Returns:
        Parsed weather dict on success, None if city not found.
        Raises requests.RequestException on network errors.
    """
    params = {
        "q": city,  # city name (supports English city names)
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",  # use Celsius; "imperial" for Fahrenheit
        "lang": "en",  # response language
    }

    # Make HTTP GET request to OpenWeatherMap
    response = requests.get(OWM_URL, params=params, timeout=10)

    # HTTP 404 = city not found
    if response.status_code == 404:
        return None

    # Raise exception for other HTTP errors (401, 500, etc.)
    response.raise_for_status()

    # Parse JSON response
    data = response.json()

    # Extract only the fields we need from the response
    return {
        "city": data["name"],
        "country": data["sys"]["country"],
        "temp": data["main"]["temp"],  # °C
        "feels_like": data["main"]["feels_like"],  # °C
        "humidity": data["main"]["humidity"],  # %
        "description": data["weather"][0]["description"].capitalize(),
        "main": data["weather"][0]["main"],  # e.g. "Rain", "Clear"
        "wind_speed": data["wind"]["speed"],  # m/s
    }


# ================================================================
#  /start COMMAND
# ================================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name
    welcome = (
        f"👋 Hello, *{name}*!\n\n"
        "🌤️ I'm your *Weather Bot*!\n"
        "I can fetch real-time weather for any city in the world.\n\n"
        "Type /help to see how to use me."
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


# ================================================================
#  /help COMMAND
# ================================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *Available Commands:*\n\n"
        "▶ /start              — Start the bot\n"
        "▶ /help               — Show this message\n"
        "▶ /thoitiet [city]    — Get current weather\n\n"
        "📌 *Examples:*\n"
        "`/thoitiet Hanoi`\n"
        "`/thoitiet Ho Chi Minh City`\n"
        "`/thoitiet Tokyo`\n"
        "`/thoitiet London`\n\n"
        "🌍 Supports cities worldwide!"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


# ================================================================
#  /thoitiet COMMAND — Main weather lookup feature
# ================================================================
@bot.message_handler(commands=["thoitiet"])
def handle_weather(message):
    # Split command to get city name
    # message.text example: "/thoitiet Hanoi" or "/thoitiet Ho Chi Minh City"
    parts = message.text.split(maxsplit=1)

    # Check if user provided a city name
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            "⚠️ Please provide a city name!\n\n"
            "Usage: `/thoitiet [city]`\n"
            "Example: `/thoitiet Hanoi`",
            parse_mode="Markdown",
        )
        return

    city = parts[1].strip()  # extract city name from command

    # Send a "searching..." message while fetching data
    searching_msg = bot.reply_to(
        message, f"🔍 Looking up weather for *{city}*...", parse_mode="Markdown"
    )

    try:
        weather = get_weather(city)

        # City not found (HTTP 404)
        if weather is None:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=searching_msg.message_id,
                text=(
                    f"❌ *City not found:* `{city}`\n\n"
                    "Please check the spelling and try again.\n"
                    "Tip: Use English city names (e.g. `Hanoi`, `Da Nang`)"
                ),
                parse_mode="Markdown",
            )
            return

        # Get matching emoji for this weather condition
        emoji = WEATHER_EMOJI.get(weather["main"], "🌡️")

        # Build the weather report message
        report = (
            f"{emoji} *Weather in {weather['city']}, {weather['country']}*\n"
            f"{'─' * 30}\n"
            f"🌡️  Temperature:  *{weather['temp']:.1f}°C*\n"
            f"🤔  Feels like:   *{weather['feels_like']:.1f}°C*\n"
            f"💧  Humidity:     *{weather['humidity']}%*\n"
            f"💨  Wind speed:   *{weather['wind_speed']} m/s*\n"
            f"{'─' * 30}\n"
            f"📋  Condition:    *{weather['description']}*"
        )

        # Replace "searching..." with the actual weather report
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=searching_msg.message_id,
            text=report,
            parse_mode="Markdown",
        )

    except requests.exceptions.ConnectionError:
        # No internet connection
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=searching_msg.message_id,
            text="🔌 *Connection error.* Please check your internet and try again.",
            parse_mode="Markdown",
        )

    except requests.exceptions.Timeout:
        # API took too long to respond
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=searching_msg.message_id,
            text="⏱️ *Request timed out.* The weather service is slow. Please try again.",
            parse_mode="Markdown",
        )

    except Exception as err:
        # Any other unexpected error
        print(f"[ERROR] Weather API: {err}")
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=searching_msg.message_id,
            text="⚠️ *An unexpected error occurred.* Please try again later.",
            parse_mode="Markdown",
        )


# ================================================================
#  HANDLE PLAIN TEXT (not a command)
# ================================================================
@bot.message_handler(content_types=["text"], func=lambda m: not m.text.startswith("/"))
def handle_text(message):
    bot.reply_to(
        message,
        "💡 To check the weather, use:\n`/thoitiet [city name]`\n\nExample: `/thoitiet Hanoi`",
        parse_mode="Markdown",
    )


# ================================================================
#  MAIN LOOP
# ================================================================
if __name__ == "__main__":
    print("🌤️  Weather Bot is starting...")
    print("✅  Bot is running! Press Ctrl+C to stop.\n")
    bot.infinity_polling(none_stop=True, interval=0)
