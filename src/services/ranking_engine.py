"""
Bot 5 — Ranking Engine + Top 20 Generation
Applies final ranking with allocation-awareness and generates the official
Top 20 portfolio recommendation with ₹ amounts, risk categories, and inclusion reasons.
"""

import os
from datetime import date
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.domain.models import (
    AllocationResult, SymbolMaster, ProcessedMarketData,
    Top20Portfolio, SystemSettings
)


class RankingEngine:
    """Ranking Engine + Top 20 Generation (Bot 5)"""

    def __init__(self, session: Session):
        self.session = session
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load Bot 4 config (shared capital settings) from SystemSettings or env."""
        configs = self.session.query(SystemSettings).filter(SystemSettings.key.in_([
            'BOT4_TOTAL_CAPITAL', 'BOT5_TOP_N'
        ])).all()
        config_map = {c.key: c.value for c in configs}
        
        return {
            "total_capital": float(config_map.get("BOT4_TOTAL_CAPITAL", os.getenv("BOT4_TOTAL_CAPITAL", "1000000"))),
            "top_n": int(config_map.get("BOT5_TOP_N", os.getenv("BOT5_TOP_N", "20"))),
        }

    def _classify_risk(self, volatility: float) -> str:
        """Classify risk based on 30-day annualized volatility."""
        if volatility is None or volatility == 0:
            return "MEDIUM"
        if volatility > 0.40:
            return "HIGH"
        elif volatility > 0.20:
            return "MEDIUM"
        return "LOW"

    def _generate_inclusion_reason(self, alloc: AllocationResult, symbol: SymbolMaster) -> str:
        """Generate a human-readable reason for why this stock was included in Top 20."""
        reasons = []
        
        # Score-based reasoning
        if alloc.ein_score and alloc.ein_score >= 60:
            reasons.append("Strong EIN score")
        elif alloc.ein_score and alloc.ein_score >= 40:
            reasons.append("Moderate EIN score")
        
        # Volatility-based reasoning
        if alloc.volatility_30d is not None:
            if alloc.volatility_30d < 0.15:
                reasons.append("Low volatility")
            elif alloc.volatility_30d < 0.25:
                reasons.append("Stable price action")
        
        # Weight-based reasoning
        if alloc.position_size_pct and alloc.position_size_pct >= 5:
            reasons.append("High allocation weight")
        
        # Sector
        if alloc.sector:
            reasons.append(f"{alloc.sector} sector")
        
        # Risk flags
        if not alloc.risk_flag:
            reasons.append("No risk flags")
        
        if not reasons:
            reasons.append("Passed all qualification filters")
        
        return " • ".join(reasons)

    def generate_top_20(self) -> str:
        """
        Main Bot 5 pipeline:
        1. Read latest AllocationResult from Bot 4
        2. Apply final filters (active symbols, no critical risk flags)
        3. Select top N (default 20)
        4. Normalize weights to sum to 100%
        5. Calculate ₹ amounts
        6. Assign risk categories and inclusion reasons
        7. Save to Top20Portfolio table
        """
        print("🤖 Bot 5: Starting Ranking Engine + Top 20 Generation...")

        # 1. Get latest allocation date
        latest_alloc = self.session.query(AllocationResult).order_by(
            AllocationResult.date.desc()
        ).first()
        
        if not latest_alloc:
            return "No allocation data available. Run Bot 4 first."

        latest_date = latest_alloc.date

        # 2. Fetch all allocations for the latest date with symbol info
        alloc_data = self.session.query(AllocationResult, SymbolMaster).join(
            SymbolMaster, AllocationResult.symbol_id == SymbolMaster.symbol_id
        ).filter(
            AllocationResult.date == latest_date,
            SymbolMaster.active == True
        ).order_by(AllocationResult.risk_adjusted_weight.desc()).all()

        if not alloc_data:
            return "No allocation results found for today."

        print(f"   ✓ Found {len(alloc_data)} allocation records")

        # 3. Apply final filters — exclude symbols with critical issues
        filtered = []
        for alloc, symbol in alloc_data:
            # Skip symbols with both HIGH_VOLATILITY and LOW_CONFIDENCE
            if alloc.risk_flag and "HIGH_VOLATILITY" in alloc.risk_flag and "LOW_CONFIDENCE" in alloc.risk_flag:
                print(f"   ⚠️ Excluded {symbol.nse_ticker or symbol.symbol_id}: dual risk flags")
                continue
            
            # Skip symbols with zero or negative allocation
            if alloc.risk_adjusted_weight is None or alloc.risk_adjusted_weight <= 0:
                continue
            
            filtered.append((alloc, symbol))

        if not filtered:
            print("   ⚠️ No symbols passed final filters. Holding cash (empty Top 20).")
            return "No symbols qualified for Top 20. Skipping ranking."

        # 4. Take top N
        top_n = min(self.config["top_n"], len(filtered))
        top_picks = sorted(filtered, key=lambda x: x[0].ein_score, reverse=True)[:top_n]

        print(f"   ✓ Selected Top {len(top_picks)} from {len(filtered)} candidates")

        # 5. Normalize weights to sum to 100%
        total_weight = sum(a.risk_adjusted_weight for a, _ in top_picks if a.risk_adjusted_weight)
        if total_weight == 0:
            total_weight = 1

        total_capital = self.config["total_capital"]
        today = date.today()
        saved_count = 0

        # Delete existing records for today to avoid stale data
        self.session.query(Top20Portfolio).filter_by(date=today).delete()
        
        records_to_insert = []
        for rank, (alloc, symbol) in enumerate(top_picks, start=1):
            # Normalized allocation percentage
            normalized_pct = (alloc.risk_adjusted_weight / total_weight) * 100 if alloc.risk_adjusted_weight else 0
            allocation_amount = (normalized_pct / 100) * total_capital

            # Risk category
            risk_cat = self._classify_risk(alloc.volatility_30d)

            # Inclusion reason
            reason = self._generate_inclusion_reason(alloc, symbol)

            record = Top20Portfolio(
                symbol_id=alloc.symbol_id,
                date=today,
                final_rank=rank,
                allocation_pct=round(normalized_pct, 2),
                allocation_amount=round(allocation_amount, 2),
                ein_score=alloc.ein_score,
                risk_category=risk_cat,
                inclusion_reason=reason,
            )
            records_to_insert.append(record)
            saved_count += 1
            
        self.session.add_all(records_to_insert)

        self.session.commit()
        print(f"   ✓ Bot 5: Generated Top {saved_count} portfolio entries.")
        return f"Success: Generated Top {saved_count} portfolio."

    def get_top_20_summary(self) -> Dict:
        """Returns aggregate stats for the latest Top 20 portfolio."""
        latest = self.session.query(Top20Portfolio).order_by(
            Top20Portfolio.date.desc()
        ).first()
        
        if not latest:
            return {"error": "No Top 20 data available"}

        latest_date = latest.date

        entries = self.session.query(Top20Portfolio, SymbolMaster).join(
            SymbolMaster, Top20Portfolio.symbol_id == SymbolMaster.symbol_id
        ).filter(Top20Portfolio.date == latest_date).order_by(
            Top20Portfolio.final_rank.asc()
        ).all()

        if not entries:
            return {"error": "No Top 20 entries found"}

        total_allocation = sum(e.allocation_amount for e, _ in entries)
        avg_ein = sum(e.ein_score for e, _ in entries if e.ein_score) / len(entries)
        
        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        sectors = set()
        for entry, symbol in entries:
            risk_counts[entry.risk_category] = risk_counts.get(entry.risk_category, 0) + 1
            # Get sector from allocation results
            alloc = self.session.query(AllocationResult).filter_by(
                symbol_id=entry.symbol_id, date=latest_date
            ).first()
            if alloc and alloc.sector:
                sectors.add(alloc.sector)

        # Portfolio risk score: weighted by risk category
        total_entries = len(entries)
        risk_score = round(
            ((risk_counts["LOW"] * 100 + risk_counts["MEDIUM"] * 60 + risk_counts["HIGH"] * 20) / total_entries),
            1
        ) if total_entries > 0 else 50

        return {
            "date": str(latest_date),
            "total_entries": total_entries,
            "total_allocation": round(total_allocation, 2),
            "avg_ein_score": round(avg_ein, 2),
            "risk_score": risk_score,
            "risk_distribution": risk_counts,
            "sector_count": len(sectors),
            "sectors": list(sectors),
        }
