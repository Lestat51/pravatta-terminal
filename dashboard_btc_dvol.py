# -*- coding: utf-8 -*-

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
import time


st.title("Pravatta BTC Volatility Dashboard")

st.caption(
    "Real-time Bitcoin volatility, derivatives and positioning analytics powered by Deribit data."
)


# =========================
# Helpers
# =========================

def now_ms():
    return int(time.time() * 1000)


def hours_ago_ms(hours):
    return int((time.time() - hours * 3600) * 1000)


# =========================
# Data functions
# =========================

@st.cache_data(ttl=60)
def get_btc_price():
    url = "https://www.deribit.com/api/v2/public/get_index_price"
    params = {"index_name": "btc_usd"}

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    return r.json()["result"]["index_price"]


@st.cache_data(ttl=60)
def get_btc_ticker():
    url = "https://www.deribit.com/api/v2/public/ticker"
    params = {"instrument_name": "BTC-PERPETUAL"}

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    return r.json()["result"]


@st.cache_data(ttl=60)
def get_btc_24h_history():
    url = "https://www.deribit.com/api/v2/public/get_tradingview_chart_data"

    params = {
        "instrument_name": "BTC-PERPETUAL",
        "start_timestamp": hours_ago_ms(24),
        "end_timestamp": now_ms(),
        "resolution": "1"
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    result = r.json()["result"]

    df = pd.DataFrame({
        "time": pd.to_datetime(result["ticks"], unit="ms"),
        "BTC": result["close"]
    })

    df = df.dropna()
    df = df.sort_values("time")

    return df


@st.cache_data(ttl=60)
def get_dvol_24h_history():
    url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"

    params = {
        "currency": "BTC",
        "start_timestamp": hours_ago_ms(24),
        "end_timestamp": now_ms(),
        "resolution": "60"
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    result = r.json()["result"]["data"]

    df = pd.DataFrame(
        result,
        columns=["timestamp", "open", "high", "low", "close"]
    )

    df["time"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["DVOL"] = df["close"]

    df = df[["time", "DVOL"]].dropna()
    df = df.sort_values("time")

    return df


@st.cache_data(ttl=60)
def get_options_summary():
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
    params = {"currency": "BTC", "kind": "option"}

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()

    return pd.DataFrame(r.json()["result"])


# =========================
# Fetch data
# =========================

btc_price = get_btc_price()
ticker = get_btc_ticker()
btc_df = get_btc_24h_history()
dvol_df = get_dvol_24h_history()
options_df = get_options_summary()

current_dvol = dvol_df["DVOL"].iloc[-1]
funding_8h = ticker.get("funding_8h", 0) * 100

options_df = options_df[options_df["open_interest"] > 0].copy()

total_oi_usd = (
    options_df["open_interest"].sum() * btc_price
    if not options_df.empty
    else 0
)

avg_skew = 0

if not options_df.empty:
    options_df["instrument_name"] = options_df["instrument_name"].astype(str)
    parts = options_df["instrument_name"].str.split("-", expand=True)

    options_df["strike"] = parts[2].astype(float)
    options_df["option_type"] = parts[3]

    calls = options_df[options_df["option_type"] == "C"]
    puts = options_df[options_df["option_type"] == "P"]

    if not calls.empty and not puts.empty:
        avg_put_iv = puts["mark_iv"].mean()
        avg_call_iv = calls["mark_iv"].mean()
        avg_skew = avg_put_iv - avg_call_iv


# =========================
# Metrics
# =========================

col1, col2, col3, col4, col5 = st.columns(5)

col1.metric("BTC Price", f"${btc_price:,.2f}")
col2.metric("DVOL", f"{current_dvol:.2f}%")
col3.metric("Skew", f"{avg_skew:.2f}")
col4.metric("Funding 8h", f"{funding_8h:.5f}%")
col5.metric("Open Interest", f"${total_oi_usd / 1e6:,.2f}M")


# =========================
# Volatility regime
# =========================

st.subheader("Volatility Regime")

if current_dvol < 35:
    regime = "Extreme Complacency"
    regime_icon = "🔵"
elif current_dvol < 42:
    regime = "Normal Volatility"
    regime_icon = "🟢"
elif current_dvol < 55:
    regime = "Rising Risk"
    regime_icon = "🟡"
elif current_dvol < 70:
    regime = "Stress"
    regime_icon = "🟠"
else:
    regime = "Capitulation / Panic"
    regime_icon = "🔴"

st.success(f"{regime_icon} Regime: {regime}")

regime_table = pd.DataFrame({
    "DVOL": ["< 35", "35–42", "42–55", "55–70", "> 70"],
    "Regime": [
        "Extreme Complacency",
        "Normal Volatility",
        "Rising Risk",
        "Stress",
        "Capitulation / Panic"
    ]
})

st.dataframe(regime_table, use_container_width=True, hide_index=True)

st.caption(f"DVOL history points: {len(dvol_df)}")


# =========================
# BTC vs DVOL 24h
# =========================

st.subheader("BTC vs DVOL — 24h")

btc_resampled = (
    btc_df.set_index("time")
    .resample("5min")
    .last()
    .dropna()
    .reset_index()
)

dvol_resampled = (
    dvol_df.set_index("time")
    .resample("5min")
    .last()
    .dropna()
    .reset_index()
)

df_combined = pd.merge_asof(
    btc_resampled.sort_values("time"),
    dvol_resampled.sort_values("time"),
    on="time",
    direction="nearest",
    tolerance=pd.Timedelta("5min")
)

df_combined = df_combined.dropna()

df_combined["BTC Normalized"] = (
    df_combined["BTC"] / df_combined["BTC"].iloc[0]
) * 100

df_combined["DVOL Normalized"] = (
    df_combined["DVOL"] / df_combined["DVOL"].iloc[0]
) * 100

fig = px.line(
    df_combined,
    x="time",
    y=["BTC Normalized", "DVOL Normalized"],
    title="BTC vs DVOL — 24h"
)

fig.update_layout(
    xaxis_title="Time",
    yaxis_title="Normalized Value"
)

st.plotly_chart(fig, use_container_width=True)


# =========================
# Footer
# =========================

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

st.caption(f"Última atualização: {now}")

st.markdown("---")
st.caption("© 2026 Pravatta Research")
st.caption("Market analytics and volatility research.")