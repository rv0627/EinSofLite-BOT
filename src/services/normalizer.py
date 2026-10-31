from typing import Dict, Any, Tuple
from datetime import datetime, date
from src.domain.models import ProcessedMarketData

class MarketDataNormalizer:
    def __init__(self, max_price_jump_pct: float = 0.20):
        self.max_price_jump_pct = max_price_jump_pct

    def process_raw_payload(self, raw_data: Dict[str,Any], symbol_id: str, prev_close: float = None) ->Tuple[ProcessedMarketData, float]:
        """Takes raw EOD data and normalizes it into ProcessedMarketData format. Also calculates confidence score based on data quality."""

        # Extract fields from raw data
        try:
            date_str = raw_data.get("datetime")
            record_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            open_p = float(raw_data.get("open", 0))
            high_p = float(raw_data.get("high", 0))
            low_p = float(raw_data.get("low", 0))
            close_p = float(raw_data.get("close", 0))
            volume = int(raw_data.get("volume", 0))

        except (ValueError, TypeError) as e:
            print(f"Data extraction error: {str(e)}")
            return None, 0.0
        
        # Basic validation checks
        is_anomalous = False
        health_score = 1.0

        if high_p < low_p:
            health_score -= 0.5
            is_anomalous = True

        if open_p <= 0 or close_p <= 0:
            health_score -= 0.8
            is_anomalous = True

        if volume < 0:
            health_score -= 0.2

        if prev_close and prev_close > 0:
            price_change_pct = abs((close_p - prev_close) / prev_close)
            if price_change_pct > self.max_price_jump_pct:
                # Check corporate actions before flagging as anomaly
                if not self._has_corporate_action(symbol_id, record_date):
                    health_score -= 0.3
                    is_anomalous = True

        health_score = max(0.0, round(health_score, 2))

        # finalize ProcessedMarketData object
        processed_record = ProcessedMarketData(
            symbol_id=symbol_id,
            date=record_date,
            open_price=open_p,
            high_price=high_p,
            low_price=low_p,
            close_price=close_p,
            volume=volume,
            confidence_score=0.0,  # Will be set by aggregation logic
            is_anomalous=is_anomalous
        )

        return processed_record, health_score

    def _has_corporate_action(self, symbol_id: str, check_date: date) -> bool:
        """Check if there was a stock split or dividend on or around this date."""
        # Placeholder for corporate action check against DB or external API
        # Returning False implies the >20% jump is unexplained
        return False