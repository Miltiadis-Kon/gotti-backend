from typing import Union

from fastapi import FastAPI

app = FastAPI()

import orders as od
import account as ac
import positions as ps
import strategies as st

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

@app.post('/add_order_sql')
def add_order_sql(order_id:str,strategy:str):
    """ Add order to database.
    
        Will only include strategy and order ID.
        Other info will be added from the Alpaca webhook.
    """
    order = od.add_order_sql(order_id, strategy)
    return order

@app.put('/update_order_sql')
def update_order_sql(order_id:str):
    """ Update order in database.
    Based on the Alpaca webhook, look for the order in the database and update it.
    """
    order = od.update_order_sql(order_id)
    return order

@app.get('/get_order_sql')
def get_order_sql(order_id:str):
    """ Get order from database.
    """
    order = od.filter_orders_by(order_id)
    return order

@app.delete('/delete_order_sql')
def delete_order_sql(order_id:str):
    """ Delete order from database.
    """
    order = od.delete_order_sql(order_id)
    return order

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
