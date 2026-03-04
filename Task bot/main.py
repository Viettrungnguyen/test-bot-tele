"""
================================================================
  Telegram Task Manager Bot
  Library: pyTelegramBotAPI, python-dotenv
  Storage: SQLite (built-in, no extra install needed)
================================================================
  Commands:
    /start          — Welcome message
    /help           — Show instructions
    /add [task]     — Add a new task
    /list           — Show all pending tasks
    /done [number]  — Mark task as done and remove it

  Data is stored in tasks.db (SQLite).
  Tasks persist across bot restarts.
  Each user has their own separate task list.
================================================================
"""

import os
import sqlite3
import telebot
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

# SQLite database file path (stored next to main.py)
DB_PATH = os.path.join(os.path.dirname(__file__), "tasks.db")


# ================================================================
#  STEP 3: DATABASE FUNCTIONS
#  These functions handle all reading/writing to SQLite.
#  SQLite is built into Python — no extra library needed!
# ================================================================


def db_init():
    """
    Create the tasks table if it doesn't exist yet.
    Called once at startup.

    Table structure:
        id        — Auto-incrementing primary key
        user_id   — Telegram user ID (each user has their own tasks)
        task      — The task description text
        created   — Timestamp when task was added
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task    TEXT    NOT NULL,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()  # save changes
    conn.close()  # always close the connection when done


def db_add_task(user_id: int, task_text: str):
    """
    Insert a new task for the given user into the database.

    Args:
        user_id:   Telegram user ID
        task_text: The task description
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, task) VALUES (?, ?)",
        (user_id, task_text),  # use ? placeholders to prevent SQL injection
    )
    conn.commit()
    conn.close()


def db_get_tasks(user_id: int) -> list[tuple]:
    """
    Retrieve all tasks for the given user, ordered by creation time.

    Returns:
        List of (id, task_text) tuples
        Example: [(1, "Buy groceries"), (2, "Call dentist")]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, task FROM tasks WHERE user_id = ? ORDER BY created ASC",
        (user_id,),  # note: single-element tuple needs trailing comma
    )
    rows = cursor.fetchall()  # get all matching rows
    conn.close()
    return rows


def db_delete_task(task_id: int, user_id: int) -> bool:
    """
    Delete a specific task by its database ID.
    user_id check ensures users can only delete their own tasks.

    Returns:
        True if a task was deleted, False if not found.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    deleted = cursor.rowcount > 0  # rowcount = number of rows affected
    conn.commit()
    conn.close()
    return deleted


# ================================================================
#  STEP 4: BOT COMMAND HANDLERS
# ================================================================


@bot.message_handler(commands=["start"])
def handle_start(message):
    name = message.from_user.first_name
    welcome = (
        f"👋 Hello, *{name}*!\n\n"
        "📝 I'm your *Personal Task Manager Bot*.\n"
        "I'll help you keep track of your to-do list!\n\n"
        "Type /help to see all available commands."
    )
    bot.reply_to(message, welcome, parse_mode="Markdown")


@bot.message_handler(commands=["help"])
def handle_help(message):
    guide = (
        "📋 *Available Commands:*\n\n"
        "▶ `/add [task]`    — Add a new task\n"
        "▶ `/list`          — Show all your tasks\n"
        "▶ `/done [number]` — Mark a task as done\n\n"
        "📌 *Examples:*\n"
        "`/add Buy groceries`\n"
        "`/add Call dentist at 3pm`\n"
        "`/list`\n"
        "`/done 1`"
    )
    bot.reply_to(message, guide, parse_mode="Markdown")


@bot.message_handler(commands=["add"])
def handle_add(message):
    """Add a new task to the user's list."""
    user_id = message.from_user.id

    # Split to get task text after "/add"
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            "⚠️ Please provide a task description!\n\n"
            "Usage: `/add [task]`\n"
            "Example: `/add Buy groceries`",
            parse_mode="Markdown",
        )
        return

    task_text = parts[1].strip()

    # Save task to database
    db_add_task(user_id, task_text)

    # Count total tasks for this user after adding
    total = len(db_get_tasks(user_id))

    bot.reply_to(
        message,
        f"✅ Task added!\n\n"
        f"📝 *{task_text}*\n\n"
        f"You now have *{total}* task(s). Use /list to see all.",
        parse_mode="Markdown",
    )


@bot.message_handler(commands=["list"])
def handle_list(message):
    """Show all tasks for the current user."""
    user_id = message.from_user.id
    tasks = db_get_tasks(user_id)  # returns list of (id, task_text)

    if not tasks:
        bot.reply_to(
            message,
            "🎉 *Your task list is empty!*\n\n"
            "Use `/add [task]` to add your first task.",
            parse_mode="Markdown",
        )
        return

    # Build the numbered task list
    # We use enumerate to create position numbers (1, 2, 3...)
    # The actual DB id is stored separately for /done command
    lines = ["📋 *Your Task List:*\n"]
    for position, (db_id, task_text) in enumerate(tasks, start=1):
        lines.append(f"{position}. {task_text}")

    lines.append(f"\nTotal: *{len(tasks)}* task(s)")
    lines.append("Use `/done [number]` to complete a task.")

    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=["done"])
def handle_done(message):
    """Mark a task as done by its position number in the list."""
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)

    # Check if user provided a number
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            "⚠️ Please provide a task number!\n\n"
            "Usage: `/done [number]`\n"
            "Example: `/done 1`\n\n"
            "Use /list to see task numbers.",
            parse_mode="Markdown",
        )
        return

    # Validate that input is actually a number
    try:
        position = int(parts[1].strip())
    except ValueError:
        bot.reply_to(
            message,
            "❌ Please enter a *valid number*.\nExample: `/done 1`",
            parse_mode="Markdown",
        )
        return

    # Get current tasks to find which DB id corresponds to that position
    tasks = db_get_tasks(user_id)

    if not tasks:
        bot.reply_to(message, "📭 Your task list is already empty!")
        return

    # Check if position is within valid range
    if position < 1 or position > len(tasks):
        bot.reply_to(
            message,
            f"❌ Invalid task number *{position}*.\n\n"
            f"You have *{len(tasks)}* task(s). Use a number between 1 and {len(tasks)}.",
            parse_mode="Markdown",
        )
        return

    # Convert position (1-based) to list index (0-based) and get DB id
    db_id, task_text = tasks[position - 1]

    # Delete from database using actual DB id
    db_delete_task(db_id, user_id)

    remaining = len(tasks) - 1  # tasks count after deletion

    bot.reply_to(
        message,
        f"🎉 *Task completed!*\n\n~~{task_text}~~\n\n*{remaining}* task(s) remaining.",
        parse_mode="Markdown",
    )


# ================================================================
#  HANDLE PLAIN TEXT
# ================================================================
@bot.message_handler(content_types=["text"], func=lambda m: not m.text.startswith("/"))
def handle_text(message):
    bot.reply_to(
        message,
        "💡 Use these commands:\n"
        "`/add [task]` — Add a task\n"
        "`/list`       — View all tasks\n"
        "`/done [num]` — Complete a task",
        parse_mode="Markdown",
    )


# ================================================================
#  MAIN — Initialize DB then start bot
# ================================================================
if __name__ == "__main__":
    # Create the SQLite table if it doesn't exist yet
    db_init()
    print("🗄️  Database initialized: tasks.db")
    print("📝  Task Manager Bot is starting...")
    print("✅  Bot is running! Press Ctrl+C to stop.\n")

    bot.infinity_polling(
        none_stop=True, interval=0, timeout=20, long_polling_timeout=20
    )
