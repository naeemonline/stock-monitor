"""
Automated Stock Monitor with Claude API Integration
Minimalist design - clean tables, simple charts, intelligent insights
"""

import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic
import yfinance as yf
import pandas as pd
from typing import Dict, List, Any

# ============================================================================
# CONFIGURATION - Edit these with your stocks
# ============================================================================

TICKERS = [
    # Major Indices (use ^ prefix for index symbols)
    "SPY", "QQQ", "DIA",  # ETFs tracking major indices
    
    # SP Funds ETFs - UPDATE THESE WITH YOUR ACTUAL HOLDINGS
    "SPUS",   # SP Funds S&P 500 Sharia Industry Exclusions ETF
    
    # Other Islamic Finance ETFs
    "HLAL",   # Wahed FTSE USA Shariah ETF
    "UMMA",   # Wahed Dow Jones Islamic World ETF
    
    # Large Cap Tech (commonly Sharia-compliant)
    "AAPL", "MSFT", "GOOGL", "NVDA", "META",
    
    # Add more of your actual holdings below...
    # Example: "AMZN", "TSLA", "ADBE", "CRM", etc.
]

class StockMonitor:
    def __init__(self):
        """Initialize the stock monitor with API clients"""
        self.anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.teams_webhook = os.environ.get("TEAMS_WEBHOOK_URL")
        self.email_from = os.environ.get("EMAIL_FROM")
        self.email_to = os.environ.get("EMAIL_TO")
        self.sendgrid_api_key = os.environ.get("SENDGRID_API_KEY")
        
    def fetch_stock_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch comprehensive stock data for a single ticker"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if hist.empty:
                print(f"  ⚠️  No data for {ticker}")
                return None
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            
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
            day_change = ((current_price - prev_close) / prev_close * 100)
            mtd_return = ((current_price - hist_month['Close'].iloc[0]) / hist_month['Close'].iloc[0] * 100) if len(hist_month) > 0 else 0
            three_m_return = ((current_price - hist_3m['Close'].iloc[0]) / hist_3m['Close'].iloc[0] * 100) if len(hist_3m) > 0 else 0
            ytd_return = ((current_price - hist_ytd['Close'].iloc[0]) / hist_ytd['Close'].iloc[0] * 100) if len(hist_ytd) > 0 else 0
            
            # Get basic info
            info = stock.info
            
            return {
                'ticker': ticker,
                'name': info.get('longName', ticker),
                'current_price': round(current_price, 2),
                'day_change': round(day_change, 2),
                'mtd_return': round(mtd_return, 2),
                'ytd_return': round(ytd_return, 2),
                'three_month_return': round(three_m_return, 2),
                'volume': info.get('volume', 0),
                'market_cap': info.get('marketCap', 0),
                'sector': info.get('sector', 'N/A')
            }
        except Exception as e:
            print(f"  ❌ Error fetching {ticker}: {str(e)}")
            return None
    
    def fetch_all_stocks(self) -> List[Dict[str, Any]]:
        """Fetch data for all tickers"""
        print(f"\n📊 Fetching data for {len(TICKERS)} stocks...")
        stock_data = []
        
        for i, ticker in enumerate(TICKERS, 1):
            print(f"  [{i}/{len(TICKERS)}] Fetching {ticker}...", end=" ")
            data = self.fetch_stock_data(ticker)
            if data:
                stock_data.append(data)
                print("✓")
            else:
                print("✗")
        
        print(f"\n✅ Successfully fetched {len(stock_data)} stocks\n")
        return stock_data
    
    def fetch_market_news(self, max_articles: int = 10) -> List[Dict[str, str]]:
        """Fetch recent market news using RSS feed"""
        try:
            import feedparser
            feed = feedparser.parse('https://news.google.com/rss/search?q=stock+market+OR+nasdaq+OR+sp500&hl=en-US&gl=US&ceid=US:en')
            
            news_items = []
            for entry in feed.entries[:max_articles]:
                news_items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.get('published', '')
                })
            return news_items
        except Exception as e:
            print(f"  ⚠️  Could not fetch news: {e}")
            return []
    
    def format_with_claude(self, stock_data: List[Dict], news_data: List[Dict]) -> Dict[str, str]:
        """Use Claude API to intelligently format the data"""
        
        # Create a simple data summary for Claude
        summary_stats = {
            'total_stocks': len(stock_data),
            'gainers': len([s for s in stock_data if s['day_change'] > 0]),
            'losers': len([s for s in stock_data if s['day_change'] < 0]),
            'top_gainer': max(stock_data, key=lambda x: x['day_change']),
            'top_loser': min(stock_data, key=lambda x: x['day_change']),
            'avg_day_change': sum(s['day_change'] for s in stock_data) / len(stock_data)
        }
        
        # Prepare prompt for Claude
        prompt = f"""You are analyzing a stock portfolio. Here's today's data:

PORTFOLIO SUMMARY:
- Total stocks tracked: {summary_stats['total_stocks']}
- Gainers: {summary_stats['gainers']} | Losers: {summary_stats['losers']}
- Average daily change: {summary_stats['avg_day_change']:.2f}%
- Top gainer: {summary_stats['top_gainer']['ticker']} (+{summary_stats['top_gainer']['day_change']:.2f}%)
- Top loser: {summary_stats['top_loser']['ticker']} ({summary_stats['top_loser']['day_change']:.2f}%)

STOCK DATA:
{json.dumps(stock_data, indent=2)}

RECENT NEWS HEADLINES:
{json.dumps([n['title'] for n in news_data[:5]], indent=2)}

Please provide:
1. EXECUTIVE_SUMMARY: A 2-3 sentence overview of today's market performance and key themes (keep it concise and professional)
2. HTML_EMAIL: A clean, minimalist HTML email with:
   - Brief executive summary at top
   - Clean table of all stocks with current price, day change, MTD, YTD, 3M returns
   - Color coding: green for positive, red for negative returns
   - Top 3 news headlines with links
   - Simple, professional styling (white background, minimal colors)
3. TEAMS_MESSAGE: JSON for Microsoft Teams adaptive card (modern, clean design)

Return your response in this exact JSON format:
{{
  "executive_summary": "Your summary here",
  "html_email": "Full HTML content here",
  "teams_card": {{...adaptive card JSON...}}
}}"""

        print("🤖 Asking Claude to format the data...")
        
        try:
            message = self.anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",  # Using Haiku for cost efficiency
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract the response
            response_text = message.content[0].text
            
            # Parse JSON response
            # Claude might wrap it in markdown, so let's clean it
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(response_text)
            print("✅ Claude formatted the data successfully\n")
            return result
            
        except Exception as e:
            print(f"❌ Claude API error: {e}")
            # Fallback to basic formatting
            return self._create_basic_format(stock_data, news_data, summary_stats)
    
    def _create_basic_format(self, stock_data, news_data, summary_stats):
        """Fallback basic formatting if Claude API fails"""
        html_email = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h2>Daily Stock Report - {datetime.now().strftime('%B %d, %Y')}</h2>
            <p><strong>Portfolio Overview:</strong> {summary_stats['gainers']} gainers, {summary_stats['losers']} losers</p>
            <table border="1" cellpadding="8" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f0f0f0;">
                    <th>Ticker</th><th>Price</th><th>Day %</th><th>MTD %</th><th>YTD %</th><th>3M %</th>
                </tr>
                {''.join([f'''<tr>
                    <td>{s['ticker']}</td>
                    <td>${s['current_price']}</td>
                    <td style="color: {'green' if s['day_change'] > 0 else 'red'}">{s['day_change']:+.2f}%</td>
                    <td>{s['mtd_return']:+.2f}%</td>
                    <td>{s['ytd_return']:+.2f}%</td>
                    <td>{s['three_month_return']:+.2f}%</td>
                </tr>''' for s in stock_data])}
            </table>
        </body>
        </html>
        """
        
        return {
            "executive_summary": f"Portfolio tracking {len(stock_data)} stocks",
            "html_email": html_email,
            "teams_card": {}
        }
    
    def send_email(self, html_content: str, subject: str):
        """Send email via Resend or SendGrid"""
        if not self.sendgrid_api_key or not self.email_to:
            print("⚠️  Email not configured (missing SENDGRID_API_KEY or EMAIL_TO)")
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
                    "from": self.email_from or "onboarding@resend.dev",
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
                    "from": {"email": self.email_from or "stock-monitor@yourdomain.com"},
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
    
    def post_to_teams(self, teams_card: dict, summary: str):
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
        print("  AUTOMATED STOCK MONITOR")
        print("  " + datetime.now().strftime('%A, %B %d, %Y %I:%M %p'))
        print("="*60)
        
        # Fetch stock data
        stock_data = self.fetch_all_stocks()
        
        if not stock_data:
            print("❌ No stock data available. Exiting.")
            return
        
        # Fetch news
        print("📰 Fetching market news...")
        news_data = self.fetch_market_news()
        print(f"✅ Found {len(news_data)} news articles\n")
        
        # Format with Claude
        formatted_output = self.format_with_claude(stock_data, news_data)
        
        # Send email
        subject = f"📊 Daily Stock Report - {datetime.now().strftime('%b %d, %Y')}"
        self.send_email(formatted_output['html_email'], subject)
        
        # Post to Teams
        self.post_to_teams(
            formatted_output.get('teams_card', {}),
            formatted_output['executive_summary']
        )
        
        print("\n" + "="*60)
        print("✅ DAILY STOCK REPORT COMPLETE")
        print("="*60 + "\n")
        
        return formatted_output

if __name__ == "__main__":
    monitor = StockMonitor()
    monitor.run()
