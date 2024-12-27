
from fastapi import FastAPI, Request, WebSocket

import api.orders as od
import api.account as ac
import api.positions as ps
import api.strategies as st
import api.telegram_handler as tg


import asyncio
import websockets
import json
from typing import Optional


import uvicorn
import os
from dotenv import load_dotenv

app = FastAPI()

#region Websocket

load_dotenv()


apikey = os.getenv("APCA_API_KEY_PAPER")
apisecret = os.getenv("APCA_API_SECRET_KEY_PAPER")



class AlpacaWebSocket:
    def __init__(self):
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.uri = "wss://paper-api.alpaca.markets/stream"
        
    async def connect(self):
        self.ws = await websockets.connect(self.uri)
        await self.authenticate()
        await self.subscribe()
        
    async def authenticate(self):
        auth_data = {
            "action": "auth",
            "key": apikey,
            "secret": apisecret
        }
        await self.ws.send(json.dumps(auth_data))
        resp = await self.ws.recv()
        print(f"Auth response: {resp}")
        
    async def subscribe(self):
        subscribe_message = {
            "action": "listen",
            "data": {
                "streams": ["trade_updates"]
            }
        }
        await self.ws.send(json.dumps(subscribe_message))
        
    async def process_messages(self):
        while True:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                print(f"Received: {data}")
                # Handle message here
                if data.get('data'):
                    await update_order_sql(message)
            except Exception as e:
                print(f"Error processing message: {e}")
                await asyncio.sleep(1)

# Create WebSocket instance
alpaca_ws = AlpacaWebSocket()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(connect_and_process())

async def connect_and_process():
    while True:
        try:
            await alpaca_ws.connect()
            await alpaca_ws.process_messages()
        except Exception as e:
            print(f"WebSocket error: {e}")
            await asyncio.sleep(1)

def start():
    uvicorn.run(app, host="0.0.0.0", port=10000)

#region API 


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/account_pnl")
def get_pnl():
    """ Get total profit/loss from active positions.
        
        Response: "pnl":"802.234"
    """
    pnl = ac.get_pnl()
    return pnl

@app.get("/account_cash")
def get_cash_balance():
    """ Get available cash balance
        Response: 
        {"available_balance": cash}
    """
    cash = ac.get_cash_balance()
    return cash

@app.get("/manage_orders")
def manage_orders(order_id:str):
    """ 
    Find main and side orders and remove them
    """
    order = od.get_order(order_id)
    od.find_related_order(order)
    return {"message": "Orders removed"}, 200


@app.get("/orders")
def get_orders():
   return od.get_orders()

@app.get('/order_count')
def get_order_count():
    return od.get_order_count()

@app.get('/order_info')
def get_order_info(client_order_id:str):
    """ Get details of a trade. """
    pnl = od.get_order_profit_loss(client_order_id)
    return pnl


@app.put('/update_order_sql')
async def update_order_sql(message:bytes):
    """ Update order in database.
    Based on the Alpaca webhook, look for the order in the database and update it.
    """
    data = od.format_order_data(message)
    if data['order_id'] is None :
        return
    # TODO: Add logic to update order status in database when a finished order message is sent!
    
    order = od.update_order_sql(data)
    if  data['status'] == 'new' :
        await tg.send_message(order)
    return order

@app.get('/get_order_sql')
def get_order_sql(order_id:str):
    """ Get order from database.
    """
    order = od.filter_orders_by(order_id)
    return order

@app.post('/update_order_strategy')
def update_order_strategy(rq:od.OrderStrategy):
    """ Update order strategy in database.
    """
    print(rq.order_id, rq.strategy)
    od.update_order_strategy(rq.order_id, rq.strategy)
    manage_orders(rq.order_id)
    return {"message": "Strategy updated"}, 200


@app.delete('/delete_order_sql')
def delete_order_sql(order_id:str):
    """ Delete order from database.
    """
    order = od.delete_order_sql(order_id)
    return {"message": "Order deleted"}, 200

@app.get('/positions')
def get_positions():
    """
    Get active positions registered on Alpaca.
    """
    return ps.get_positions()

@app.get('/position_count')
def get_position_count():
    """
    Get number of active positions
    """
    return ps.get_position_count()

@app.get('/strategies')
def get_strategies():
    """
    Get all strategies.
    """
    return st.get_strategies()

@app.get('/strategy')
def get_strategy(strategy_name:str):
    """
    Get details of a strategy
    """
    return st.get_strategy(strategy_name)

@app.post('/add_strategy')
def add_strategy(strategy_name: str,description: str,risk_reward_ratio: str,max_drawdown: str):
    """
    Add a new strategy
    """
    return st.add_strategy(strategy_name,description,risk_reward_ratio,max_drawdown)

@app.post('/enable_strategy')
def enable_strategy(strategy_name:str):
    """
    Enable a strategy
    """
    return st.enable_strategy(strategy_name)