import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import norm
from datetime import datetime

from gamma_utils import build_gex_by_strike, calculate_gamma_flip


st.title("BTC Skew & Term Structure Dashboard")


# =========================
# Deribit Data
# =========================

@st.cache_data(ttl=60)
def get_options_data():
    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
    params = {"currency": "BTC", "kind": "option"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()["result"]
    return pd.DataFrame(data)


@st.cache_data(ttl=60)
def get_btc_price():
    url = "https://www.deribit.com/api/v2/public/get_index_price"
    params = {"index_name": "btc_usd"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()["result"]["index_price"]


df = get_options_data()
btc_price = get_btc_price()

df = df[df["open_interest"] > 0].copy()
df["instrument_name"] = df["instrument_name"].astype(str)

parts = df["instrument_name"].str.split("-", expand=True)

df["expiry_raw"] = parts[1]
df["strike"] = parts[2].astype(float)
df["option_type"] = parts[3].map({"C": "call", "P": "put"})

df["expiration"] = pd.to_datetime(df["expiry_raw"], format="%d%b%y", errors="coerce")
df = df.dropna(subset=["expiration"])

df["days_to_expiration"] = (
    (df["expiration"] - pd.Timestamp.utcnow().tz_localize(None)).dt.total_seconds()
    / 86400
)

df = df[df["days_to_expiration"] > 0].copy()

df["T"] = df["days_to_expiration"] / 365
df["iv"] = df["mark_iv"] / 100


# =========================
# Black-Scholes Gamma
# =========================

def bs_gamma(S, K, vol, T):
    if vol <= 0 or T <= 0 or K <= 0:
        return 0

    d1 = (np.log(S / K) + 0.5 * vol ** 2 * T) / (vol * np.sqrt(T))
    return norm.pdf(d1) / (S * vol * np.sqrt(T))


df["gamma"] = df.apply(
    lambda row: bs_gamma(
        btc_price,
        row["strike"],
        row["iv"],
        row["T"]
    ),
    axis=1
)


# =========================
# Raw Data
# =========================

st.subheader("BTC Options Data")

with st.expander("Show raw BTC options data"):
    st.dataframe(df)


# =========================
# ATM Term Structure
# =========================

st.subheader("ATM Volatility Term Structure")

atm_rows = []

for exp, group in df.groupby("expiration"):
    group = group.copy()
    group["atm_distance"] = (group["strike"] - btc_price).abs()

    atm_option = group.sort_values("atm_distance").iloc[0]

    atm_rows.append({
        "expiration": exp,
        "days_to_expiration": atm_option["days_to_expiration"],
        "atm_iv": atm_option["mark_iv"]
    })

atm_df = pd.DataFrame(atm_rows).sort_values("days_to_expiration")

fig_term = px.line(
    atm_df,
    x="days_to_expiration",
    y="atm_iv",
    markers=True,
    title="ATM Implied Volatility Term Structure"
)

fig_term.update_layout(
    xaxis_title="Days to Expiration",
    yaxis_title="ATM IV"
)

st.plotly_chart(fig_term, use_container_width=True)


# =========================
# 25 Delta Skew Approximation
# =========================

# =========================
# 25 Delta Skew Approximation
# Approximation by moneyness
# =========================

st.subheader("25 Delta Skew Approximation")

skew_rows = []

for exp, group in df.groupby("expiration"):
    calls = group[group["option_type"] == "call"].copy()
    puts = group[group["option_type"] == "put"].copy()

    if calls.empty or puts.empty:
        continue

    # proxy: OTM call around +25% and OTM put around -25%
    calls["target_distance"] = (calls["strike"] - btc_price * 1.25).abs()
    puts["target_distance"] = (puts["strike"] - btc_price * 0.75).abs()

    call_25 = calls.sort_values("target_distance").iloc[0]
    put_25 = puts.sort_values("target_distance").iloc[0]

    skew_rows.append({
        "expiration": exp,
        "skew_25d": put_25["mark_iv"] - call_25["mark_iv"]
    })

skew_df = pd.DataFrame(skew_rows).sort_values("expiration")

fig_skew = px.bar(
    skew_df,
    x="expiration",
    y="skew_25d",
    title="25 Delta Skew Approximation: Put IV - Call IV"
)

fig_skew.update_layout(
    xaxis_title="Expiration",
    yaxis_title="skew_25d"
)

st.plotly_chart(fig_skew, use_container_width=True)

# =========================
# Gamma Exposure Approximation
# =========================

gex_by_strike = build_gex_by_strike(df, btc_price)

gex_by_strike = build_gex_by_strike(df, btc_price)

gamma_flip = calculate_gamma_flip(gex_by_strike, btc_price)

fig_gex = px.bar(
    gex_by_strike,
    x="strike",
    y="gex",
    title="Signed Gamma Exposure by Strike"
)

fig_gex.add_vline(
    x=gamma_flip,
    line_dash="dash",
    annotation_text=f"Gamma Flip: {gamma_flip:,.0f}",
    annotation_position="top"
)

fig_gex.update_layout(
    xaxis_title="Strike",
    yaxis_title="Signed Gamma Exposure"
)

st.plotly_chart(fig_gex, use_container_width=True)


# =========================
# Volatility Smile
# =========================

st.subheader("Volatility Smile")

available_expirations = sorted(df["expiration"].unique())

selected_expiry = st.selectbox(
    "Select Expiration",
    available_expirations
)

smile_df = df[df["expiration"] == selected_expiry].copy()
smile_df = smile_df.sort_values(["option_type", "strike"])

fig_smile = px.line(
    smile_df,
    x="strike",
    y="mark_iv",
    color="option_type",
    line_group="option_type",
    markers=True,
    title=f"Volatility Smile - {selected_expiry}"
)

fig_smile.update_layout(
    xaxis_title="Strike",
    yaxis_title="Implied Volatility"
)

st.plotly_chart(fig_smile, use_container_width=True)


# =========================
# IV Surface
# =========================

st.subheader("Implied Volatility Surface")

surface_df = df[
    (df["strike"] > btc_price * 0.5) &
    (df["strike"] < btc_price * 1.8)
].copy()

fig_surface = px.scatter_3d(
    surface_df,
    x="strike",
    y="days_to_expiration",
    z="mark_iv",
    color="option_type",
    title="BTC Implied Volatility Surface"
)

fig_surface.update_layout(
    scene=dict(
        xaxis_title="Strike",
        yaxis_title="Days to Expiration",
        zaxis_title="IV"
    )
)

st.plotly_chart(fig_surface, use_container_width=True)


# =========================
# Interpretation
# =========================

st.subheader("Market Interpretation")

avg_skew = skew_df["skew_25d"].mean() if not skew_df.empty else 0

if avg_skew > 5:
    st.warning("Put skew is elevated, suggesting stronger downside hedging demand.")
elif avg_skew < -5:
    st.info("Call skew is elevated, suggesting stronger upside demand.")
else:
    st.info("Skew is relatively neutral, suggesting balanced options positioning.")