# ticker_functions.py
import requests
import yfinance as yf
from decouple import config

APCA_API_KEY_ID = config('APCA_API_KEY_ID')
APCA_API_SECRET_KEY = config('APCA_API_SECRET_KEY')

# Function to fetch data from yfinance
def get_ticker(stock_symbol, timespan, time):
    # Fetch data from yfinance
    ticker = yf.Ticker(stock_symbol)
    # Fetch historical data from yfinance
    data = ticker.history(period=timespan, interval=time)
    return data

def get_news(symbol):
    # Fetch news data from Alpac
    url = f"https://data.alpaca.markets/v1beta1/news?sort=desc&symbols={symbol}"

    headers = {
    "accept": "application/json",
    "APCA-API-KEY-ID": APCA_API_KEY_ID,
    "APCA-API-SECRET-KEY": APCA_API_SECRET_KEY
    }
    response = requests.get(url, headers=headers)
    print(response.text)
    return response.json()
   

def get_account():
    url = "https://api.alpaca.markets/v2/account"
    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": APCA_API_KEY_ID,
        "APCA-API-SECRET-KEY": APCA_API_SECRET_KEY
    }
    response = requests.get(url, headers=headers)
    print(response.text)
    return response.json()