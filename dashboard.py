import streamlit as st
import random

# Simulação DVOL
# Depois conectamos API real
dvol = random.randint(35, 50)

# BTC via Binance
import ccxt

exchange = ccxt.binance()
btc = exchange.fetch_ticker("BTC/USDT")
price = btc["last"]

# Layout
st.set_page_config(page_title="BTC Vol Monitor", layout="wide")

st.title("BTC Volatility Monitor")

# Métricas
col1, col2 = st.columns(2)

col1.metric("BTC Price", f"${price:,.2f}")
col2.metric("DVOL", f"{dvol}%")

# Alertas
if dvol > 42:
    st.error("🚨 ALERTA: DVOL acima de 42")
else:
    st.success("✅ DVOL em regime normal")