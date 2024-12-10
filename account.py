from alpaca import login
import requests

def get_pnl():
    """ Get total profit/loss from active positions.
        
        Response: "pnl":"802.234"
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/positions"
    response = requests.get(url, headers=headers)
    intraday_pnl = sum(float(position['unrealized_pl']) for position in response.json())
    return ({"pnl": intraday_pnl}), 200

def get_cash_balance():
    """ Get available cash balance
        Response: 
        {"available_balance": cash}
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/account"
    response = requests.get(url, headers=headers)
    cash = response.json()['cash']
    print(cash)
    return ({"available_balance": cash}), 200