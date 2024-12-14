import telegram

async def send_message(message:str):
    """ Send message to telegram channel."""
    response = format_msg(message)
    bot = telegram.Bot(token="7924089058:AAHfnR2vcgBq3LRyKVKu4XdqfRu0ofQMI40")
    try:
        await bot.send_message(chat_id=8139983484, text=f"New Order: {response}")
        return {"message": "Message sent"}, 200
    except Exception as e:
        print(e)
        return {"message": "Message not sent"}, 400


def format_msg(message):
    """ Format message to be sent to telegram channel."""
    order = message[0]  # Extract the order dictionary from the tuple
    symbol = order.get('symbol', 'N/A')
    side = order.get('side', 'N/A')
    stop_loss = order.get('stop_price', 'N/A')
    take_profit = order.get('limit_price', 'N/A')
    avg_entry_price = order.get('filled_avg_price', 'N/A') #TODO: add default value to get current market price via yfiannce or apca 

    msg = f"\n{side}   {symbol}   @{avg_entry_price}\nStop Loss: {stop_loss} $     Take Profit: {take_profit} $\n"
    
    return msg