from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .ticker_functions import get_ticker, get_news,get_account

@api_view(['GET'])
def test_api(request):
    return Response({"message": "Hello, world!"})

@api_view(['GET'])
def get_stock_data_api(request,stock_id, timespan, time):
    # Fetch data from yfinance
    data = get_ticker(stock_id, "1y", "1d")
    return Response(data.to_json())


@api_view(['GET'])
def get_news_api(request,stock_id):
    # Fetch news data from Alpaca
    news = get_news(stock_id)
    return Response(news)

@api_view(['GET'])
def get_account_api(request):
    # Fetch account data from Alpaca
    account = get_account()
    return Response(account)

