import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

ALERTA_DVOL = 42
DERIBIT = "https://www.deribit.com/api/v2/public"

st.set_page_config(page_title="BTC Quant Dashboard", layout="wide")

def deribit_get(endpoint, params=None):
    r = requests.get(f"{DERIBIT}/{endpoint}", params=params or {}, timeout=10)
    r.raise_for_status()
    return r.json()["result"]

def get_index_price(index_name):
    return deribit_get("get_index_price", {"index_name": index_name})["index_price"]

def get_perp_summary():
    data = deribit_get("get_book_summary_by_instrument", {
        "instrument_name": "BTC-PERPETUAL"
    })
    return data[0]

def get_options_summary():
    return deribit_get("get_book_summary_by_currency", {
        "currency": "BTC",
        "kind": "option"
    })

def calculate_25d_skew(options):
    df = pd.DataFrame(options)

    df = df.dropna(subset=["mark_iv", "underlying_price"])
    df = df[df["mark_iv"] > 0]

    if df.empty:
        return None

    # pega o vencimento mais próximo com opções disponíveis
    df["expiry"] = df["instrument_name"].str.extract(r"BTC-(\d{1,2}[A-Z]{3}\d{2})-")
    expiry = df["expiry"].dropna().iloc[0]
    df = df[df["expiry"] == expiry]

    calls = df[df["instrument_name"].str.endswith("-C")]
    puts = df[df["instrument_name"].str.endswith("-P")]

    if calls.empty or puts.empty:
        return None

    # aproximação simples: call OTM e put OTM mais próximas de 25 delta usando strike relativo
    spot = df["underlying_price"].median()

    calls = calls.copy()
    puts = puts.copy()

    calls["strike"] = calls["instrument_name"].str.extract(r"BTC-\d{1,2}[A-Z]{3}\d{2}-(\d+)-C").astype(float)
    puts["strike"] = puts["instrument_name"].str.extract(r"BTC-\d{1,2}[A-Z]{3}\d{2}-(\d+)-P").astype(float)

    call_25 = calls[calls["strike"] > spot].sort_values("strike").head(3)["mark_iv"].mean()
    put_25 = puts[puts["strike"] < spot].sort_values("strike", ascending=False).head(3)["mark_iv"].mean()

    if pd.isna(call_25) or pd.isna(put_25):
        return None

    return put_25 - call_25

def dvol_regime(dvol):
    if dvol < 35:
        return "Complacência extrema"
    elif dvol < 42:
        return "Normal"
    elif dvol < 55:
        return "Risco crescente"
    elif dvol < 70:
        return "Stress"
    else:
        return "Capitulação / Pânico"

if "history" not in st.session_state:
    st.session_state.history = []

st.title("BTC Quant Dashboard")

try:
    btc_price = get_index_price("btc_usd")
    dvol = get_index_price("btcdvol_usdc")
    perp = get_perp_summary()
    options = get_options_summary()

    funding = perp.get("funding_8h", 0)
    oi = perp.get("open_interest", 0)
    skew = calculate_25d_skew(options)

    now = datetime.now().strftime("%H:%M:%S")

    st.session_state.history.append({
        "time": now,
        "BTC": btc_price,
        "DVOL": dvol
    })

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("BTC Price", f"${btc_price:,.2f}")
    col2.metric("DVOL", f"{dvol:.2f}%")
    col3.metric("Skew", f"{skew:.2f}" if skew is not None else "N/A")
    col4.metric("Funding 8h", f"{funding * 100:.4f}%")
    col5.metric("Open Interest", f"{oi:,.2f} BTC")

    regime = dvol_regime(dvol)

    st.subheader("Regime de Volatilidade")

    if dvol > ALERTA_DVOL:
        st.error(f"🚨 ALERTA: DVOL acima de {ALERTA_DVOL}. Regime: {regime}")
    else:
        st.success(f"✅ DVOL abaixo de {ALERTA_DVOL}. Regime: {regime}")

    regime_table = pd.DataFrame({
        "DVOL": ["< 35", "35–42", "42–55", "> 55", "> 70"],
        "Regime": [
            "Complacência extrema",
            "Normal",
            "Risco crescente",
            "Stress",
            "Capitulação / Pânico"
        ]
    })

    st.table(regime_table)

    df_hist = pd.DataFrame(st.session_state.history)

    st.subheader("Gráfico DVOL")
    st.line_chart(df_hist.set_index("time")["DVOL"])

    st.subheader("Gráfico BTC")
    st.line_chart(df_hist.set_index("time")["BTC"])

    st.caption(f"Última atualização: {now}")

except Exception as e:
    st.error(f"Erro ao buscar dados: {e}")

time.sleep(10)
st.rerun()