import mysql.connector
import os
from dotenv import load_dotenv
load_dotenv()



def connect():
    return mysql.connector.connect(
        host="localhost",
        user = os.getenv("MYSQL_USER"),
        password = os.getenv("MYSQL_PASSWORD"),
        database = "gotti"
    )