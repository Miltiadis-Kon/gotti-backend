# FOR ALPACA MASTER ACCOUNT
import os
from dotenv import load_dotenv
load_dotenv()


apikey = os.getenv("APCA_API_KEY_PAPER")
apisecret = os.getenv("APCA_API_SECRET_KEY_PAPER")


def login():
    headers = {
    "accept": "application/json",
    "APCA-API-KEY-ID": apikey,
    "APCA-API-SECRET-KEY": apisecret
    }
    return headers

