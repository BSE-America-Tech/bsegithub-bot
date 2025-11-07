import os
import logging
import requests
import asyncio
import threading
from datetime import datetime
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

# Vercel API configuration
VERCEL_API_TOKEN = os.getenv("VERCEL_API_TOKEN")
VERCEL_TEAM_ID = os.getenv("VERCEL_TEAM_ID")  # Optional, if you're working with a team
VERCEL_PROJECT_ID = os.getenv("VERCEL_PROJECT_ID")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Chat ID where deployment notifications will be sent

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


async def get_deployment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command to get the latest deployment information"""
    try:
        deployment_data = get_latest_deployment()
        if deployment_data:
            message = format_deployment_message(deployment_data)
            await update.message.reply_text(message, parse_mode="HTML")
        else:
            await update.message.reply_text("❌ No deployment data found.")
    except Exception as e:
        logger.error(f"Error fetching deployment: {e}")
        await update.message.reply_text(f"❌ Error fetching deployment data: {str(e)}")


def get_latest_deployment():
    """Get the latest deployment from Vercel API"""
    url = "https://api.vercel.com/v6/deployments"
    
    # Add query parameters
    params = {
        "projectId": VERCEL_PROJECT_ID,
        "limit": 1,  # We only want the latest deployment
    }
    
    # Add team ID if present
    if VERCEL_TEAM_ID:
        params["teamId"] = VERCEL_TEAM_ID
    
    # Headers for Vercel API
    headers = {
        "Authorization": f"Bearer {VERCEL_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        deployments = response.json().get("deployments", [])
        if deployments:
            return deployments[0]
    
    logger.error(f"Failed to get deployment: {response.status_code} - {response.text}")
    return None


def format_deployment_message(deployment):
    """Format deployment data into a readable message"""
    created_at = datetime.fromtimestamp(deployment.get("createdAt") / 1000).strftime("%Y-%m-%d %H:%M:%S")
    state = deployment.get("state", "unknown")
    url = deployment.get("url", "No URL")
    branch = deployment.get("meta", {}).get("githubCommitRef", "unknown branch")
    commit_message = deployment.get("meta", {}).get("githubCommitMessage", "No commit message")
    
    # Build a nice message with emoji indicators
    state_emoji = "✅" if state == "READY" else "🔄" if state == "BUILDING" else "❌"
    
    message = (
        f"<b>Latest Deployment</b>\n\n"
        f"{state_emoji} <b>Status:</b> {state}\n"
        f"🔗 <b>URL:</b> https://{url}\n"
        f"🌿 <b>Branch:</b> {branch}\n"
        f"💬 <b>Commit:</b> {commit_message}\n"
        f"🕒 <b>Created:</b> {created_at}"
    )
    
    return message


async def send_deployment_notification(deployment_data, context=None):
    """Send deployment notification to the configured Telegram chat"""
    if not deployment_data:
        logger.error("No deployment data to send")
        return
    
    if not TELEGRAM_CHAT_ID:
        logger.error("No TELEGRAM_CHAT_ID configured")
        return
    
    message = format_deployment_message(deployment_data)
    
    # Use context if provided (for command cases) or send directly using the bot
    if context:
        await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML")
    else:
        await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML")


async def check_deployment(context: ContextTypes.DEFAULT_TYPE):
    """Periodic job to check for new deployments"""
    try:
        deployment_data = get_latest_deployment()
        if deployment_data:
            # Check if we've already notified about this deployment
            deployment_id = deployment_data.get("uid")
            last_notified_id = context.bot_data.get("last_deployment_id")
            
            if deployment_id != last_notified_id:
                await send_deployment_notification(deployment_data, context)
                context.bot_data["last_deployment_id"] = deployment_id
    except Exception as e:
        logger.error(f"Error in check_deployment job: {e}")


async def start_polling_deployments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start polling for deployment updates"""
    job_removed = remove_job_if_exists("check_deployment", context)
    
    # Add job to run every 5 minutes
    context.job_queue.run_repeating(check_deployment, interval=300, first=1, name="check_deployment")
    
    message = "✅ Started monitoring Vercel deployments."
    if job_removed:
        message = "♻️ Restarted monitoring Vercel deployments."
    
    await update.message.reply_text(message)


async def stop_polling_deployments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop polling for deployment updates"""
    job_removed = remove_job_if_exists("check_deployment", context)
    
    if job_removed:
        await update.message.reply_text("🛑 Stopped monitoring Vercel deployments.")
    else:
        await update.message.reply_text("⚠️ No active monitoring to stop.")


def remove_job_if_exists(name, context):
    """Remove job with given name if it exists"""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


# Webhook route for Vercel deployments
@flask_app.route("/vercel-webhook", methods=["POST"])
def vercel_webhook():
    if request.method == "POST":
        data = request.get_json(force=True)
        
        # Check if this is a deployment event
        if data.get("type") == "deployment.ready" or data.get("type") == "deployment.error":
            deployment_id = data.get("payload", {}).get("id")
            
            # Fetch full deployment details
            deployment_data = get_deployment_by_id(deployment_id)
            
            if deployment_data:
                # Schedule the notification to be sent
                asyncio.run_coroutine_threadsafe(
                    send_deployment_notification(deployment_data),
                    loop
                )
        
        return "OK"


def get_deployment_by_id(deployment_id):
    """Get a specific deployment by ID"""
    if not deployment_id:
        return None
    
    url = f"https://api.vercel.com/v11/deployments/{deployment_id}"
    
    params = {}
    if VERCEL_TEAM_ID:
        params["teamId"] = VERCEL_TEAM_ID
    
    headers = {
        "Authorization": f"Bearer {VERCEL_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    
    logger.error(f"Failed to get deployment by ID: {response.status_code} - {response.text}")
    return None


# Global variables for async handling
application = None
loop = None
loop_thread = None


def run_event_loop(loop):
    """Run the event loop in a separate thread"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def setup_application():
    """Initialize the telegram application"""
    global application, loop, loop_thread

    # Create application and add handlers
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("pull", pull))
    application.add_handler(CommandHandler("hello", hello))
    application.add_handler(CommandHandler("deployment", get_deployment))
    application.add_handler(CommandHandler("start_monitor", start_polling_deployments))
    application.add_handler(CommandHandler("stop_monitor", stop_polling_deployments))

    # Create event loop for async operations
    loop = asyncio.new_event_loop()

    # Run the event loop in a background thread
    loop_thread = threading.Thread(target=run_event_loop, args=(loop,), daemon=True)
    loop_thread.start()

    # Initialize and start the application
    asyncio.run_coroutine_threadsafe(application.initialize(), loop).result()
    asyncio.run_coroutine_threadsafe(application.start(), loop).result()

    logger.info("Telegram application initialized and started")

    return application, loop


# Webhook route
@flask_app.route(f"/webhook/{SECRET_TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        try:
            update_data = request.get_json(force=True)
            logger.info(f"Received webhook update: {update_data}")

            update = Update.de_json(update_data, application.bot)
            logger.info(f"Parsed update object: {update}")

            # Process the update asynchronously and get the future
            future = asyncio.run_coroutine_threadsafe(
                application.process_update(update),
                loop
            )

            # Add a callback to log any exceptions
            def log_exception(fut):
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Error in async update processing: {e}", exc_info=True)

            future.add_done_callback(log_exception)

            return "OK", 200
        except Exception as e:
            logger.error(f"Error processing webhook: {e}", exc_info=True)
            return "Error", 500


if __name__ == "__main__":
    # Setup the application
    setup_application()

    # Set the webhook
    webhook_url = f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    asyncio.run_coroutine_threadsafe(application.bot.set_webhook(url=webhook_url), loop).result()
    print(f"✅ Webhook set: {webhook_url}")

    # Run the Flask application
    try:
        flask_app.run(host="0.0.0.0", port=PORT)
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down application...")
        asyncio.run_coroutine_threadsafe(application.stop(), loop).result()
        asyncio.run_coroutine_threadsafe(application.shutdown(), loop).result()
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=5)
        logger.info("Application shutdown complete")