import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
from datetime import date

from database import init_db, get_scan_time
from scanner import run_scan, run_backfill, is_market_closed
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
    st.header("Ayarlar")

    if st.button("Tarama Yap", type="primary", width="stretch"):
        with st.status("BIST semollleri taraniyor...", expanded=True) as status:
            st.write("Tam tarama yapiliyor. Ilk calistirmada birkaç dakika surebilir...")
            try:
                run_scan()
                status.update(label="Tarama tamamlandi!", state="complete")
            except Exception as e:
                status.update(label=f"Tarama basarisiz: {e}", state="error")
        st.cache_data.clear()
        st.rerun()

    if is_market_closed():
        st.caption("Piyasa kapali — bugunun kapanmis mumlari dahil ediliyor")
    else:
        st.caption("Piyasa acik — bugunun mumu atlanıyor, sadece kapanmis mumlar taraniyor")

    last_scan = get_scan_time()
    if last_scan:
        from datetime import datetime
        scan_dt = datetime.fromisoformat(last_scan)
        st.caption(f"Son tarama: {scan_dt.strftime('%d.%m.%Y %H:%M')}")
    else:
        st.caption("Son tarama: —")

    if st.button("Gecmis Taramasi (Backfill)", width="stretch"):
        with st.status("Gecmis sinyaller taraniyor...", expanded=True) as status:
            def update_progress(current, total):
                st.write(f"  {current}/{total} sembol isleniyor...")
            try:
                result = run_backfill(progress_callback=update_progress)
                if result:
                    status.update(
                        label=f"Backfill tamamlandi! {result['total']} sinyal bulundu ({result['buy']} ALIS, {result['sell']} SATIS)",
                        state="complete",
                    )
                else:
                    status.update(label="Backfill tamamlandi ama sinyal bulunamadi.", state="complete")
            except Exception as e:
                status.update(label=f"Backfill basarisiz: {e}", state="error")
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Strateji Parametreleri")

    ema_fast = st.slider("EMA Hizli", 5, 20, EMA_FAST)
    ema_slow = st.slider("EMA Yavas", 15, 50, EMA_SLOW)
    near_pct = st.slider("Yakin Kesisim Toleransi (%)", 0.10, 1.0, NEAR_CROSS_PCT, step=0.05)

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

    if st.button("Varsayilanlara Don", width="stretch"):
        st.rerun()

st.divider()

today_str = date.today().strftime("%Y-%m-%d")
all_signals_df = load_signals_df(all_signals=True)
today_signals_df = load_signals_df(all_signals=False)

market_closed = is_market_closed()

if market_closed:
    tab_today, tab_history, tab_chart = st.tabs(["Bugunun Sinyalleri", "Sinyal Gecmisi", "Grafikler"])
else:
    tab_today, tab_history, tab_chart = st.tabs(["Son Kapanan Sinyaller", "Sinyal Gecmisi", "Grafikler"])

with tab_today:
    if market_closed:
        st.subheader(f"Bugunun Sinyalleri — {today_str}")
    else:
        st.subheader("Son Kapanan Sinyaller (Dun)")

    if today_signals_df.empty:
        st.info("Sinyal bulunamadi. Tarama yapin veya daha sonra kontrol edin.")
    else:
        if market_closed:
            st.metric("Toplam Sinyal", len(today_signals_df))
        else:
            st.metric("Dunun Sinyalleri", len(today_signals_df))
        render_signal_table(today_signals_df, key="today")

with tab_history:
    st.subheader("Sinyal Gecmisi")

    if all_signals_df.empty:
        st.info("Henuz sinyal gecmisi yok. Once bir tarama yapin.")
    else:
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            signal_filter = st.multiselect(
                "Sinyal Tipi", ["BUY", "SELL"], default=["BUY", "SELL"], key="hist_type"
            )
        with col2:
            from datetime import datetime, timedelta
            default_end = date.today()
            default_start = default_end - timedelta(days=30)
            date_range = st.date_input(
                "Tarih Araligi",
                value=(default_start, default_end),
                min_value=date(2020, 1, 1),
                max_value=default_end,
                key="hist_date",
            )
        with col3:
            symbol_search = st.text_input("Sembol Ara", key="hist_search")

        filtered = all_signals_df[
            all_signals_df["signal_type"].isin(signal_filter)
        ]
        if symbol_search:
            filtered = filtered[
                filtered["symbol"].str.contains(symbol_search.upper(), case=False)
            ]

        if "signal_date" in filtered.columns:
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start, end = date_range
                filtered = filtered[
                    (filtered["signal_date"] >= start.strftime("%Y-%m-%d"))
                    & (filtered["signal_date"] <= end.strftime("%Y-%m-%d"))
                ]
            elif isinstance(date_range, date):
                filtered = filtered[
                    filtered["signal_date"] == date_range.strftime("%Y-%m-%d")
                ]

        st.metric("Toplam Sinyal", len(filtered))
        render_signal_table(filtered, key="history")

with tab_chart:
    st.subheader("Grafik")

    symbols = get_cached_symbols_list()
    if not symbols:
        st.info("Veri bulunamadi. Once bir tarama yapin.")
    else:
        selected = st.selectbox("Sembol Sec", symbols, key="chart_symbol")

        if selected:
            result = compute_stock_chart(
                selected, ema_fast, ema_slow,
                macd_fast, macd_slow, macd_signal,
                rsi_period, rsi_buy, rsi_sell,
                dmi_period, adx_min, near_pct,
            )

            if result is None:
                st.warning(f"{selected} icin yeterli veri yok. En az 50 mum gerekli.")
            else:
                signal_info = result["signal"]
                if signal_info:
                    sig_type, sig_close = signal_info
                    if sig_type == "BUY":
                        st.success(f"**ALIS** sinyali — {selected} @ {sig_close:.2f}")
                    else:
                        st.error(f"**SATIS** sinyali — {selected} @ {sig_close:.2f}")
                else:
                    st.info(f"{selected} icin su an sinyal yok.")

                last = result["last"]
                c1, c2, c3, c4, c5 = st.columns(5)
                c1.metric("Kapanis", f"{last['close']:.2f}")
                c2.metric("RSI", f"{last['rsi']:.1f}")
                c3.metric("ADX", f"{last['adx']:.1f}")
                c4.metric("+DI / -DI", f"{last['plus_di']:.1f} / {last['minus_di']:.1f}")
                c5.metric("MACD Hist", f"{last['macd_hist']:.4f}")

                all_sigs = result["all_signals"]
                if all_sigs:
                    buys = sum(1 for s in all_sigs if s[1] == "BUY")
                    sells = sum(1 for s in all_sigs if s[1] == "SELL")
                    st.caption(f"Gecmis sinyaller: {len(all_sigs)} toplam ({buys} ALIS, {sells} SATIS)")

                pc = result["price_change"]
                if pc:
                    arrow = "↑" if pc["pct"] >= 0 else "↓"
                    color = "normal" if pc["pct"] >= 0 else "inverse"
                    if pc["from_type"] == "BUY":
                        label = f"ALIS ({pc['from_date']}) → SATIS ({pc['to_date']})"
                    else:
                        label = f"SATIS ({pc['from_date']}) → ALIS ({pc['to_date']})"
                    st.metric(
                        label=label,
                        value=f"{pc['to_price']:.2f} TL",
                        delta=f"{pc['pct']:+.1f}% ({pc['from_price']:.2f} → {pc['to_price']:.2f})",
                        delta_color=color,
                    )

                st.plotly_chart(result["figure"], width="stretch")
