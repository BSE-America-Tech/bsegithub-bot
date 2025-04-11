import os
import logging
import requests
import asyncio
import json
from flask import Flask, request, jsonify
from telegram import Update, Bot
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
CHAT_ID = os.getenv("CHAT_ID")  # Chat ID where deployment notifications will be sent

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
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"👋 Hello! The bot is up and running. Your chat ID is: {chat_id}")

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

# Function to send deployment notification
async def send_deployment_notification(deployment_data):
    """Send notification about Vercel deployment status to the configured chat"""
    bot = Bot(token=TELEGRAM_TOKEN)
    
    # Extract relevant information from the deployment data
    deployment_id = deployment_data.get('id', 'Unknown')
    project_name = deployment_data.get('name', 'Unknown project')
    url = deployment_data.get('url', '')
    state = deployment_data.get('state', 'unknown')
    commit_message = deployment_data.get('meta', {}).get('githubCommitMessage', 'No commit message')
    commit_sha = deployment_data.get('meta', {}).get('githubCommitSha', '')
    if commit_sha:
        commit_sha = commit_sha[:7]  # First 7 characters of SHA
    branch = deployment_data.get('meta', {}).get('githubCommitRef', 'unknown branch')
    
    # Format the deployment URL if it exists
    deployment_url = f"https://{url}" if url else "No URL available"
    
    # Create status emoji based on state
    if state == 'READY':
        status_emoji = "✅"
    elif state == 'ERROR':
        status_emoji = "❌"
    elif state == 'BUILDING':
        status_emoji = "🔄"
    elif state == 'CANCELED':
        status_emoji = "⚠️"
    else:
        status_emoji = "ℹ️"
    
    # Create the message
    message = f"{status_emoji} *Vercel Deployment Update*\n\n"
    message += f"*Project:* {project_name}\n"
    message += f"*Status:* {state}\n"
    message += f"*Branch:* {branch}\n"
    
    if commit_sha:
        message += f"*Commit:* `{commit_sha}`\n"
    
    if commit_message:
        # Truncate long commit messages
        if len(commit_message) > 100:
            commit_message = commit_message[:97] + "..."
        message += f"*Message:* {commit_message}\n"
    
    if url:
        message += f"*URL:* {deployment_url}\n"
    
    # Send the message to the configured chat ID
    if CHAT_ID:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
    else:
        logger.error("No CHAT_ID configured for deployment notifications")

# Telegram webhook route
@flask_app.route(f"/webhook/{SECRET_TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # Process the update asynchronously using the existing event loop
        loop.run_until_complete(application.process_update(update))
        
        return "OK"

# Vercel webhook route (no authentication)
@flask_app.route("/vercel-webhook", methods=["POST"])
def vercel_webhook():
    if request.method == "POST":
        # Get deployment data from the request
        try:
            deployment_data = request.get_json(force=True)
            logger.info(f"Received Vercel webhook: {deployment_data.get('type')}")
            
            # Check if this is a deployment event
            if deployment_data.get('type') == 'deployment.ready' or deployment_data.get('type') == 'deployment.error':
                # Send notification asynchronously
                loop.run_until_complete(send_deployment_notification(deployment_data.get('payload', {})))
                
            return jsonify({"status": "success"}), 200
        except Exception as e:
            logger.error(f"Error processing Vercel webhook: {str(e)}")
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Set the webhook using the event loop
    webhook_url = f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    loop.run_until_complete(application.bot.set_webhook(url=webhook_url))
    print(f"✅ Telegram webhook set: {webhook_url}")
    print(f"✅ Vercel webhook available at: {WEBHOOK_HOST}/vercel-webhook")

    # Run the Flask application
    flask_app.run(host="0.0.0.0", port=PORT)