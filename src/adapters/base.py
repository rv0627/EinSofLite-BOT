from typing import Protocol,List,Dict,Any
from datetime import date

# Interface
class MarketDataProvider(Protocol):
    name: str
    base_weight: float

    # End of day data
    def fetch_eod_data(self, symbol_id: str, ticker: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        ...

    # API working status 
    def health_probe(self) -> bool:
        ...