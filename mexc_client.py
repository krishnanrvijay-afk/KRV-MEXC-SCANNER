"""
mexc_client.py — Public MEXC Perpetual Futures API wrapper (no auth required).
Handles candles, order-book depth, and last-price fetch.
"""

import httpx
import asyncio
import logging
from typing import Optional

log = logging.getLogger("mexc_client")

MEXC_BASE = "https://contract.mexc.com"

# MEXC interval strings for kline endpoint
INTERVAL_15M = "Min15"
INTERVAL_1H  = "Min60"


class MexcClient:
    def __init__(self):
        self._http: Optional[httpx.AsyncClient] = None

    @property
    def http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=MEXC_BASE,
                timeout=10.0,
                headers={"Content-Type": "application/json"},
            )
        return self._http

    async def close(self):
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    async def _get(self, path: str, params: dict = None) -> dict:
        try:
            r = await self.http.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.warning(f"[mexc] GET {path} failed: {e}")
            return {"success": False}

    async def fetch_candles(
        self, symbol: str, interval: str, limit: int = 100
    ) -> list[dict]:
        """
        Fetch OHLCV candles from MEXC.
        Returns list of dicts: {open, high, low, close, volume}
        MEXC response: data.{time, open, high, low, close, vol}
        """
        data = await self._get(
            f"/api/v1/contract/kline/{symbol}",
            params={"interval": interval, "count": limit},
        )
        if not data.get("success"):
            return []
        d = data.get("data") or {}
        times  = d.get("time",  [])
        opens  = d.get("open",  [])
        highs  = d.get("high",  [])
        lows   = d.get("low",   [])
        closes = d.get("close", [])
        vols   = d.get("vol",   [])
        candles = []
        for i in range(len(closes)):
            try:
                candles.append({
                    "time":   int(times[i])  if i < len(times)  else 0,
                    "open":   float(opens[i])  if i < len(opens)  else 0.0,
                    "high":   float(highs[i])  if i < len(highs)  else 0.0,
                    "low":    float(lows[i])   if i < len(lows)   else 0.0,
                    "close":  float(closes[i]),
                    "volume": float(vols[i])   if i < len(vols)   else 0.0,
                })
            except (ValueError, TypeError):
                continue
        return candles

    async def fetch_orderbook(self, symbol: str, limit: int = 20) -> dict:
        """
        Fetch order-book depth.
        Returns {bids: [{px, sz}], asks: [{px, sz}]}
        MEXC response: data.{asks: [[price,vol],...], bids: [[price,vol],...]}
        """
        data = await self._get(
            f"/api/v1/contract/depth/{symbol}",
            params={"limit": limit},
        )
        if not data.get("success"):
            return {"bids": [], "asks": []}
        raw = data.get("data") or {}
        def _parse(levels):
            out = []
            for lv in (levels or []):
                try:
                    out.append({"px": float(lv[0]), "sz": float(lv[1])})
                except (IndexError, TypeError, ValueError):
                    pass
            return out
        return {
            "bids": _parse(raw.get("bids", [])),
            "asks": _parse(raw.get("asks", [])),
        }

    async def fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch latest traded price from public ticker."""
        data = await self._get(
            "/api/v1/contract/ticker",
            params={"symbol": symbol},
        )
        if not data.get("success"):
            return None
        try:
            return float(data["data"]["lastPrice"])
        except (KeyError, TypeError, ValueError):
            return None

    async def fetch_funding_rate(self, symbol: str) -> float:
        """Fetch current funding rate. Returns 0.0 on failure."""
        data = await self._get(
            "/api/v1/contract/funding_rate",
            params={"symbol": symbol},
        )
        if not data.get("success"):
            return 0.0
        try:
            return float(data["data"]["fundingRate"])
        except (KeyError, TypeError, ValueError):
            return 0.0
