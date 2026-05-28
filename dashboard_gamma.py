import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.express as px
from scipy.stats import norm
from datetime import datetime
from gamma_utils import calculate_gamma_flip


st.title("Dealer Gamma")

# -------------------------
# DERIBIT API
# -------------------------

url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"

params = {
    "currency": "BTC",
    "kind": "option"
}

response = requests.get(url, params=params)
json_data = response.json()

if "result" not in json_data:
    st.error("Deribit API did not return result.")
    st.json(json_data)
    st.stop()

data = json_data["result"]

df = pd.DataFrame(data)

# -------------------------
# CLEAN DATA
# -------------------------

df = df[df["open_interest"] > 0]

df["instrument_name"] = df["instrument_name"].astype(str)

split_cols = df["instrument_name"].str.split("-", expand=True)

df["expiry"] = split_cols[1]
df["strike"] = split_cols[2].astype(float)
df["type"] = split_cols[3]

# -------------------------
# BTC PRICE
# -------------------------

btc_price = df["underlying_price"].mean()

# -------------------------
# FILTER LIQUID STRIKES
# -------------------------

lower = btc_price * 0.5
upper = btc_price * 1.8

df = df[
    (df["strike"] >= lower) &
    (df["strike"] <= upper)
]

# -------------------------
# IMPLIED VOL
# -------------------------

df["iv"] = df["mark_iv"] / 100

# -------------------------
# TIME TO EXPIRY
# -------------------------

def calculate_t(expiry):
    try:
        exp = datetime.strptime(expiry, "%d%b%y")
        t = (exp - datetime.utcnow()).days / 365
        return max(t, 0.001)
    except:
        return 0.001

df["T"] = df["expiry"].apply(calculate_t)
df = df[df["T"] > 1/365]

# -------------------------
# BLACK-SCHOLES GAMMA
# -------------------------

def gamma(S, K, vol, T):

    try:

        d1 = (
            np.log(S / K)
            + (0.5 * vol ** 2) * T
        ) / (vol * np.sqrt(T))

        return norm.pdf(d1) / (S * vol * np.sqrt(T))

    except:
        return 0

df["gamma"] = df.apply(
    lambda row: gamma(
        btc_price,
        row["strike"],
        row["iv"],
        row["T"]
    ),
    axis=1
)

# -------------------------
# GAMMA EXPOSURE
# -------------------------

df["gex"] = (
    df["gamma"]
    * df["open_interest"]
    * btc_price ** 2
)

# puts negative
df.loc[df["type"] == "P", "gex"] *= -1

# -------------------------
# AGGREGATE BY STRIKE
# -------------------------

gex_by_strike = (
    df.groupby("strike")["gex"]
    .sum()
    .reset_index()
)

# -------------------------
# CALL WALL / PUT WALL
# -------------------------

call_wall = (
    df[df["type"] == "C"]
    .groupby("strike")["open_interest"]
    .sum()
    .idxmax()
)

put_wall = (
    df[df["type"] == "P"]
    .groupby("strike")["open_interest"]
    .sum()
    .idxmax()
)

# -------------------------
# GAMMA FLIP
# same logic as Skew & Term Structure
# -------------------------

gamma_flip = calculate_gamma_flip(gex_by_strike, btc_price)

# -------------------------
# METRICS
# -------------------------

# -------------------------
# DEALER REGIME
# -------------------------

total_gex = gex_by_strike["gex"].sum()

if total_gex > 0:
    regime = "Long Gamma"
else:
    regime = "Short Gamma"


# -------------------------
# METRICS
# -------------------------

col1, col2, col3, col4 = st.columns(4)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Gamma Flip",
    f"${gamma_flip:,.0f}"
)

col2.metric(
    "Call Wall",
    f"${call_wall:,.0f}"
)

col3.metric(
    "Put Wall",
    f"${put_wall:,.0f}"
)

col4.metric(
    "Dealer Regime",
    regime
)

# -------------------------
# CHART
# -------------------------

fig = px.bar(
    gex_by_strike,
    x="gex",
    y="strike",
    orientation="h",
    title="Gamma Exposure by Strike"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# -------------------------
# INTERPRETATION
# -------------------------

st.subheader("Market Interpretation")

if regime == "Long Gamma":

    st.success(
        """
Dealers are currently long gamma.

This regime tends to:
- suppress volatility
- create mean reversion
- increase pinning behavior
        """
    )

else:

    st.error(
        """
Dealers are currently short gamma.

This regime tends to:
- amplify volatility
- accelerate directional moves
- increase liquidation cascades
        """
    )