# Import the yfinance library
import yfinance as yf

# Function to get the ticker data
def get_ticker(stock_symbol, timespan, time):
    # Fetch data from yfinance
    ticker = yf.Ticker(stock_symbol)
    # Fetch historical data from yfinance
    data = ticker.history(period=timespan, interval=time)
    return data

# Example: Get the data for the stock symbol 'AAPL' for the last 5 days with 1 minute interval
data = get_ticker('AAPL', '1d', '1m')
#print(data) 


import mplfinance as mpf
# Inspect the DataFrame structure
#print(data.columns)
#print(data.head())

# Plot the candlestick chart

#mpf.plot(data, type='candle', style='charles', title='Candlestick Chart', ylabel='Price')

# Suppose that you have dataframe like the below.
#             date    open    high     low   close     volume
# 0     2018-12-31  244.92  245.54  242.87  245.28  147031456
# 1     2018-12-28  244.94  246.73  241.87  243.15  155998912
# 2     2018-12-27  238.06  243.68  234.52  243.46  189794032
# ...          ...     ...     ...     ...     ...        ...

from stock_indicators.indicators.common.quote import Quote

def get_historical_quotes(data):
    # Convert float64 to decimal.Decimal
    quotes = []
    for index, row in data.iterrows():
        #print(row)
        quote = Quote(index, row['Open'], row['High'], row['Low'], row['Close'], row['Volume'])
        print(type(row['Open']))
        print(row['Open'])
        print(type(quote.open))
        print(quote.open)
        quotes.append(quote)
    return quotes

# Example: Get the historical quotes for the data
quotes = get_historical_quotes(data)
print(quotes)
