import requests
from sqlalchemy import JSON
from .base import MarketDataProvider
from datetime import date
from typing import List, Dict, Any

class TwelveDataAdapter(MarketDataProvider):

    name = "twelve_data"
    base_weight = 0.85

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.twelvedata.com"

    def health_probe(self) -> bool:
        # Check if API works
        url = f"{self.base_url}/api_usage?apikey={self.api_key}"
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
        
    def fetch_eod_data(self, symbol_id: str, ticker: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/time_series"
        params = {
            "symbol": ticker,
            "exchange": "NSE",
            "interval": "1day",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "apikey": self.api_key,
            "format": "JSON"
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # create data in the format we want
        if "values" in data:
            return data["values"]
        return []