import os
import requests
import time
import json
import uuid
import redis
from typing import Dict, List, Optional

from src.adapters.zerodha_client import ZerodhaClient
from src.adapters.eodhd_client import EodhdClient
from src.adapters.upstox_client import UpstoxClient
from src.adapters.marketstack_client import MarketstackClient
from src.adapters.nsebse_client import NSEBSEClient
from src.core.config import read_env

class MarketDataRouter:
    """Routes market data requests to appropriate providers based on availability and health status."""
    def __init__(self):
        self.twelve_data_key = read_env("TWELVE_DATA_API_KEY")
        
        # API Clients Initialization
        self.zerodha = ZerodhaClient()
        self.eodhd = EodhdClient()
        self.upstox = UpstoxClient()
        self.marketstack = MarketstackClient(api_key=read_env("MARKETSTACK_API_KEY"))
        self.nsebse = NSEBSEClient(api_key=read_env("NSEBSE_API_KEY"))
        
        # Redis setup for routing logs
        redis_url = read_env("REDIS_URL") or "redis://localhost:6379/0"
        try:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        except Exception as e:
            print(f"Failed to connect to Redis for logging: {e}")
            self.redis_client = None

    def _log_routing_event(self, provider: str, path: str, status: str, latency: int, is_error: bool):
        """Logs a routing event to Redis list 'system:routing_logs'"""
        if not self.redis_client:
            return
            
        log_entry = {
            "id": f"[{str(uuid.uuid4())[:4]}]",
            "provider": provider.upper(),
            "path": path,
            "status": status,
            "latency": f"{latency}ms",
            "isError": is_error
        }
        
        try:
            # Push to left of list
            self.redis_client.lpush("system:routing_logs", json.dumps(log_entry))
            # Keep only the last 50 logs
            self.redis_client.ltrim("system:routing_logs", 0, 49)
        except Exception as e:
            print(f"Error logging to Redis: {e}")

    def fetch_eod_data(self, ticker: str, start_date: str = None, end_date: str = None) -> Dict[str, List[Dict]]:
        """Fetch EOD data from all available providers concurrently."""
        print(f"[ROUTING] Routing Concurrent EOD request for {ticker}")
        import concurrent.futures

        results = {}

        def get_twelve_data():
            return self.fetch_twelve_data(ticker)


        def get_marketstack():
            if start_date and end_date:
                start_time = time.time()
                try:
                    data = self.marketstack.fetch_eod_data(None, ticker, start_date, end_date)
                    latency = int((time.time() - start_time) * 1000)
                    if data:
                        self._log_routing_event("MARKETSTACK", "GET /eod", "200 OK", latency, False)
                        return data
                    else:
                        self._log_routing_event("MARKETSTACK", "GET /eod", "404 NOT_FOUND", latency, True)
                except Exception as e:
                    latency = int((time.time() - start_time) * 1000)
                    self._log_routing_event("MARKETSTACK", "GET /eod", "500 ERROR", latency, True)
            return None

        def get_nsebse():
            if start_date and end_date:
                start_time = time.time()
                try:
                    data = self.nsebse.fetch_eod_data(None, ticker, start_date, end_date)
                    latency = int((time.time() - start_time) * 1000)
                    if data:
                        self._log_routing_event("NSEBSE", "GET /historical", "200 OK", latency, False)
                        return data
                    else:
                        self._log_routing_event("NSEBSE", "GET /historical", "404 NOT_FOUND", latency, True)
                except Exception as e:
                    latency = int((time.time() - start_time) * 1000)
                    self._log_routing_event("NSEBSE", "GET /historical", "500 ERROR", latency, True)
            return None

        def get_eodhd():
            if start_date and end_date:
                start_time = time.time()
                try:
                    data = self.eodhd.fetch_eod_data(ticker, start_date, end_date)
                    latency = int((time.time() - start_time) * 1000)
                    if data:
                        self._log_routing_event("EODHD", "GET /eod", "200 OK", latency, False)
                        return self.__format__eodhd(data)
                    else:
                        self._log_routing_event("EODHD", "GET /eod", "404 NOT_FOUND", latency, True)
                except Exception as e:
                    latency = int((time.time() - start_time) * 1000)
                    self._log_routing_event("EODHD", "GET /eod", "500 ERROR", latency, True)
            return None

        tasks = {
            "twelvedata": get_twelve_data,
            "marketstack": get_marketstack,
            "nsebse": get_nsebse,
            "eodhd": get_eodhd
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_source = {executor.submit(func): source for source, func in tasks.items()}
            for future in concurrent.futures.as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    data = future.result()
                    if data:
                        results[source] = data
                        print(f"[SUCCESS] Data fetched successfully from {source} for {ticker}")
                    else:
                        print(f"[WARN] No data from {source} for {ticker}")
                except Exception as exc:
                    print(f"[ERROR] {source} generated an exception for {ticker}: {exc}")

        return results
    
    def fetch_live_data(self, ticker: str, instrument_token: str) -> Optional[Dict]:
        """Fetch live data for a given symbol."""
        print(f"[ROUTING] Routing live data request for {ticker} -> Primary: Zerodha")
        
        start_time = time.time()
        try:
            zerodha_data = self.zerodha.fetch_ltp(instrument_token)
            latency = int((time.time() - start_time) * 1000)
            if zerodha_data:
                self._log_routing_event("ZERODHA", "GET /quote", "200 OK", latency, False)
                return zerodha_data
            else:
                self._log_routing_event("ZERODHA", "GET /quote", "404 NOT_FOUND", latency, True)
        except Exception as e:
            latency = int((time.time() - start_time) * 1000)
            self._log_routing_event("ZERODHA", "GET /quote", "500 ERROR", latency, True)
            
        return None
    
    def fetch_twelve_data(self, ticker: str) -> Optional[List[Dict]]:
        """Call Twelve Data API."""
        url = f"https://api.twelvedata.com/time_series?symbol={ticker}&exchange=NSE&interval=1day&outputsize=90&apikey={self.twelve_data_key}"
        
        start_time = time.time()
        try:
            response = requests.get(url, timeout=10)
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code == 429:
                self._log_routing_event("TWELVEDATA", "GET /time_series", "429 TOO_MANY", latency, True)
            elif response.status_code != 200:
                self._log_routing_event("TWELVEDATA", "GET /time_series", f"{response.status_code} ERROR", latency, True)
                
            response.raise_for_status()
            result = response.json()

            if "values" in result:
                self._log_routing_event("TWELVEDATA", "GET /time_series", "200 OK", latency, False)
                return result["values"]
            else:
                self._log_routing_event("TWELVEDATA", "GET /time_series", "404 NOT_FOUND", latency, True)
        
        except requests.exceptions.RequestException as e:
            latency = int((time.time() - start_time) * 1000)
            self._log_routing_event("TWELVEDATA", "GET /time_series", "500 ERROR", latency, True)
            print(f"[ERROR] TwelveData API Error: {e}")
        return None
    
    # --- Formatting Methods ---

    def __format__zerodha_historical(self, candles: List[List]) -> List[Dict]:
        formatted_data = []
        for candle in candles:
            formatted_data.append({
                "datetime": candle[0][:10],  # Convert timestamp to date string
                "open": str(candle[1]),
                "high": str(candle[2]),
                "low": str(candle[3]),
                "close": str(candle[4]),
                "volume": str(candle[5])
            })
        return formatted_data

    def __format__eodhd(self, raw_data: List[Dict]) -> List[Dict]:
        formatted = []
        for row in raw_data:
            formatted.append({
                "datetime": row.get("date"),
                "open": str(row.get("open")),
                "high": str(row.get("high")),
                "low": str(row.get("low")),
                "close": str(row.get("close")),
                "volume": str(row.get("volume"))
            })
        return formatted

    def __format__upstox(self, candles: List[List]) -> List[Dict]:
        formatted = []
        for candle in candles:
            formatted.append({
                "datetime": candle[0][:10],
                "open": str(candle[1]),
                "high": str(candle[2]),
                "low": str(candle[3]),
                "close": str(candle[4]),
                "volume": str(candle[5])
            })
        return formatted






# import os
# import requests
# from typing import Dict, List, Optional
# from src.adapters.zerodha_client import ZerodhaClient

# class MarketDataRouter:
#     """Routes market data requests to appropriate providers based on availability and health status."""
#     def __init__(self):
#         self.zerodha = ZerodhaClient()
#         self.twelve_data_key = os.getenv("TWELVE_DATA_API_KEY")

#     def fetch_eod_data(self, ticker: str, instrument_token: str = None, start_date: str = None, end_date: str = None) -> Optional[List[Dict]]:
#         """Fetch EOD data for a given symbol and date range."""

#         print(f"[ROUTING] Routing EOD request for {ticker} -> Primary: Twelve Data")

#         # Try Twelve Data first
#         data = self.fetch_twelve_data(ticker)

#         # If Twelve Data fails, fallback to Zerodha
#         if not data and instrument_token and start_date and end_date:
#             print(f"[WARN] Twelve Data failed for {ticker}. Falling back to Zerodha.")
#             zerodha_data = self.zerodha.fetch_historical_data(instrument_token, start_date, end_date)

#             if zerodha_data and "data" in zerodha_data and "candles" in zerodha_data["data"]:
#                 return self.__format__zerodha_historical(zerodha_data["data"]["candles"])
            
#         return data
    
#     def fetch_live_data(self, ticker: str, instrument_token: str) -> Optional[Dict]:
#         """Fetch live data for a given symbol."""

#         print(f"[ROUTING] Routing live data request for {ticker} -> Primary: Zerodha")
#         return self.zerodha.fetch_ltp(instrument_token)
    
#     def fetch_twelve_data(self, ticker: str) -> Optional[List[Dict]]:
#         """Call Twelve Data API."""

#         url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=7&apikey={self.twelve_data_key}"
#         try:
#             response = requests.get(url, timeout=10)
#             response.raise_for_status()
#             result = response.json()

#             if "values" in result:
#                 return result["values"]
        
#         except requests.exceptions.RequestException as e:
#             print(f"[ERROR] TwelveData API Error: {e}")
#         return None
    
#     def __format__zerodha_historical(self, candles: List[List]) -> List[Dict]:
#         """Format Zerodha historical data to match Twelve Data structure."""
#         formatted_data = []
#         for candle in candles:
#             formatted_data.append({
#                 "datetime": candle[0][:10],  # Convert timestamp to date string
#                 "open": str(candle[1]),
#                 "high": str(candle[2]),
#                 "low": str(candle[3]),
#                 "close": str(candle[4]),
#                 "volume": str(candle[5])
#             })
#         return formatted_data