from fastapi import APIRouter, Query, Response
from models.order import OrderDataModel
from services.stock_data_service import stock_data_service

router = APIRouter(tags=["Stock Data & Orders"])


@router.get("/stock_data")
def get_stock_data(
    ticker: str = Query("AAPL", description="Stock ticker symbol"),
    period: str = Query("1y", description="Data period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)"),
    interval: str = Query("1d", description="Bar interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo)")
):
    """
    Fetch historical close price series formatted for gotti-frontend's TickerChart.
    Returns JSON string with {"Close": {"<timestamp_ms>": price, ...}}
    """
    json_str = stock_data_service.get_stock_close_data(ticker=ticker, period=period, interval=interval)
    # The frontend calls JSON.parse(response.data), so returning the raw JSON string matching the expectation
    return json_str


@router.get("/orders", response_model=list[OrderDataModel])
def get_orders_history(limit: int = Query(50, le=200)):
    """Fetch order execution history for the orders table."""
    return stock_data_service.get_orders_list(limit=limit)
