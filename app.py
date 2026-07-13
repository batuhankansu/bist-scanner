import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
from datetime import date

from database import init_db, get_scan_time, get_latest_signal_date
from scanner import run_scan, run_backfill, is_market_closed
from ui.cache import load_signals_df, get_cached_symbols_list, compute_stock_chart, compute_accumulation_for_symbol
from data_fetcher import fetch_live_data
from ui.tables import render_signal_table, render_signal_table_selectable
from tv_data import fetch_candles_from_tv
from mfi_strategy import detect_accumulation_signal
from indicators import compute_accumulation_indicators
from config import (
    EMA_FAST, EMA_SLOW, NEAR_CROSS_PCT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    RSI_PERIOD, RSI_BUY_LEVEL, RSI_SELL_LEVEL,
    DMI_PERIOD, ADX_MIN, today_str,
)

st.set_page_config(page_title="BIST-SCANNER", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("BIST-SCANNER")
    st.caption("Giris yapin")

    with st.form("login_form"):
        username = st.text_input("Kullanici Adi")
        password = st.text_input("Sifre", type="password")
        submitted = st.form_submit_button("Giris Yap", type="primary", width="stretch")

    if submitted:
        from users import USERS
        if username in USERS and USERS[username] == password:
            st.session_state.authenticated = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("Kullanici adi veya sifre hatali.")
    st.stop()

st.title("BIST-SCANNER")

with st.sidebar:
    st.caption(f"Giris yapan: {st.session_state.username}")
    if st.button("Cikis Yap"):
        st.session_state.authenticated = False
        if "username" in st.session_state:
            del st.session_state.username
        st.rerun()

try:
    init_db()
except Exception as e:
    st.error(f"Veritabani hatasi: {e}")

market_closed = is_market_closed()

if market_closed:
    tab_labels = ["Bugunun Sinyalleri", "Sinyal Gecmisi", "Grafikler", "Birikim Taramasi", "Anlik Birikim (TV)"]
else:
    tab_labels = ["Son Kapanan Sinyaller", "Sinyal Gecmisi", "Grafikler", "Birikim Taramasi", "Anlik Birikim (TV)"]

if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "chart_symbol" not in st.session_state:
    st.session_state.chart_symbol = None

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

    if market_closed:
        st.caption("Piyasa kapali — bugunun kapanmis mumlari dahil ediliyor")
    else:
        st.caption("Piyasa acik — bugunun mumu atlanıyor, sadece kapanmis mumlar taraniyor")

    last_scan = get_scan_time()
    if last_scan:
        from datetime import datetime
        scan_dt = datetime.fromisoformat(last_scan)
        st.caption(f"Son tarama: {scan_dt.strftime('%d/%m/%Y %H:%M')}")
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

all_signals_df = load_signals_df(all_signals=True)
today_signals_df = load_signals_df(all_signals=False)

if "pending_tab" in st.session_state:
    st.session_state["seg_tab"] = tab_labels[st.session_state.pending_tab]
    st.session_state.active_tab = st.session_state.pending_tab
    del st.session_state.pending_tab

active_tab = st.segmented_control(
    "Sekmeler",
    tab_labels,
    default=tab_labels[st.session_state.active_tab],
    selection_mode="single",
    label_visibility="collapsed",
    key="seg_tab",
)

if active_tab and active_tab in tab_labels:
    new_idx = tab_labels.index(active_tab)
    if new_idx != st.session_state.active_tab:
        st.session_state.active_tab = new_idx

if tab_labels[st.session_state.active_tab] == tab_labels[0]:
    latest_date = get_latest_signal_date() or today_str()
    if market_closed:
        st.subheader(f"Bugunun Sinyalleri — {latest_date}")
    else:
        st.subheader("Son Kapanan Sinyaller (Dun)")

    if today_signals_df.empty:
        st.info("Sinyal bulunamadi. Tarama yapin veya daha sonra kontrol edin.")
    else:
        if market_closed:
            st.metric("Toplam Sinyal", len(today_signals_df))
        else:
            st.metric("Dunun Sinyalleri", len(today_signals_df))

        selected_row = render_signal_table_selectable(today_signals_df, key="today")

        if selected_row is not None:
            st.session_state.chart_symbol = selected_row["symbol"]
            st.session_state.pending_tab = 2
            st.rerun()

if tab_labels[st.session_state.active_tab] == tab_labels[1]:
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
            from config import BIST_TZ
            default_end = datetime.now(BIST_TZ).date()
            default_start = default_end - timedelta(days=3)
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
        selected_row = render_signal_table_selectable(filtered, key="history")

        if selected_row is not None:
            st.session_state.chart_symbol = selected_row["symbol"]
            st.session_state.pending_tab = 2
            st.rerun()

elif tab_labels[st.session_state.active_tab] == tab_labels[2]:
    st.subheader("Grafik")

    symbols = get_cached_symbols_list()
    if not symbols:
        st.info("Veri bulunamadi. Once bir tarama yapin.")
    else:
        chart_sym = st.session_state.get("chart_symbol")
        default_idx = 0
        if chart_sym and chart_sym in symbols:
            default_idx = symbols.index(chart_sym)
        col_sel, col_tv = st.columns([4, 1])
        with col_sel:
            selected = st.selectbox("Sembol Sec", symbols, index=default_idx, key="chart_symbol")
        with col_tv:
            if selected:
                tv_url = f"https://www.tradingview.com/chart/?symbol=BIST:{selected}"
                st.markdown(
                    f'<a href="{tv_url}" target="_blank" '
                    'style="display:inline-block;width:100%;padding:0.5rem 1rem;'
                    'background-color:#000;color:#fff;text-align:center;'
                    'border-radius:0.5rem;text-decoration:none;font-weight:600;'
                    'border:1px solid #444;">TradingView ile Aç</a>',
                    unsafe_allow_html=True,
                )

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
                    sig_type, _, sig_close = signal_info
                    if sig_type == "BUY":
                        st.success(f"**ALIS** sinyali — {selected} @ {sig_close:.2f}")
                    else:
                        st.error(f"**SATIS** sinyali — {selected} @ {sig_close:.2f}")
                else:
                    st.info(f"{selected} icin su an sinyal yok.")

                last = result["last"]
                dc = result["daily_change"]
                if dc:
                    c0, c1, c2, c3, c4 = st.columns(5)
                    c0.metric(
                        "Gunluk",
                        f"{dc['curr_close']:.2f}",
                        delta=f"{dc['pct']:+.2f}% ({dc['prev_close']:.2f} → {dc['curr_close']:.2f})",
                    )
                else:
                    c0, c1, c2, c3, c4 = st.columns(5)
                    c0.metric("Kapanis", f"{last['close']:.2f}")
                c1.metric("RSI", f"{last['rsi']:.1f}")
                c2.metric("ADX", f"{last['adx']:.1f}")
                c3.metric("+DI / -DI", f"{last['plus_di']:.1f} / {last['minus_di']:.1f}")
                c4.metric("MACD Hist", f"{last['macd_hist']:.4f}")

                all_sigs = result["all_signals"]
                if all_sigs:
                    buys = sum(1 for s in all_sigs if s[1] == "BUY")
                    sells = sum(1 for s in all_sigs if s[1] == "SELL")
                    st.caption(f"Gecmis sinyaller: {len(all_sigs)} toplam ({buys} ALIS, {sells} SATIS)")

                st.plotly_chart(result["figure"], width="stretch")

elif tab_labels[st.session_state.active_tab] == tab_labels[3]:
    st.subheader("Birikim Taramasi")
    st.caption("MFI, CMF, ADX, RSI, EMA20 ve Hacim kosullarini es zamanli kontrol eder")

    symbols = get_cached_symbols_list()
    if not symbols:
        st.info("Veri bulunamadi. Once bir tarama yapin.")
    else:
        with st.form("accum_scan_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                min_score = st.slider("Minimum Kosul Sayisi", 1, 7, 7, help="Kac kosulun ayni anda saglanacagi")
            with col2:
                symbol_filter = st.text_input("Sembol Filtrele (opsiyonel)", key="acc_filter")
            with col3:
                use_live = st.checkbox("Anlik Veri ile Tara", value=False, help="Isaretlenirse kapanmamis son mum dahil edilir, isaretlenmezse sadece kapanmis mumlar kullanilir")
            submitted = st.form_submit_button("Tarama Yap", type="primary", width="stretch")

        if submitted or "accum_results" in st.session_state:
            if submitted:
                results = []
                progress_bar = st.progress(0, text="Taranıyor...")
                filtered_syms = [s for s in symbols if symbol_filter.upper() in s] if symbol_filter else symbols
                total = len(filtered_syms)

                live_data = None
                if use_live:
                    progress_bar.progress(0, text="Anlik veriler cekiliyor (yfinance)...")
                    live_data = fetch_live_data(filtered_syms)
                    st.caption(f"Anlik veri cekildi: {len(live_data)}/{len(filtered_syms)} sembol")

                for i, sym in enumerate(filtered_syms):
                    if (i + 1) % 50 == 0 or i == 0 or i == total - 1:
                        label = f"{i+1}/{total} {sym}" + (" (canli)" if use_live else "")
                        progress_bar.progress((i + 1) / total, text=label)
                    acc = compute_accumulation_for_symbol(sym, use_live=use_live, live_data=live_data)
                    if acc:
                        met_count = sum(1 for v in acc["conditions"].values() if v)
                        if met_count >= min_score:
                            results.append({"symbol": sym, **acc})
                progress_bar.empty()
                st.session_state["accum_results"] = results
                st.session_state["accum_total_scanned"] = total

            results = st.session_state.get("accum_results", [])
            total_scanned = st.session_state.get("accum_total_scanned", 0)

            if not results:
                st.info("Belirtilen kosullari saglayan sembol bulunamadi.")
            else:
                st.metric("Bulunan Sinyal", len(results), delta=f"{total_scanned} sembol tarandi")

                table_data = []
                for r in sorted(results, key=lambda x: sum(1 for v in x["conditions"].values() if v), reverse=True):
                    vals = r["values"]
                    conds = r["conditions"]
                    met = sum(1 for v in conds.values() if v)
                    table_data.append({
                        "Sembol": r["symbol"],
                        "Kapanis": f"{r['close']:.2f}",
                        "MFI": f"{vals['mfi']:.1f}" + (" ✓" if conds["mfi_cross"] else ""),
                        "CMF": f"{vals['cmf']:.4f}" + (" ✓" if conds["cmf_cross"] else ""),
                        "ADX": f"{vals['adx']:.1f}" + (" ✓" if conds["adx_range"] else ""),
                        "RSI": f"{vals['rsi']:.1f}" + (" ✓" if conds["rsi_cross"] else ""),
                        "Kapanis>EMA20": "✓" if conds["above_ema20"] else "",
                        "Hacim>1.5x": "✓" if conds["volume_surge"] else "",
                        "Rel.Hacim": f"{vals['rel_volume']:.2f}" + (" ✓" if conds["high_rel_volume"] else ""),
                        "Kosul": f"{met}/7",
                    })

                result_df = pd.DataFrame(table_data)
                st.dataframe(result_df, width="stretch", height=min(len(result_df) * 35 + 40, 600))

                with st.expander("Kosul Aciklamalari"):
                    st.markdown("""
| Gosterge | Kosul | Anlam |
|----------|-------|-------|
| MFI (14) | 50'u yukari kesti | Para girisi yeni basliyor |
| CMF (20) | 0'i yukari kesti | Para akisi pozitife donuyor |
| ADX (14) | 15 – 25 arasi | Trend yeni olusum asamasinda |
| RSI (14) | 50'i yukari kesti | Momentum yukari donuyor |
| Kapanis | > EMA 20 | Kisa vadeli trendi yukari kirmis |
| Hacim | > Ort. Hacim (20) x 1.5 | Hacim artisi basliyor |
| Rel. Hacim | > 1.5 | Ortalamanin 1.5 kati hacim |
                    """)

elif tab_labels[st.session_state.active_tab] == tab_labels[4]:
    st.subheader("Anlik Birikim Taramasi (TradingView)")
    st.caption("TradingView WebSocket uzerinden anlik veri ile tarama — yfinance 15dk gecikme olmadan")

    symbols = get_cached_symbols_list()
    if not symbols:
        st.info("Veri bulunamadi. Once bir tarama yapin.")
    else:
        with st.form("tv_accum_scan_form"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                tv_interval_label = st.selectbox(
                    "Mum Araligi",
                    ["1 Gun", "4 Saat", "2 Saat", "1 Saat"],
                    index=0,
                    key="tv_interval",
                    help="TradingView'dancekilecek mum araligi"
                )
                TV_INTERVAL_MAP = {"1 Gun": "1D", "4 Saat": "240", "2 Saat": "120", "1 Saat": "60"}
                tv_interval = TV_INTERVAL_MAP[tv_interval_label]
            with col2:
                tv_min_score = st.slider("Minimum Kosul Sayisi", 1, 7, 7, key="tv_min_score", help="Kac kosulun ayni anda saglanacagi")
            with col3:
                tv_symbol_filter = st.text_input("Sembol Filtrele (opsiyonel)", key="tv_acc_filter")
            with col4:
                tv_use_db = st.checkbox("DB'den fallback kullan", value=True, help="TradingView basarisizsa veritabanindan yukle")
            tv_submitted = st.form_submit_button("Anlik Tara (TradingView)", type="primary", width="stretch")

        if tv_submitted or "tv_accum_results" in st.session_state:
            if tv_submitted:
                tv_results = []
                tv_progress = st.progress(0, text="TradingView'a baglaniliyor...")
                filtered_syms = [s for s in symbols if tv_symbol_filter.upper() in s] if tv_symbol_filter else symbols
                total = len(filtered_syms)
                BATCH = 50

                tv_data_map = {}
                batches = [filtered_syms[i:i+BATCH] for i in range(0, len(filtered_syms), BATCH)]

                tv_bar_count = 500 if tv_interval in ("60", "120", "240") else 100

                for bi, batch in enumerate(batches):
                    pct = (bi + 1) / (len(batches) + 1)
                    syms_str = ", ".join(batch[:3]) + ("..." if len(batch) > 3 else "")
                    tv_progress.progress(pct, text=f"Batch {bi+1}/{len(batches)} — {syms_str} ({tv_interval_label}) cekiliyor...")

                    batch_result = fetch_candles_from_tv(batch, interval=tv_interval, count=tv_bar_count)
                    tv_data_map.update(batch_result)

                tv_progress.progress(1.0, text=f"Veri cekildi: {len(tv_data_map)}/{total} sembol")

                if tv_use_db:
                    from database import load_ohlcv
                    missing = [s for s in filtered_syms if s not in tv_data_map]
                    if missing:
                        st.caption(f"DB'den {len(missing)} eksik sembol yukleniyor...")
                        for sym in missing:
                            rows = load_ohlcv(sym, limit=100)
                            if len(rows) >= 50:
                                df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
                                tv_data_map[sym] = df

                tv_scan_progress = st.progress(0, text="Indikatorler hesaplaniyor...")
                scanned_count = 0
                for i, sym in enumerate(filtered_syms):
                    if (i + 1) % 50 == 0 or i == 0 or i == total - 1:
                        tv_scan_progress.progress((i + 1) / total, text=f"{i+1}/{total} {sym} isleniyor...")

                    if sym not in tv_data_map:
                        continue

                    df = tv_data_map[sym]
                    if len(df) < 50:
                        continue

                    try:
                        df = compute_accumulation_indicators(df)
                        result = detect_accumulation_signal(df)
                        scanned_count += 1

                        if result:
                            met_count = sum(1 for v in result["conditions"].values() if v)
                            if met_count >= tv_min_score:
                                tv_results.append({"symbol": sym, **result})
                    except Exception:
                        continue

                tv_scan_progress.empty()

                st.session_state["tv_accum_results"] = tv_results
                st.session_state["tv_accum_total_scanned"] = scanned_count
                st.session_state["tv_data_source"] = "tradingview"
                st.session_state["tv_interval_used"] = tv_interval_label

            tv_results = st.session_state.get("tv_accum_results", [])
            tv_total_scanned = st.session_state.get("tv_accum_total_scanned", 0)
            tv_source = st.session_state.get("tv_data_source", "unknown")
            tv_interval_used = st.session_state.get("tv_interval_used", "1 Gun")

            if not tv_results:
                st.info("Belirtilen kosullari saglayan sembol bulunamadi.")
            else:
                source_label = "TradingView" if tv_source == "tradingview" else "yfinance"
                st.metric("Bulunan Sinyal", len(tv_results), delta=f"{tv_total_scanned} sembol tarandi — {tv_interval_used} ({source_label})")

                tv_table_data = []
                for r in sorted(tv_results, key=lambda x: sum(1 for v in x["conditions"].values() if v), reverse=True):
                    vals = r["values"]
                    conds = r["conditions"]
                    met = sum(1 for v in conds.values() if v)
                    tv_table_data.append({
                        "Sembol": r["symbol"],
                        "Kapanis": f"{r['close']:.2f}",
                        "MFI": f"{vals['mfi']:.1f}" + (" ✓" if conds["mfi_cross"] else ""),
                        "CMF": f"{vals['cmf']:.4f}" + (" ✓" if conds["cmf_cross"] else ""),
                        "ADX": f"{vals['adx']:.1f}" + (" ✓" if conds["adx_range"] else ""),
                        "RSI": f"{vals['rsi']:.1f}" + (" ✓" if conds["rsi_cross"] else ""),
                        "Kapanis>EMA20": "✓" if conds["above_ema20"] else "",
                        "Hacim>1.5x": "✓" if conds["volume_surge"] else "",
                        "Rel.Hacim": f"{vals['rel_volume']:.2f}" + (" ✓" if conds["high_rel_volume"] else ""),
                        "Kosul": f"{met}/7",
                    })

                tv_result_df = pd.DataFrame(tv_table_data)
                st.dataframe(tv_result_df, width="stretch", height=min(len(tv_result_df) * 35 + 40, 600))

                with st.expander("Kosul Aciklamalari"):
                    st.markdown("""
| Gosterge | Kosul | Anlam |
|----------|-------|-------|
| MFI (14) | 50'u yukari kesti | Para girisi yeni basliyor |
| CMF (20) | 0'i yukari kesti | Para akisi pozitife donuyor |
| ADX (14) | 15 – 25 arasi | Trend yeni olusum asamasinda |
| RSI (14) | 50'i yukari kesti | Momentum yukari donuyor |
| Kapanis | > EMA 20 | Kisa vadeli trendi yukari kirmis |
| Hacim | > Ort. Hacim (20) x 1.5 | Hacim artisi basliyor |
| Rel. Hacim | > 1.5 | Ortalamanin 1.5 kati hacim |
                    """)

                with st.expander("Veri Kaynagi Hakkinda"):
                    st.markdown("""
**TradingView WebSocket** ile anlik veri cekildi:
- yfinance 15 dakika gecikmeli veri verirken, TradingView WebSocket ile anlik veri alinir
- Veriler TradingView'in resmi olmayan WebSocket protokolu ile cekilmektedir
- Baglanti basarisiz olursa veritabanindan fallback yapilir
- Gunluk mumlar (1D) kullanilmaktadir — indikatorler gunluk bazda hesaplanir
                    """)
