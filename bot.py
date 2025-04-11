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
from threading import Thread

load_dotenv()

# Env vars
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
PORT = int(os.getenv("PORT", 8443))
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
TELEGRAM_GROUP_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID")
VERCEL_API_TOKEN = os.getenv("VERCEL_API_TOKEN")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID")  # Optional, if using a team
VERCEL_PROJECT_ID = os.getenv("VERCEL_PROJECT_ID")

# GitHub headers
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhook
flask_app = Flask(__name__)

# Headers for Vercel API
vercel_headers = {
    "Authorization": f"Bearer {VERCEL_API_TOKEN}",
    "Content-Type": "application/json",
}


async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! The bot is up and running.")


async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a PR number or branch name.")
        return

    pr_ref = context.args[0]
    pr_url = f"https://api.github.com/repos/{GITHUB_REPO}/pulls/{pr_ref}"
    pr_resp = requests.get(pr_url, headers=headers)

    if pr_resp.status_code != 200:
        await update.message.reply_text(f"❌ PR #{pr_ref} not found.")
        return

    merge_url = f"https://api.github.com/repos/{GITHUB_REPO}/pulls/{pr_ref}/merge"
    merge_resp = requests.put(
        merge_url, headers=headers, json={"commit_title": f"Merge PR #{pr_ref}"}
    )

    if merge_resp.status_code == 200:
        await update.message.reply_text(f"✅ PR #{pr_ref} has been merged!")
    else:
        await update.message.reply_text(
            f"❌ Failed to merge PR #{pr_ref}. Error: {merge_resp.json().get('message')}"
        )


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


# Track notified deployments
notified_deployments = set()


# Function to poll Vercel API
async def poll_vercel_deployments():
    while True:
        try:
            # Fetch recent deployments
            url = f"https://api.vercel.com/v6/deployments"
            params = {
                "projectId": VERCEL_PROJECT_ID               
            }
            response = requests.get(url, headers=vercel_headers, params=params)
            response.raise_for_status()
            deployments = response.json().get("deployments", [])

            # Process deployments
            for deployment in deployments:
                deployment_id = deployment.get("uid")
                deployment_state = deployment.get("state", "unknown").upper()
                deployment_url = deployment.get("url", "No URL provided")
                project_name = deployment.get("name", "Unknown Project")

                # Skip already-notified deployments
                if deployment_id in notified_deployments:
                    continue

                # Notify based on deployment state
                if deployment_state == "READY":
                    message = f"🚀 Deployment Successful!\nProject: {project_name}\nURL: {deployment_url}"
                elif deployment_state == "ERROR":
                    message = f"❌ Deployment Failed!\nProject: {project_name}\nDeployment ID: {deployment_id}"
                else:
                    continue  # Skip other states (e.g., QUEUED, BUILDING)

                # Send the message to the Telegram group
                chat_id = TELEGRAM_GROUP_CHAT_ID
                if chat_id:
                    await application.bot.send_message(chat_id=chat_id, text=message)

                # Mark deployment as notified
                notified_deployments.add(deployment_id)

        except Exception as e:
            logger.error(f"Error polling Vercel API: {e}")

        # Wait before polling again
        await asyncio.sleep(60)  # Poll every 60 seconds


# Start the polling task in a separate thread
def start_polling_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_vercel_deployments())


if __name__ == "__main__":
    # Set the webhook using the event loop
    webhook_url = f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    loop.run_until_complete(application.bot.set_webhook(url=webhook_url))
    print(f"✅ Webhook set: {webhook_url}")
    
    polling_thread = Thread(target=start_polling_task, daemon=True)
    polling_thread.start()

    # Run the Flask application
    flask_app.run(host="0.0.0.0", port=PORT)
