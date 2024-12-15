""" Implement all api endpoints for orders """

import json
from fastapi import HTTPException
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from api.alpaca import login
import requests
import api.sql as sql
import mysql.connector
import api.strategies as st


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
def get_order_profit_loss(client_order_id):
    """ Get profit/loss of a trade.
        Response:
        {"profit_loss": 100}
    """
    pass
# Function to parse and format datetime strings
def parse_datetime(dt_str):
    return datetime.strptime(dt_str[:26], '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d %H:%M:%S')



def add_order_sql_from_apca(order):
    """ Add order to database.
        All info are added from the Alpaca webhook.
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        # Ensure all keys are present in the order dictionary
        order_data = {
            "order_id": order.get("order_id"),
            "client_order_id": order.get("client_order_id"),
            "created_at": parse_datetime(order.get("created_at")),
            "submitted_at": parse_datetime(order.get("submitted_at")),
            "symbol": order.get("symbol"),
            "qty": order.get("qty"),
            "filled_avg_price": order.get("filled_avg_price"),
            "type": order.get("type"),
            "side": order.get("side"),
            "limit_price": order.get("limit_price"),
            "stop_price": order.get("stop_price"),
            "status": order.get("status"),
            "trail_percent": order.get("trail_percent"),
            "trail_price": order.get("trail_price"),
            "strategy": "N/A"
        }
        # Insert the order into the database
        cursor.execute("INSERT INTO orders VALUES ( %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s, %s, %s, %s,%s) ", (
            order_data['order_id'], order_data['client_order_id'], order_data['created_at'], order_data['submitted_at'],
            order_data['symbol'], order_data['qty'], order_data['filled_avg_price'], order_data['type'],
            order_data['side'], order_data['limit_price'], order_data['stop_price'], order_data['status'],
            order_data['trail_percent'], order_data['trail_price'], order_data['strategy']
        )) 
        conn.commit()
        print("Order added to db!")
        return order, 200
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return {"error": str(err)}, 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}, 500
    finally:
        cursor.close()
        conn.close()
        
        
def update_order_sql(order):
    """ Update order in database.
    Based on the Alpaca webhook, look for the order in the database and update it.
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order['order_id'],))
        existing_order = cursor.fetchone()
        if existing_order is None:
            print(f"There is no associated orded with the following id {order['order_id']}... Creating new order! ")
            return add_order_sql_from_apca(order)
        print(f"Updating order with id {order['order_id']}... ")
        cursor.execute("UPDATE orders SET client_order_id = %s, created_at = %s, submitted_at = %s, symbol = %s, qty = %s, filled_avg_price = %s, type = %s, side = %s, limit_price = %s, stop_price = %s, status = %s, trail_percent = %s, trail_price = %s WHERE order_id = %s", (
            order['client_order_id'], parse_datetime(order['created_at']), parse_datetime(order['submitted_at']),
            order['symbol'], order['qty'], order['filled_avg_price'], order['type'], order['side'], order['limit_price'],
            order['stop_price'], order['status'], order['trail_percent'], order['trail_price'], order['order_id']
        ))
        conn.commit()
        return order, 200

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return {"error": str(err)}, 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}, 500
    finally:
        cursor.close()
        conn.close()


def update_order_strategy(order_id:str,strategy:str):
    """ Update order in database.
    Based on the Alpaca webhook, look for the order in the database and update it.
    """
    od_found = False
    while not od_found:
        try:
            conn = sql.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            existing_order = cursor.fetchone()
            if existing_order is None:
                continue 
            od_found = True
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return {"error": str(err)}, 500
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {"error": str(e)}, 500
        finally:
            cursor.close()
            conn.close()
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET strategy = %s WHERE order_id = %s", (strategy,order_id))
        conn.commit()
        return order_id, 200
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return {"error": str(err)}, 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {"error": str(e)}, 500
    finally:
        cursor.close()
        conn.close()


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
    

def format_order_data(data):
        # Parse the byte data to a dictionary
    data_dict = json.loads(data.decode('utf-8'))
    
    # Extract the relevant information
    event_data = data_dict.get('data', {})
    order = event_data.get('order', {})
    
    # Format the order data
    formatted_data = {
        "order_id": order.get('id'),
        "client_order_id": order.get('client_order_id'),
        "created_at": order.get('created_at'),
        "updated_at": order.get('updated_at'),
        "submitted_at": order.get('submitted_at'),
        "filled_at": order.get('filled_at'),
        "expired_at": order.get('expired_at'),
        "cancel_requested_at": order.get('cancel_requested_at'),
        "canceled_at": order.get('canceled_at'),
        "failed_at": order.get('failed_at'),
        "replaced_at": order.get('replaced_at'),
        "replaced_by": order.get('replaced_by'),
        "replaces": order.get('replaces'),
        "asset_id": order.get('asset_id'),
        "symbol": order.get('symbol'),
        "asset_class": order.get('asset_class'),
        "notional": order.get('notional'),
        "qty": order.get('qty'),
        "filled_qty": order.get('filled_qty'),
        "filled_avg_price": order.get('filled_avg_price'),
        "order_class": order.get('order_class'),
        "order_type": order.get('order_type'),
        "type": order.get('type'),
        "side": order.get('side'),
        "time_in_force": order.get('time_in_force'),
        "limit_price": order.get('limit_price'),
        "stop_price": order.get('stop_price'),
        "status": order.get('status'),
        "extended_hours": order.get('extended_hours'),
        "legs": order.get('legs'),
        "trail_percent": order.get('trail_percent'),
        "trail_price": order.get('trail_price'),
        "hwm": order.get('hwm')
    }    
    return formatted_data


from pydantic import BaseModel
import time

class OrderStrategy(BaseModel):
    order_id: str
    strategy: str
    