
import requests
from alpaca import login

def get_positions():
    """ Get active positions registered on Alpaca.

        Response :   
        [{
        "asset_id":"b0b6dd9d-8b9b-48a9-ba46-b9d54906e415",
        "symbol":"AAPL",
        "exchange":"NASDAQ",
        "asset_class":"us_equity",
        "asset_marginable":true,
        "qty":"21",
        "avg_entry_price":"239.707835",
        "side":"long",
        "market_value":"5184.2007",
        "cost_basis":"5033.864545",
        "unrealized_pl":"150.336155",
        "unrealized_plpc":"0.0298649583547743",
        "unrealized_intraday_pl":"84.5607",
        "unrealized_intraday_plpc":"0.0165816998846977",
        "current_price":"246.8667",
        "lastday_price":"242.84",
        "change_today":"0.0165816998846977",
        "qty_available":"5"
    },...]
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/positions"
    response = requests.get(url, headers=headers)
    return (response.text), 200


def get_position_count():
    """ Get number of active positions
        Response:
        {"active_positions":10}
    """
    headers = login()
    url = "https://paper-api.alpaca.markets/v2/positions"
    response = requests.get(url, headers=headers)
    active_pos_ctr = len(response.json() )
    return ({"active_positions": active_pos_ctr}), 200
