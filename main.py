
from fastapi import FastAPI, Request, WebSocket

import api.orders as od
import api.account as ac
import api.positions as ps
import api.strategies as st
import api.telegram_handler as tg


app = FastAPI()


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
    print(order)
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
def add_strategy():
    """
    Add a new strategy
    """
    return st.add_strategy()

@app.post('/enable_strategy')
def enable_strategy(strategy_name:str):
    """
    Enable a strategy
    """
    return st.enable_strategy(strategy_name)


#region Websockets
import asyncio
import websockets
import uvicorn

import os
from dotenv import load_dotenv
import threading
load_dotenv()


apikey = os.getenv("APCA_API_KEY_PAPER")
apisecret = os.getenv("APCA_API_SECRET_KEY_PAPER")


async def listen():
    uri = "wss://paper-api.alpaca.markets/stream"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket server")
        # Send ack msg
        AUTH = f'{{"action": "auth","key": "{apikey}","secret": "{apisecret}"}}'
        await websocket.send(AUTH)
        once = False
        try:
            async for message in websocket:
                if once:
                    await update_order_sql(message) # Update order in database 
                    #print(f"Received message: {message}")
                # subscribe to trade updates stream once    
                if not once:
                    await websocket.send('{"action":"listen","data":{"streams":["trade_updates"]}}')
                    once = True
        except websockets.ConnectionClosed:
            print("Connection closed")

def start_websocket_listener():
    asyncio.run(listen())

def start_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    websocket_thread = threading.Thread(target=start_websocket_listener)
    websocket_thread.start()

    start_fastapi()
