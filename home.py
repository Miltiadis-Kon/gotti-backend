import threading
from main import start_fastapi, start_websocket_listener
PORT = 8000
HOST = "0.0.0.0"



if __name__ == "__main__":
    websocket_thread = threading.Thread(target=start_websocket_listener)
    websocket_thread.start()

    start_fastapi()
