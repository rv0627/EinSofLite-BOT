import os
import requests
from typing import List, Dict, Any, Optional
from src.core.config import read_env
import time

class ZerodhaClient:
    """Adapter for Zerodha Kite Connect API"""
    name = "zerodha"
    
    def __init__(self):
        self.api_key = read_env("ZERODHA_API_KEY")
        self.access_token = read_env("ZERODHA_ACCESS_TOKEN")
        self.base_url = "https://api.kite.trade"

        self.headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {self.api_key}:{self.access_token}"
        }

    def fetch_historical_data(self, instrument_token: str, start_date: str, end_date:str, interval: str = "day") -> Optional[Dict[str, Any]]:
        """Fetch historical data for a given instrument token and date range."""
        
        if not self.api_key or not self.access_token:
            print("Error: ZZerodha API credentials missing.")
            return None
        
        endpoint = f"{self.base_url}/instruments/historical/{instrument_token}/{interval}"

        params = {
            "from": start_date,
            "to": end_date
        }

        try:
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Zerodha API Error: {str(e)}")
            return None
        
    def fetch_ltp(self, instrument_token: str) -> Optional[Dict[str, Any]]:
        """Fetch last traded price for a given instrument token."""
        
        if not self.api_key or not self.access_token:
            print("Error: Zerodha API credentials missing.")
            return None
        
        endpoint = f"{self.base_url}/quote/ltp"
        params = {
            "i": instrument_token
        }

        try:
            response = requests.get(endpoint, headers=self.headers, timeout=5)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Zerodha API Error: {str(e)}")
            return None