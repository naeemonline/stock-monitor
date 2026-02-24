#!/usr/bin/env python3
"""
Automated Stock Monitor with Claude AI
Sends daily email reports and Teams notifications
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import re

import yfinance as yf
import pandas as pd
import requests
import feedparser
from anthropic import Anthropic

# ============================================================================
# CONFIGURATION
# ============================================================================

# Market Indexes (tracked separately from funds)
INDEXES = [
    {"ticker": "SPY", "name": "S&P 500", "category": "Index"},
    {"ticker": "QQQ", "name": "Nasdaq 100", "category": "Index"},
    {"ticker": "DIA", "name": "Dow Jones", "category": "Index"},
    {"ticker": "IWM", "name": "Russell 2000", "category": "Index"},
]

# Sharia-Compliant Funds with metadata
FUNDS = [
    # SP Funds ETFs
    {"ticker": "SPUS", "name": "SP Funds S&P 500 Sharia Industry Exclusions ETF", "category": "US Equity Large-Cap", "expense_ratio": 0.49},
    {"ticker": "SPSK", "name": "SP Funds Dow Jones Global Sukuk ETF", "category": "Fixed Income/Sukuk", "expense_ratio": 0.55},
    {"ticker": "SPRE", "name": "SP Funds S&P Global REIT Sharia ETF", "category": "Real Estate", "expense_ratio": 0.59},
    {"ticker": "SPTE", "name": "SP Funds S&P Global Technology ETF", "category": "Technology", "expense_ratio": 0.55},
    {"ticker": "SPWO", "name": "SP Funds S&P World ex-US ETF", "category": "International Equity", "expense_ratio": 0.55},
    
    # Wahed ETFs
    {"ticker": "HLAL", "name": "Wahed FTSE USA Shariah ETF", "category": "US Equity Large/Mid-Cap", "expense_ratio": 0.50},
    {"ticker": "UMMA", "name": "Wahed Dow Jones Islamic World ETF", "category": "International Equity", "expense_ratio": 0.65},
    
    # SP Funds Target Date Mutual Funds
    {"ticker": "SPTAX", "name": "SP Funds 2030 Target Date Fund", "category": "Target Date 2030", "expense_ratio": 1.40},
    {"ticker": "SPTBX", "name": "SP Funds 2040 Target Date Fund", "category": "Target Date 2040", "expense_ratio": 1.40},
    {"ticker": "SPTCX", "name": "SP Funds 2050 Target Date Fund", "category": "Target Date 2050", "expense_ratio": 1.40},
]

# Combine all tickers for data fetching
ALL_TICKERS = [item["ticker"] for item in INDEXES + FUNDS]

# ============================================================================
# STOCK MONITOR CLASS
# ============================================================================

class StockMonitor:
    """Automated stock monitoring with Claude AI formatting"""
    
    def __init__(self):
        """Initialize with API credentials from environment"""
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL")
        self.email_from = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
        self.email_to = os.getenv("EMAIL_TO")
        
        if not self.anthropic_api_key:
            print("⚠️  ANTHROPIC_API_KEY not set")
    
    def fetch_stock_data(self, ticker: str, metadata: dict) -> Optional[Dict]:
        """Fetch comprehensive stock data including returns"""
        try:
            stock = yf.Ticker(ticker)
            
            # Get current price
            info = stock.info
            current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
            
            if not current_price:
                print(f"  ⚠️  No price data for {ticker}")
                return None
            
            # Get historical data for returns calculation
            hist = stock.history(period="1y")
            if hist.empty:
                print(f"  ⚠️  No historical data for {ticker}")
                return None
            
            # Calculate time-based returns
            today = datetime.now()
            month_ago = today - timedelta(days=30)
            three_months_ago = today - timedelta(days=90)
            year_start = datetime(today.year, 1, 1)
            
            # Get historical prices - make timestamps timezone-aware
            hist_month = hist[hist.index >= pd.Timestamp(month_ago, tz=hist.index.tz)]
            hist_3m = hist[hist.index >= pd.Timestamp(three_months_ago, tz=hist.index.tz)]
            hist_ytd = hist[hist.index >= pd.Timestamp(year_start, tz=hist.index.tz)]
            
            # Calculate returns
            mtd_return = ((current_price / hist_month['Close'].iloc[0]) - 1) * 100 if len(hist_month) > 0 else 0
            three_month_return = ((current_price / hist_3m['Close'].iloc[0]) - 1) * 100 if len(hist_3m) > 0 else 0
            ytd_return = ((current_price / hist_ytd['Close'].iloc[0]) - 1) * 100 if len(hist_ytd) > 0 else 0
            day_change = info.get('regularMarketChangePercent', 0)
            
            return {
                "ticker": ticker,
                "name": metadata.get("name", ticker),
                "category": metadata.get("category", "N/A"),
                "expense_ratio": metadata.get("expense_ratio", None),
                "price": current_price,
                "day_change": day_change,
                "mtd_return": mtd_return,
                "three_month_return": three_month_return,
                "ytd_return": ytd_return,
                "volume": info.get('volume', 0),
                "market_cap": info.get('marketCap', 0),
                "sector": info.get('sector', 'N/A'),
            }
            
        except Exception as e:
            print(f"  ❌ Error fetching {ticker}: {e}")
            return None
    
    def fetch_sharia_news(self) -> List[Dict]:
        """Fetch Sharia-compliant investing news using Google News RSS"""
        try:
            # Search for Sharia/Islamic/Halal investing news
            queries = [
                "Sharia compliant investing USA",
                "Islamic finance ETF",
                "Halal investing news",
                "SP Funds Islamic",
                "Shariah investing"
            ]
            
            all_articles = []
            
            for query in queries:
                url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
                feed = feedparser.parse(url)
                
                for entry in feed.entries[:3]:  # Get top 3 from each query
                    all_articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get('published', ''),
                        "source": entry.get('source', {}).get('title', 'Unknown')
                    })
            
            # Remove duplicates and sort by recency (USA first)
            seen_titles = set()
            unique_articles = []
            for article in all_articles:
                if article['title'] not in seen_titles:
                    seen_titles.add(article['title'])
                    unique_articles.append(article)
            
            # Prioritize USA news
            usa_articles = [a for a in unique_articles if any(kw in a['title'].lower() or kw in a['source'].lower() 
                          for kw in ['usa', 'us ', 'america', 'united states', 'sp funds', 'wahed'])]
            global_articles = [a for a in unique_articles if a not in usa_articles]
            
            return (usa_articles + global_articles)[:10]
            
        except Exception as e:
            print(f"⚠️  Error fetching news: {e}")
            return []
    
    def format_with_claude(self, indexes_data: List[Dict], funds_data: List[Dict], news: List[Dict]) -> Dict:
        """Use Claude to format the data into email and Teams content"""
        if not self.anthropic_api_key:
            return self.fallback_format(indexes_data, funds_data, news)
        
        try:
            client = Anthropic(api_key=self.anthropic_api_key)
            
            prompt = f"""You are a financial reporting assistant. Format this stock market data into a professional daily report.

TODAY'S DATE: {datetime.now().strftime('%A, %B %d, %Y')}

MARKET INDEXES:
{json.dumps(indexes_data, indent=2)}

SHARIA-COMPLIANT FUNDS:
{json.dumps(funds_data, indent=2)}

TOP NEWS (prioritized: USA Sharia-compliant news first, then global):
{json.dumps(news, indent=2)}

Generate a response with EXACTLY this structure:

1. EXECUTIVE SUMMARY (2-3 sentences about market performance and key trends)

2. HTML EMAIL with these sections IN THIS ORDER:
   a) Market Indexes table (separate from funds)
   b) Sharia-Compliant Funds table 
   c) Top News (Sharia-compliant investing focus)

TABLE REQUIREMENTS:
- Columns in this EXACT order: Symbol | Name | Category | Price | Day % | 3M % | MTD % | YTD % | Expense Ratio
- Color code: green for positive, red for negative
- Clean, minimalist design (white background, simple borders)
- Expense Ratio column: show as "X.XX%" or "—" for indexes

3. TEAMS SUMMARY (1-2 sentences max)

Format your response as JSON:
{{
  "executive_summary": "...",
  "html_email": "...",
  "teams_summary": "..."
}}"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            result = json.loads(content)
            
            return {
                "executive_summary": result.get("executive_summary", "Market data updated."),
                "html_email": result.get("html_email", ""),
                "teams_summary": result.get("teams_summary", "")
            }
            
        except Exception as e:
            print(f"❌ Claude API error: {e}")
            return self.fallback_format(indexes_data, funds_data, news)
    
    def fallback_format(self, indexes_data: List[Dict], funds_data: List[Dict], news: List[Dict]) -> Dict:
        """Fallback formatting without Claude"""
        html_email = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h2>📊 Daily Stock Report - {datetime.now().strftime('%B %d, %Y')}</h2>
            
            <h3>Market Indexes</h3>
            <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f0f0f0;">
                    <th>Symbol</th><th>Name</th><th>Price</th><th>Day %</th><th>3M %</th><th>MTD %</th><th>YTD %</th>
                </tr>
                {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>${s['price']:.2f}</td><td style='color: {'green' if s['day_change'] >= 0 else 'red'}'>{s['day_change']:.2f}%</td><td>{s['three_month_return']:.2f}%</td><td>{s['mtd_return']:.2f}%</td><td>{s['ytd_return']:.2f}%</td></tr>" for s in indexes_data])}
            </table>
            
            <h3>Sharia-Compliant Funds</h3>
            <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f0f0f0;">
                    <th>Symbol</th><th>Name</th><th>Category</th><th>Price</th><th>Day %</th><th>3M %</th><th>MTD %</th><th>YTD %</th><th>Expense Ratio</th>
                </tr>
                {"".join([f"<tr><td>{s['ticker']}</td><td>{s['name']}</td><td>{s['category']}</td><td>${s['price']:.2f}</td><td style='color: {'green' if s['day_change'] >= 0 else 'red'}'>{s['day_change']:.2f}%</td><td>{s['three_month_return']:.2f}%</td><td>{s['mtd_return']:.2f}%</td><td>{s['ytd_return']:.2f}%</td><td>{s['expense_ratio']:.2f}%</td></tr>" for s in funds_data])}
            </table>
            
            <h3>📰 Sharia-Compliant Investing News</h3>
            <ul>
                {"".join([f"<li><a href='{n['link']}'>{n['title']}</a> - {n['source']}</li>" for n in news[:5]])}
            </ul>
        </body>
        </html>
        """
        
        return {
            "executive_summary": f"Portfolio tracking {len(indexes_data) + len(funds_data)} securities",
            "html_email": html_email,
            "teams_summary": f"Stock report generated for {len(indexes_data)} indexes and {len(funds_data)} funds"
        }
    
    def send_email(self, html_content: str, subject: str):
        """Send email via Resend or SendGrid"""
        if not self.sendgrid_api_key or not self.email_to:
            print("⚠️  Email not configured (missing API_KEY or EMAIL_TO)")
            return
        
        print("📧 Sending email...")
        
        try:
            # Check if using Resend (API key starts with 're_') or SendGrid (starts with 'SG.')
            is_resend = self.sendgrid_api_key.startswith('re_')
            
            if is_resend:
                # Resend API
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {self.sendgrid_api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "from": self.email_from,
                    "to": [self.email_to],
                    "subject": subject,
                    "html": html_content
                }
                success_code = 200
            else:
                # SendGrid API
                url = "https://api.sendgrid.com/v3/mail/send"
                headers = {
                    "Authorization": f"Bearer {self.sendgrid_api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "personalizations": [{
                        "to": [{"email": self.email_to}]
                    }],
                    "from": {"email": self.email_from},
                    "subject": subject,
                    "content": [{
                        "type": "text/html",
                        "value": html_content
                    }]
                }
                success_code = 202
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code in [200, 202]:
                print(f"✅ Email sent to {self.email_to}")
            else:
                print(f"❌ Email failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Email error: {e}")
    
    def post_to_teams(self, summary: str):
        """Post to Microsoft Teams via webhook"""
        if not self.teams_webhook:
            print("⚠️  Teams webhook not configured")
            return
        
        print("📢 Posting to Microsoft Teams...")
        
        try:
            # Always use a simple, reliable card format
            card = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "summary": "Daily Stock Report",
                "themeColor": "0078D4",
                "title": f"📊 Daily Stock Report - {datetime.now().strftime('%B %d, %Y')}",
                "text": summary if summary else "Stock report generated successfully. Check your email for details."
            }
            
            response = requests.post(
                self.teams_webhook,
                headers={"Content-Type": "application/json"},
                json=card
            )
            
            if response.status_code == 200:
                print("✅ Posted to Teams successfully")
            else:
                print(f"❌ Teams post failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Teams error: {e}")
    
    def run(self):
        """Main execution"""
        print("\n" + "="*60)
        print(f"  AUTOMATED STOCK MONITOR")
        print(f"  {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}")
        print("="*60 + "\n")
        
        # Fetch stock data
        print(f"📊 Fetching data for {len(ALL_TICKERS)} securities...")
        
        indexes_data = []
        funds_data = []
        
        for idx, item in enumerate(INDEXES + FUNDS, 1):
            ticker = item["ticker"]
            print(f"  [{idx}/{len(ALL_TICKERS)}] Fetching {ticker}... ", end="")
            
            data = self.fetch_stock_data(ticker, item)
            if data:
                if item in INDEXES:
                    indexes_data.append(data)
                else:
                    funds_data.append(data)
                print("✓")
            else:
                print("✗")
        
        print(f"\n✅ Successfully fetched {len(indexes_data)} indexes and {len(funds_data)} funds\n")
        
        if len(indexes_data) == 0 and len(funds_data) == 0:
            print("❌ No data available. Exiting.")
            return
        
        # Fetch news
        print("📰 Fetching Sharia-compliant investing news...")
        news = self.fetch_sharia_news()
        print(f"✅ Found {len(news)} news articles\n")
        
        # Format with Claude
        print("🤖 Asking Claude to format the data...")
        formatted = self.format_with_claude(indexes_data, funds_data, news)
        print("✅ Claude formatted the data successfully\n")
        
        # Send email
        subject = f"📊 Daily Stock Report - {datetime.now().strftime('%b %d, %Y')}"
        self.send_email(formatted['html_email'], subject)
        
        # Post to Teams
        self.post_to_teams(formatted.get('teams_summary', formatted['executive_summary']))
        
        print("\n" + "="*60)
        print("✅ DAILY STOCK REPORT COMPLETE")
        print("="*60 + "\n")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    monitor = StockMonitor()
    monitor.run()
