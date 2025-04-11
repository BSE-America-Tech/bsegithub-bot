import os
import logging
import requests
import asyncio
import json
import time
import threading
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

# Set up file logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# GitHub headers
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github+json'
}

# Flask app for webhook
flask_app = Flask(__name__)

# Create a global event loop in the main thread
main_loop = asyncio.new_event_loop()
asyncio.set_event_loop(main_loop)

# Lock for thread-safe access to the event loop
loop_lock = threading.Lock()

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

# New command to test Vercel notifications
async def test_vercel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test the Vercel notification functionality"""
    chat_id = update.effective_chat.id
    
    # Create sample test data
    test_payload = {
        "id": "test-deployment-id",
        "name": "test-project",
        "url": "test-deployment.vercel.app",
        "state": "READY",
        "meta": {
            "githubCommitMessage": "Test deployment",
            "githubCommitSha": "1234567890abcdef",
            "githubCommitRef": "main"
        }
    }
    
    try:
        # Send a test notification
        await send_deployment_notification(test_payload)
        await update.message.reply_text("✅ Test Vercel notification sent!")
    except Exception as e:
        logger.error(f"Error sending test notification: {str(e)}")
        await update.message.reply_text(f"❌ Error sending test notification: {str(e)}")

# Create application and add handlers
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("pull", pull))
application.add_handler(CommandHandler("hello", hello))
application.add_handler(CommandHandler("test_vercel", test_vercel))

# Initialize the application
main_loop.run_until_complete(application.initialize())

# Function to send deployment notification 
async def send_deployment_notification(deployment_data):
    """Send notification about Vercel deployment status to the configured chat"""
    logger.debug(f"Preparing to send deployment notification with data: {deployment_data}")
    
    if not CHAT_ID:
        logger.error("No CHAT_ID configured for deployment notifications")
        return
    
    # Create bot instance
    bot = Bot(token=TELEGRAM_TOKEN)
    
    try:
        # Extract relevant information from the deployment data
        deployment_id = deployment_data.get('id', 'Unknown')
        project_name = deployment_data.get('name', 'Unknown project')
        url = deployment_data.get('url', '')
        state = deployment_data.get('state', 'unknown')
        
        # Handle different payload structures (Vercel has inconsistent webhooks)
        meta = deployment_data.get('meta', {})
        if not meta and 'deployment' in deployment_data:
            # Alternative payload structure
            meta = deployment_data.get('deployment', {}).get('meta', {})
        
        commit_message = meta.get('githubCommitMessage', 'No commit message')
        commit_sha = meta.get('githubCommitSha', '')
        if commit_sha:
            commit_sha = commit_sha[:7]  # First 7 characters of SHA
        branch = meta.get('githubCommitRef', 'unknown branch')
        
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
        
        logger.debug(f"Sending message to chat ID {CHAT_ID}: {message}")
        
        # Send the message to the configured chat ID
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        logger.info(f"Successfully sent deployment notification to chat {CHAT_ID}")
    except Exception as e:
        logger.error(f"Error in send_deployment_notification: {str(e)}", exc_info=True)
        # Try sending a simpler error message
        try:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ Error processing deployment notification: {str(e)}\n\nRaw data: {json.dumps(deployment_data)[:500]}..."
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message: {str(inner_e)}")

# Helper function to run async functions from synchronous code (thread-safe)
def run_async(coroutine):
    with loop_lock:
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, main_loop)
            return future.result()
        except Exception as e:
            logger.error(f"Error in run_async: {str(e)}", exc_info=True)
            raise

# Telegram webhook route
@flask_app.route(f"/webhook/{SECRET_TOKEN}", methods=["POST"])
def telegram_webhook():
    if request.method == "POST":
        logger.info("Received Telegram webhook request")
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, application.bot)
        
        # Process the update using the thread-safe helper
        run_async(application.process_update(update))
        
        return "OK"

# Vercel webhook route (no authentication)
@flask_app.route("/vercel-webhook", methods=["POST"])
def vercel_webhook():
    logger.info("🔍 WEBHOOK RECEIVED")
    
    # Log request details
    logger.info(f"Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    
    if request.data:
        logger.info(f"Raw data length: {len(request.data)} bytes")
    
    # Get deployment data from the request
    try:
        payload = request.get_json(force=True)
        logger.info(f"Received Vercel webhook with type: {payload.get('type', 'unknown')}")
        
        # Save raw payload for debugging
        timestamp = int(time.time())
        with open(f"vercel_payload_{timestamp}.json", "w") as f:
            json.dump(payload, f, indent=2)
        
        # Handle different webhook formats
        event_type = payload.get('type')
        deployment_data = None
        
        if event_type in ['deployment', 'deployment.ready', 'deployment.error']:
            # Standard Vercel webhook format
            if 'payload' in payload:
                deployment_data = payload.get('payload', {})
            else:
                deployment_data = payload
        
        # If we have deployment data, send the notification
        if deployment_data:
            logger.info(f"Processing deployment with state: {deployment_data.get('state', 'unknown')}")
            # Run the async function in a thread-safe way
            run_async(send_deployment_notification(deployment_data))
            
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logger.error(f"Error processing Vercel webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Add a simple test endpoint
@flask_app.route("/test", methods=["GET"])
def test_endpoint():
    return jsonify({
        "status": "ok",
        "message": "Bot is running",
        "vercel_webhook": f"{WEBHOOK_HOST}/vercel-webhook",
        "telegram_webhook": f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}",
        "chat_id": CHAT_ID or "Not configured"
    })

# Manual test endpoint
@flask_app.route("/manual-test", methods=["GET"])
def manual_test():
    # Run the test payload through the notification system
    test_payload = {
        "id": "manual-test",
        "name": "manual-test",
        "url": "test.vercel.app",
        "state": "READY",
        "meta": {
            "githubCommitMessage": "Manual test",
            "githubCommitSha": "abcdef1",
            "githubCommitRef": "main" 
        }
    }
    
    try:
        # Use the thread-safe helper
        run_async(send_deployment_notification(test_payload))
        return jsonify({"status": "Test notification triggered"})
    except Exception as e:
        logger.error(f"Error in manual test: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Set the webhook in a thread-safe way
    webhook_url = f"{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}"
    run_async(application.bot.set_webhook(url=webhook_url))
    print(f"✅ Telegram webhook set: {webhook_url}")
    print(f"✅ Vercel webhook available at: {WEBHOOK_HOST}/vercel-webhook")
    print(f"✅ Test endpoint available at: {WEBHOOK_HOST}/test")
    print(f"✅ Manual test available at: {WEBHOOK_HOST}/manual-test")

    # Run the Flask application
    flask_app.run(host="0.0.0.0", port=PORT)