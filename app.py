import streamlit as st

st.set_page_config(
    page_title="Pravatta Bitcoin Volatility Terminal",
    layout="wide"
)

st.sidebar.title("Pravatta Terminal")

page = st.sidebar.radio(
    "Select Dashboard",
    [
        "BTC DVOL Dashboard",
        "BTC Skew & Term Structure"
    ]
)

if page == "BTC DVOL Dashboard":
    exec(open("dashboard_btc_dvol.py", encoding="utf-8").read())

elif page == "BTC Skew & Term Structure":
    exec(open("dashboard_skew_term.py", encoding="utf-8").read())