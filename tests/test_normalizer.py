"""
Tests for Bot 2 — MarketDataNormalizer (src/services/normalizer.py)
Validates data normalization, anomaly detection, and confidence scoring.
"""

import pytest
from datetime import date

from src.services.normalizer import MarketDataNormalizer
from src.domain.models import ProcessedMarketData


class TestMarketDataNormalizer:
    """Test the MarketDataNormalizer service."""

    @pytest.fixture
    def normalizer(self):
        return MarketDataNormalizer(max_price_jump_pct=0.20)

    # ── Happy Path Tests ──

    def test_valid_data_returns_processed_record(self, normalizer):
        """Valid raw data should produce a ProcessedMarketData object."""
        raw = {
            "datetime": "2026-07-23",
            "open": "1500.00", "high": "1520.00",
            "low": "1490.00", "close": "1510.00",
            "volume": "2500000"
        }
        record, health = normalizer.process_raw_payload(raw, "INFY")

        assert record is not None
        assert isinstance(record, ProcessedMarketData)
        assert record.symbol_id == "INFY"
        assert record.open_price == 1500.0
        assert record.close_price == 1510.0
        assert record.volume == 2500000

    def test_health_score_perfect_data(self, normalizer):
        """Perfect data should yield a health score of 1.0."""
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "105",
            "low": "98", "close": "103",
            "volume": "1000000"
        }
        _, health = normalizer.process_raw_payload(raw, "TEST")
        assert health == 1.0

    def test_date_parsing(self, normalizer):
        """Date should be correctly parsed from raw payload."""
        raw = {
            "datetime": "2026-01-15",
            "open": "100", "high": "105",
            "low": "95", "close": "102",
            "volume": "500000"
        }
        record, _ = normalizer.process_raw_payload(raw, "TEST")
        assert record.date == date(2026, 1, 15)

    # ── Anomaly Detection Tests ──

    def test_high_less_than_low_is_anomalous(self, normalizer):
        """If high < low, the data is anomalous and health score drops."""
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "95",   # high < low = invalid
            "low": "98", "close": "97",
            "volume": "1000000"
        }
        record, health = normalizer.process_raw_payload(raw, "BAD")

        assert record.is_anomalous is True
        assert health <= 0.5  # Significant penalty

    def test_zero_price_is_anomalous(self, normalizer):
        """Zero or negative prices should be flagged as anomalous."""
        raw = {
            "datetime": "2026-07-23",
            "open": "0", "high": "105",
            "low": "98", "close": "103",
            "volume": "1000000"
        }
        record, health = normalizer.process_raw_payload(raw, "ZERO")

        assert record.is_anomalous is True
        assert health < 1.0

    def test_negative_volume_penalizes_health(self, normalizer):
        """Negative volume should reduce health score."""
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "105",
            "low": "98", "close": "103",
            "volume": "-500"
        }
        _, health = normalizer.process_raw_payload(raw, "NEGVOL")
        assert health == 0.8  # 1.0 - 0.2 penalty

    def test_large_price_jump_flagged(self, normalizer):
        """A price jump > 20% from previous close should be flagged."""
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "130",
            "low": "95", "close": "125",  # 25% jump from prev_close=100
            "volume": "2000000"
        }
        record, health = normalizer.process_raw_payload(raw, "JUMP", prev_close=100.0)

        assert record.is_anomalous is True
        assert health < 1.0

    def test_normal_price_change_not_flagged(self, normalizer):
        """A normal price change (< 20%) should not be flagged."""
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "108",
            "low": "98", "close": "105",  # 5% change
            "volume": "2000000"
        }
        record, health = normalizer.process_raw_payload(raw, "NORMAL", prev_close=100.0)

        assert record.is_anomalous is False
        assert health == 1.0

    # ── Edge Cases ──

    def test_invalid_date_returns_none(self, normalizer):
        """Invalid date format should return None."""
        raw = {
            "datetime": "not-a-date",
            "open": "100", "high": "105",
            "low": "98", "close": "103",
            "volume": "1000000"
        }
        record, health = normalizer.process_raw_payload(raw, "BADDATE")
        assert record is None
        assert health == 0.0

    def test_missing_fields_handled(self, normalizer):
        """Missing price fields should default to 0 and be caught as anomalous."""
        raw = {
            "datetime": "2026-07-23",
            # open, high, low, close, volume all missing
        }
        record, health = normalizer.process_raw_payload(raw, "EMPTY")

        assert record is not None
        assert record.close_price == 0
        assert record.is_anomalous is True  # Zero price triggers anomaly

    def test_health_score_never_below_zero(self, normalizer):
        """Health score should be clamped at 0.0 minimum."""
        raw = {
            "datetime": "2026-07-23",
            "open": "0", "high": "50",
            "low": "100", "close": "0",  # Multiple violations
            "volume": "-1000"
        }
        _, health = normalizer.process_raw_payload(raw, "WORST")
        assert health >= 0.0

    def test_custom_max_price_jump(self):
        """Custom max_price_jump_pct should be respected."""
        normalizer = MarketDataNormalizer(max_price_jump_pct=0.05)  # 5% threshold
        raw = {
            "datetime": "2026-07-23",
            "open": "100", "high": "112",
            "low": "98", "close": "110",  # 10% jump > 5% threshold
            "volume": "1000000"
        }
        record, health = normalizer.process_raw_payload(raw, "STRICT", prev_close=100.0)

        assert record.is_anomalous is True
