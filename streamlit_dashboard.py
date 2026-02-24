import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# Page config
st.set_page_config(
    page_title="Sharia-Compliant Stock Monitor",
    page_icon="📊",
    layout="wide"
)

# ============================================================================
# CONFIGURATION  
# ============================================================================

# Market Indexes
INDEXES = [
    {"ticker": "SPY", "name": "S&P 500", "category": "Index"},
    {"ticker": "QQQ", "name": "Nasdaq 100", "category": "Index"},
    {"ticker": "DIA", "name": "Dow Jones", "category": "Index"},
    {"ticker": "IWM", "name": "Russell 2000", "category": "Index"},
]

# Sharia-Compliant Funds
FUNDS = [
    # SP Funds ETFs
    {"ticker": "SPUS", "name": "SP Funds S&P 500 Sharia", "category": "US Equity Large-Cap", "expense_ratio": 0.49},
    {"ticker": "SPSK", "name": "SP Funds Global Sukuk", "category": "Fixed Income", "expense_ratio": 0.55},
    {"ticker": "SPRE", "name": "SP Funds Global REIT Sharia", "category": "Real Estate", "expense_ratio": 0.59},
    {"ticker": "SPTE", "name": "SP Funds Global Technology", "category": "Technology", "expense_ratio": 0.55},
    {"ticker": "SPWO", "name": "SP Funds World ex-US", "category": "International Equity", "expense_ratio": 0.55},
    
    # Wahed ETFs
    {"ticker": "HLAL", "name": "Wahed FTSE USA Shariah", "category": "US Equity", "expense_ratio": 0.50},
    {"ticker": "UMMA", "name": "Wahed Islamic World", "category": "International Equity", "expense_ratio": 0.65},
    
    # Manzil
    {"ticker": "MNZL", "name": "Manzil Russell Halal USA", "category": "US Broad Market", "expense_ratio": 0.25},
    
    # Amana Mutual Funds
    {"ticker": "AMANX", "name": "Amana Income Fund", "category": "US Equity Income", "expense_ratio": 0.79},
    {"ticker": "AMAGX", "name": "Amana Growth Fund", "category": "US Equity Growth", "expense_ratio": 0.88},
]

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_stock_data(ticker, metadata):
    """Fetch stock data with returns calculation"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        if not current_price:
            return None
        
        # Get historical data
        hist = stock.history(period="1y")
        if hist.empty:
            return None
        
        # Calculate returns
        today = datetime.now()
        month_ago = today - timedelta(days=30)
        three_months_ago = today - timedelta(days=90)
        year_start = datetime(today.year, 1, 1)
        
        hist_month = hist[hist.index >= pd.Timestamp(month_ago, tz=hist.index.tz)]
        hist_3m = hist[hist.index >= pd.Timestamp(three_months_ago, tz=hist.index.tz)]
        hist_ytd = hist[hist.index >= pd.Timestamp(year_start, tz=hist.index.tz)]
        
        mtd_return = ((current_price / hist_month['Close'].iloc[0]) - 1) * 100 if len(hist_month) > 0 else 0
        three_month_return = ((current_price / hist_3m['Close'].iloc[0]) - 1) * 100 if len(hist_3m) > 0 else 0
        ytd_return = ((current_price / hist_ytd['Close'].iloc[0]) - 1) * 100 if len(hist_ytd) > 0 else 0
        day_change = info.get('regularMarketChangePercent', 0)
        
        return {
            "Symbol": ticker,
            "Name": metadata.get("name", ticker),
            "Category": metadata.get("category", "N/A"),
            "Price": f"${current_price:.2f}",
            "Day %": day_change,
            "3M %": three_month_return,
            "MTD %": mtd_return,
            "YTD %": ytd_return,
            "Expense Ratio": f"{metadata.get('expense_ratio', 0):.2f}%" if metadata.get('expense_ratio') else "—",
        }
    except Exception as e:
        st.error(f"Error fetching {ticker}: {e}")
        return None

def load_all_data():
    """Load data for all indexes and funds"""
    indexes_data = []
    funds_data = []
    
    # Load indexes
    for item in INDEXES:
        data = fetch_stock_data(item["ticker"], item)
        if data:
            data["Expense Ratio"] = "—"  # Indexes don't have expense ratios
            indexes_data.append(data)
    
    # Load funds
    for item in FUNDS:
        data = fetch_stock_data(item["ticker"], item)
        if data:
            funds_data.append(data)
    
    return indexes_data, funds_data

# ============================================================================
# UI
# ============================================================================

st.title("📊 Sharia-Compliant Stock Monitor")
st.caption(f"Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

# Load data
with st.spinner("Loading market data..."):
    indexes_data, funds_data = load_all_data()

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

total_securities = len(indexes_data) + len(funds_data)
avg_change = sum([d["Day %"] for d in indexes_data + funds_data]) / total_securities if total_securities > 0 else 0
gainers = sum(1 for d in indexes_data + funds_data if d["Day %"] > 0)
losers = sum(1 for d in indexes_data + funds_data if d["Day %"] < 0)

col1.metric("Total Securities", total_securities)
col2.metric("Average Day Change", f"{avg_change:.2f}%", delta=f"{avg_change:.2f}%")
col3.metric("Gainers", gainers, delta=gainers)
col4.metric("Losers", losers, delta=-losers, delta_color="inverse")

st.divider()

# Market Indexes Section
st.header("📈 Market Indexes")
if indexes_data:
    df_indexes = pd.DataFrame(indexes_data)
    
    # Style the dataframe
    def color_negative_red(val):
        if isinstance(val, str) and '%' in val:
            return ''
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        return f'color: {color}'
    
    styled_indexes = df_indexes.style.applymap(
        color_negative_red, 
        subset=['Day %', '3M %', 'MTD %', 'YTD %']
    ).format({
        'Day %': '{:.2f}%',
        '3M %': '{:.2f}%',
        'MTD %': '{:.2f}%',
        'YTD %': '{:.2f}%'
    })
    
    st.dataframe(styled_indexes, use_container_width=True, hide_index=True)
else:
    st.warning("No index data available")

st.divider()

# Sharia-Compliant Funds Section
st.header("🕌 Sharia-Compliant Funds")
if funds_data:
    df_funds = pd.DataFrame(funds_data)
    
    styled_funds = df_funds.style.applymap(
        color_negative_red,
        subset=['Day %', '3M %', 'MTD %', 'YTD %']
    ).format({
        'Day %': '{:.2f}%',
        '3M %': '{:.2f}%',
        'MTD %': '{:.2f}%',
        'YTD %': '{:.2f}%'
    })
    
    st.dataframe(styled_funds, use_container_width=True, hide_index=True)
    
    # Download button
    csv = df_funds.to_csv(index=False)
    st.download_button(
        label="📥 Download as CSV",
        data=csv,
        file_name=f"sharia_funds_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
else:
    st.warning("No fund data available")

# Auto-refresh
if st.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Footer
st.divider()
st.caption("Data provided by Yahoo Finance. Not financial advice. For informational purposes only.")
