import numpy as np
import pandas as pd
from scipy.stats import norm


def bs_gamma(S, K, vol, T):
    if vol <= 0 or T <= 0 or K <= 0:
        return 0

    d1 = (np.log(S / K) + 0.5 * vol ** 2 * T) / (vol * np.sqrt(T))
    return norm.pdf(d1) / (S * vol * np.sqrt(T))


def build_gex_by_strike(df, btc_price):
    df = df.copy()

    df = df[
        (df["strike"] > btc_price * 0.5) &
        (df["strike"] < btc_price * 1.8)
    ].copy()

    df["iv"] = df["mark_iv"] / 100

    df["gamma"] = df.apply(
        lambda row: bs_gamma(
            btc_price,
            row["strike"],
            row["iv"],
            row["T"]
        ),
        axis=1
    )

    df["signed_gamma"] = np.where(
        df["option_type"].isin(["call", "C"]),
        df["gamma"],
        -df["gamma"]
    )

    df["gex"] = (
        df["signed_gamma"] *
        df["open_interest"] *
        btc_price ** 2
    )

    gex_by_strike = (
        df.groupby("strike")["gex"]
        .sum()
        .reset_index()
        .sort_values("strike")
    )

    return gex_by_strike


def calculate_gamma_flip(gex_by_strike, btc_price):
    gex = gex_by_strike.copy()
    gex = gex.sort_values("strike").reset_index(drop=True)

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

    return float(gex.iloc[gex["gex"].abs().argsort()[:1]]["strike"].values[0])