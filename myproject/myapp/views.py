from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .ticker_functions import get_ticker

@api_view(['GET'])
def test_api(request):
    return Response({"message": "Hello, world!"})

@api_view(['GET'])
def get_stock_data(request):
    # Fetch data from yfinance
    data = get_ticker("AAPL", "1y", "1d")
    return Response(data.to_json())





