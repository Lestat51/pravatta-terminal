import streamlit as st

st.set_page_config(
    page_title="Pravatta Terminal",
    layout="wide"
)

st.sidebar.title("Pravatta Terminal")

dashboard = st.sidebar.radio(
    "Select Dashboard",
    [
        "BTC DVOL Dashboard",
        "BTC Skew & Term Structure",
        "Dealer Gamma"
    ]
)

if dashboard == "BTC DVOL Dashboard":
    exec(open("dashboard_btc_dvol.py", encoding="utf-8").read())

elif dashboard == "BTC Skew & Term Structure":
    exec(open("dashboard_skew_term.py", encoding="utf-8").read())

elif dashboard == "Dealer Gamma":
    exec(open("dashboard_gamma.py", encoding="utf-8").read())
   