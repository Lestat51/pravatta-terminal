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
        "BTC Skew & Term Structure"
    ]
)

if dashboard == "BTC DVOL Dashboard":
    exec(open("dashboard_btc_dvol.py").read())

elif dashboard == "BTC Skew & Term Structure":
    exec(open("dashboard_skew_term.py").read())