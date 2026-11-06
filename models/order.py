from typing import Literal, Optional
from pydantic import BaseModel


class OrderDataModel(BaseModel):
    id: int
    date: str
    symbol: str
    name: str
    etfLevel: Optional[int] = 3
    status: Literal["Open", "Closed"]
    buyPrice: float | str
    sellPrice: float | str
    profit: float | str
    orderAmount: float
    totalAmount: float
    type: Literal["Buy", "Sell"]
