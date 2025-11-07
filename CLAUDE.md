# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Telegram bot that integrates GitHub PR management with Vercel deployment monitoring. The bot responds to Telegram commands and webhooks from both Telegram and Vercel platforms.

## Development Commands

### Running the Bot

```bash
python bot.py
```

The bot will:
1. Set up a webhook at `{WEBHOOK_HOST}/webhook/{SECRET_TOKEN}` for Telegram
2. Start Flask server on port specified by `PORT` (default: 8443)
3. Listen for Vercel webhooks at `/vercel-webhook`

### Installing Dependencies

```bash
pip install -r requirements.txt
```

### Environment Setup

Copy `.env.example` to `.env` and configure:
- `TELEGRAM_TOKEN`: Bot token from @BotFather
- `GITHUB_TOKEN`: GitHub personal access token with repo permissions
- `GITHUB_REPO`: Format `owner/repo-name`
- `WEBHOOK_HOST`: Public HTTPS URL where bot is hosted
- `PORT`: Port for Flask server (default 8443)
- `SECRET_TOKEN`: Random string for webhook security
- `TELEGRAM_CHAT_ID`: Chat ID for deployment notifications
- `VERCEL_API_TOKEN`: Token from Vercel account settings
- `VERCEL_TEAM_ID`: (Optional) If using team account
- `VERCEL_PROJECT_ID`: Project ID from Vercel dashboard

## Architecture

### Hybrid Async/Sync Design

The bot uses a complex threading model that combines Flask (synchronous) with python-telegram-bot (asynchronous):

- **Event Loop**: A single asyncio event loop (`loop`) is created and kept running throughout the application lifecycle
- **Flask Integration**: Flask runs synchronously but uses `loop.run_until_complete()` to process Telegram updates
- **Webhook Processing**: Telegram webhooks are processed via `application.process_update()` on the event loop
- **Cross-thread Communication**: Vercel webhook handler uses `asyncio.run_coroutine_threadsafe()` to schedule async notifications

### Dual Webhook System

1. **Telegram Webhook** (`/webhook/{SECRET_TOKEN}`):
   - Receives bot command updates from Telegram
   - Processes commands through telegram-python-bot handlers
   - Secret token in URL provides basic security

2. **Vercel Webhook** (`/vercel-webhook`):
   - Receives deployment events (`deployment.ready`, `deployment.error`)
   - Fetches full deployment details via Vercel API
   - Sends notifications to configured Telegram chat

### Bot Commands

- `/hello`: Health check
- `/pull <pr_number>`: Merge GitHub PR by number
- `/deployment`: Get latest Vercel deployment status
- `/start_monitor`: Begin polling Vercel API every 5 minutes for new deployments
- `/stop_monitor`: Stop deployment monitoring

### State Management

The bot uses `context.bot_data["last_deployment_id"]` to track which deployments have been notified to prevent duplicate notifications when using the polling monitor.

## Important Patterns

### Error Handling

The codebase has minimal error handling. When adding new features:
- Wrap API calls in try/except blocks
- Use `logger.error()` for error logging
- Return user-friendly error messages via `update.message.reply_text()`

### GitHub API Calls

All GitHub API calls use:
- Base URL: `https://api.github.com/repos/{GITHUB_REPO}/...`
- Headers: `{'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github+json'}`
- Direct `requests` library (not async)

### Vercel API Calls

- Use Bearer token authentication: `Authorization: Bearer {VERCEL_API_TOKEN}`
- Include `teamId` parameter when `VERCEL_TEAM_ID` is set
- API v6 for listing deployments, v11 for fetching by ID

## Known Limitations

- No test coverage exists
- No linting or code quality tools configured
- The mixing of sync Flask and async telegram-bot can cause threading issues if not careful
- Webhook endpoint `/vercel-webhook` has no authentication
- GitHub PR merge always uses default merge commit, no squash/rebase options
