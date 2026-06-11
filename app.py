import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
from datetime import date

from database import init_db
from scanner import run_scan
from ui.cache import load_signals_df, get_cached_symbols_list, compute_stock_chart
from ui.tables import render_signal_table
from config import (
    EMA_FAST, EMA_SLOW, NEAR_CROSS_PCT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    RSI_PERIOD, RSI_BUY_LEVEL, RSI_SELL_LEVEL,
    DMI_PERIOD, ADX_MIN,
)

st.set_page_config(page_title="BIST-SCANNER", layout="wide")
st.title("BIST-SCANNER")

init_db()

with st.sidebar:
    st.header("Settings")

    if st.button("Run Scan", type="primary", use_container_width=True):
        with st.status("Scanning BIST symbols...", expanded=True) as status:
            st.write("Running full scan. This may take a few minutes on first run...")
            try:
                run_scan()
                status.update(label="Scan complete!", state="complete")
            except Exception as e:
                status.update(label=f"Scan failed: {e}", state="error")
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Strategy Parameters")

    ema_fast = st.slider("EMA Fast", 5, 20, EMA_FAST)
    ema_slow = st.slider("EMA Slow", 15, 50, EMA_SLOW)
    near_pct = st.slider("Near-Cross Tolerance (%)", 0.10, 1.0, NEAR_CROSS_PCT, step=0.05)

    st.caption("MACD")
    macd_fast = st.slider("MACD Fast", 5, 20, MACD_FAST)
    macd_slow = st.slider("MACD Slow", 10, 30, MACD_SLOW)
    macd_signal = st.slider("MACD Signal", 3, 15, MACD_SIGNAL)

    st.caption("RSI")
    rsi_period = st.slider("RSI Period", 5, 30, RSI_PERIOD)
    rsi_buy = st.slider("RSI Buy Level (>)", 30.0, 60.0, RSI_BUY_LEVEL, step=0.5)
    rsi_sell = st.slider("RSI Sell Level (<)", 40.0, 70.0, RSI_SELL_LEVEL, step=0.5)

    st.caption("DMI / ADX")
    dmi_period = st.slider("DMI Period", 2, 20, DMI_PERIOD)
    adx_min = st.slider("ADX Min", 10.0, 40.0, ADX_MIN, step=1.0)

    if st.button("Reset Defaults", use_container_width=True):
        st.rerun()

st.divider()

today_str = date.today().strftime("%Y-%m-%d")
all_signals_df = load_signals_df(all_signals=True)
today_signals_df = load_signals_df(all_signals=False)

tab_today, tab_history, tab_chart = st.tabs(["Today's Signals", "Signal History", "Charts"])

with tab_today:
    st.subheader(f"Today's Signals — {today_str}")
    if today_signals_df.empty:
        st.info("No signals generated today. Run a scan or check back later.")
    else:
        st.metric("Signals Today", len(today_signals_df))
        render_signal_table(today_signals_df, key="today")

with tab_history:
    st.subheader("Signal History")

    if all_signals_df.empty:
        st.info("No signal history yet. Run a scan first.")
    else:
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            signal_filter = st.multiselect(
                "Signal Type", ["BUY", "SELL"], default=["BUY", "SELL"], key="hist_type"
            )
        with col2:
            if "signal_date" in all_signals_df.columns:
                dates = pd.to_datetime(all_signals_df["signal_date"]).dt.date
                min_date = dates.min()
                max_date = dates.max()
                date_range = st.date_input(
                    "Date Range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date,
                    key="hist_date",
                )
        with col3:
            symbol_search = st.text_input("Search Symbol", key="hist_search")

        filtered = all_signals_df[
            all_signals_df["signal_type"].isin(signal_filter)
        ]
        if symbol_search:
            filtered = filtered[
                filtered["symbol"].str.contains(symbol_search.upper(), case=False)
            ]
        if "signal_date" in filtered.columns and len(date_range) == 2:
            start, end = date_range
            filtered = filtered[
                (filtered["signal_date"] >= start.strftime("%Y-%m-%d"))
                & (filtered["signal_date"] <= end.strftime("%Y-%m-%d"))
            ]

        st.metric("Total Signals", len(filtered))
        render_signal_table(filtered, key="history")

with tab_chart:
    st.subheader("Stock Chart")

    symbols = get_cached_symbols_list()
    if not symbols:
        st.info("No data cached. Run a scan first.")
    else:
        selected = st.selectbox("Select Symbol", symbols, key="chart_symbol")

        if selected:
            result = compute_stock_chart(
                selected, ema_fast, ema_slow,
                macd_fast, macd_slow, macd_signal,
                rsi_period, rsi_buy, rsi_sell,
                dmi_period, adx_min, near_pct,
            )

            if result is None:
                st.warning(f"Not enough data for {selected}. Need at least 50 bars.")
            else:
                signal_info = result["signal"]
                if signal_info:
                    sig_type, sig_close = signal_info
                    if sig_type == "BUY":
                        st.success(f"**BUY signal** for {selected} at {sig_close:.2f}")
                    else:
                        st.error(f"**SELL signal** for {selected} at {sig_close:.2f}")
                else:
                    st.info(f"No signal for {selected} today.")

                last = result["last"]
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Close", f"{last['close']:.2f}")
                c2.metric("RSI", f"{last['rsi']:.1f}")
                c3.metric("ADX", f"{last['adx']:.1f}")
                c4.metric("+DI / -DI", f"{last['plus_di']:.1f} / {last['minus_di']:.1f}")
                c5.metric("MACD Hist", f"{last['macd_hist']:.4f}")

                all_sigs = result["all_signals"]
                if all_sigs:
                    buys = sum(1 for s in all_sigs if s[1] == "BUY")
                    sells = sum(1 for s in all_sigs if s[1] == "SELL")
                    st.caption(f" historical signals: {len(all_sigs)} total ({buys} BUY, {sells} SELL)")

                st.plotly_chart(result["figure"], use_container_width=True)
