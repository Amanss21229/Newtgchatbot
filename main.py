#!/usr/bin/env python3
"""
Telegram Anonymous Chatbot - Main Entry Point (Render + Auto Cleanup)
"""

import os
import sys
import asyncio
import traceback
from dotenv import load_dotenv
from telegram.error import Forbidden
from telegram.ext import Application, ContextTypes

# Flask trick for Render web service (uptime ke liye)
from flask import Flask
import threading

# -----------------------------
# Flask server for uptime
# -----------------------------
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is running fine ✅"


def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))


# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

required_vars = ['BOT_TOKEN']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(
        f"Error: Missing required environment variables: {', '.join(missing_vars)}"
    )
    sys.exit(1)

# -----------------------------
# Import project modules
# -----------------------------
try:
    from bot import TelegramBot
    from database import Database

    print("Starting Telegram Anonymous Chatbot...")
    print("Bot username: @BoyGirlChatBot")

    print("Initializing database...")
    db = Database()
    print("Database connected successfully!")

    # -----------------------------
    # Error Handler (Block → Auto Cleanup)
    # -----------------------------
    async def error_handler(update: object,
                            context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            raise context.error
        except Forbidden:
            if update and hasattr(update,
                                  "effective_user") and update.effective_user:
                user_id = update.effective_user.id
                try:
                    db.delete_user(user_id)  # custom method in database.py
                    print(f"User {user_id} blocked the bot → Data removed ✅")
                except Exception as e:
                    print(f"Error cleaning user {user_id}: {e}")
        except Exception as e:
            print(f"Unhandled error: {e}")

    # -----------------------------
    # Start bot
    # -----------------------------
    print("Starting bot...")
    bot = TelegramBot()
    application = bot.application  # TelegramBot class se Application instance lo
    application.add_error_handler(error_handler)

    # Flask server ko alag thread me run karo
    threading.Thread(target=run_flask).start()

    bot.run()

except Exception as e:
    print(f"Error starting bot: {e}")
    traceback.print_exc()
    sys.exit(1)