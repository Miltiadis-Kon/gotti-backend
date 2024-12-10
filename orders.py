""" Implement all api endpoints for orders """

from fastapi import HTTPException
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from alpaca import login
import requests
import sql as sql
import mysql.connector
import strategies as st


class Order(BaseModel):
    id: str
    client_order_id: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime
    filled_at: Optional[datetime]
    expired_at: Optional[datetime]
    canceled_at: Optional[datetime]
    failed_at: Optional[datetime]
    replaced_at: Optional[datetime]
    replaced_by: Optional[str]
    replaces: Optional[str]
    asset_id: str
    symbol: str
    asset_class: str
    notional: Optional[float]
    qty: str
    filled_qty: str
    filled_avg_price: Optional[float]
    order_class: str
    order_type: str
    type: str
    side: str
    position_intent: str
    time_in_force: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    status: str
    extended_hours: bool
    legs: Optional[List["Order"]]
    trail_percent: Optional[float]
    trail_price: Optional[float]
    hwm: Optional[float]
    subtag: Optional[str]
    source: Optional[str]
    expires_at: datetime
    strategy: str


def get_orders():
    """Get pending orders registered on Alpaca.

        Response:
        [{
        "id": "1e1c6250-bb75-4e7a-b540-88c8f262161d",
        "client_order_id": "d3135a79-c8d2-4694-8115-5aa25bf51c80",
        "created_at": "2024-12-06T14:30:09.570798Z",
        "updated_at": "2024-12-06T14:30:17.771331Z",
        "submitted_at": "2024-12-06T14:30:17.7705Z",
        "filled_at": null,
        "expired_at": null,
        "canceled_at": null,
        "failed_at": null,
        "replaced_at": null,
        "replaced_by": null,
        "replaces": null,
        "asset_id": "f801f835-bfe6-4a9d-a6b1-ccbb84bfd75f",
        "symbol": "AMZN",
        "asset_class": "us_equity",
        "notional": null,
        "qty": "2",
        "filled_qty": "0",
        "filled_avg_price": null,
        "order_class": "bracket",
        "order_type": "limit",
        "type": "limit",
        "side": "sell",
        "position_intent": "sell_to_close",
        "time_in_force": "gtc",
        "limit_price": "243.5",
        "stop_price": null,
        "status": "new",
        "extended_hours": false,
        "legs": null,
        "trail_percent": null,
        "trail_price": null,
        "hwm": null,
        "subtag": null,
        "source": null,
        "expires_at": "2025-03-06T21:00:00Z"
    },...]
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/orders"
    response = requests.get(url, headers=headers)
    return response.json()

def get_order_count():
    """ Get number of pending orders
        Response:
        {"pending_orders":10}
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/orders"
    response = requests.get(url, headers=headers)
    rs = response.json()
    order_ctr=0
    for order in rs:
        if order['type'] != 'limit': #TODO: DO NOT RETURN TAKE PROFIT, STOP LOSS ORDERS 
            order_ctr +=1    
    return ({"pending_orders": order_ctr}), 200 
   

#TODO Test the following function 
def filter_order(client_order_id):
    """ Preprocess orders to get main order, take profit and stop loss orders.
        Each order is of type bracket.  
            Main order (at market value) + 2 suborders(take profit and stop loss)
        
        The three orders are linked by the client_order_id.
        So, when a suborder gets filled the trade can be considered complete.
        And we can get the profit/loss of the trade, and the time it took to complete.
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/orders"
    response = requests.get(url, headers=headers)
    orders = response.json()
    filtered_orders = [order for order in orders if order['client_order_id'] == client_order_id] # Get all orders with the same client_order_id
    filtered_orders.sort(key=lambda x: (x['filled_at'] is None, x['filled_at'])) # Sort by filled_at date (if filled_at is None, it will be at the end)
    main_order = filtered_orders[0] # Main order is the first one
    
    # Sort suborders by ascending limit price
    filtered_orders = filtered_orders[1:].sort(key=lambda x: x['limit_price']) 
    if main_order['side'] == 'buy':
        take_profit_order = filtered_orders[1]
        stop_loss_order = filtered_orders[0]
    else:
        take_profit_order = filtered_orders[0]
        stop_loss_order = filtered_orders[1] 
        
    return main_order, take_profit_order, stop_loss_order

#TODO Test the following function
def get_order_profit_loss(client_order_id):
    """ Get profit/loss of a trade.
        Response:
        {"profit_loss": 100}
    """
    main_order, take_profit_order, stop_loss_order = filter_order(client_order_id)
    if take_profit_order['filled_at'] is None and stop_loss_order['filled_at'] is None:
        return ({"profit_loss": "Trade not completed"}), 200
    else:
        # Sort take_profit_order and stop_loss_order by filled_at, if one is None then put it last
        orders = [take_profit_order, stop_loss_order]
        filled_order = orders.sort(key=lambda x: (x['filled_at'] is None, x['filled_at']))[0] # Get the first order that is not None   
        profit_loss = float(filled_order['filled_avg_price']) - float(main_order['filled_avg_price'])
        
        #TODO Update the order in the database with the profit_loss,and time it took to complete
        completion_time = 60 # TODO: fix this
        
        #Delete take_profit_order and stop_loss_order from database to reduce clutter.
        delete_order_sql(take_profit_order['id'])
        delete_order_sql(stop_loss_order['id'])
        
        # Update strategy params
        st.update_strategy_params(main_order, profit_loss,completion_time)
        
        return ({"profit_loss": profit_loss}), 200

#TODO Test the following function
def add_order_sql(order_id,strategy):
    """ Add order to database.
    
        Will only include strategy and order ID.
        Other info will be added from the Alpaca webhook.
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO orders (id, strategy) VALUES (%s, %s)", (order_id, strategy))
        conn.commit()
        cursor.close()
        conn.close()
        print(" Order added to db!")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return order_id,200

#TODO Test the following function
def update_order_sql(order_id):
    """ Update order in database.
    Based on the Alpaca webhook, look for the order in the database and update it.
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        if order is None:
            return ({"error": "Order not found"}), 404
        cursor.execute("""
            UPDATE orders
            SET client_order_id = %s, created_at = %s, updated_at = %s, submitted_at = %s, filled_at = %s,
            expired_at = %s, canceled_at = %s, failed_at = %s, replaced_at = %s, replaced_by = %s,
            replaces = %s, asset_id = %s, symbol = %s, asset_class = %s, notional = %s, qty = %s,
            filled_qty = %s, filled_avg_price = %s, order_class = %s, order_type = %s, type = %s,
            side = %s, position_intent = %s, time_in_force = %s, limit_price = %s, stop_price = %s,
            status = %s, extended_hours = %s, legs = %s, trail_percent = %s, trail_price = %s,
            hwm = %s, subtag = %s, source = %s, expires_at = %s
            WHERE id = %s
        """, (
            order.client_order_id, order.created_at, order.updated_at, order.submitted_at, order.filled_at,
            order.expired_at, order.canceled_at, order.failed_at, order.replaced_at, order.replaced_by,
            order.replaces, order.asset_id, order.symbol, order.asset_class, order.notional, order.qty,
            order.filled_qty, order.filled_avg_price, order.order_class, order.order_type, order.type,
            order.side, order.position_intent, order.time_in_force, order.limit_price, order.stop_price,
            order.status, order.extended_hours, order.legs, order.trail_percent, order.trail_price,
            order.hwm, order.subtag, order.source, order.expires_at, order_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        print(" Order updated in db!")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return order, 200

def filter_orders_by(id=None,strategy=None, symbol=None, side=None,state=None, from_date=None, to_date=None):
    """
    Get orders based on various filters.
    
    Parameters:
    strategy (str): The strategy of the orders.
    symbol (str): The symbol of the orders.
    side (str): The side of the orders (e.g., 'long' or 'short').
    from_date (str): The start date for filtering orders.
    to_date (str): The end date for filtering orders.
    
    Returns:
    list: A list of orders matching the filters.
    
    Example:
    orders = get_orders_by_filter(strategy='strategy1', from_date='2023-01-01', to_date='2023-01-31')
    """
    conn = sql.connect()
    cursor = conn.cursor()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    
    if strategy:
        query += " AND strategy = %s"
        params.append(strategy)
    if symbol:
        query += " AND symbol = %s"
        params.append(symbol)
    if side:
        query += " AND side = %s"
        params.append(side)
    if from_date:
        query += " AND created_at >= %s"
        params.append(from_date)
    if to_date:
        query += " AND created_at <= %s"
        params.append(to_date)
    if state:
        query += " AND order_state = %s"
        params.append(state)
    if id:
        query += " AND order_id = %s"
        params.append(id)
    
    cursor.execute(query, tuple(params))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return orders
 

def delete_order_sql(order_id):
    """ Delete order from database.
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()
        cursor.close()
        conn.close()
        print(" Order deleted from db!")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None, 200
    