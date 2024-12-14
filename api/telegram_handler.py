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


def format_msg(message:str):
    """ Format message to be sent to telegram channel."""
    symbol = message['symbol']
    side = message['side']
    stop_loss = message['stop_loss']
    take_profit = message['take_profit']
    avg_entry_price = message['filled_avg_price']
    msg = f"\n{side}   {symbol}   @{avg_entry_price}\nStop Loss: {stop_loss} $     Take Profit: {take_profit} $\n"
    
    return msg