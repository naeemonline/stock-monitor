# 🚀 Quick Start Guide for Naeem

## What You're Getting

A complete automated stock monitoring system that:
- ✅ Runs daily at 6 PM EST (after market close)
- ✅ Tracks your 25-30 stocks
- ✅ Emails you a clean, formatted report
- ✅ Posts summary to SP Funds Teams channel
- ✅ Provides 24/7 live dashboard
- ✅ Uses Claude AI for intelligent insights
- ✅ Costs ~$0.15/month to run

## 5-Minute Setup Checklist

### ☐ Step 1: Get API Keys (10 min)

1. **Claude API** (https://console.anthropic.com/)
   - Sign up → Get API Keys → Copy key
   - You get $5 free credit (lasts ~33 months!)

2. **SendGrid Email** (https://signup.sendgrid.com/)
   - Free account → Settings → API Keys
   - Create key with "Mail Send" permission

3. **Teams Webhook**
   - In your SP Funds Teams channel
   - Click "..." → Connectors → Incoming Webhook
   - Name: "Stock Monitor" → Copy URL

### ☐ Step 2: Add Your Stocks (2 min)

Edit `stock_monitor.py` line 20-30:

```python
TICKERS = [
    # SP Funds portfolio
    "SPY", "AGG", "VTI",  # Your actual holdings
    # Add all 25-30 tickers here
]
```

### ☐ Step 3: Deploy to GitHub (3 min)

```bash
# Create new repo on GitHub: stock-monitor
git clone https://github.com/YOUR_USERNAME/stock-monitor.git
cd stock-monitor

# Copy all files into the folder
# Then:
git add .
git commit -m "Setup stock monitor"
git push
```

### ☐ Step 4: Add Secrets (2 min)

In GitHub repo → Settings → Secrets → Add these:

- `ANTHROPIC_API_KEY` = your Claude key
- `TEAMS_WEBHOOK_URL` = your Teams webhook
- `SENDGRID_API_KEY` = your SendGrid key
- `EMAIL_FROM` = stockmonitor@spfunds.com (or any email)
- `EMAIL_TO` = naeem@spfunds.com (your email)

### ☐ Step 5: Deploy Dashboard (2 min)

1. Go to https://streamlit.io/cloud
2. Sign in with GitHub
3. New app → Select your repo → `streamlit_dashboard.py`
4. Deploy!

## ✅ Done!

Starting today at 6 PM EST:
- Email arrives in your inbox
- Teams gets a notification
- Dashboard is live 24/7

## Test It Now (Optional)

Want to test before waiting until 6 PM?

```bash
# In your repo on GitHub
Go to Actions → Daily Stock Report → Run workflow
```

Or test locally:

```bash
pip install -r requirements.txt

export ANTHROPIC_API_KEY="your-key"
export TEAMS_WEBHOOK_URL="your-webhook"
export SENDGRID_API_KEY="your-key"
export EMAIL_FROM="your-email"
export EMAIL_TO="naeem@spfunds.com"

python stock_monitor.py
```

## What the Email Looks Like

```
Subject: 📊 Daily Stock Report - Feb 21, 2026

Markets showed mixed performance today with tech leading gains.
Your portfolio is up 0.8% led by NVDA (+3.2%) and MSFT (+1.8%).

┌────────┬─────────┬────────┬────────┬────────┬────────┐
│ Ticker │  Price  │ Day %  │ MTD %  │ YTD %  │  3M %  │
├────────┼─────────┼────────┼────────┼────────┼────────┤
│  SPY   │ $568.42 │ +0.5%  │ +2.1%  │ +8.3%  │ +12.4% │
│  NVDA  │ $142.18 │ +3.2%  │ +5.6%  │ +45.2% │ +38.1% │
...

Top News:
• Fed signals rate cuts may come in Q2
• Tech stocks rally on AI chip demand
• Energy sector lags on oil price weakness
```

## Customization Ideas

1. **Different schedule**: Edit `.github/workflows/daily_stock_report.yml`
2. **Add charts**: Extend `streamlit_dashboard.py`
3. **Multiple portfolios**: Duplicate the workflow
4. **Weekly summary**: Add another cron schedule

## Need Help?

- Check `README.md` for detailed docs
- GitHub Actions logs show any errors
- Test locally first if issues

## Cost Reminder

- Claude API: $0.003/day = $0.09/month
- Everything else: FREE
- With $5 credit: **33 months free**

That's it! Enjoy your automated stock monitoring. 📈
