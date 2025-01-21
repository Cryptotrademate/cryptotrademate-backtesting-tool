
import requests
import pandas as pd
import bt
import matplotlib.pyplot as plt

# Fetch OHLCV Data from Binance
def fetch_binance_ohlcv(symbol, interval='1d', limit=365):
    base_url = "https://api.binance.us/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_asset_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit='ms')
    df.set_index("timestamp", inplace=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["close"]]

# Fetch data for multiple cryptocurrencies
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "LTCUSDT", "MKRUSDT"]
dataframes = []

for symbol in symbols:
    print(f"Fetching data for {symbol}...")
    df = fetch_binance_ohlcv(symbol, limit=365)
    df.rename(columns={"close": symbol.split('USDT')[0].lower()}, inplace=True)
    dataframes.append(df)

# Combine all data into a single DataFrame
combined_data = pd.concat(dataframes, axis=1)
combined_data.dropna(inplace=True)  # Drop rows with missing data
normalized_data = combined_data / combined_data.iloc[0] * 100  # Normalize prices

# Simulate historical market capitalization
import numpy as np
np.random.seed(42)
historical_market_cap = pd.DataFrame(
    np.random.uniform(1e8, 1e10, size=(len(combined_data), len(symbols))),
    index=combined_data.index,
    columns=[symbol.split('USDT')[0].lower() for symbol in symbols]
)
historical_market_cap = historical_market_cap.div(historical_market_cap.sum(axis=1), axis=0)

# Define normalized prices for strategies
normalized_historical_prices = normalized_data.copy()

# Define WeighMW Class
class WeighMW(bt.Algo):
    def __init__(self, market_caps):
        self.market_caps = market_caps

    def __call__(self, target):
        current_market_caps = self.market_caps.loc[target.now].dropna()
        weights = current_market_caps / current_market_caps.sum()
        target.temp['weights'] = weights.to_dict()
        return True

# Define SMA-50 and EMA-200 Crossover Strategy
class SMACrossover(bt.Algo):
    def __call__(self, target):
        data = target.universe[target.universe.columns[0]]  # Use the first column
        sma_50 = data.rolling(window=50).mean()
        ema_200 = data.ewm(span=200).mean()
        signal = (sma_50 > ema_200).astype(int)
        target.temp['weights'] = signal
        return True

sma_ema_strategy = bt.Strategy('SMA-EMA-Crossover',
                                [bt.algos.RunDaily(),
                                 bt.algos.SelectAll(),
                                 SMACrossover(),
                                 bt.algos.WeighEqually(),
                                 bt.algos.Rebalance()])

# Define other strategies
btc_strategy = bt.Strategy('Bitcoin',
                          [bt.algos.RunOnce(),
                           bt.algos.SelectThese(['btc']),
                           bt.algos.WeighEqually(),
                           bt.algos.Rebalance()])

eth_strategy = bt.Strategy('Ethereum',
                          [bt.algos.RunOnce(),
                           bt.algos.SelectThese(['eth']),
                           bt.algos.WeighEqually(),
                           bt.algos.Rebalance()])

ew_strategy = bt.Strategy('Equal-Weighted',
                         [bt.algos.RunMonthly(),
                          bt.algos.SelectAll(),
                          bt.algos.WeighEqually(),
                          bt.algos.Rebalance()])

mw_strategy = bt.Strategy('Market-Weighted',
                          [bt.algos.RunMonthly(),
                           bt.algos.SelectAll(),
                           WeighMW(historical_market_cap),
                           bt.algos.Rebalance()])

# Create backtests
btc_backtest = bt.Backtest(btc_strategy, normalized_historical_prices)
eth_backtest = bt.Backtest(eth_strategy, normalized_historical_prices)
ew_backtest = bt.Backtest(ew_strategy, normalized_historical_prices)
mw_backtest = bt.Backtest(mw_strategy, normalized_historical_prices)
sma_ema_backtest = bt.Backtest(sma_ema_strategy, normalized_historical_prices)

# Run backtests
results = bt.run(btc_backtest, eth_backtest, ew_backtest, mw_backtest, sma_ema_backtest)

# Plot results
results.plot(title='Backtest Results for Crypto Strategies', figsize=(12, 8))
plt.show()