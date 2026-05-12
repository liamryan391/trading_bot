from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from app.domain import Candle

try:
    import talib  # type: ignore

    HAS_TALIB = True
except ImportError:  # pragma: no cover - depends on optional native install
    talib = None  # type: ignore
    HAS_TALIB = False


def _clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


class IndicatorEngine:
    def calculate(self, candles: list[Candle]) -> dict[str, Any]:
        if len(candles) < 30:
            raise ValueError("At least 30 candles are required for indicator analysis")

        close = np.array([candle.close for candle in candles], dtype=float)
        high = np.array([candle.high for candle in candles], dtype=float)
        low = np.array([candle.low for candle in candles], dtype=float)
        volume = np.array([candle.volume for candle in candles], dtype=float)

        indicators = (
            self._calculate_talib(close, high, low, volume)
            if HAS_TALIB
            else self._calculate_pandas(close, high, low, volume)
        )
        indicators["backend"] = "TA-Lib" if HAS_TALIB else "pandas-fallback"
        indicators["latest_close"] = _clean_number(close[-1])
        indicators["candles"] = len(candles)
        return indicators

    def candle_payload(self, candles: list[Candle]) -> list[dict[str, Any]]:
        return [asdict(candle) for candle in candles]

    def _calculate_talib(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> dict[str, Any]:
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        upper, middle, lower = talib.BBANDS(close, timeperiod=20)
        return {
            "sma_20": _clean_number(talib.SMA(close, timeperiod=20)[-1]),
            "sma_50": _clean_number(talib.SMA(close, timeperiod=50)[-1]),
            "ema_20": _clean_number(talib.EMA(close, timeperiod=20)[-1]),
            "rsi_14": _clean_number(talib.RSI(close, timeperiod=14)[-1]),
            "macd": _clean_number(macd[-1]),
            "macd_signal": _clean_number(macd_signal[-1]),
            "macd_hist": _clean_number(macd_hist[-1]),
            "bb_upper": _clean_number(upper[-1]),
            "bb_middle": _clean_number(middle[-1]),
            "bb_lower": _clean_number(lower[-1]),
            "atr_14": _clean_number(talib.ATR(high, low, close, timeperiod=14)[-1]),
            "obv": _clean_number(talib.OBV(close, volume)[-1]),
        }

    def _calculate_pandas(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> dict[str, Any]:
        close_s = pd.Series(close)
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        volume_s = pd.Series(volume)

        ema_12 = close_s.ewm(span=12, adjust=False).mean()
        ema_26 = close_s.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        bb_middle = close_s.rolling(window=20).mean()
        bb_std = close_s.rolling(window=20).std()
        tr = pd.concat(
            [
                high_s - low_s,
                (high_s - close_s.shift()).abs(),
                (low_s - close_s.shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)

        return {
            "sma_20": _clean_number(close_s.rolling(window=20).mean().iloc[-1]),
            "sma_50": _clean_number(close_s.rolling(window=50).mean().iloc[-1]),
            "ema_20": _clean_number(close_s.ewm(span=20, adjust=False).mean().iloc[-1]),
            "rsi_14": _clean_number(_rsi(close_s, period=14).iloc[-1]),
            "macd": _clean_number(macd.iloc[-1]),
            "macd_signal": _clean_number(macd_signal.iloc[-1]),
            "macd_hist": _clean_number((macd - macd_signal).iloc[-1]),
            "bb_upper": _clean_number((bb_middle + 2 * bb_std).iloc[-1]),
            "bb_middle": _clean_number(bb_middle.iloc[-1]),
            "bb_lower": _clean_number((bb_middle - 2 * bb_std).iloc[-1]),
            "atr_14": _clean_number(tr.rolling(window=14).mean().iloc[-1]),
            "obv": _clean_number(_obv(close_s, volume_s).iloc[-1]),
        }


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()

