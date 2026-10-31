import os
import requests
from typing import Dict, Any, Optional
from src.core.config import read_env

class EodhdClient:
    def __init__(self):
        self.api_key = read_env("EODHD_API_KEY")
        self.base_url = "https://eodhd.com/api"

    def fetch_eod_data(self, ticker: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        """EODHD API get EOD data for a given ticker and date range. Returns None if API key is missing or if there's an error."""
        if not self.api_key:
            return None
        url = f"{self.base_url}/eod/{ticker}.NSE?api_token={self.api_key}&fmt=json&from={start_date}&to={end_date}"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ EODHD API Error: {e}")
            return None