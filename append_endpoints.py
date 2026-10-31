# --- Bot 4 API ---
@app.get("/api/allocation/results", tags=["Bot 4"])
def get_allocations(limit: int = 50):
    from src.domain.models import AllocationResult, SymbolMaster
    session = SessionLocal()
    try:
        results = session.query(AllocationResult, SymbolMaster).join(
            SymbolMaster, AllocationResult.symbol_id == SymbolMaster.symbol_id
        ).order_by(AllocationResult.allocation_amount.desc()).limit(limit).all()
        data = []
        for alloc, symbol in results:
            data.append({
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "company_name": symbol.company_name or "Unknown",
                "allocation_pct": alloc.allocation_pct,
                "allocation_amount": alloc.allocation_amount,
                "ein_score": alloc.ein_score,
                "risk_flags": alloc.risk_flags,
                "date": alloc.date.isoformat() if alloc.date else ""
            })
        return {"data": data}
    finally:
        session.close()

@app.get("/api/allocation/risk-summary", tags=["Bot 4"])
def get_risk_summary():
    from src.services.allocation_engine import AllocationEngine
    session = SessionLocal()
    try:
        engine = AllocationEngine(session)
        return engine.get_portfolio_risk_summary()
    finally:
        session.close()

# --- Bot 5 API ---
@app.get("/api/top20/portfolio", tags=["Bot 5"])
def get_top20_portfolio():
    from src.domain.models import Top20Portfolio, SymbolMaster
    session = SessionLocal()
    try:
        results = session.query(Top20Portfolio, SymbolMaster).join(
            SymbolMaster, Top20Portfolio.symbol_id == SymbolMaster.symbol_id
        ).order_by(Top20Portfolio.final_rank.asc()).all()
        data = []
        for row, symbol in results:
            data.append({
                "rank": row.final_rank,
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "company_name": symbol.company_name or "Unknown",
                "allocation_pct": row.allocation_pct,
                "allocation_amount": row.allocation_amount,
                "ein_score": row.ein_score,
                "risk_category": row.risk_category,
                "inclusion_reason": row.inclusion_reason,
                "sector": row.sector,
                "date": row.date.isoformat() if row.date else ""
            })
        return {"data": data}
    finally:
        session.close()

@app.get("/api/top20/summary", tags=["Bot 5"])
def get_top20_summary():
    from src.services.ranking_engine import RankingEngine
    session = SessionLocal()
    try:
        engine = RankingEngine(session)
        return engine.get_top_20_summary()
    finally:
        session.close()

# --- Bot 4 Settings API ---
@app.get("/api/settings/bot4", tags=["Settings"])
def get_bot4_settings():
    from src.domain.models import Configuration
    session = SessionLocal()
    try:
        configs = session.query(Configuration).filter(Configuration.key.in_([
            'BOT4_TOTAL_CAPITAL', 'BOT4_MAX_POSITION_PCT', 'BOT4_MAX_SECTOR_PCT', 'BOT4_MIN_CONFIDENCE'
        ])).all()
        config_map = {c.key: c.value for c in configs}
        return {
            "total_capital": float(config_map.get("BOT4_TOTAL_CAPITAL", 1000000.0)),
            "max_position_pct": float(config_map.get("BOT4_MAX_POSITION_PCT", 5.0)),
            "max_sector_pct": float(config_map.get("BOT4_MAX_SECTOR_PCT", 25.0)),
            "min_confidence": float(config_map.get("BOT4_MIN_CONFIDENCE", 70.0))
        }
    finally:
        session.close()

@app.post("/api/settings/bot4", tags=["Settings"])
def update_bot4_settings(config: dict):
    from src.domain.models import Configuration
    session = SessionLocal()
    try:
        mapping = {
            'BOT4_TOTAL_CAPITAL': config.get('total_capital'),
            'BOT4_MAX_POSITION_PCT': config.get('max_position_pct'),
            'BOT4_MAX_SECTOR_PCT': config.get('max_sector_pct'),
            'BOT4_MIN_CONFIDENCE': config.get('min_confidence')
        }
        for k, v in mapping.items():
            if v is not None:
                record = session.query(Configuration).filter(Configuration.key == k).first()
                if record:
                    record.value = str(v)
                else:
                    session.add(Configuration(key=k, value=str(v), description="Bot 4 Setting"))
        session.commit()
        return {"message": "Settings updated"}
    finally:
        session.close()
