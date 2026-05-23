import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
from datetime import datetime

ALERTA_DVOL = 42
DERIBIT = "https://www.deribit.com/api/v2/public"

st.set_page_config(
    page_title="Pravatta BTC Volatility Dashboard",
    layout="wide"
)


def deribit_get(endpoint, params=None):
    response = requests.get(
        f"{DERIBIT}/{endpoint}",
        params=params or {},
        timeout=10
    )
    response.raise_for_status()
    return response.json()["result"]


def get_index_price(index_name):
    data = deribit_get("get_index_price", {"index_name": index_name})
    return data["index_price"]


def get_perp_summary():
    data = deribit_get(
        "get_book_summary_by_instrument",
        {"instrument_name": "BTC-PERPETUAL"}
    )
    return data[0]


def get_options_summary():
    return deribit_get(
        "get_book_summary_by_currency",
        {"currency": "BTC", "kind": "option"}
    )


def calculate_skew(options):
    df = pd.DataFrame(options)
    df = df.dropna(subset=["mark_iv", "underlying_price"])

    if df.empty:
        return None

    spot = df["underlying_price"].median()

    df["expiry"] = df["instrument_name"].str.extract(
        r"BTC-(\d{1,2}[A-Z]{3}\d{2})-"
    )

    df["strike"] = df["instrument_name"].str.extract(
        r"BTC-\d{1,2}[A-Z]{3}\d{2}-(\d+)-[CP]"
    ).astype(float)

    df = df.dropna(subset=["expiry", "strike"])

    expiries = sorted(df["expiry"].unique())

    if len(expiries) == 0:
        return None

    expiry = expiries[0]
    df = df[df["expiry"] == expiry]

    calls = df[df["instrument_name"].str.endswith("-C")].copy()
    puts = df[df["instrument_name"].str.endswith("-P")].copy()

    if calls.empty or puts.empty:
        return None

    target_call_strike = spot * 1.05
    target_put_strike = spot * 0.95

    calls["distance"] = abs(calls["strike"] - target_call_strike)
    puts["distance"] = abs(puts["strike"] - target_put_strike)

    call_iv = calls.sort_values("distance").iloc[0]["mark_iv"]
    put_iv = puts.sort_values("distance").iloc[0]["mark_iv"]

    return put_iv - call_iv


def dvol_regime(dvol):
    if dvol < 35:
        return "Extreme Complacency"
    elif dvol < 42:
        return "Normal Volatility"
    elif dvol < 55:
        return "Rising Risk"
    elif dvol < 70:
        return "Stress"
    else:
        return "Capitulation / Panic"


if "history" not in st.session_state:
    st.session_state.history = []


st.title("Pravatta BTC Volatility Dashboard")
st.caption("Real-time Bitcoin volatility, derivatives and positioning analytics powered by Deribit data.")

try:
    btc_price = get_index_price("btc_usd")
    dvol = get_index_price("btcdvol_usdc")
    perp = get_perp_summary()
    options = get_options_summary()

    funding = perp.get("funding_8h", 0)
    oi = perp.get("open_interest", 0)
    skew = calculate_skew(options)

    regime = dvol_regime(dvol)
    now = datetime.now().strftime("%H:%M:%S")

    st.session_state.history.append({
        "time": now,
        "BTC": btc_price,
        "DVOL": dvol
    })
    st.session_state.history = st.session_state.history[-300:]

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("BTC Price", f"${btc_price:,.2f}")
    col2.metric("DVOL", f"{dvol:.2f}%")
    col3.metric("Skew", f"{skew:.2f}" if skew is not None else "N/A")
    col4.metric("Funding 8h", f"{funding * 100:.5f}%")
    col5.metric("Open Interest", f"${oi/1_000_000:,.2f}M")

    st.subheader("Volatility Regime")

    if dvol < 35:
        st.info(f"🟦 Regime: {regime}")
    elif dvol < 42:
        st.success(f"🟩 Regime: {regime}")
    elif dvol < 55:
        st.warning(f"🟨 Regime: {regime}")
    else:
        st.error(f"🟥 Regime: {regime}")

    regime_table = pd.DataFrame({
        "DVOL": ["< 35", "35–42", "42–55", "55–70", "\\> 70"],
        "Regime": [
            "Extreme Complacency",
            "Normal Volatility",
            "Rising Risk",
            "Stress",
            "Capitulation / Panic"
        ]
    })

    st.table(regime_table)

    df_hist = pd.DataFrame(st.session_state.history)

    st.subheader("BTC + DVOL")

    df_combined = df_hist.copy()

    df_combined["BTC Normalizado"] = (
        df_combined["BTC"] / df_combined["BTC"].iloc[0]
    ) * 100

    df_combined["DVOL Normalizado"] = (
        df_combined["DVOL"] / df_combined["DVOL"].iloc[0]
    ) * 100

    st.subheader("BTC + DVOL")

    fig = px.line(
    df_combined,
    x="time",
    y=["BTC Normalizado", "DVOL Normalizado"],
    )

    fig.update_yaxes(autorange=True)

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("DVOL Chart")

    fig_dvol = px.line(
    df_hist,
    x="time",
    y="DVOL Indexed",
    )

    fig_dvol.update_yaxes(autorange=True)

    st.plotly_chart(fig_dvol, use_container_width=True)

    st.subheader("BTC Chart")

    fig_btc = px.line(
    df_hist,
    x="time",
    y="BTC Indexed",
    )

    fig_btc.update_yaxes(autorange=True)

    st.plotly_chart(fig_btc, use_container_width=True)

    st.caption(f"Última atualização: {now}")

    except Exception as e:
    st.error(f"Erro ao buscar dados: {e}")

    time.sleep(5)
    st.rerun()
