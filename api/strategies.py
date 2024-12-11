import sql as sql
import mysql.connector

#TODO: IMPLEMENT THIS
def get_strategies():
    """ Get list of strategies available
        Response:
        [{"strategy_name":"mean_reversion",
        "description":"buy low, sell high",
        "winrate: 0.7",
        "risk_reward_ratio": 2.0,
        "max_drawdown": 0.1,
        "avg_return": 0.05,
        "avg_holding_period": 3,
        "avg_trades_per_month": 10,
        "avg_profit_per_trade": 1000,
        "total_trades": 100,
        "total_profit_loss": 5000,
        "created_at": "2024-12-06T14:30:09.570798Z",
        "updated_at": "2024-12-06T14:30:17.771331Z",
        "is_active": true,
        }]
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies")
        strategies = cursor.fetchall()
        cursor.close()
        conn.close()
        print(" Strategies fetched from db!")
        return strategies, 200
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Error: {e}")
        return ({"error": "Error fetching strategies"}), 500
    

#TODO: IMPLEMENT THIS
def get_strategy(strategy_name):
    """ Get details of a strategy
        Response:
        {"strategy_name":"mean_reversion",
        "description":"buy low, sell high",
        "winrate: 0.7",
        "risk_reward_ratio": 2.0,
        "max_drawdown": 0.1,
        "avg_return": 0.05,
        "avg_holding_period": 3,
        "avg_trades_per_month": 10,
        "avg_profit_per_trade": 1000,
        "total_trades": 100,
        "total_profit_loss": 5000,
        "created_at": "2024-12-06T14:30:09.570798Z",
        "updated_at": "2024-12-06T14:30:17.771331Z",
        "is_active": true,
        }
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies WHERE strategy_name = %s", (strategy_name,))
        strategy = cursor.fetchone()
        cursor.close()
        conn.close()
        print(" Strategy fetched from db!")
        return strategy, 200
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Error: {e}")
        return ({"error": "Error fetching strategy"}), 500


def add_strategy(strategy_name,description,risk_reward_ratio,max_drawdown):
    """ Add a new strategy
        Request:
        {"strategy_name":"mean_reversion",
        "description":"buy low, sell high",
        "winrate: 0.7",
        "risk_reward_ratio": 2.0,
        "max_drawdown": 0.1,
        "avg_holding_period": 3,
        "avg_trades_per_month": 10,
        "avg_profit_per_trade": 1000,
        "total_trades": 100,
        "total_profit_loss": 5000,
        "created_at": "2024-12-06T14:30:09.570798Z",
        "updated_at": "2024-12-06T14:30:17.771331Z",
        "is_active": true,
        }
        Response:
        {"message":"Strategy added successfully"}
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO strategies (strategy_name,description,risk_reward_ratio,max_drawdown) VALUES (%s,%s,%s,%s)", (strategy_name,description,risk_reward_ratio,max_drawdown))
        conn.commit()
        cursor.close()
        conn.close()
        print(" Strategy added to db!")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Error: {e}")
        return ({"error": "Error adding strategy"}), 500
    return ({"message":"Strategy added successfully"}), 200

def enable_strategy(strategy_name):
    """ Enable/Disable a strategy
        Response:
        {"message":"Strategy enabled successfully"}
    """
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies WHERE strategy_name = %s", strategy_name)
        stratrgy = cursor.fetchone()
        if stratrgy is None:
            return ({"error": "Strategy not found"}), 404
        is_active = not stratrgy['is_active']
        cursor.execute(
            "UPDATE strategies SET is_active = %s WHERE strategy_name = %s", (is_active, strategy_name)
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(" Strategy updated in db!")
        
        #TODO: Add logic to enable/disable strategy script in trading bot
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Error: {e}")
        return ({"error": "Error updating strategy"}), 500
    return ({"message":"Strategy enabled successfully"}), 200


# Add logic to calculate strategy params 
def update_strategy_params(profit_loss,completion_time,strategy):
    """ Update parameters of single strategy.
    
        Strategies have specific fields that need to be calculated.
        
        Risk Reward Ratio: Average profit per trade / Average loss per trade
        Winrate: Number of profitable trades / Total trades
        Max Drawdown: Maximum loss from peak to trough
        
        Average Holding Period: Average time between buy and sell
        Average Trades Per Month: Total trades / Total months
        Average Profit Per Trade: Total profit / Total trades
        Total Trades: Number of trades
        Total Profit Loss: Total profit - Total loss
        profitable_trades: Number of profitable trades
    """
    total_trades = strategy['total_trades'] + 1 # Increment total trades by 1
    total_profit_loss = strategy['total_profit_loss'] + profit_loss # Increment total profit loss by profit_loss
    avg_profit_per_trade = total_profit_loss / total_trades # Calculate average profit per trade
    avg_trades_per_mo = round(total_trades / 12, 2) # Calculate average trades per monthtotal_trades / 12 # Calculate average trades per month
    avg_holding_period = round(completion_time, 2) # Calculate average holding period
    if profit_loss > 0:
        profitable_trades = strategy['profitable_trades'] + 1 # Increment profitable trades by 1
    else:
        profitable_trades = strategy['profitable_trades'] # Keep profitable trades the same
    
    winrate = profitable_trades / total_trades # Calculate winrate
    
    # Update the strategy with the calculated parameters
    try:
        conn = sql.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM strategies WHERE strategy_name = %s", (strategy['strategy_name'],))
        order = cursor.fetchone()
        if order is None:
            return ({"error": "Strategy not found"}), 404
        cursor.execute(
            "UPDATE strategies SET winrate = %s, avg_holding_period = %s, avg_trades_per_month = %s, avg_profit_per_trade = %s, total_trades = %s, total_profit_loss = %s, profitable_trades = %s WHERE strategy_name = %s",
            (winrate,avg_holding_period, avg_trades_per_mo, avg_profit_per_trade, total_trades, total_profit_loss, profitable_trades, strategy['strategy_name'])
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(" Strategy updated in db!")
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    except Exception as e:
        print(f"Error: {e}")
    return ({"error": "Error updating order"}), 500
        