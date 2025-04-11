import os
import logging
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from dotenv import load_dotenv
load_dotenv()

# Env vars
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 8443))
SECRET_TOKEN = os.getenv("SECRET_TOKEN")

# GitHub headers
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json'
}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhook
flask_app = Flask(__name__)

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! The bot is up and running.")

async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a PR number or branch name.")
        return

    pr_ref = context.args[0]
    pr_url = f'https://api.github.com/repos/{GITHUB_REPO}/pulls/{pr_ref}'
    pr_resp = requests.get(pr_url, headers=headers)

    if pr_resp.status_code != 200:
        await update.message.reply_text(f"❌ PR #{pr_ref} not found.")
        return

    merge_url = f'https://api.github.com/repos/{GITHUB_REPO}/pulls/{pr_ref}/merge'
    merge_resp = requests.put(merge_url, headers=headers, json={"commit_title": f"Merge PR #{pr_ref}"})

    if merge_resp.status_code == 200:
        await update.message.reply_text(f"✅ PR #{pr_ref} has been merged!")
    else:
        await update.message.reply_text(f"❌ Failed to merge PR #{pr_ref}. Error: {merge_resp.json().get('message')}")

# Main bot setup
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("pull", pull))
application.add_handler(CommandHandler("hello", hello))


# Webhook route
@flask_app.route(f"/webhook/{SECRET_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK"

if __name__ == "__main__":
    # Set Telegram webhook
    application.bot.set_webhook(
        url=f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    )

    # Run Flask server
    flask_app.run(host="0.0.0.0", port=PORT)
