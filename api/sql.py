import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()



def connect():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("SUPABASE_CODE"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    print("Connected to db")
    return conn