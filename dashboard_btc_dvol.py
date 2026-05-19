import streamlit as st
import requests
import time
from datetime import datetime

ALERTA_DVOL = 42
DERIBIT_URL = "https://www.deribit.com/api/v2/public/get_index_price"

st.set_page_config(page_title="BTC + DVOL Dashboard", layout="wide")

def get_index_price(index_name):
    params = {"index_name": index_name}
    r = requests.get(DERIBIT_URL, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["result"]["index_price"]

st.title("BTC + Deribit DVOL Dashboard")

placeholder = st.empty()

while True:
    try:
        btc_price = get_index_price("btc_usd")
        dvol = get_index_price("btcdvol_usdc")

        with placeholder.container():
            col1, col2, col3 = st.columns(3)

            col1.metric("BTC Price", f"${btc_price:,.2f}")
            col2.metric("Deribit DVOL", f"{dvol:.2f}%")
            col3.metric("Alerta DVOL", "ON" if dvol > ALERTA_DVOL else "OFF")

            if dvol > ALERTA_DVOL:
                st.error(f"🚨 ALERTA: DVOL acima de {ALERTA_DVOL}! Volatilidade subindo.")
            else:
                st.success(f"DVOL abaixo de {ALERTA_DVOL}. Regime ainda controlado.")

            st.caption(f"Última atualização: {datetime.now().strftime('%H:%M:%S')}")

        time.sleep(10)

    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        time.sleep(10)