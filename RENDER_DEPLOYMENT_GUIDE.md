# Deploy Telegram Bot to Render - Complete Beginner's Guide

This guide will walk you through deploying your GitHub/Telegram bot to Render step-by-step.

## Prerequisites

Before you start, make sure you have:
- A GitHub account with this repository pushed
- A Telegram bot token (from @BotFather)
- A GitHub personal access token
- Your environment variables ready

---

## Step 1: Create a Render Account

1. Go to [https://render.com](https://render.com)
2. Click **"Get Started for Free"**
3. Sign up using your **GitHub account** (recommended for easier deployment)
4. Verify your email if prompted

---

## Step 2: Push Your Code to GitHub

If you haven't already pushed this code to GitHub:

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin claude/bot-hosting-suggestions-011CUuH5yCWRzveQ319AJJ6U
```

Or push to your main branch if you prefer.

---

## Step 3: Create a New Web Service on Render

1. **Log in to Render** at [https://dashboard.render.com](https://dashboard.render.com)

2. Click the **"New +"** button in the top right corner

3. Select **"Web Service"**

4. **Connect your GitHub repository**:
   - Click "Connect account" if this is your first time
   - Grant Render access to your repositories
   - Find and select **"bsegithub-bot"** repository
   - Click **"Connect"**

---

## Step 4: Configure Your Web Service

Fill out the form with these settings:

### Basic Settings

| Field | Value |
|-------|-------|
| **Name** | `bsegithub-bot` (or any name you prefer) |
| **Region** | Choose closest to you (e.g., Oregon, Frankfurt) |
| **Branch** | `main` or your current branch |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |

### Instance Type

- Select **"Free"** (for testing) or **"Starter - $7/month"** (for production)
- **Important**: Free tier spins down after 15 minutes of inactivity, which will cause webhook issues
- **Recommended**: Use the $7/month Starter plan for reliable webhook operation

---

## Step 5: Set Environment Variables

Scroll down to the **"Environment Variables"** section and add these variables one by one:

Click **"Add Environment Variable"** for each of these:

### Required Variables

| Key | Value | Example |
|-----|-------|---------|
| `TELEGRAM_TOKEN` | Your bot token from @BotFather | `123456789:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `GITHUB_TOKEN` | Your GitHub Personal Access Token | `ghp_xxxxxxxxxxxx` |
| `GITHUB_REPO` | Your repo in format `owner/repo` | `yourusername/yourrepo` |
| `SECRET_TOKEN` | Random secret string (make one up!) | `my_super_secret_webhook_token_123` |
| `PORT` | Leave as default | `10000` |

### Optional Variables (for Vercel monitoring)

| Key | Value |
|-----|-------|
| `VERCEL_API_TOKEN` | Your Vercel API token |
| `VERCEL_TEAM_ID` | Your Vercel team ID |
| `VERCEL_PROJECT_ID` | Your Vercel project ID |
| `TELEGRAM_CHAT_ID` | Chat ID for notifications |

**Note**: You'll get the `WEBHOOK_HOST` URL after deployment, so skip it for now.

---

## Step 6: Deploy Your Service

1. Click **"Create Web Service"** at the bottom
2. Render will start building and deploying your app
3. Wait for the deployment to complete (2-5 minutes)
4. You'll see logs in real-time

---

## Step 7: Get Your Webhook URL

After deployment completes:

1. Look at the top of the page for your service URL
   - It will look like: `https://bsegithub-bot-xxxx.onrender.com`

2. Copy this URL

3. Go to **"Environment"** tab on the left sidebar

4. Click **"Add Environment Variable"**

5. Add:
   - **Key**: `WEBHOOK_HOST`
   - **Value**: `https://bsegithub-bot-xxxx.onrender.com` (your actual URL)

6. Click **"Save Changes"**

7. Your service will automatically redeploy with the new variable

---

## Step 8: Set Up Telegram Webhook

Your bot automatically sets the webhook when it starts. To verify:

1. Wait for the redeployment to complete
2. Check the logs (go to "Logs" tab)
3. Look for: `✅ Webhook set: https://your-url.onrender.com/webhook/your-secret-token`

### Manual Webhook Setup (if needed)

If the automatic setup fails, you can set it manually:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-render-url.onrender.com/webhook/your-secret-token"}'
```

Replace:
- `<YOUR_TELEGRAM_TOKEN>` with your actual token
- `your-render-url.onrender.com` with your Render URL
- `your-secret-token` with your SECRET_TOKEN value

---

## Step 9: Test Your Bot

1. Open Telegram and find your bot
2. Send `/hello` command
3. You should receive: "👋 Hello! The bot is up and running."

### Available Commands

- `/hello` - Test if bot is working
- `/pull <PR_number>` - Merge a GitHub PR
- `/deployment` - Get latest Vercel deployment info
- `/start_monitor` - Start monitoring Vercel deployments
- `/stop_monitor` - Stop monitoring deployments

---

## Step 10: Set Up Vercel Webhook (Optional)

If you want real-time Vercel deployment notifications:

1. Go to your Vercel project dashboard
2. Go to **Settings** → **Git** → **Deploy Hooks**
3. Add a new webhook:
   - **URL**: `https://your-render-url.onrender.com/vercel-webhook`
   - Select events: `deployment.created`, `deployment.ready`, `deployment.error`
4. Save

---

## Troubleshooting

### Bot Not Responding

1. Check the **Logs** tab in Render dashboard
2. Look for errors in red
3. Make sure all environment variables are set correctly
4. Verify your TELEGRAM_TOKEN is valid

### Webhook Issues

Run this command to check webhook status:

```bash
curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
```

You should see your Render URL in the response.

### Free Tier Sleeping

If using the free tier:
- Your service sleeps after 15 minutes of inactivity
- First request after sleep takes 30-60 seconds to wake up
- Consider upgrading to Starter ($7/month) for always-on service

---

## Cost Comparison

| Plan | Price | Features |
|------|-------|----------|
| **Free** | $0 | 750 hours/month, spins down after 15 min inactivity |
| **Starter** | $7/month | Always-on, no sleeping, better performance |

**Recommendation**: Start with free tier to test, upgrade to Starter for production use.

---

## Monitoring Your Bot

### View Logs

1. Go to Render Dashboard
2. Click on your service
3. Click **"Logs"** tab
4. See real-time logs of your bot activity

### Check Service Status

- Green dot = Running
- Red dot = Failed
- Yellow dot = Deploying

---

## Updating Your Bot

When you push changes to GitHub:

1. Render automatically detects the push
2. Starts a new deployment
3. Takes 2-5 minutes
4. Your bot restarts with new code

**Auto-deploy is enabled by default!**

---

## Security Best Practices

1. Never commit `.env` file to Git
2. Use strong SECRET_TOKEN
3. Keep your tokens secret
4. Regularly rotate your tokens
5. Only give GitHub token necessary permissions

---

## Need Help?

- Render Docs: [https://render.com/docs](https://render.com/docs)
- Render Community: [https://community.render.com](https://community.render.com)
- Check the logs first - most issues are visible there

---

## Summary Checklist

- [ ] Created Render account
- [ ] Connected GitHub repository
- [ ] Created Web Service
- [ ] Added all environment variables
- [ ] Deployed successfully
- [ ] Added WEBHOOK_HOST after getting URL
- [ ] Tested bot with /hello command
- [ ] (Optional) Set up Vercel webhook

---

Congratulations! Your bot is now deployed on Render. 🎉
