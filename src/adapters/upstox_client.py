import os
import requests
from typing import Dict, Any, Optional
from src.core.config import read_env

class UpstoxClient:
    def __init__(self):
        self.access_token = read_env("UPSTOX_ACCESS_TOKEN")
        self.base_url = "https://api.upstox.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }

    def fetch_historical_data(self, instrument_key: str, interval: str, to_date: str, from_date: str) -> Optional[Dict[str, Any]]:
        if not self.access_token:
            return None
        url = f"{self.base_url}/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Upstox API Error: {e}")
            return None

    def fetch_ltp(self, instrument_key: str) -> Optional[Dict[str, Any]]:
        if not self.access_token:
            return None
        url = f"{self.base_url}/market-quote/ltp"
        params = {"instrument_key": instrument_key}
        try:
            resp = requests.get(url, headers=self.headers, params=params, timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Upstox API Error: {e}")
            return None