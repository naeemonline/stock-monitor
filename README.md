# 📊 Automated Stock Monitor - Setup Guide

A fully automated stock monitoring system that:
- Tracks 25-30 stocks daily
- Sends formatted email reports
- Posts to Microsoft Teams
- Provides interactive dashboard
- Uses Claude AI for intelligent insights

**Total Cost: ~$0.15/month** (just Claude API usage)

---

## 🚀 Quick Start (5 Steps)

### Step 1: Get Your API Keys (Free)

#### A) Claude API Key
1. Go to https://console.anthropic.com/
2. Sign up/login
3. Click "Get API Keys"
4. Create a new key
5. Copy it (starts with `sk-ant-...`)
6. You get $5 free credit (~5,000 reports!)

#### B) SendGrid API Key (for email)
1. Go to https://signup.sendgrid.com/
2. Sign up (free tier: 100 emails/day)
3. Go to Settings → API Keys
4. Create API Key with "Mail Send" permissions
5. Copy it (starts with `SG.`)

#### C) Microsoft Teams Webhook
1. In Teams, go to your channel
2. Click "..." → Connectors → Incoming Webhook
3. Configure → Name it "Stock Monitor"
4. Copy the webhook URL

---

### Step 2: Create GitHub Repository

```bash
# Create new repository on GitHub.com
# Name it: stock-monitor

# Clone it locally
git clone https://github.com/YOUR_USERNAME/stock-monitor.git
cd stock-monitor

# Copy all files from this project into the repository
```

---

### Step 3: Configure Your Stocks

Edit `stock_monitor.py` and update the TICKERS list:

```python
TICKERS = [
    # Replace with your actual stocks
    "SPY", "QQQ", "AAPL", "MSFT", "GOOGL",
    # Add your 25-30 tickers here...
]
```

Also update `streamlit_dashboard.py` with the same tickers.

---

### Step 4: Add Secrets to GitHub

1. Go to your GitHub repo
2. Settings → Secrets and variables → Actions
3. Click "New repository secret" for each:

**Required Secrets:**
- `ANTHROPIC_API_KEY` - Your Claude API key
- `TEAMS_WEBHOOK_URL` - Your Teams webhook URL
- `SENDGRID_API_KEY` - Your SendGrid API key
- `EMAIL_FROM` - Your email (e.g., stockmonitor@yourdomain.com)
- `EMAIL_TO` - Where to send reports (e.g., naeem@spfunds.com)

---

### Step 5: Deploy Everything

#### A) Push to GitHub (enables automation)
```bash
git add .
git commit -m "Initial setup"
git push origin main
```

GitHub Actions will now run daily at 6 PM EST automatically!

#### B) Deploy Dashboard to Streamlit Cloud
1. Go to https://streamlit.io/cloud
2. Sign up with GitHub
3. Click "New app"
4. Select your repository
5. Main file: `streamlit_dashboard.py`
6. Click "Deploy"
7. Your dashboard is now live!

---

## ✅ Testing Before Automation

Test locally first:

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (temporary)
export ANTHROPIC_API_KEY="your-key-here"
export TEAMS_WEBHOOK_URL="your-webhook-here"
export SENDGRID_API_KEY="your-key-here"
export EMAIL_FROM="your-email@domain.com"
export EMAIL_TO="recipient@domain.com"

# Run the script
python stock_monitor.py
```

You should see:
- ✅ Stock data fetched
- ✅ Claude formatted the data
- ✅ Email sent
- ✅ Posted to Teams

---

## 📅 Schedule Customization

The automation runs **6 PM EST on weekdays** (after market close).

To change the schedule, edit `.github/workflows/daily_stock_report.yml`:

```yaml
schedule:
  - cron: '0 23 * * 1-5'  # 6 PM EST
  # Change to:
  # '0 14 * * 1-5'  # 9 AM EST
  # '30 20 * * 1-5' # 3:30 PM EST (before close)
```

Cron format: `minute hour day month weekday`
Remember: GitHub uses UTC time!

---

## 🎨 Customizing the Output

### Email Styling
Claude generates the HTML email. To customize, modify the prompt in `stock_monitor.py`:

```python
# Find this section in format_with_claude()
prompt = f"""...
2. HTML_EMAIL: A clean, minimalist HTML email with:
   - YOUR CUSTOMIZATION HERE
   ...
"""
```

### Teams Card
Same process - customize the prompt to change Teams message format.

### Dashboard
Edit `streamlit_dashboard.py`:
- Change colors in the CSS section
- Add/remove columns
- Modify charts

---

## 🔧 Troubleshooting

### "No stock data available"
- Check if market is open
- Verify tickers are correct (use Yahoo Finance symbols)
- Some international stocks may not be available

### "Email failed"
- Verify SendGrid API key is correct
- Check EMAIL_FROM is verified in SendGrid
- Free tier limit: 100 emails/day

### "Teams post failed"
- Verify webhook URL is complete
- Check Teams connector is still active
- Test webhook with curl:
  ```bash
  curl -H "Content-Type: application/json" \
       -d '{"text":"Test message"}' \
       YOUR_WEBHOOK_URL
  ```

### GitHub Actions not running
- Check Settings → Actions is enabled
- Verify secrets are added correctly
- Manual trigger: Actions → Daily Stock Report → Run workflow

---

## 💰 Cost Breakdown

| Service | Cost | Usage |
|---------|------|-------|
| Claude API (Haiku) | ~$0.15/month | 30 reports × 3,000 tokens |
| GitHub Actions | $0 | Free tier (2,000 min/month) |
| SendGrid | $0 | Free tier (100 emails/day) |
| Streamlit Cloud | $0 | Free public hosting |
| Teams Webhook | $0 | Native feature |
| **TOTAL** | **~$0.15/month** | |

With $5 free Claude credit, you get **~33 months free!**

---

## 📊 What You Get

### Daily Email (6 PM EST)
- Executive summary from Claude
- Clean table with all stocks
- Price, Day%, MTD%, YTD%, 3M% returns
- Color-coded gains/losses
- Top 3 market news headlines

### Microsoft Teams Post
- Summary card with key metrics
- Gainers/losers count
- Top performers
- Clickable for full details

### Live Dashboard
- Real-time stock data
- Interactive table
- Filter/sort capabilities
- CSV export
- Auto-refreshes every 5 minutes

---

## 🎯 Pro Tips

1. **Test on weekdays** - Yahoo Finance data is best during market hours
2. **Customize tickers** - Add ETFs, mutual funds, crypto (BTC-USD, ETH-USD)
3. **Multiple reports** - Clone the workflow for different portfolios
4. **Add charts** - Extend Streamlit dashboard with plotly charts
5. **Save history** - Modify script to write daily CSV files

---

## 📝 File Structure

```
stock-monitor/
├── stock_monitor.py              # Main automation script
├── streamlit_dashboard.py        # Interactive web dashboard
├── requirements.txt              # Python dependencies
├── README.md                     # This file
└── .github/
    └── workflows/
        └── daily_stock_report.yml  # GitHub Actions config
```

---

## 🆘 Support

Issues? Questions?
1. Check GitHub Actions logs (Actions tab)
2. Test locally first
3. Verify all API keys are correct
4. Check the troubleshooting section above

---

## 🎉 You're All Set!

Once deployed, you'll receive:
- **Daily email at 6 PM EST**
- **Teams notification at 6 PM EST**
- **24/7 live dashboard**

All completely automated. Zero maintenance. ~$0.15/month.

Enjoy your minimalist, AI-powered stock monitoring system! 📈
