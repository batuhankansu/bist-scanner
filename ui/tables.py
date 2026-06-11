import streamlit as st
import pandas as pd


def render_signal_table(df: pd.DataFrame, key: str = "signals"):
    if df.empty:
        st.info("No signals found.")
        return

    if "signal_date" in df.columns:
        display_df = df[["symbol", "signal_type", "close_price", "signal_date"]].copy()
        display_df["signal_date"] = display_df["signal_date"].apply(
            lambda d: f"{d[8:10]}/{d[5:7]}/{d[:4]}" if isinstance(d, str) and len(d) >= 10 else d
        )
        display_df.columns = ["Symbol", "Signal", "Close", "Date"]
    else:
        display_df = df[["symbol", "signal_type", "close_price"]].copy()
        display_df.columns = ["Symbol", "Signal", "Close"]

    display_df.index = range(len(display_df))

    def color_signal(val):
        if val == "BUY":
            return "background-color: #c8e6c9; color: #1b5e20"
        elif val == "SELL":
            return "background-color: #ffcdd2; color: #b71c1c"
        return ""

    styled = display_df.style.map(color_signal, subset=["Signal"])

    st.dataframe(
        styled,
        width="stretch",
        height=min(len(display_df) * 35 + 40, 500),
        key=key,
    )


def render_signal_table_selectable(df: pd.DataFrame, key: str = "today"):
    if df.empty:
        st.info("Sinyal bulunamadi.")
        return None

    has_date = "signal_date" in df.columns
    if has_date:
        display_df = df[["symbol", "signal_type", "close_price", "signal_date"]].copy()
        display_df["signal_date"] = display_df["signal_date"].apply(
            lambda d: f"{d[8:10]}/{d[5:7]}/{d[:4]}" if isinstance(d, str) and len(d) >= 10 else d
        )
        display_df.columns = ["Sembol", "Sinyal", "Kapanis", "Tarih"]
    else:
        display_df = df[["symbol", "signal_type", "close_price"]].copy()
        display_df.columns = ["Sembol", "Sinyal", "Kapanis"]

    display_df.index = range(len(display_df))

    def color_signal(val):
        if val == "BUY":
            return "background-color: #c8e6c9; color: #1b5e20"
        elif val == "SELL":
            return "background-color: #ffcdd2; color: #b71c1c"
        return ""

    styled = display_df.style.map(color_signal, subset=["Sinyal"])

    result = st.dataframe(
        styled,
        width="stretch",
        height=min(len(display_df) * 35 + 40, 500),
        on_select="rerun",
        key=key,
        selection_mode="single-row",
    )

    if result and result.selection and result.selection.rows:
        idx = result.selection.rows[0]
        return df.iloc[idx]
    return None
