
import requests
import pandas as pd
import bt
import matplotlib.pyplot as plt
import numpy as np

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
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "SUIUSDT", "DOTUSDT", "ADAUSDT"]
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
np.random.seed(42)
historical_market_cap = pd.DataFrame(
    np.random.uniform(1e8, 1e10, size=(len(combined_data), len(symbols))),
    index=combined_data.index,
    columns=[symbol.split('USDT')[0].lower() for symbol in symbols]
)
historical_market_cap = historical_market_cap.div(historical_market_cap.sum(axis=1), axis=0)

# Define WeighMW Class for Market-Weighted Strategy
class WeighMW(bt.Algo):
    def __init__(self, market_caps):
        self.market_caps = market_caps

    def __call__(self, target):
        current_market_caps = self.market_caps.loc[target.now].dropna()
        weights = current_market_caps / current_market_caps.sum()
        target.temp['weights'] = weights.to_dict()
        return True

# Define Risk Parity Strategy
class RiskParityStrategy(bt.Algo):
    def __init__(self, returns_data):
        self.returns_data = returns_data

    def __call__(self, target):
        # Calculate daily returns and covariance
        returns = self.returns_data.pct_change().dropna()
        cov_matrix = returns.cov()

        # Calculate inverse of standard deviations
        inv_volatility = 1 / np.sqrt(np.diag(cov_matrix))

        # Allocate based on risk parity (inverse volatility weighting)
        risk_parity_weights = inv_volatility / inv_volatility.sum()
        target.temp['weights'] = {asset: weight for asset, weight in zip(self.returns_data.columns, risk_parity_weights)}

        return True

# Define Mean-Variance Strategy
class MeanVarianceStrategy(bt.Algo):
    def __init__(self, returns_data):
        self.returns_data = returns_data

    def __call__(self, target):
        # Calculate daily returns and covariance
        returns = self.returns_data.pct_change().dropna()
        mean_returns = returns.mean()
        cov_matrix = returns.cov()

        # Calculate portfolio weights based on mean-variance optimization
        # Simplified to use equal allocation for illustration
        weights = mean_returns / mean_returns.sum()
        target.temp['weights'] = {asset: weight for asset, weight in zip(self.returns_data.columns, weights)}

        return True

# Create the strategies
risk_parity_strategy = bt.Strategy('Risk Parity Strategy',
                                  [bt.algos.RunMonthly(),
                                   bt.algos.SelectAll(),
                                   RiskParityStrategy(normalized_data),
                                   bt.algos.Rebalance()])

mean_variance_strategy = bt.Strategy('Mean Variance Strategy',
                                    [bt.algos.RunMonthly(),
                                     bt.algos.SelectAll(),
                                     MeanVarianceStrategy(normalized_data),
                                     bt.algos.Rebalance()])

# Create backtests for each strategy
btc_backtest = bt.Backtest(bt.Strategy('Bitcoin', [bt.algos.RunOnce(), bt.algos.SelectThese(['btc']), bt.algos.WeighEqually(), bt.algos.Rebalance()]), normalized_data)
eth_backtest = bt.Backtest(bt.Strategy('Ethereum', [bt.algos.RunOnce(), bt.algos.SelectThese(['eth']), bt.algos.WeighEqually(), bt.algos.Rebalance()]), normalized_data)
ew_backtest = bt.Backtest(bt.Strategy('Equal-Weighted', [bt.algos.RunMonthly(), bt.algos.SelectAll(), bt.algos.WeighEqually(), bt.algos.Rebalance()]), normalized_data)
mw_backtest = bt.Backtest(bt.Strategy('Market-Weighted', [bt.algos.RunMonthly(), bt.algos.SelectAll(), WeighMW(historical_market_cap), bt.algos.Rebalance()]), normalized_data)
risk_parity_backtest = bt.Backtest(risk_parity_strategy, normalized_data)
mean_variance_backtest = bt.Backtest(mean_variance_strategy, normalized_data)

# Run the backtests
results = bt.run(btc_backtest, eth_backtest, ew_backtest, mw_backtest, risk_parity_backtest, mean_variance_backtest)

# Plot results
results.plot(title='Backtest Results for Crypto Strategies', figsize=(12, 8))
plt.show()
