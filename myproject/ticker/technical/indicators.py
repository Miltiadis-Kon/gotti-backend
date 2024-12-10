import numpy as np
import pandas as pd

def candle_hammer(df: pd.DataFrame = None) -> pd.Series:
    """* Candlestick Detected: Hammer ("Weak - Reversal - Bullish Signal - Up"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["high"] - df["low"]) > 3 * (df["open"] - df["close"]))
        & (((df["close"] - df["low"]) / (0.001 + df["high"] - df["low"])) > 0.6)
        & (((df["open"] - df["low"]) / (0.001 + df["high"] - df["low"])) > 0.6)
    )

def candle_inverted_hammer(df: pd.DataFrame = None) -> pd.Series:
    """* Candlestick Detected: Inverted Hammer ("Weak - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["high"] - df["low"]) > 3 * (df["open"] - df["close"]))
        & ((df["high"] - df["close"]) / (0.001 + df["high"] - df["low"]) > 0.6)
        & ((df["high"] - df["open"]) / (0.001 + df["high"] - df["low"]) > 0.6)
    )

def candle_shooting_star(df: pd.DataFrame = None) -> pd.Series:
    """* Candlestick Detected: Shooting Star ("Weak - Reversal - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["open"].shift(1) < df["close"].shift(1)) & (df["close"].shift(1) < df["open"]))
        & (df["high"] - np.maximum(df["open"], df["close"]) >= (abs(df["open"] - df["close"]) * 3))
        & ((np.minimum(df["close"], df["open"]) - df["low"]) <= abs(df["open"] - df["close"]))
    )

def candle_hanging_man(df: pd.DataFrame = None) -> pd.Series:
    """* Candlestick Detected: Hanging Man ("Weak - Reliable - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["high"] - df["low"]) > (4 * (df["open"] - df["close"])))
        & (((df["close"] - df["low"]) / (0.001 + df["high"] - df["low"])) >= 0.75)
        & (((df["open"] - df["low"]) / (0.001 + df["high"] - df["low"])) >= 0.75)
        & (df["high"].shift(1) < df["open"])
        & (df["high"].shift(2) < df["open"])
    )

def candle_three_white_soldiers(df: pd.DataFrame = None) -> pd.Series:
    """*** Candlestick Detected: Three White Soldiers ("Strong - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["open"] > df["open"].shift(1)) & (df["open"] < df["close"].shift(1)))
        & (df["close"] > df["high"].shift(1))
        & (df["high"] - np.maximum(df["open"], df["close"]) < (abs(df["open"] - df["close"])))
        & ((df["open"].shift(1) > df["open"].shift(2)) & (df["open"].shift(1) < df["close"].shift(2)))
        & (df["close"].shift(1) > df["high"].shift(2))
        & (
            df["high"].shift(1) - np.maximum(df["open"].shift(1), df["close"].shift(1))
            < (abs(df["open"].shift(1) - df["close"].shift(1)))
        )
    )

def candle_three_black_crows(df: pd.DataFrame = None) -> pd.Series:
    """* Candlestick Detected: Three Black Crows ("Strong - Reversal - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["open"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1)))
        & (df["close"] < df["low"].shift(1))
        & (df["low"] - np.maximum(df["open"], df["close"]) < (abs(df["open"] - df["close"])))
        & ((df["open"].shift(1) < df["open"].shift(2)) & (df["open"].shift(1) > df["close"].shift(2)))
        & (df["close"].shift(1) < df["low"].shift(2))
        & (
            df["low"].shift(1) - np.maximum(df["open"].shift(1), df["close"].shift(1))
            < (abs(df["open"].shift(1) - df["close"].shift(1)))
        )
    )

def candle_doji(df: pd.DataFrame = None) -> pd.Series:
    """! Candlestick Detected: Doji ("Indecision / Neutral")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((abs(df["close"] - df["open"]) / (df["high"] - df["low"])) < 0.1)
        & ((df["high"] - np.maximum(df["close"], df["open"])) > (3 * abs(df["close"] - df["open"])))
        & ((np.minimum(df["close"], df["open"]) - df["low"]) > (3 * abs(df["close"] - df["open"])))
    )

def candle_three_line_strike(df: pd.DataFrame = None) -> pd.Series:
    """** Candlestick Detected: Three Line Strike ("Reliable - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["open"].shift(1) < df["open"].shift(2)) & (df["open"].shift(1) > df["close"].shift(2)))
        & (df["close"].shift(1) < df["low"].shift(2))
        & (
            df["low"].shift(1) - np.maximum(df["open"].shift(1), df["close"].shift(1))
            < (abs(df["open"].shift(1) - df["close"].shift(1)))
        )
        & ((df["open"].shift(2) < df["open"].shift(3)) & (df["open"].shift(2) > df["close"].shift(3)))
        & (df["close"].shift(2) < df["low"].shift(3))
        & (
            df["low"].shift(2) - np.maximum(df["open"].shift(2), df["close"].shift(2))
            < (abs(df["open"].shift(2) - df["close"].shift(2)))
        )
        & ((df["open"] < df["low"].shift(1)) & (df["close"] > df["high"].shift(3)))
    )

def candle_two_black_gapping(df: pd.DataFrame = None) -> pd.Series:
    """*** Candlestick Detected: Two Black Gapping ("Reliable - Reversal - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        ((df["open"] < df["open"].shift(1)) & (df["open"] > df["close"].shift(1)))
        & (df["close"] < df["low"].shift(1))
        & (df["low"] - np.maximum(df["open"], df["close"]) < (abs(df["open"] - df["close"])))
        & (df["high"].shift(1) < df["low"].shift(2))
    )

def candle_morning_star(df: pd.DataFrame = None) -> pd.Series:
    """*** Candlestick Detected: Morning Star ("Strong - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        (np.maximum(df["open"].shift(1), df["close"].shift(1)) < df["close"].shift(2)) & (df["close"].shift(2) < df["open"].shift(2))
    ) & ((df["close"] > df["open"]) & (df["open"] > np.maximum(df["open"].shift(1), df["close"].shift(1))))

def candle_evening_star(df: pd.DataFrame = None) -> np.ndarray:
    """*** Candlestick Detected: Evening Star ("Strong - Reversal - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        (np.minimum(df["open"].shift(1), df["close"].shift(1)) > df["close"].shift(2)) & (df["close"].shift(2) > df["open"].shift(2))
    ) & ((df["close"] < df["open"]) & (df["open"] < np.minimum(df["open"].shift(1), df["close"].shift(1))))

def candle_abandoned_baby(df: pd.DataFrame = None) -> pd.Series:
    """** Candlestick Detected: Abandoned Baby ("Reliable - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (
        (df["open"] < df["close"])
        & (df["high"].shift(1) < df["low"])
        & (df["open"].shift(2) > df["close"].shift(2))
        & (df["high"].shift(1) < df["low"].shift(2))
    )

def candle_morning_doji_star(df: pd.DataFrame = None) -> pd.Series:
    """** Candlestick Detected: Morning Doji Star ("Reliable - Reversal - Bullish Pattern - Up")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (df["close"].shift(2) < df["open"].shift(2)) & (
        abs(df["close"].shift(2) - df["open"].shift(2)) / (df["high"].shift(2) - df["low"].shift(2)) >= 0.7
    ) & (abs(df["close"].shift(1) - df["open"].shift(1)) / (df["high"].shift(1) - df["low"].shift(1)) < 0.1) & (
        df["close"] > df["open"]
    ) & (
        abs(df["close"] - df["open"]) / (df["high"] - df["low"]) >= 0.7
    ) & (
        df["close"].shift(2) > df["close"].shift(1)
    ) & (
        df["close"].shift(2) > df["open"].shift(1)
    ) & (
        df["close"].shift(1) < df["open"]
    ) & (
        df["open"].shift(1) < df["open"]
    ) & (
        df["close"] > df["close"].shift(2)
    ) & (
        (df["high"].shift(1) - np.maximum(df["close"].shift(1), df["open"].shift(1)))
        > (3 * abs(df["close"].shift(1) - df["open"].shift(1)))
    ) & (
        np.minimum(df["close"].shift(1), df["open"].shift(1)) - df["low"].shift(1)
    ) > (
        3 * abs(df["close"].shift(1) - df["open"].shift(1))
    )

def candle_evening_doji_star(df: pd.DataFrame = None) -> pd.Series:

    """** Candlestick Detected: Evening Doji Star ("Reliable - Reversal - Bearish Pattern - Down")"""

    # Fill NaN values with 0
    df = df.fillna(0)

    return (df["close"].shift(2) > df["open"].shift(2)) & (
        abs(df["close"].shift(2) - df["open"].shift(2)) / (df["high"].shift(2) - df["low"].shift(2)) >= 0.7
    ) & (abs(df["close"].shift(1) - df["open"].shift(1)) / (df["high"].shift(1) - df["low"].shift(1)) < 0.1) & (
        df["close"] < df["open"]
    ) & (
        abs(df["close"] - df["open"]) / (df["high"] - df["low"]) >= 0.7
    ) & (
        df["close"].shift(2) < df["close"].shift(1)
    ) & (
        df["close"].shift(2) < df["open"].shift(1)
    ) & (
        df["close"].shift(1) > df["open"]
    ) & (
        df["open"].shift(1) > df["open"]
    ) & (
        df["close"] < df["close"].shift(2)
    ) & (
        (df["high"].shift(1) - np.maximum(df["close"].shift(1), df["open"].shift(1)))
        > (3 * abs(df["close"].shift(1) - df["open"].shift(1)))
    ) & (
        np.minimum(df["close"].shift(1), df["open"].shift(1)) - df["low"].shift(1)
    ) > (
        3 * abs(df["close"].shift(1) - df["open"].shift(1))
    )

def fibonacci(df: pd.DataFrame = None) -> pd.Series:
    """* Fibonacci Retracement"""
    # Fill NaN values with 0
    df = df.fillna(0)
    levels = [0.236, 0.382, 0.5, 0.618, 0.786]
    retracement = (df["close"] - df["low"]) / (df["high"] - df["low"])    
    return retracement.isin(levels)


if __name__ == "__main__":
    df = get_ohlc_data()

    df["three_white_soldiers"] = candle_three_white_soldiers(df)
    df["three_black_crows"] = candle_three_black_crows(df)
    df["morning_star"] = candle_morning_star(df)
    df["evening_star"] = candle_evening_star(df)

    print(df[(df["three_white_soldiers"] == True) | (df["three_black_crows"] == True) | (df["morning_star"] == True) | (df["evening_star"] == True)])
    
    