"""
================================================================
  Telegram AI Chatbot - Dual Provider: Gemini + Groq
  Libraries: pyTelegramBotAPI, google-generativeai, groq, python-dotenv
================================================================
  AI Call Strategy:
    1. Try Gemini first (if GEMINI_API_KEY is set)
    2. If Gemini fails/quota exceeded → auto fallback to Groq
    3. If both fail → notify user with error message
================================================================
"""

import os
import time
import re
import telebot
import google.generativeai as genai
from groq import Groq
from dotenv import load_dotenv

# ================================================================
#  STEP 1: LOAD ENVIRONMENT VARIABLES
# ================================================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Optional
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Optional

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env file!")
if not GEMINI_API_KEY and not GROQ_API_KEY:
    raise ValueError("At least one of GEMINI_API_KEY or GROQ_API_KEY is required!")


# ================================================================
#  STEP 2: INITIALIZE BOT AND AI CLIENTS
# ================================================================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# --- Gemini setup (if key is provided) ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # Models to try in order of priority
    GEMINI_MODELS = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.0-pro"]
else:
    GEMINI_MODELS = []
    print("[INFO] No GEMINI_API_KEY found → using Groq only")

# --- Groq setup (if key is provided) ---
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if not groq_client:
    print("[INFO] No GROQ_API_KEY found → using Gemini only")

# Groq default model (free and fast)
GROQ_MODEL = "llama-3.3-70b-versatile"

# System prompt shared by both providers
SYSTEM_PROMPT = (
    "You are a friendly, smart, and helpful AI assistant. "
    "Answer clearly and concisely. "
    "If you don't know the answer, be honest and say so."
)


# ================================================================
#  STEP 3A: CALL GEMINI (with auto-retry on rate limit)
# ================================================================
def call_gemini(question: str) -> str:
    """Try Gemini models in order, retry if temporarily rate-limited."""
    if not GEMINI_MODELS:
        raise RuntimeError("No GEMINI_API_KEY configured")

    prompt = f"{SYSTEM_PROMPT}\n\nUser: {question}"

    for model_name in GEMINI_MODELS:
        model = genai.GenerativeModel(model_name)
        attempts = 0

        while attempts <= 1:  # max 2 attempts per model
            try:
                print(f"[Gemini] Trying model: {model_name}")
                response = model.generate_content(prompt)
                return f"[Gemini/{model_name}]\n\n{response.text}"

            except Exception as err:
                err_str = str(err)
                # Temporary rate limit → wait and retry same model
                if "429" in err_str and "retry" in err_str.lower():
                    wait = 15
                    match = re.search(r"seconds:\s*(\d+)", err_str)
                    if match:
                        wait = int(match.group(1)) + 2
                    attempts += 1
                    if attempts <= 1:
                        print(f"[Gemini] Rate limited. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                # Quota exhausted or other error → try next model
                print(f"[Gemini] {model_name} failed: {err_str[:80]}")
                break

    raise RuntimeError("All Gemini models are unavailable")


# ================================================================
#  STEP 3B: CALL GROQ
# ================================================================
def call_groq(question: str) -> str:
    """Call Groq API using LLaMA model. Fast and free."""
    if not groq_client:
        raise RuntimeError("No GROQ_API_KEY configured")

    print(f"[Groq] Using model: {GROQ_MODEL}")

    # Groq uses OpenAI-compatible message format
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.7,  # 0 = deterministic, 1 = creative
        max_tokens=1024,  # max response length
    )

    return f"[Groq/{GROQ_MODEL}]\n\n{response.choices[0].message.content}"


# ================================================================
#  STEP 3C: ORCHESTRATOR — Try Gemini first, fallback to Groq
# ================================================================
def call_ai(question: str) -> str:
    """
    Routes the question: tries Gemini first, falls back to Groq.
    Raises RuntimeError if both providers fail.
    """
    if GEMINI_MODELS:
        try:
            return call_gemini(question)
        except RuntimeError:
            print("[INFO] Gemini unavailable → switching to Groq...")

    if groq_client:
        return call_groq(question)

    raise RuntimeError("No AI provider is available!")


# ================================================================
#  /start COMMAND
# ================================================================
@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name

    providers = []
    if GEMINI_MODELS:
        providers.append("Gemini ✨")
    if groq_client:
        providers.append("Groq ⚡")
    provider_list = " + ".join(providers)

    welcome = (
        f"👋 Hello, *{name}*!\n\n"
        f"🤖 I'm your AI assistant powered by: *{provider_list}*\n"
        "Ask me anything and I'll do my best to help!\n\n"
        "Type /help to see available commands."
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


# ================================================================
#  /help COMMAND
# ================================================================
@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *Available Commands:*\n\n"
        "▶ /start  — Start the bot and get a greeting\n"
        "▶ /help   — Show this help message\n"
        "▶ /status — Check AI provider status\n\n"
        "💬 *How to use:*\n"
        "Just type any question!\n"
        'Example: _"What is machine learning?"_\n\n'
        "⚡ Powered by Gemini + Groq AI"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


# ================================================================
#  /status COMMAND — Check which AI providers are active
# ================================================================
@bot.message_handler(commands=["status"])
def handle_status(message):
    gemini_status = "✅ Ready" if GEMINI_MODELS else "❌ No API key"
    groq_status = "✅ Ready" if groq_client else "❌ No API key"

    status = (
        "🔍 *AI Provider Status:*\n\n"
        f"◈ *Gemini* (Google): {gemini_status}\n"
        f"◈ *Groq* (LLaMA):    {groq_status}\n\n"
        "_Gemini is tried first. Groq serves as backup._"
    )
    bot.reply_to(message, status, parse_mode="Markdown")


# ================================================================
#  HANDLE REGULAR TEXT MESSAGES — Call AI
# ================================================================
@bot.message_handler(content_types=["text"], func=lambda m: not m.text.startswith("/"))
def handle_ai_message(message):
    question = message.text

    # Send "processing" message immediately so user knows bot is working
    processing_msg = bot.reply_to(message, "⏳ Processing, please wait...")

    try:
        # Call AI (Gemini first, Groq as fallback)
        answer = call_ai(question)

        # Delete "processing" message and send the real answer
        bot.delete_message(message.chat.id, processing_msg.message_id)
        bot.reply_to(message, answer)

    except Exception as err:
        print(f"[FATAL ERROR] {err}")
        # Edit "processing" message to show error
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=processing_msg.message_id,
            text=(
                "⚠️ *Unable to reach AI at the moment.*\n\n"
                "Possible reasons:\n"
                "• All provider quotas are exhausted\n"
                "• Network or API is temporarily down\n\n"
                "💡 _Use /status to check provider availability._\n"
                "Please try again later!"
            ),
            parse_mode="Markdown",
        )


# ================================================================
#  MAIN LOOP
# ================================================================
if __name__ == "__main__":
    print("🚀 Telegram AI Bot (Gemini + Groq) starting...")
    print(f"   Gemini: {'✅ ' + str(GEMINI_MODELS) if GEMINI_MODELS else '❌ No key'}")
    print(f"   Groq:   {'✅ ' + GROQ_MODEL if groq_client else '❌ No key'}")
    print("📩 Bot is ready! Press Ctrl+C to stop.\n")

    bot.infinity_polling(none_stop=True, interval=0)
