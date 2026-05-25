import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="BTC Skew & Term Structure", layout="wide")

st.title("BTC Skew & Term Structure Dashboard")

df = pd.read_csv("btc_options_data.csv")

# Converter timestamp
df["expiration"] = pd.to_datetime(df["expiration"], unit="ms")

# Dias até vencimento
today = pd.Timestamp.now()

df["days_to_expiry"] = (
    (df["expiration"] - today).dt.total_seconds() / 86400
)

# Remover expirados/ruído
df = df[df["days_to_expiry"] > 0]

st.subheader("BTC Options Data")

with st.expander("Show raw BTC options data"):
    st.dataframe(df, use_container_width=True)

# =====================
# Term Structure
# =====================
# =====================
# Better ATM Term Structure
# =====================

st.subheader("ATM Volatility Term Structure")

# Spot BTC aproximado
spot = 77000

# Distância ATM
df["atm_distance"] = abs(df["strike"] - spot)

# Pegar strikes mais ATM
atm = (
    df.sort_values("atm_distance")
    .groupby("expiration")
    .first()
    .reset_index()
)

fig_term = px.line(
    atm,
    x="days_to_expiry",
    y="mark_iv",
    markers=True,
    title="ATM Implied Volatility Term Structure"
)

fig_term.update_layout(
    xaxis_title="Days to Expiration",
    yaxis_title="ATM IV"
)

st.plotly_chart(fig_term, use_container_width=True)

# =====================
# 25 Delta Skew Approx
# =====================

st.subheader("25 Delta Skew Approximation")

calls = df[df["option_type"] == "call"].copy()
puts = df[df["option_type"] == "put"].copy()

calls["delta_distance"] = (calls["delta"] - 0.25).abs()
puts["delta_distance"] = (puts["delta"] + 0.25).abs()

call_25 = calls.sort_values("delta_distance").groupby("expiration").first().reset_index()
put_25 = puts.sort_values("delta_distance").groupby("expiration").first().reset_index()

skew = pd.merge(
    put_25[["expiration", "mark_iv"]],
    call_25[["expiration", "mark_iv"]],
    on="expiration",
    suffixes=("_put_25d", "_call_25d")
)

skew["skew_25d"] = skew["mark_iv_put_25d"] - skew["mark_iv_call_25d"]

fig_skew = px.bar(
    skew,
    x="expiration",
    y="skew_25d",
    title="25 Delta Skew Approximation: Put IV - Call IV"
)

st.plotly_chart(fig_skew, use_container_width=True)

# =====================
# Gamma Exposure Approx
# =====================

st.subheader("Gamma Exposure Approximation")

# Filtrar strikes extremos
spot = 77000

gex_df = df[
    (df["strike"] > spot * 0.5) &
    (df["strike"] < spot * 1.8)
].copy()

# Convencao simples:
# Calls = gamma positivo
# Puts = gamma negativo
gex_df["signed_gamma"] = gex_df.apply(
    lambda row: row["gamma"] if row["option_type"] == "call" else -row["gamma"],
    axis=1
)

gex_df["signed_gex"] = (
    gex_df["signed_gamma"] *
    gex_df["open_interest"] *
    (spot ** 2)
)

gex = (
    gex_df.groupby("strike")["signed_gex"]
    .sum()
    .reset_index()
    .sort_values("strike")
)

fig_gex = px.bar(
    gex,
    x="strike",
    y="signed_gex",
    title="Signed Gamma Exposure by Strike"
)

fig_gex.update_layout(
    xaxis_title="Strike",
    yaxis_title="Signed Gamma Exposure"
)

# Gamma Flip Level - first negative to positive transition
gex = gex.sort_values("strike").reset_index(drop=True)

gex["prev_signed_gex"] = gex["signed_gex"].shift(1)

flip_candidates = gex[
    (gex["prev_signed_gex"] < 0) &
    (gex["signed_gex"] > 0)
]

if not flip_candidates.empty:
    gamma_flip = flip_candidates.iloc[0]["strike"]

    fig_gex.add_vline(
        x=gamma_flip,
        line_dash="dash",
        annotation_text=f"Gamma Flip: {gamma_flip:,.0f}",
        annotation_position="top"
    )

st.plotly_chart(fig_gex, use_container_width=True)

# =====================
# Volatility Smile
# =====================

st.subheader("Volatility Smile")

available_expirations = sorted(df["expiration"].unique())

selected_expiry = st.selectbox(
    "Select Expiration",
    available_expirations
)

smile_df = df[df["expiration"] == selected_expiry].copy()

fig_smile = px.line(
    smile_df,
    x="strike",
    y="mark_iv",
    color="option_type",
    markers=True,
    title=f"Volatility Smile - {selected_expiry}"
)

fig_smile.update_layout(
    xaxis_title="Strike",
    yaxis_title="Implied Volatility"
)

st.plotly_chart(fig_smile, use_container_width=True)

# =====================
# IV Surface 3D
# =====================

st.subheader("Implied Volatility Surface")

surface_df = df.copy()

surface_df = surface_df[
    (surface_df["strike"] > spot * 0.5) &
    (surface_df["strike"] < spot * 1.8)
]

fig_surface = px.scatter_3d(
    surface_df,
    x="strike",
    y="days_to_expiry",
    z="mark_iv",
    color="option_type",
    title="BTC Implied Volatility Surface"
)

fig_surface.update_layout(
    scene=dict(
        xaxis_title="Strike",
        yaxis_title="Days to Expiry",
        zaxis_title="IV"
    )
)

st.plotly_chart(fig_surface, use_container_width=True)

# =====================
# Interpretation
# =====================

st.subheader("Market Interpretation")

latest_skew = skew["skew_25d"].mean()

if latest_skew > 5:
    st.warning("Put skew is elevated. This suggests stronger downside hedging demand.")
elif latest_skew < -5:
    st.success("Call skew is dominant. This suggests stronger upside speculation.")
else:
    st.info("Skew is relatively neutral, suggesting balanced options positioning.")