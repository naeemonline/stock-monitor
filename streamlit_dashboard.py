"""
Minimalist Stock Dashboard - Streamlit Interface
Clean tables, simple charts, real-time data
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.graph_objects as go

# Page configuration
st.set_page_config(
    page_title="Stock Monitor Dashboard",
    page_icon="📊",
    layout="wide"
)

# Same tickers as in stock_monitor.py
TICKERS = [
    "SPY", "QQQ", "DIA", "INX", "IXIC", "DJI",
    
    # Your stocks - ADD YOUR 25-30 TICKERS HERE
    "SPUS", "SPSK", "SPRE", "SPTE", "SPWO", "HLAL", "UMMA", "AMAP",
    "ISWD", "ISDE", "ISUS", "WSHR", "IGDA", "HIUA", "HIES", "MWLV",

]

# Custom CSS for minimalist design
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stDataFrame {
        font-size: 14px;
    }
    h1 {
        font-weight: 300;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 4px;
        border-left: 3px solid #0078D4;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_stock_data(tickers):
    """Fetch data for all stocks"""
    data = []
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            
            if hist.empty:
                continue
            
            current_price = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
            
            # Calculate returns
            today = datetime.now()
            month_ago = today - timedelta(days=30)
            three_months_ago = today - timedelta(days=90)
            year_start = datetime(today.year, 1, 1)
            
            hist_month = hist[hist.index >= pd.Timestamp(month_ago)]
            hist_3m = hist[hist.index >= pd.Timestamp(three_months_ago)]
            hist_ytd = hist[hist.index >= pd.Timestamp(year_start)]
            
            day_change = ((current_price - prev_close) / prev_close * 100)
            mtd_return = ((current_price - hist_month['Close'].iloc[0]) / hist_month['Close'].iloc[0] * 100) if len(hist_month) > 0 else 0
            three_m_return = ((current_price - hist_3m['Close'].iloc[0]) / hist_3m['Close'].iloc[0] * 100) if len(hist_3m) > 0 else 0
            ytd_return = ((current_price - hist_ytd['Close'].iloc[0]) / hist_ytd['Close'].iloc[0] * 100) if len(hist_ytd) > 0 else 0
            
            info = stock.info
            
            data.append({
                'Ticker': ticker,
                'Name': info.get('longName', ticker)[:30],
                'Price': f"${current_price:.2f}",
                'Day %': f"{day_change:+.2f}%",
                'MTD %': f"{mtd_return:+.2f}%",
                'YTD %': f"{ytd_return:+.2f}%",
                '3M %': f"{three_m_return:+.2f}%",
                'Sector': info.get('sector', 'N/A'),
                'day_change_num': day_change  # For sorting
            })
        except:
            continue
    
    return pd.DataFrame(data)

def color_negative_red(val):
    """Color negative values red, positive green"""
    if isinstance(val, str) and '%' in val:
        num = float(val.replace('%', '').replace('+', ''))
        color = '#00AA00' if num > 0 else '#DD0000' if num < 0 else '#666666'
        return f'color: {color}; font-weight: 500'
    return ''

# Main app
st.title("📊 Stock Monitor Dashboard")
st.caption(f"Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

# Load data
with st.spinner('Loading stock data...'):
    df = fetch_stock_data(TICKERS)

if df.empty:
    st.error("Could not load stock data. Please try again later.")
    st.stop()

# Summary metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Stocks", len(df))

with col2:
    gainers = len(df[df['day_change_num'] > 0])
    st.metric("Gainers", gainers, delta=f"{gainers/len(df)*100:.0f}%")

with col3:
    losers = len(df[df['day_change_num'] < 0])
    st.metric("Losers", losers, delta=f"-{losers/len(df)*100:.0f}%", delta_color="inverse")

with col4:
    avg_change = df['day_change_num'].mean()
    st.metric("Avg Change", f"{avg_change:+.2f}%", delta=f"{avg_change:+.2f}%")

st.markdown("---")

# Main data table
st.subheader("Portfolio Overview")

# Display styled dataframe
display_df = df.drop('day_change_num', axis=1)
styled_df = display_df.style.applymap(color_negative_red, subset=['Day %', 'MTD %', 'YTD %', '3M %'])

st.dataframe(
    styled_df,
    use_container_width=True,
    height=600,
    hide_index=True
)

# Download button
csv = display_df.to_csv(index=False)
st.download_button(
    label="📥 Download CSV",
    data=csv,
    file_name=f"stock_data_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv"
)

# Footer
st.markdown("---")
st.caption("Data provided by Yahoo Finance | Auto-refreshes every 5 minutes")
