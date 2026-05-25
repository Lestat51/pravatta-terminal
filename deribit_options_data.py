import requests
import pandas as pd
import time

BASE_URL = "https://www.deribit.com/api/v2"

# =========================
# Buscar instrumentos BTC options
# =========================

url = f"{BASE_URL}/public/get_instruments"

params = {
    "currency": "BTC",
    "kind": "option",
    "expired": "false"
}

response = requests.get(url, params=params)
json_data = response.json()
print(json_data)

if "result" not in json_data:
    raise Exception("Deribit API did not return result")

instruments = json_data["result"]

# =========================
# Coletar dados detalhados
# =========================

all_data = []

for instrument in instruments:
    instrument_name = instrument["instrument_name"]

    ticker_url = f"{BASE_URL}/public/ticker"

    ticker_params = {
        "instrument_name": instrument_name
    }

    try:
        ticker_response = requests.get(ticker_url, params=ticker_params)
        ticker_data = ticker_response.json()["result"]

        greeks = ticker_data.get("greeks", {})

        row = {
            "instrument_name": instrument_name,
            "strike": instrument["strike"],
            "option_type": instrument["option_type"],
            "expiration": instrument["expiration_timestamp"],

            "mark_iv": ticker_data.get("mark_iv"),
            "open_interest": ticker_data.get("open_interest"),

            "delta": greeks.get("delta"),
            "gamma": greeks.get("gamma"),
            "vega": greeks.get("vega"),
            "theta": greeks.get("theta")
        }

        all_data.append(row)

        print(f"Loaded: {instrument_name}")

        time.sleep(0.1)

    except Exception as e:
        print(f"Error loading {instrument_name}: {e}")

# =========================
# DataFrame final
# =========================

df = pd.DataFrame(all_data)

# remover IV absurdas / lixo
df = df[
    (df["mark_iv"] > 5) &
    (df["mark_iv"] < 200)
]

# remover open interest zerado
df = df[df["open_interest"] > 0]

print(df.head())

# salvar CSV
df.to_csv("btc_options_data.csv", index=False)

print("CSV salvo com sucesso.")
