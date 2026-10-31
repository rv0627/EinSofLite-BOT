import requests
from typing import List, Dict, Any
from datetime import date
from .base import MarketDataProvider

class MarketstackClient(MarketDataProvider):
    name = "marketstack"
    base_weight = 0.75  # Slightly lower weight than primary

    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "http://api.marketstack.com/v1"

    def health_probe(self) -> bool:
        return bool(self.api_key)
        
    def fetch_eod_data(self, symbol_id: str, ticker: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        if not self.api_key:
            print("⚠️ Marketstack API key missing. Returning empty data.")
            return []
            
        url = f"{self.base_url}/eod"
        params = {
            "access_key": self.api_key,
            "symbols": f"{ticker}.XNSE", # Assuming NSE symbols for India
            "date_from": start_date,
            "date_to": end_date,
            "limit": 100
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            formatted_data = []
            if "data" in result:
                for row in result["data"]:
                    formatted_data.append({
                        "datetime": row.get("date")[:10],
                        "open": row.get("open"),
                        "high": row.get("high"),
                        "low": row.get("low"),
                        "close": row.get("close"),
                        "volume": row.get("volume")
                    })
            return formatted_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Marketstack API Error: {e}")
        
        return []
