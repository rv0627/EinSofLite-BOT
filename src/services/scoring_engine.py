import os
import statistics
from datetime import date
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.domain.models import ProcessedMarketData, SymbolMaster, ScoringDataset, SystemSettings

class ScoringEngine:
    def __init__(self, session: Session):
        self.session = session
        self.factor_weights = self._load_factor_weights()
        self.penalty_params = self._load_penalty_params()

    def _load_penalty_params(self) -> Dict[str, float]:
        setting = self.session.query(SystemSettings).filter_by(key="bot3_config").first()
        if setting and setting.value and "penalty_params" in setting.value:
            return setting.value["penalty_params"]
        return {"base": 0.5, "multiplier": 0.5}

    def _load_factor_weights(self) -> Dict[str, float]:
        setting = self.session.query(SystemSettings).filter_by(key="bot3_config").first()
        if setting and setting.value and "weights" in setting.value:
            w = setting.value["weights"]
            _w_value = int(w.get("value", 20))
            _w_dividend = int(w.get("dividend", 20))
            _w_quality = int(w.get("quality", 20))
            _w_momentum = int(w.get("momentum", 20))
            _w_volatility = int(w.get("volatility", 20))
        else:
            _w_value = int(os.getenv("WEIGHT_VALUE", "20"))
            _w_dividend = int(os.getenv("WEIGHT_DIVIDEND", "20"))
            _w_quality = int(os.getenv("WEIGHT_QUALITY", "20"))
            _w_momentum = int(os.getenv("WEIGHT_MOMENTUM", "20"))
            _w_volatility = int(os.getenv("WEIGHT_VOLATILITY", "20"))
            
        _total = _w_value + _w_dividend + _w_quality + _w_momentum + _w_volatility
        if _total == 0: _total = 100
        return {
            "value":      _w_value      / _total,
            "dividend":   _w_dividend   / _total,
            "quality":    _w_quality    / _total,
            "momentum":   _w_momentum   / _total,
            "volatility": _w_volatility / _total,
        }

    def _calculate_momentum_score(self, price_history: List[ProcessedMarketData]) -> float:
        """
        Calculates momentum based on short-term vs long-term moving averages and rate of change.
        Returns a score from 0 to 100.
        """
        if len(price_history) < 20:
            return 50.0  # Neutral if not enough data
        
        # Calculate 10-day and 20-day moving averages as proxies for momentum if data is limited
        closes = [p.close_price for p in price_history if p.close_price is not None]
        if not closes:
            return 50.0

        short_term_period = min(10, len(closes) // 2)
        long_term_period = min(20, len(closes))

        short_term_ma = sum(closes[-short_term_period:]) / short_term_period
        long_term_ma = sum(closes[-long_term_period:]) / long_term_period

        # Trend strength: short term vs long term
        trend_ratio = short_term_ma / long_term_ma if long_term_ma > 0 else 1.0
        
        # Rate of change over the full available period
        start_price = closes[0]
        end_price = closes[-1]
        roc = (end_price - start_price) / start_price if start_price > 0 else 0

        # Base score 50, adjust based on trend and roc
        score = 50.0 + (trend_ratio - 1.0) * 100.0 + roc * 50.0
        
        return max(0.0, min(100.0, score))

    def _calculate_volatility_score(self, price_history: List[ProcessedMarketData]) -> float:
        """
        Calculates volatility score. Lower volatility = higher score (safer).
        Returns a score from 0 to 100.
        """
        if len(price_history) < 5:
            return 50.0
        
        closes = [p.close_price for p in price_history if p.close_price is not None]
        returns = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                returns.append((closes[i] - closes[i-1]) / closes[i-1])
            else:
                returns.append(0.0)

        if len(returns) < 2:
            return 50.0

        std_dev = statistics.stdev(returns)
        
        # Normalize: Assuming a daily stdev of 0.02 (2%) is average (score 50)
        # Stdev 0.0 -> score 100
        # Stdev 0.04+ -> score 0
        score = 100.0 - (std_dev / 0.04) * 100.0
        
        return max(0.0, min(100.0, score))

    def _fetch_fundamental_data(self, ticker: str) -> Tuple[float, float, float]:
        """
        Connects to Yahoo Finance (yfinance) to get fundamental data (P/E, Yield, ROE, Profit Margin)
        and calculates Value, Dividend, and Quality scores (0-100).
        """
        import yfinance as yf
        
        value_score = 50.0
        dividend_score = 50.0
        quality_score = 50.0
        
        try:
            # For Indian stocks (NSE), yfinance requires the ".NS" suffix
            yf_ticker = f"{ticker}.NS"
            stock = yf.Ticker(yf_ticker)
            info = stock.info
            
            # 1. Value Score (Based on P/E Ratio)
            # Lower P/E is better for value
            pe = info.get("trailingPE", info.get("forwardPE"))
            if isinstance(pe, str):
                try: pe = float(pe)
                except ValueError: pe = None

            if pe is not None and pe > 0:
                if pe < 10: value_score = 100.0
                elif pe < 15: value_score = 80.0
                elif pe < 20: value_score = 60.0
                elif pe < 30: value_score = 40.0
                else: value_score = 20.0
            else:
                value_score = 50.0  # Neutral if unknown or negative
                
            # 2. Dividend Score (Based on Dividend Yield)
            # Higher Yield is better
            yield_val = info.get("dividendYield")
            if isinstance(yield_val, str):
                try: yield_val = float(yield_val)
                except ValueError: yield_val = None

            if yield_val is not None:
                if yield_val >= 0.05: dividend_score = 100.0        # >= 5%
                elif yield_val >= 0.04: dividend_score = 80.0       # >= 4%
                elif yield_val >= 0.02: dividend_score = 60.0       # >= 2%
                elif yield_val >= 0.01: dividend_score = 40.0       # >= 1%
                elif yield_val > 0: dividend_score = 20.0           # > 0%
                else: dividend_score = 0.0
            else:
                dividend_score = 50.0
                
            # 3. Quality Score (Based on ROE and Profit Margin)
            # Higher ROE and Margin is better
            roe = info.get("returnOnEquity")
            margin = info.get("profitMargins")
            
            if isinstance(roe, str):
                try: roe = float(roe)
                except ValueError: roe = None
                
            if isinstance(margin, str):
                try: margin = float(margin)
                except ValueError: margin = None
            
            roe_score = 50.0
            if roe is not None:
                if roe >= 0.20: roe_score = 100.0
                elif roe >= 0.15: roe_score = 80.0
                elif roe >= 0.10: roe_score = 60.0
                elif roe >= 0.05: roe_score = 40.0
                else: roe_score = 20.0
                
            margin_score = 50.0
            if margin is not None:
                if margin >= 0.20: margin_score = 100.0
                elif margin >= 0.15: margin_score = 80.0
                elif margin >= 0.10: margin_score = 60.0
                elif margin >= 0.05: margin_score = 40.0
                else: margin_score = 20.0
                
            quality_score = (roe_score + margin_score) / 2.0

        except Exception as e:
            print(f"Error fetching fundamentals from Yahoo Finance for {ticker}: {e}")
            
        return value_score, dividend_score, quality_score

    def calculate_scores_for_symbol(self, symbol: SymbolMaster) -> ScoringDataset:
        """
        Calculates all factor scores and the final confidence-weighted EIN score for a single symbol.
        """
        # Fetch last 30 days of processed data for momentum and volatility
        recent_data = self.session.query(ProcessedMarketData).filter(
            ProcessedMarketData.symbol_id == symbol.symbol_id
        ).order_by(ProcessedMarketData.date.desc()).limit(30).all()

        if not recent_data:
            return None # Skip scoring if no real data

        recent_data.reverse()  # Chronological order

        # Calculate Technical Factors
        momentum = self._calculate_momentum_score(recent_data)
        volatility = self._calculate_volatility_score(recent_data)

        # Calculate Fundamental Factors (Real data will be fetched here when premium API is added)
        value, dividend, quality = self._fetch_fundamental_data(symbol.nse_ticker or symbol.symbol_id)

        # Average data quality confidence over the period
        if recent_data:
            avg_confidence = sum(d.confidence_score for d in recent_data if d.confidence_score is not None) / len(recent_data)
        else:
            avg_confidence = 0.5 # default moderate confidence if no data

        # Weighted EIN Score (weights loaded from DB or .env)
        base_ein_score = (
            value      * self.factor_weights["value"]      +
            dividend   * self.factor_weights["dividend"]   +
            quality    * self.factor_weights["quality"]    +
            momentum   * self.factor_weights["momentum"]   +
            volatility * self.factor_weights["volatility"]
        )

        # Confidence-Weighted adjustment (Penalize score based on data uncertainty)
        # If confidence is 1.0 (100%), score remains unchanged.
        # If confidence is 0.8 (80%), score is reduced by 10% (adjust formula as needed).
        confidence_penalty_factor = self.penalty_params.get("base", 0.5) + (self.penalty_params.get("multiplier", 0.5) * avg_confidence) # Maps [0,1] confidence to [0.5, 1.0] multiplier
        
        final_ein_score = base_ein_score * confidence_penalty_factor

        dataset = ScoringDataset(
            symbol_id=symbol.symbol_id,
            date=date.today(),
            value_score=round(value, 2),
            dividend_score=round(dividend, 2),
            quality_score=round(quality, 2),
            momentum_score=round(momentum, 2),
            volatility_score=round(volatility, 2),
            confidence_weight=round(avg_confidence, 2),
            ein_score=round(final_ein_score, 2)
        )
        return dataset

    def rank_and_save_datasets(self, datasets: List[ScoringDataset]):
        """
        Assigns ranks based on the final EIN score and saves to the database.
        """
        # Sort descending by EIN Score
        datasets.sort(key=lambda x: x.ein_score, reverse=True)
        
        for rank, dataset in enumerate(datasets, start=1):
            dataset.rank = rank
            
            # Check if record for today already exists
            existing = self.session.query(ScoringDataset).filter_by(
                symbol_id=dataset.symbol_id,
                date=dataset.date
            ).first()
            
            if existing:
                existing.value_score = dataset.value_score
                existing.dividend_score = dataset.dividend_score
                existing.quality_score = dataset.quality_score
                existing.momentum_score = dataset.momentum_score
                existing.volatility_score = dataset.volatility_score
                existing.confidence_weight = dataset.confidence_weight
                existing.ein_score = dataset.ein_score
                existing.rank = dataset.rank
                existing.calculated_at = func.now()
            else:
                self.session.add(dataset)
        
        self.session.commit()
