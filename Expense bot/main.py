"""
================================================================
  Telegram Expense Tracker Bot - Google Sheets Integration
  Libraries: pyTelegramBotAPI, gspread, google-auth, python-dotenv
================================================================
  How it works:
    User sends: "50k cà phê" or "150000 đổ xăng"
    Bot parses: amount=50000, reason="cà phê", date=now
    Bot writes a new row to Google Sheets
    Bot replies: "✅ Saved: 50,000đ for cà phê"

  Message format accepted:
    [amount] [reason]
    - Amount can be: 50k / 50K / 50,000 / 50000
    - Reason is any text after the amount

  Google Sheets columns: Date | Reason | Amount (VND)
================================================================
"""

import os
import re
from datetime import datetime

import gspread
import telebot
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# ================================================================
#  STEP 1: LOAD ENVIRONMENT VARIABLES
#  SCRIPT_DIR must be computed FIRST so we can load .env from
#  the script's own folder, regardless of where the bot is launched.
# ================================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from the Expense bot folder, not from the working directory
load_dotenv(dotenv_path=os.path.join(SCRIPT_DIR, ".env"))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")  # from Sheet URL
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")

# Resolve credentials path relative to the script folder if it's not absolute
if not os.path.isabs(GOOGLE_CREDS_FILE):
    GOOGLE_CREDS_FILE = os.path.join(SCRIPT_DIR, GOOGLE_CREDS_FILE)


if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env!")
if not GOOGLE_SHEET_ID:
    raise ValueError("Missing GOOGLE_SHEET_ID in .env!")

# ================================================================
#  STEP 2: INITIALIZE BOT AND GOOGLE SHEETS CLIENT
# ================================================================
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Google Sheets API requires these permission scopes
SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet():
    """
    Authenticate with Google Sheets API using service account credentials.
    Returns the first worksheet of the configured spreadsheet.

    Raises FileNotFoundError if credentials.json is missing.
    Raises gspread.exceptions.SpreadsheetNotFound if sheet ID is wrong.
    """
    if not os.path.exists(GOOGLE_CREDS_FILE):
        raise FileNotFoundError(
            f"Credentials file not found: {GOOGLE_CREDS_FILE}\n"
            "Please follow setup instructions to create credentials.json"
        )

    # Load service account credentials from JSON file
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=SCOPES)

    # Authorize gspread client with credentials
    client = gspread.authorize(creds)

    # Open spreadsheet by ID and return the first sheet (tab)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return spreadsheet.sheet1  # first tab


# ================================================================
#  STEP 3: MESSAGE PARSER
#  Parse user input like "50k cà phê" or "150,000 đổ xăng"
# ================================================================

# Regex pattern to match amount at the start of the message:
#   \d+[,.]?\d*  - matches: 50000, 50,000, 50.000
#   [kK]?        - optionally followed by 'k' or 'K' (for thousands)
AMOUNT_PATTERN = re.compile(r"^(\d+[,.]?\d*)\s*([kK]?)\s+(.+)$")


def parse_expense(text: str) -> tuple[int, str] | None:
    """
    Parse an expense message into (amount_in_vnd, reason).

    Examples:
        "50k cà phê"       → (50000, "cà phê")
        "50K ăn trưa"      → (50000, "ăn trưa")
        "150000 đổ xăng"   → (150000, "đổ xăng")
        "150,000 tiền nhà" → (150000, "tiền nhà")
        "2.5k nước"        → (2500, "nước")

    Returns None if the message doesn't match the expected format.
    """
    text = text.strip()
    match = AMOUNT_PATTERN.match(text)

    if not match:
        return None

    amount_str, k_suffix, reason = match.groups()

    # Clean the amount string: remove commas and dots used as thousand separators
    amount_str = amount_str.replace(",", "").replace(".", "")
    amount = int(amount_str)

    # If user wrote 'k' or 'K', multiply by 1000 (e.g. 50k → 50000)
    if k_suffix.lower() == "k":
        amount *= 1000

    return amount, reason.strip()


def write_to_sheet(date: str, reason: str, amount: int) -> bool:
    """
    Append a new expense row to Google Sheets.
    Returns True on success, False on failure.
    """
    import traceback

    try:
        sheet = get_sheet()
        sheet.append_row([date, reason, amount])
        return True
    except FileNotFoundError as e:
        print(f"[ERROR] credentials.json not found:\n{e}")
        return False
    except Exception as e:
        # Use traceback for full error detail (gspread errors often have empty str())
        print("[ERROR] Google Sheets write failed!")
        print(f"  Type   : {type(e).__name__}")
        print(f"  Message: {e!r}")
        print(f"  Detail :\n{traceback.format_exc()}")
        return False


# ================================================================
#  STEP 4: BOT COMMAND HANDLERS
# ================================================================


@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name
    welcome = (
        f"👋 Hello, *{name}*!\n\n"
        "💰 I'm your *Expense Tracker Bot*.\n"
        "I'll record your spending directly to Google Sheets!\n\n"
        "Type /help to see how to use me."
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *How to log an expense:*\n\n"
        "Just send a message in this format:\n"
        "`[amount] [reason]`\n\n"
        "📌 *Examples:*\n"
        "`50k cà phê`\n"
        "`150000 đổ xăng`\n"
        "`200,000 tiền điện`\n"
        "`30K ăn trưa`\n\n"
        "📊 *Supported amount formats:*\n"
        "• `50k` or `50K` → 50,000đ\n"
        "• `50000` → 50,000đ\n"
        "• `50,000` → 50,000đ\n\n"
        "📒 Data is saved to your Google Sheets automatically!"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


# ================================================================
#  HANDLE EXPENSE MESSAGES — Core feature
# ================================================================
@bot.message_handler(content_types=["text"], func=lambda m: not m.text.startswith("/"))
def handle_expense(message):
    text = message.text.strip()

    # Step 1: Try to parse the message
    result = parse_expense(text)

    # Step 2: If parsing failed → guide the user
    if result is None:
        bot.reply_to(
            message,
            "⚠️ *Could not understand that format.*\n\n"
            "Please use: `[amount] [reason]`\n\n"
            "Examples:\n"
            "• `50k cà phê`\n"
            "• `150000 đổ xăng`\n"
            "• `200,000 ăn tối`",
            parse_mode="Markdown",
        )
        return

    amount, reason = result

    # Step 3: Get current timestamp for the Date column
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Step 4: Send "saving..." message while writing to Sheets
    saving_msg = bot.reply_to(message, "💾 Saving to Google Sheets...")

    # Step 5: Write row to Google Sheets
    success = write_to_sheet(date=now, reason=reason, amount=amount)

    # Step 6: Respond with result
    if success:
        # Format amount with thousand separator: 50000 → "50,000"
        formatted_amount = f"{amount:,}"

        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=saving_msg.message_id,
            text=(
                f"✅ *Saved successfully!*\n\n"
                f"📅 Date:    `{now}`\n"
                f"📝 Reason:  `{reason}`\n"
                f"💵 Amount:  `{formatted_amount}đ`\n\n"
                f"_Check your Google Sheet to see the new entry._"
            ),
            parse_mode="Markdown",
        )
    else:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=saving_msg.message_id,
            text=(
                "❌ *Failed to save to Google Sheets.*\n\n"
                "Possible reasons:\n"
                "• `credentials.json` file is missing\n"
                "• Sheet was not shared with the service account\n"
                "• Network error\n\n"
                "_Check the terminal for error details._"
            ),
            parse_mode="Markdown",
        )


# ================================================================
#  MAIN LOOP
# ================================================================
if __name__ == "__main__":
    print("💰 Expense Tracker Bot is starting...")
    print(f"   Sheet ID:     {GOOGLE_SHEET_ID}")
    print(f"   Credentials:  {GOOGLE_CREDS_FILE}")
    print("✅ Bot is running! Press Ctrl+C to stop.\n")

    bot.infinity_polling(
        none_stop=True, interval=0, timeout=20, long_polling_timeout=20
    )
