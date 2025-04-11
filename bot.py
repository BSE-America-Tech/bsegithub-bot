import os
import logging
import requests
import asyncio
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
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")

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

# Create application and add handlers
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("pull", pull))
application.add_handler(CommandHandler("hello", hello))

# Create event loop for async processing
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Initialize the application
loop.run_until_complete(application.initialize())

# Webhook route
@flask_app.route(f"/webhook/{SECRET_TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # Process the update asynchronously using the existing event loop
        loop.run_until_complete(application.process_update(update))
        
        return "OK"

# Vercel webhook route
@flask_app.route("/webhook/vercel", methods=["POST"])
def vercel_webhook():
    try:
        # Parse the JSON payload from Vercel
        payload = request.get_json(force=True)
        
        # Extract relevant information
        deployment_state = payload.get("state", "unknown")
        deployment_url = payload.get("url", "No URL provided")
        project_name = payload.get("projectName", "Unknown Project")
        deployment_id = payload.get("id", "Unknown ID")

        # Define the message based on the deployment state
        if deployment_state == "READY":
            message = f"🚀 Deployment Successful!\nProject: {project_name}\nURL: {deployment_url}"
        elif deployment_state == "ERROR":
            message = f"❌ Deployment Failed!\nProject: {project_name}\nDeployment ID: {deployment_id}"
        else:
            message = f"ℹ️ Deployment State: {deployment_state}\nProject: {project_name}"

        # Send the message to the Telegram group
        chat_id = TELEGRAM_GROUP_CHAT_ID
        if chat_id:
            loop.run_until_complete(application.bot.send_message(chat_id=chat_id, text=message))
        else:
            logger.error("Telegram group chat ID not set.")

        return "OK"
    
    except Exception as e:
        logger.error(f"Error processing Vercel webhook: {e}")
        return "Error", 500

if __name__ == "__main__":
    # Set the webhook using the event loop
    webhook_url = f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    loop.run_until_complete(application.bot.set_webhook(url=webhook_url))
    print(f"✅ Webhook set: {webhook_url}")

    # Run the Flask application
    flask_app.run(host="0.0.0.0", port=PORT)