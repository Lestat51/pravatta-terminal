import pandas as pd

def calculate_gamma_flip(gex_by_strike, btc_price):
    gex = gex_by_strike.copy()
    gex = gex.sort_values("strike").reset_index(drop=True)

    # foco operacional perto do spot
    lower = btc_price * 0.75
    upper = btc_price * 1.25

    gex = gex[
        (gex["strike"] >= lower) &
        (gex["strike"] <= upper)
    ].copy()

    gex["prev_gex"] = gex["gex"].shift(1)

    flip_candidates = gex[
        ((gex["prev_gex"] < 0) & (gex["gex"] > 0)) |
        ((gex["prev_gex"] > 0) & (gex["gex"] < 0))
    ]

    if not flip_candidates.empty:
        return float(flip_candidates.iloc[0]["strike"])

    return float(gex.iloc[(gex["gex"]).abs().argsort()[:1]]["strike"].values[0])