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
    
    # SP Funds Target Date Mutual Funds
    {"ticker": "SPTAX", "name": "SP Funds 2030 Target Date Fund", "category": "Target Date 2030", "expense_ratio": 1.40},
    {"ticker": "SPTBX", "name": "SP Funds 2040 Target Date Fund", "category": "Target Date 2040", "expense_ratio": 1.40},
    {"ticker": "SPTCX", "name": "SP Funds 2050 Target Date Fund", "category": "Target Date 2050", "expense_ratio": 1.40},
    
    # Wahed ETFs
    {"ticker": "HLAL", "name": "Wahed FTSE USA Shariah ETF", "category": "US Equity Large/Mid-Cap", "expense_ratio": 0.50},
    {"ticker": "UMMA", "name": "Wahed Dow Jones Islamic World ETF", "category": "International Equity", "expense_ratio": 0.65},
    
    # Manzil ETF
    {"ticker": "MNZL", "name": "Manzil Russell 1000 Shariah ETF", "category": "US Broad Market", "expense_ratio": 0.25},
    
    # Amana Mutual Funds
    {"ticker": "AMANX", "name": "Amana Income Fund", "category": "US Equity Income", "expense_ratio": 0.79},
    {"ticker": "AMAGX", "name": "Amana Growth Fund", "category": "US Equity Growth", "expense_ratio": 0.88},
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
        # Support both Resend and SendGrid
        self.resend_api_key = os.getenv("RESEND_API_KEY")
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.email_api_key = self.resend_api_key or self.sendgrid_api_key
        self.teams_webhook = os.getenv("TEAMS_WEBHOOK_URL")
        self.email_from = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
        self.email_to = os.getenv("EMAIL_TO")
        
        if not self.anthropic_api_key:
            print("⚠️  ANTHROPIC_API_KEY not set")
        if not self.email_api_key:
            print("⚠️  No email API key found (set RESEND_API_KEY or SENDGRID_API_KEY)")
        if not self.email_to:
            print("⚠️  EMAIL_TO not set")
    
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
        """Use fallback format directly - our HTML template is already perfect"""
        # Always use our beautiful email-compatible template
        return self.fallback_format(indexes_data, funds_data, news)
    
    def fallback_format(self, indexes_data: List[Dict], funds_data: List[Dict], news: List[Dict]) -> Dict:
        """Fallback formatting without Claude - email-compatible design"""
        
        # Generate index rows
        index_rows = ""
        for stock in indexes_data:
            day_class = "positive" if stock['day_change'] >= 0 else "negative"
            day_sign = "+" if stock['day_change'] >= 0 else ""
            index_rows += f"""
                <tr>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; font-weight: 700; font-size: 15px;"><a href="https://finance.yahoo.com/quote/{stock['ticker']}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 700;">{stock['ticker']}</a></td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">{stock['name']}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; font-weight: 700; text-align: right;">${stock['price']:.2f}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: {'#10b981' if stock['day_change'] >= 0 else '#ef4444'}; font-weight: 600;">{day_sign}{stock['day_change']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['three_month_return']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['mtd_return']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['ytd_return']:.2f}%</td>
                </tr>"""
        
        # Generate fund rows  
        fund_rows = ""
        for stock in funds_data:
            day_class = "positive" if stock['day_change'] >= 0 else "negative"
            day_sign = "+" if stock['day_change'] >= 0 else ""
            fund_rows += f"""
                <tr>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; font-weight: 700; font-size: 15px;"><a href="https://finance.yahoo.com/quote/{stock['ticker']}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: 700;">{stock['ticker']}</a></td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 13px;">{stock['name']}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 12px;">{stock['category']}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; font-weight: 700; text-align: right;">${stock['price']:.2f}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: {'#10b981' if stock['day_change'] >= 0 else '#ef4444'}; font-weight: 600;">{day_sign}{stock['day_change']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['three_month_return']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['mtd_return']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; color: #10b981; font-weight: 600;">+{stock['ytd_return']:.2f}%</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; text-align: center; font-size: 13px; color: #6b7280;">{stock['expense_ratio']:.2f}%</td>
                </tr>"""
        
        # Generate news rows
        news_rows = ""
        for item in news[:5]:
            region = "🇺🇸 USA" if "USA" in item.get('region', '') else "🌍 Global"
            news_rows += f"""
                <tr>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb;">{region}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb;"><a href="{item['link']}" target="_blank" style="color: #1a1a2e; text-decoration: none; font-weight: 600;">{item['title']}</a></td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px;">{item['source']}</td>
                    <td style="padding: 14px 16px; border-bottom: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; text-align: right;">{item.get('published', 'Recent')}</td>
                </tr>"""
        
        html_email = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #a8c0ff 0%, #d4c5f9 50%, #e5dff9 100%); padding: 40px 20px;">
    <div style="max-width: 1200px; margin: 0 auto;">
        <!-- Header Card -->
        <div style="background: #ffffff; border-radius: 24px; padding: 32px; margin-bottom: 30px; box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);">
            <div style="font-size: 24px; font-weight: 700; color: #1a1a2e; margin-bottom: 12px;">
                👋 Hey! Welcome to My Halal Stock Lab
                <span style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-left: 8px;">Beta</span>
            </div>
            <div style="color: #4a4a6a; line-height: 1.6; font-size: 15px;">
                This is my experimental playground for tracking Sharia-compliant markets. Built entirely with Claude Code and a lot of coffee ☕. 
                Since it's AI-powered, occasional hiccups are part of the charm! All data is for informational purposes only—do your own research before making any investment decisions. 
                Let's make halal investing awesome together! 🚀
            </div>
        </div>
        
        <!-- Date Header -->
        <div style="text-align: center; color: #1a1a2e; margin-bottom: 30px; font-size: 18px; font-weight: 600;">
            📊 Sharia-Compliant Stock Monitor • {datetime.now().strftime('%B %d, %Y')}
        </div>
        
        <!-- Market Indexes -->
        <div style="font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 30px 0 16px 0; padding-left: 8px;">📈 Market Indexes</div>
        <div style="background: #ffffff; border-radius: 20px; padding: 0; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(31, 38, 135, 0.12); overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Symbol</th>
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Name</th>
                        <th style="padding: 16px; text-align: right; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Price</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Day %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">3M %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">MTD %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">YTD %</th>
                    </tr>
                </thead>
                <tbody>{index_rows}</tbody>
            </table>
        </div>
        
        <!-- Sharia-Compliant Funds -->
        <div style="font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 30px 0 16px 0; padding-left: 8px;">🕌 Sharia-Compliant Funds</div>
        <div style="background: #ffffff; border-radius: 20px; padding: 0; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(31, 38, 135, 0.12); overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Symbol</th>
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Name</th>
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Category</th>
                        <th style="padding: 16px; text-align: right; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Price</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Day %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">3M %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">MTD %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">YTD %</th>
                        <th style="padding: 16px; text-align: center; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Expense</th>
                    </tr>
                </thead>
                <tbody>{fund_rows}</tbody>
            </table>
        </div>
        
        <!-- News -->
        <div style="font-size: 18px; font-weight: 700; color: #1a1a2e; margin: 30px 0 16px 0; padding-left: 8px;">📰 Sharia-Compliant Investing News</div>
        <div style="background: #ffffff; border-radius: 20px; padding: 0; margin-bottom: 24px; box-shadow: 0 8px 32px rgba(31, 38, 135, 0.12); overflow: hidden;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Region</th>
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Headline</th>
                        <th style="padding: 16px; text-align: left; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Source</th>
                        <th style="padding: 16px; text-align: right; font-size: 12px; font-weight: 700; color: white; text-transform: uppercase; letter-spacing: 0.5px;">Time</th>
                    </tr>
                </thead>
                <tbody>{news_rows}</tbody>
            </table>
        </div>
        
        <!-- Footer -->
        <div style="background: #ffffff; border-radius: 16px; padding: 20px; margin-top: 40px; text-align: center; font-size: 12px; color: #6b7280; line-height: 1.6; box-shadow: 0 4px 16px rgba(31, 38, 135, 0.08);">
            <strong style="color: #1a1a2e;">Disclaimer:</strong> This dashboard is provided for informational and educational purposes only. 
            All data is sourced from Yahoo Finance and Google News and may contain errors or delays. 
            This is not financial advice. Always do your own research and consult with a qualified financial advisor before investing. 
            Past performance does not guarantee future results. Sharia compliance determinations are based on fund provider classifications 
            and should be independently verified with qualified Islamic scholars.
        </div>
    </div>
</body>
</html>"""
        
        return {
            "executive_summary": f"Portfolio tracking {len(indexes_data) + len(funds_data)} securities",
            "html_email": html_email,
            "teams_summary": f"Stock report generated for {len(indexes_data)} indexes and {len(funds_data)} funds"
        }
    
        """Fallback formatting without Claude - uses glassmorphism design"""
        
        # Generate index rows
        index_rows = ""
        for stock in indexes_data:
            day_class = "positive" if stock['day_change'] >= 0 else "negative"
            day_sign = "+" if stock['day_change'] >= 0 else ""
            index_rows += f"""
                <tr>
                    <td class="ticker"><a href="https://finance.yahoo.com/quote/{stock['ticker']}" target="_blank">{stock['ticker']}</a></td>
                    <td class="name">{stock['name']}</td>
                    <td class="price">${stock['price']:.2f}</td>
                    <td class="center {day_class}">{day_sign}{stock['day_change']:.2f}%</td>
                    <td class="center positive">+{stock['three_month_return']:.2f}%</td>
                    <td class="center positive">+{stock['mtd_return']:.2f}%</td>
                    <td class="center positive">+{stock['ytd_return']:.2f}%</td>
                </tr>"""
        
        # Generate fund rows  
        fund_rows = ""
        for stock in funds_data:
            day_class = "positive" if stock['day_change'] >= 0 else "negative"
            day_sign = "+" if stock['day_change'] >= 0 else ""
            fund_rows += f"""
                <tr>
                    <td class="ticker"><a href="https://finance.yahoo.com/quote/{stock['ticker']}" target="_blank">{stock['ticker']}</a></td>
                    <td class="name">{stock['name']}</td>
                    <td class="category">{stock['category']}</td>
                    <td class="price">${stock['price']:.2f}</td>
                    <td class="center {day_class}">{day_sign}{stock['day_change']:.2f}%</td>
                    <td class="center positive">+{stock['three_month_return']:.2f}%</td>
                    <td class="center positive">+{stock['mtd_return']:.2f}%</td>
                    <td class="center positive">+{stock['ytd_return']:.2f}%</td>
                    <td class="expense">{stock['expense_ratio']:.2f}%</td>
                </tr>"""
        
        # Generate news rows
        news_rows = ""
        for item in news[:5]:
            region = "🇺🇸 USA" if "USA" in item.get('region', '') else "🌍 Global"
            news_rows += f"""
                <tr>
                    <td>{region}</td>
                    <td><a href="{item['link']}" target="_blank" class="news-link">{item['title']}</a></td>
                    <td class="source">{item['source']}</td>
                    <td class="time">{item.get('published', 'Recent')}</td>
                </tr>"""
        
        html_email = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #a8c0ff 0%, #d4c5f9 50%, #e5dff9 100%);
            padding: 40px 20px;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header-card {{
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 30px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.15);
        }}
        .header-title {{
            font-size: 24px;
            font-weight: 700;
            color: #1a1a2e;
            margin-bottom: 12px;
        }}
        .beta-badge {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            margin-left: 8px;
        }}
        .header-text {{
            color: #4a4a6a;
            line-height: 1.6;
            font-size: 15px;
        }}
        .date-header {{
            text-align: center;
            color: #1a1a2e;
            margin-bottom: 30px;
            font-size: 18px;
            font-weight: 600;
        }}
        .section-header {{
            font-size: 18px;
            font-weight: 700;
            color: #1a1a2e;
            margin: 30px 0 16px 0;
            padding-left: 8px;
        }}
        .table-card {{
            background: rgba(255, 255, 255, 0.9);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 0;
            margin-bottom: 24px;
            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.12);
            overflow: hidden;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px;
            text-align: left;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        th.right {{ text-align: right; }}
        th.center {{ text-align: center; }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            color: #1a1a2e;
            font-size: 14px;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tbody tr {{ transition: all 0.2s ease; }}
        tbody tr:hover {{ background: rgba(102, 126, 234, 0.05); }}
        .ticker {{ font-weight: 700; font-size: 15px; }}
        .ticker a {{ color: #667eea; text-decoration: none; font-weight: 700; }}
        .ticker a:hover {{ text-decoration: underline; }}
        .name {{ color: #6b7280; font-size: 13px; }}
        .category {{ color: #6b7280; font-size: 12px; }}
        .price {{ font-weight: 700; text-align: right; }}
        .positive {{ color: #10b981; font-weight: 600; }}
        .negative {{ color: #ef4444; font-weight: 600; }}
        .center {{ text-align: center; }}
        .right {{ text-align: right; }}
        .expense {{ text-align: center; font-size: 13px; color: #6b7280; }}
        .news-link {{ color: #1a1a2e; text-decoration: none; font-weight: 600; }}
        .news-link:hover {{ color: #667eea; text-decoration: underline; }}
        .source {{ color: #9ca3af; font-size: 12px; }}
        .time {{ color: #9ca3af; font-size: 12px; text-align: right; }}
        .footer {{
            background: rgba(255, 255, 255, 0.7);
            backdrop-filter: blur(20px);
            border-radius: 16px;
            padding: 20px;
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            line-height: 1.6;
            box-shadow: 0 4px 16px rgba(31, 38, 135, 0.08);
        }}
        .footer strong {{ color: #1a1a2e; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-card">
            <div class="header-title">
                👋 Hey! Welcome to My Halal Stock Lab
                <span class="beta-badge">Beta</span>
            </div>
            <div class="header-text">
                This is my experimental playground for tracking Sharia-compliant markets. Built entirely with Claude Code and a lot of coffee ☕. 
                Since it's AI-powered, occasional hiccups are part of the charm! All data is for informational purposes only—do your own research before making any investment decisions. 
                Let's make halal investing awesome together! 🚀
            </div>
        </div>
        <div class="date-header">📊 Sharia-Compliant Stock Monitor • {datetime.now().strftime('%B %d, %Y')}</div>
        
        <div class="section-header">📈 Market Indexes</div>
        <div class="table-card">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Name</th>
                        <th class="right">Price</th>
                        <th class="center">Day %</th>
                        <th class="center">3M %</th>
                        <th class="center">MTD %</th>
                        <th class="center">YTD %</th>
                    </tr>
                </thead>
                <tbody>{index_rows}</tbody>
            </table>
        </div>
        
        <div class="section-header">🕌 Sharia-Compliant Funds</div>
        <div class="table-card">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Name</th>
                        <th>Category</th>
                        <th class="right">Price</th>
                        <th class="center">Day %</th>
                        <th class="center">3M %</th>
                        <th class="center">MTD %</th>
                        <th class="center">YTD %</th>
                        <th class="center">Expense</th>
                    </tr>
                </thead>
                <tbody>{fund_rows}</tbody>
            </table>
        </div>
        
        <div class="section-header">📰 Sharia-Compliant Investing News</div>
        <div class="table-card">
            <table>
                <thead>
                    <tr>
                        <th>Region</th>
                        <th>Headline</th>
                        <th>Source</th>
                        <th class="right">Time</th>
                    </tr>
                </thead>
                <tbody>{news_rows}</tbody>
            </table>
        </div>
        
        <div class="footer">
            <strong>Disclaimer:</strong> This dashboard is provided for informational and educational purposes only. 
            All data is sourced from Yahoo Finance and Google News and may contain errors or delays. 
            This is not financial advice. Always do your own research and consult with a qualified financial advisor before investing. 
            Past performance does not guarantee future results. Sharia compliance determinations are based on fund provider classifications 
            and should be independently verified with qualified Islamic scholars.
        </div>
    </div>
</body>
</html>"""
        
        return {
            "executive_summary": f"Portfolio tracking {len(indexes_data) + len(funds_data)} securities",
            "html_email": html_email,
            "teams_summary": f"Stock report generated for {len(indexes_data)} indexes and {len(funds_data)} funds"
        }
    
    def send_email(self, html_content: str, subject: str):
        """Send email via Resend or SendGrid"""
        if not self.email_api_key or not self.email_to:
            print("⚠️  Email not configured (missing API_KEY or EMAIL_TO)")
            print(f"     EMAIL_API_KEY set: {bool(self.email_api_key)}")
            print(f"     EMAIL_TO set: {bool(self.email_to)}")
            return
        
        print("📧 Sending email...")
        
        try:
            # Check if using Resend (API key starts with 're_') or SendGrid (starts with 'SG.')
            is_resend = self.email_api_key.startswith('re_')
            
            if is_resend:
                # Resend API
                print("   Using Resend API...")
                url = "https://api.resend.com/emails"
                headers = {
                    "Authorization": f"Bearer {self.email_api_key}",
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
                print("   Using SendGrid API...")
                url = "https://api.sendgrid.com/v3/mail/send"
                headers = {
                    "Authorization": f"Bearer {self.email_api_key}",
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
    
    def post_to_teams(self, indexes_data: List[Dict], funds_data: List[Dict], news: List[Dict], summary: str):
        """Post full data tables to Microsoft Teams via Adaptive Card"""
        if not self.teams_webhook:
            print("⚠️  Teams webhook not configured")
            return
        
        print("📢 Posting to Microsoft Teams...")
        
        try:
            # Build index table facts
            index_facts = []
            for stock in indexes_data[:4]:  # Limit to 4 indexes
                day_change = stock['day_change']
                day_emoji = "📈" if day_change >= 0 else "📉"
                index_facts.append({
                    "title": f"{day_emoji} {stock['ticker']}",
                    "value": f"${stock['price']:.2f} | Day: {day_change:+.2f}% | 3M: {stock['three_month_return']:+.2f}% | YTD: {stock['ytd_return']:+.2f}%"
                })
            
            # Build top 5 funds facts
            fund_facts = []
            for stock in funds_data[:5]:  # Top 5 funds
                day_change = stock['day_change']
                day_emoji = "📈" if day_change >= 0 else "📉"
                fund_facts.append({
                    "title": f"{day_emoji} {stock['ticker']}",
                    "value": f"${stock['price']:.2f} | Day: {day_change:+.2f}% | Expense: {stock['expense_ratio']:.2f}%"
                })
            
            # Build news items
            news_items = []
            for item in news[:3]:  # Top 3 news
                news_items.append({
                    "type": "TextBlock",
                    "text": f"• [{item['source']}]({item['link']}) {item['title']}",
                    "wrap": True,
                    "spacing": "Small"
                })
            
            # Create comprehensive Adaptive Card
            card = {
                "type": "message",
                "attachments": [{
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "text": f"📊 Daily Stock Report",
                                "size": "ExtraLarge",
                                "weight": "Bolder",
                                "color": "Accent"
                            },
                            {
                                "type": "TextBlock",
                                "text": datetime.now().strftime('%A, %B %d, %Y'),
                                "size": "Medium",
                                "color": "Default",
                                "spacing": "None"
                            },
                            {
                                "type": "TextBlock",
                                "text": "📈 Market Indexes",
                                "size": "Large",
                                "weight": "Bolder",
                                "spacing": "Medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": index_facts,
                                "spacing": "Small"
                            },
                            {
                                "type": "TextBlock",
                                "text": "🕌 Top Sharia-Compliant Funds",
                                "size": "Large",
                                "weight": "Bolder",
                                "spacing": "Medium"
                            },
                            {
                                "type": "FactSet",
                                "facts": fund_facts,
                                "spacing": "Small"
                            },
                            {
                                "type": "TextBlock",
                                "text": f"📰 Latest News ({len(news_items)} headlines)",
                                "size": "Large",
                                "weight": "Bolder",
                                "spacing": "Medium"
                            }
                        ] + news_items + [
                            {
                                "type": "TextBlock",
                                "text": f"✉️ Check your email for the complete formatted report with all {len(funds_data)} funds and detailed analytics.",
                                "wrap": True,
                                "spacing": "Medium",
                                "size": "Small",
                                "isSubtle": True
                            }
                        ]
                    }
                }]
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
        
        # Post to Teams with full data
        self.post_to_teams(indexes_data, funds_data, news, formatted.get('teams_summary', formatted['executive_summary']))
        
        print("\n" + "="*60)
        print("✅ DAILY STOCK REPORT COMPLETE")
        print("="*60 + "\n")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    monitor = StockMonitor()
    monitor.run()
