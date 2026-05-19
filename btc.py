import ccxt

exchange = ccxt.binance()

btc = exchange.fetch_ticker('BTC/USDT')

print("Preço atual BTC:")
print(btc['last'])