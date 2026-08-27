from typing import Literal
from pydantic import BaseModel


class OrderDataModel(BaseModel):
    id: int
    date: str
    symbol: str
    name: str
    status: Literal["Open", "Closed"]
    buyPrice: float | str
    sellPrice: float | str
    profit: float | str
    orderAmount: float
    totalAmount: float
    type: Literal["Buy", "Sell"]
