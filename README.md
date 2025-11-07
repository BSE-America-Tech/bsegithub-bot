# GitHub & Telegram Bot

A Telegram bot that integrates with GitHub for managing pull requests and monitoring Vercel deployments.

## Features

- Merge GitHub pull requests via Telegram commands
- Monitor Vercel deployments
- Get real-time deployment notifications
- Simple webhook-based architecture

## Commands

- `/hello` - Check if bot is running
- `/pull <PR_number>` - Merge a GitHub pull request
- `/deployment` - Get latest Vercel deployment info
- `/start_monitor` - Start monitoring Vercel deployments (every 5 minutes)
- `/stop_monitor` - Stop monitoring deployments

## Deployment

### Deploy to Render (Recommended)

See the complete step-by-step guide: [RENDER_DEPLOYMENT_GUIDE.md](RENDER_DEPLOYMENT_GUIDE.md)

**Quick Start:**
1. Fork/clone this repository
2. Sign up at [Render.com](https://render.com)
3. Create a new Web Service from your GitHub repo
4. Add environment variables (see below)
5. Deploy!

**Cost:** Free tier available, $7/month for always-on service (recommended)

### Environment Variables

Required:
- `TELEGRAM_TOKEN` - Your Telegram bot token from @BotFather
- `GITHUB_TOKEN` - GitHub Personal Access Token
- `GITHUB_REPO` - Your repository in format `owner/repo`
- `WEBHOOK_HOST` - Your deployed service URL (e.g., `https://your-app.onrender.com`)
- `SECRET_TOKEN` - Random secret string for webhook security
- `PORT` - Port number (default: 8443, Render uses 10000)

Optional (for Vercel monitoring):
- `VERCEL_API_TOKEN` - Vercel API token
- `VERCEL_TEAM_ID` - Vercel team ID
- `VERCEL_PROJECT_ID` - Vercel project ID
- `TELEGRAM_CHAT_ID` - Chat ID for deployment notifications

## Setup for Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bsegithub-bot.git
cd bsegithub-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

4. Run the bot:
```bash
python bot.py
```

## Tech Stack

- Python 3
- Flask (Web framework)
- python-telegram-bot (Telegram Bot API)
- Requests (HTTP client)

## License

MIT
