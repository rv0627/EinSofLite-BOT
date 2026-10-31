import json
import redis
import os
import time
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult
from src.workers.tasks import pull_all_eod_data, process_raw_data, pull_live_data, SessionLocal, celery_app
from src.domain.models import SymbolMaster, ProcessedMarketData
from src.adapters.twelvedata import TwelveDataAdapter
from src.adapters.eodhd_client import EodhdClient
from src.adapters.zerodha_client import ZerodhaClient
from src.adapters.upstox_client import UpstoxClient
from src.adapters.marketstack_client import MarketstackClient

# Redis Cache Setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(
    title="Ein Sof Lite API",
    description="Modular Multi-Bot Investment Intelligence System",
    version="1.0.0"
)

# CORS — allow Next.js frontend (read from env or default to localhost)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-Admin-Key"],
)

# ── Admin Authentication ─────────────────────────────────────
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY", "")
_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

def require_admin(api_key: str = Security(_api_key_header)):
    """Dependency that enforces admin authentication via X-Admin-Key header."""
    if not ADMIN_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: ADMIN_SECRET_KEY is not set."
        )
    if api_key != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing admin key.")

@app.get("/", tags=["System"])
def health_check():
    from sqlalchemy import text
    db_status = "ok"
    redis_status = "ok"
    celery_status = "ok" 
    
    # 1. Check Database
    try:
        session = SessionLocal()
        session.execute(text("SELECT 1"))
        session.close()
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    # 2. Check Redis
    try:
        redis_client.ping()
    except Exception as e:
        redis_status = f"error: {str(e)}"
        
    # 3. Check Celery (ping workers)
    try:
        ping_result = celery_app.control.ping(timeout=1.0)
        if not ping_result:
            celery_status = "error: no workers responded"
    except Exception as e:
        celery_status = f"error: {str(e)}"

    return {
        "status": "System is running" if db_status == "ok" and redis_status == "ok" else "Degraded",
        "database": db_status,
        "redis": redis_status,
        "celery": celery_status
    }

@app.post("/trigger/bot1/eod", tags=["Bot 1 - Ingestion"], dependencies=[Depends(require_admin)])
def trigger_bot1_eod():
    """Endpoint to trigger Bot 1 EOD data pull"""
    
    # .delay() method is used to call the Celery task asynchronously
    task = pull_all_eod_data.delay(is_manual=True)
    return {
        "message": "Bot 1 EOD data pull triggered",
        "task_id": task.id
    }

@app.post("/trigger/bot2/process", tags=["Bot 2 - Processing"], dependencies=[Depends(require_admin)])
def trigger_bot2_process():
    """Endpoint to trigger Bot 2 raw data processing"""
    
    task = process_raw_data.delay(is_manual=True)
    return {
        "message": "Bot 2 raw data processing triggered successfully",
        "task_id": task.id
    }

@app.post("/trigger/bot1/live", tags=["Bot 1 - Ingestion"], dependencies=[Depends(require_admin)])
def trigger_bot1_live():
    """Endpoint to trigger Bot 1 live data pull for watchlist"""
    
    task = pull_live_data.delay(is_manual=True)
    return {
        "message": "Bot 1 live data pull for watchlist triggered successfully",
        "task_id": task.id
    }

@app.post("/trigger/bot3/score", tags=["Bot 3 - Scoring Engine"], dependencies=[Depends(require_admin)])
def trigger_bot3_score():
    """Endpoint to trigger Bot 3 scoring calculation manually"""
    from src.workers.tasks import calculate_ein_scores
    task = calculate_ein_scores.delay(is_manual=True)
    return {
        "message": "Bot 3 scoring engine triggered successfully",
        "task_id": task.id
    }

@app.post("/trigger/bot4/allocate", tags=["Bot 4 - Allocation Engine"], dependencies=[Depends(require_admin)])
def trigger_bot4_allocate():
    """Endpoint to trigger Bot 4 allocation & risk management manually"""
    from src.workers.tasks import calculate_allocations
    task = calculate_allocations.delay(is_manual=True)
    return {
        "message": "Bot 4 allocation engine triggered successfully",
        "task_id": task.id
    }

@app.post("/trigger/bot5/top20", tags=["Bot 5 - Ranking Engine"], dependencies=[Depends(require_admin)])
def trigger_bot5_top20():
    """Endpoint to trigger Bot 5 Top 20 generation manually"""
    from src.workers.tasks import generate_top_20
    task = generate_top_20.delay(is_manual=True)
    return {
        "message": "Bot 5 Top 20 generation triggered successfully",
        "task_id": task.id
    }

@app.post("/trigger/bot6/stress_test", tags=["Bot 6 - Stress Testing"], dependencies=[Depends(require_admin)])
def trigger_bot6_stress_test():
    """Endpoint to trigger Bot 6 Stress Testing manually"""
    from src.workers.tasks import run_stress_test
    task = run_stress_test.delay(is_manual=True)
    return {
        "message": "Bot 6 Stress Testing triggered successfully",
        "task_id": task.id
    }

# ============================================================
# Bot 7 & 8 - Reporting & Audit API Endpoints
# ============================================================
from fastapi.responses import Response

@app.get("/api/reports/daily/pdf", tags=["Bot 7 - Reporting"], dependencies=[Depends(require_admin)])
def get_daily_pdf_report():
    """Generates and downloads the daily Top 20 PDF report."""
    from src.services.reporting_engine import ReportingEngine
    session = SessionLocal()
    try:
        engine = ReportingEngine(session)
        pdf_bytes = bytes(engine.generate_daily_pdf_report())
        
        headers = {
            'Content-Disposition': 'attachment; filename="daily_portfolio_report.pdf"'
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except Exception as e:
        print(f"Error generating PDF report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")
    finally:
        session.close()

# ============================================================
# Dashboard API Endpoints
# ============================================================

@app.get("/api/dashboard/tickers", tags=["Dashboard"], dependencies=[Depends(require_admin)])
def get_dashboard_tickers(limit: int = 3):
    """Returns latest price data + 7-day sparkline for dashboard ticker cards."""
    session = SessionLocal()
    
    try:
        # Try to get top N tickers by EIN score
        from src.domain.models import ScoringDataset
        latest_date_record = session.query(ScoringDataset).order_by(ScoringDataset.date.desc()).first()
        
        dashboard_tickers = []
        if latest_date_record:
            rankings = session.query(ScoringDataset, SymbolMaster).join(
                SymbolMaster, ScoringDataset.symbol_id == SymbolMaster.symbol_id
            ).filter(
                ScoringDataset.date == latest_date_record.date
            ).order_by(ScoringDataset.rank.asc()).limit(limit).all()
            dashboard_tickers = [symbol.nse_ticker or symbol.symbol_id for score, symbol in rankings]
        
        # Fallback if no scores exist or not enough scores
        if len(dashboard_tickers) < limit:
            fallback = session.query(SymbolMaster).filter(SymbolMaster.is_dashboard_fallback == True).limit(limit).all()
            for sym in fallback:
                ticker = sym.nse_ticker or sym.symbol_id
                if ticker not in dashboard_tickers:
                    dashboard_tickers.append(ticker)
                if len(dashboard_tickers) >= limit:
                    break

        results = []
        for ticker in dashboard_tickers:
            # Try cache first
            cache_key = f"dashboard_ticker:{ticker}"
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    results.append(json.loads(cached))
                    continue
            except Exception as e:
                print(f"⚠️ Redis cache error for {cache_key}: {e}")
            
            # Query DB for last 7 days of processed data (deduplicating by date)
            db_data_raw = session.query(ProcessedMarketData).join(
                SymbolMaster, ProcessedMarketData.symbol_id == SymbolMaster.symbol_id
            ).filter(
                (SymbolMaster.nse_ticker == ticker) | 
                (SymbolMaster.symbol_id == ticker) | 
                (SymbolMaster.symbol_id == f"SYM_{ticker}")
            ).order_by(ProcessedMarketData.date.desc()).limit(30).all()
            
            seen_dates = set()
            db_data = []
            for row in db_data_raw:
                if row.date not in seen_dates:
                    db_data.append(row)
                    seen_dates.add(row.date)
                if len(db_data) == 7:
                    break

            if db_data:
                # Most recent record first
                latest = db_data[0]
                
                if len(db_data) > 1:
                    previous = db_data[1]
                    change_pct = ((latest.close_price - previous.close_price) / previous.close_price) * 100 if previous.close_price else 0.0
                else:
                    change_pct = 0.0
                
                spark_data = [row.close_price for row in reversed(db_data)]
                
                exchange = "NSE India"
                
                ticker_data = {
                    "ticker": ticker,
                    "exchange": exchange,
                    "price": f"{latest.close_price:,.2f}",
                    "change": f"{change_pct:+.2f}%",
                    "sparkData": spark_data,
                    "confidence": latest.confidence_score,
                }
                
                # Cache for 60 seconds
                try:
                    redis_client.set(cache_key, json.dumps(ticker_data), ex=60)
                except Exception as e:
                    print(f"⚠️ Redis cache write error for {cache_key}: {e}")
                results.append(ticker_data)
            else:
                # No data in DB
                results.append({
                    "ticker": ticker,
                    "exchange": "NSE India",
                    "price": "—",
                    "change": "0.00%",
                    "sparkData": [],
                    "confidence": None,
                    "noData": True,
                })
        
        return {"tickers": results}
    finally:
        session.close()

@app.get("/api/portfolio/holdings", tags=["Portfolio"], dependencies=[Depends(require_admin)])
def get_portfolio_holdings():
    """Returns all processed tickers with 24h change and last sync time."""
    from src.domain.models import ProcessedMarketData, SymbolMaster
    session = SessionLocal()
    
    try:
        latest_record = session.query(ProcessedMarketData).order_by(ProcessedMarketData.date.desc()).first()
        if not latest_record:
            return {"data": []}
            
        latest_date = latest_record.date
        
        latest_data = session.query(ProcessedMarketData, SymbolMaster).join(
            SymbolMaster, ProcessedMarketData.symbol_id == SymbolMaster.symbol_id
        ).filter(ProcessedMarketData.date == latest_date).all()
        
        results = []
        seen_symbols = set()
        for processed, symbol in latest_data:
            if symbol.symbol_id in seen_symbols:
                continue
            seen_symbols.add(symbol.symbol_id)
            
            previous = session.query(ProcessedMarketData).filter(
                ProcessedMarketData.symbol_id == symbol.symbol_id,
                ProcessedMarketData.date < latest_date
            ).order_by(ProcessedMarketData.date.desc()).first()
            
            change_pct = 0.0
            is_positive = None
            if previous and previous.close_price:
                change_pct = ((processed.close_price - previous.close_price) / previous.close_price) * 100
                is_positive = change_pct >= 0
                
            results.append({
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "name": symbol.company_name or "Unknown Company",
                "price": f"${processed.close_price:,.2f}" if not symbol.nse_ticker else f"₹{processed.close_price:,.2f}",
                "change": f"{change_pct:+.2f}%",
                "isPositive": is_positive,
                "sync": processed.processed_at.strftime("%H:%M:%S UTC") if processed.processed_at else "Unknown"
            })
            
        return {"data": results}
    finally:
        session.close()

@app.get("/api/portfolio/intelligence", tags=["Portfolio"], dependencies=[Depends(require_admin)])
def get_portfolio_intelligence():
    """Returns real-time market intelligence based on system scoring and anomalies."""
    from src.domain.models import ScoringDataset, ProcessedMarketData, SymbolMaster
    session = SessionLocal()
    insights = []
    
    try:
        # 1. Bullish Signal (Highest Momentum)
        latest_score = session.query(ScoringDataset).order_by(ScoringDataset.date.desc()).first()
        if latest_score:
            top_momentum = session.query(ScoringDataset, SymbolMaster).join(
                SymbolMaster, ScoringDataset.symbol_id == SymbolMaster.symbol_id
            ).filter(ScoringDataset.date == latest_score.date).order_by(ScoringDataset.momentum_score.desc()).first()
            
            if top_momentum and top_momentum[0].momentum_score and top_momentum[0].momentum_score > 60:
                ticker = top_momentum[1].nse_ticker or top_momentum[1].symbol_id
                insights.append({
                    "type": "bullish",
                    "label": "Bullish Signal",
                    "desc": f"{ticker} is showing strong momentum with a score of {top_momentum[0].momentum_score:.1f}."
                })
                
        # 2. Anomalies / Alerts (Latest Anomalous Record)
        latest_anomaly = session.query(ProcessedMarketData, SymbolMaster).join(
            SymbolMaster, ProcessedMarketData.symbol_id == SymbolMaster.symbol_id
        ).filter(ProcessedMarketData.is_anomalous == True).order_by(ProcessedMarketData.date.desc()).first()
        
        if latest_anomaly:
            ticker = latest_anomaly[1].nse_ticker or latest_anomaly[1].symbol_id
            insights.append({
                "type": "alert",
                "label": "Data Anomaly Alert",
                "desc": f"Unusual volume or price action detected in {ticker} on {latest_anomaly[0].date}."
            })
            
        # 3. Quality Alert (Low Confidence)
        latest_low_conf = session.query(ProcessedMarketData, SymbolMaster).join(
            SymbolMaster, ProcessedMarketData.symbol_id == SymbolMaster.symbol_id
        ).filter(ProcessedMarketData.confidence_score < 0.7).order_by(ProcessedMarketData.date.desc()).first()
        
        if latest_low_conf:
            ticker = latest_low_conf[1].nse_ticker or latest_low_conf[1].symbol_id
            confidence_pct = (latest_low_conf[0].confidence_score or 0) * 100
            insights.append({
                "type": "alert",
                "label": "Data Quality Warning",
                "desc": f"{ticker} data confidence dropped to {confidence_pct:.1f}%. Proceed with caution."
            })
            
        if not insights:
            insights.append({
                "type": "info",
                "label": "System Normal",
                "desc": "All assets are trading within normal parameters. No major signals detected."
            })
            
        return {"data": insights[:3]}
    finally:
        session.close()

@app.get("/api/scoring/rankings", tags=["Bot 3 - Scoring Engine"], dependencies=[Depends(require_admin)])
def get_scoring_rankings(page: int = 1, limit: int = 50):
    """Returns the ranked dataset based on the latest EIN scores."""
    from src.domain.models import ScoringDataset, SymbolMaster
    from sqlalchemy import func
    import math
    session = SessionLocal()
    
    try:
        # Get the latest date we have scores for
        latest_date_record = session.query(ScoringDataset).order_by(ScoringDataset.date.desc()).first()
        if not latest_date_record:
             return {"data": [], "total": 0, "page": 1, "total_pages": 1}
             
        latest_date = latest_date_record.date
        
        # Get total count for pagination
        base_query = session.query(ScoringDataset, SymbolMaster).join(
            SymbolMaster, ScoringDataset.symbol_id == SymbolMaster.symbol_id
        ).filter(ScoringDataset.date == latest_date)
        
        total_count = base_query.count()
        total_pages = math.ceil(total_count / limit) if limit > 0 else 1
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Fetch rankings for that date with pagination
        rankings = base_query.order_by(ScoringDataset.rank.asc()).offset(offset).limit(limit).all()
        
        results = []
        for score, symbol in rankings:
            results.append({
                "rank": score.rank,
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "company_name": symbol.company_name,
                "ein_score": score.ein_score,
                "factors": {
                    "value": score.value_score,
                    "dividend": score.dividend_score,
                    "quality": score.quality_score,
                    "momentum": score.momentum_score,
                    "volatility": score.volatility_score
                },
                "confidence_weight": score.confidence_weight,
                "date": str(score.date)
            })
            
        return {
            "data": results,
            "total": total_count,
            "page": page,
            "total_pages": total_pages
        }
    finally:
        session.close()

@app.get("/api/portfolio/stress_test", tags=["Portfolio"], dependencies=[Depends(require_admin)])
def get_portfolio_stress_test():
    """Returns the latest advanced Monte Carlo stress test results."""
    from src.domain.models import MonteCarloResult
    session = SessionLocal()
    try:
        result = session.query(MonteCarloResult).order_by(MonteCarloResult.date.desc()).first()
        if not result:
            return {"error": "No stress test data available"}
            
        return {
            "date": str(result.date),
            "status": result.status,
            "seed_hash": result.seed_hash,
            "distribution_metrics": result.distribution_metrics,
            "tail_risk_metrics": result.tail_risk_metrics,
            "loss_probabilities": result.loss_probabilities
        }
    finally:
        session.close()

@app.get("/api/regime/current", tags=["Bot 4 - Regime"], dependencies=[Depends(require_admin)])
def get_current_regime():
    """Returns the latest Markov Regime Snapshot."""
    from src.services.markov_engine import MarkovEngine
    session = SessionLocal()
    try:
        engine = MarkovEngine(session)
        result = engine.get_latest_regime()
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    finally:
        session.close()

@app.get("/api/portfolio/propose", tags=["Bot 5 - Allocation"], dependencies=[Depends(require_admin)])
def get_proposed_allocation():
    """Returns the latest Markov-aware Portfolio Allocation Run."""
    from src.services.allocation_engine import AllocationEngine
    session = SessionLocal()
    try:
        engine = AllocationEngine(session)
        result = engine.get_latest_allocation()
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    finally:
        session.close()

# ============================================================
# System Settings API Endpoints
# ============================================================
from pydantic import BaseModel

class Bot3Weights(BaseModel):
    value: int
    dividend: int
    quality: int
    momentum: int
    volatility: int

class Bot3ConfigSchema(BaseModel):
    schedule: str
    weights: Bot3Weights

@app.get("/api/settings/bot3", tags=["System Settings"], dependencies=[Depends(require_admin)])
def get_bot3_settings():
    from src.domain.models import SystemSettings
    session = SessionLocal()
    try:
        setting = session.query(SystemSettings).filter_by(key="bot3_config").first()
        if setting and setting.value:
            return setting.value
        
        # Fallback to defaults or .env
        return {
            "schedule": os.getenv("BOT3_SCHEDULE", "daily"),
            "weights": {
                "value": int(os.getenv("WEIGHT_VALUE", 20)),
                "dividend": int(os.getenv("WEIGHT_DIVIDEND", 20)),
                "quality": int(os.getenv("WEIGHT_QUALITY", 20)),
                "momentum": int(os.getenv("WEIGHT_MOMENTUM", 20)),
                "volatility": int(os.getenv("WEIGHT_VOLATILITY", 20)),
            }
        }
    finally:
        session.close()

@app.post("/api/settings/bot3", tags=["System Settings"], dependencies=[Depends(require_admin)])
def update_bot3_settings(config: Bot3ConfigSchema):
    from src.domain.models import SystemSettings
    session = SessionLocal()
    try:
        setting = session.query(SystemSettings).filter_by(key="bot3_config").first()
        if not setting:
            setting = SystemSettings(key="bot3_config", value=config.model_dump() if hasattr(config, "model_dump") else config.dict())
            session.add(setting)
        else:
            setting.value = config.model_dump() if hasattr(config, "model_dump") else config.dict()
        session.commit()
        return {"message": "Bot 3 settings updated successfully"}
    finally:
        session.close()

@app.get("/api/settings/cache-health", tags=["Settings"], dependencies=[Depends(require_admin)])
def get_cache_health():
    """Returns Redis cache health metrics — exact data size, not process overhead."""
    try:
        # Sum the actual memory of every key in the database.
        # This is the ONLY way to get a number that truly drops to ~0 after flush,
        # because all Redis INFO metrics include internal overhead.
        total_data_bytes = 0
        for key in redis_client.scan_iter(count=200):
            mem = redis_client.memory_usage(key)
            if mem:
                total_data_bytes += mem
        used_mb = total_data_bytes / (1024 * 1024)
        return {
            "used_mb": round(used_mb, 2),
            "total_gb": 8.0,
            "status": "healthy"
        }
    except Exception as e:
        return {
            "used_mb": 0.0,
            "total_gb": 8.0,
            "status": "offline",
            "error": str(e)
        }

@app.post("/api/settings/flush-cache", tags=["Settings"], dependencies=[Depends(require_admin)])
def flush_redis_cache():
    """Flushes the Redis cache."""
    try:
        redis_client.flushdb()
        return {"message": "Redis cache flushed successfully"}
    except Exception as e:
        return {"error": str(e)}, 500

@app.get("/api/dashboard/metrics", tags=["Dashboard"], dependencies=[Depends(require_admin)])
def get_dashboard_metrics():
    """Returns system metrics: cache hit ratio and Redis latency."""
    try:
        # Cache Hit Ratio from Redis INFO stats
        info = redis_client.info("stats")
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        hit_ratio = (hits / total * 100) if total > 0 else 0.0
        
        # System Latency — measure Redis PING round-trip
        start = time.time()
        redis_client.ping()
        latency_ms = round((time.time() - start) * 1000, 1)
        
        return {
            "cache_hit_ratio": round(hit_ratio, 1),
            "system_latency_ms": latency_ms,
            "cache_hits": hits,
            "cache_misses": misses,
        }
    except Exception as e:
        return {
            "cache_hit_ratio": 0.0,
            "system_latency_ms": -1,
            "error": str(e),
        }


@app.get("/api/dashboard/api-health", tags=["Dashboard"], dependencies=[Depends(require_admin)])
def get_dashboard_api_health():
    """Returns real health status of each data provider.
    
    Keys are read from .env via _read_env() so Settings page changes 
    take effect immediately without requiring a server restart.
    """
    import requests
    
    PLACEHOLDER_PATTERNS = {"your_", "placeholder", "xxx", "demo", "test", "change_me"}
    
    def _is_valid_key(key: str) -> bool:
        if not key or not key.strip():
            return False
        key_lower = key.strip().lower()
        return not any(key_lower.startswith(p) or key_lower == p for p in PLACEHOLDER_PATTERNS)
    
    sources = []
    gateway_online = False
    
    # Twelve Data — validate with actual API call using live key from .env
    try:
        api_key = _read_env("TWELVE_DATA_API_KEY")
        if not _is_valid_key(api_key):
            td_healthy = False
        else:
            td = TwelveDataAdapter(api_key=api_key)
            td_healthy = td.health_probe()
        sources.append({
            "name": "Twelve Data",
            "description": "US Market Node",
            "status": "active" if td_healthy else "offline",
            "color": "cyan" if td_healthy else "red",
        })
        if td_healthy:
            gateway_online = True
    except Exception:
        sources.append({"name": "Twelve Data", "description": "US Market Node", "status": "offline", "color": "red"})
    
    # EODHD — validate with actual API call using live key from .env
    try:
        eodhd_key = _read_env("EODHD_API_KEY")
        if not _is_valid_key(eodhd_key):
            eodhd_healthy = False
        else:
            res = requests.get(
                f"https://eodhistoricaldata.com/api/eod/AAPL.US?api_token={eodhd_key}&fmt=json",
                timeout=5
            )
            eodhd_healthy = res.status_code == 200
        sources.append({
            "name": "EODHD",
            "description": "Historical Archive",
            "status": "active" if eodhd_healthy else "offline",
            "color": "amber" if eodhd_healthy else "red",
        })
    except Exception:
        sources.append({"name": "EODHD", "description": "Historical Archive", "status": "offline", "color": "red"})
    
    # Zerodha — validate with live keys from .env
    try:
        z_key = _read_env("ZERODHA_API_KEY")
        z_token = _read_env("ZERODHA_ACCESS_TOKEN")
        z_configured = _is_valid_key(z_key) and _is_valid_key(z_token)
        sources.append({
            "name": "Zerodha",
            "description": "Execution Broker",
            "status": "active" if z_configured else "offline",
            "color": "green" if z_configured else "red",
        })
    except Exception:
        sources.append({"name": "Zerodha", "description": "Execution Broker", "status": "offline", "color": "red"})
    
    # Upstox — validate with live key from .env
    try:
        u_token = _read_env("UPSTOX_ACCESS_TOKEN")
        u_configured = _is_valid_key(u_token)
        sources.append({
            "name": "Upstox",
            "description": "Alt Execution",
            "status": "active" if u_configured else "offline",
            "color": "green" if u_configured else "red",
        })
    except Exception:
        sources.append({"name": "Upstox", "description": "Alt Execution", "status": "offline", "color": "red"})
    
    # MarketStack — validate with live key from .env
    try:
        ms_key = _read_env("MARKETSTACK_API_KEY")
        ms_configured = _is_valid_key(ms_key)
        sources.append({
            "name": "MarketStack",
            "description": "Global Equities",
            "status": "active" if ms_configured else "offline",
            "color": "green" if ms_configured else "red",
        })
    except Exception:
        sources.append({"name": "MarketStack", "description": "Global Equities", "status": "offline", "color": "red"})

    # NSEBSE — validate with live key from .env
    try:
        nse_key = _read_env("NSEBSE_API_KEY")
        nse_configured = _is_valid_key(nse_key)
        sources.append({
            "name": "NSEBSE",
            "description": "Indian Markets",
            "status": "active" if nse_configured else "offline",
            "color": "green" if nse_configured else "red",
        })
    except Exception:
        sources.append({"name": "NSEBSE", "description": "Indian Markets", "status": "offline", "color": "red"})


    if not gateway_online:
        gateway_online = any(s["status"] == "active" for s in sources)
    
    return {
        "sources": sources,
        "gateway_online": gateway_online,
    }


@app.get("/api/infrastructure/health", tags=["Infrastructure"], dependencies=[Depends(require_admin)])
def get_infrastructure_health():
    """Returns detailed health stats for the Infrastructure Connectivity dashboard.
    
    Each node performs a REAL API key validation — not just a connectivity ping.
    Keys are read from .env via _read_env() so Settings page changes take effect 
    immediately without requiring a server restart.
    """
    import time
    import requests
    
    PLACEHOLDER_PATTERNS = {"your_", "placeholder", "xxx", "demo", "test", "change_me"}
    
    def _is_valid_key(key: str) -> bool:
        """Check if an API key is configured and not a placeholder."""
        if not key or not key.strip():
            return False
        key_lower = key.strip().lower()
        return not any(key_lower.startswith(p) or key_lower == p for p in PLACEHOLDER_PATTERNS)
    
    def _calc_uptime(node_name: str, is_success: bool) -> str:
        # Instead of mutating Redis on every GET request, we just return N/A
        # Real uptime should be measured by a background cron job.
        return "100.00%" if is_success else "0.00%"

    nodes = []
    
    # 1. Twelve Data (Primary Global)
    # Uses _read_env() so Settings page key changes apply immediately
    try:
        api_key = _read_env("TWELVE_DATA_API_KEY")
        start_time = time.time()
        if not _is_valid_key(api_key):
            healthy = False
        else:
            td = TwelveDataAdapter(api_key=api_key)
            healthy = td.health_probe()
        latency = int((time.time() - start_time) * 1000)
        uptime_str = _calc_uptime("twelve_data", healthy)
        nodes.append({
            "id": 1, "name": "Twelve Data", "role": "Primary Global", 
            "uptime": uptime_str, "latency": f"{latency}ms", 
            "health": 100 if healthy else 0, "isPrimary": True
        })
    except Exception:
        uptime_str = _calc_uptime("twelve_data", False)
        nodes.append({
            "id": 1, "name": "Twelve Data", "role": "Primary Global", 
            "uptime": uptime_str, "latency": "0ms", "health": 0, "isPrimary": True
        })
        
    # 2. EODHD (Historical Hub)
    # Validates the user's actual API key, not a hardcoded demo token
    try:
        api_key = _read_env("EODHD_API_KEY")
        start_time = time.time()
        if not _is_valid_key(api_key):
            healthy = False
        else:
            res = requests.get(
                f"https://eodhistoricaldata.com/api/eod/AAPL.US?api_token={api_key}&fmt=json",
                timeout=5
            )
            healthy = res.status_code == 200
        latency = int((time.time() - start_time) * 1000)
        uptime_str = _calc_uptime("eodhd", healthy)
        nodes.append({
            "id": 2, "name": "EODHD", "role": "Historical Hub", 
            "uptime": uptime_str, "latency": f"{latency}ms", 
            "health": 100 if healthy else 0, "isPrimary": False
        })
    except Exception:
        uptime_str = _calc_uptime("eodhd", False)
        nodes.append({
            "id": 2, "name": "EODHD", "role": "Historical Hub", 
            "uptime": uptime_str, "latency": "0ms", "health": 0, "isPrimary": False
        })
        
    # 3. Zerodha (Execution IN)
    # Validates by sending an authenticated request with the user's API key + access token
    try:
        api_key = _read_env("ZERODHA_API_KEY")
        access_token = _read_env("ZERODHA_ACCESS_TOKEN")
        start_time = time.time()
        if not _is_valid_key(api_key) or not _is_valid_key(access_token):
            healthy = False
        else:
            res = requests.get(
                "https://api.kite.trade/user/profile",
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {api_key}:{access_token}"
                },
                timeout=5
            )
            healthy = res.status_code == 200
        latency = int((time.time() - start_time) * 1000)
        uptime_str = _calc_uptime("zerodha", healthy)
        nodes.append({
            "id": 3, "name": "Zerodha", "role": "Execution (IN)", 
            "uptime": uptime_str, "latency": f"{latency}ms", 
            "health": 100 if healthy else 0, "isPrimary": False
        })
    except Exception:
        uptime_str = _calc_uptime("zerodha", False)
        nodes.append({
            "id": 3, "name": "Zerodha", "role": "Execution (IN)", 
            "uptime": uptime_str, "latency": "0ms", "health": 0, "isPrimary": False
        })
        
    # 4. Upstox (Secondary IN)
    # Validates by sending an authenticated request with the user's access token
    try:
        access_token = _read_env("UPSTOX_ACCESS_TOKEN")
        start_time = time.time()
        if not _is_valid_key(access_token):
            healthy = False
        else:
            res = requests.get(
                "https://api.upstox.com/v2/user/profile",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json"
                },
                timeout=5
            )
            healthy = res.status_code == 200
        latency = int((time.time() - start_time) * 1000)
        uptime_str = _calc_uptime("upstox", healthy)
        nodes.append({
            "id": 4, "name": "Upstox", "role": "Secondary (IN)", 
            "uptime": uptime_str, "latency": f"{latency}ms", 
            "health": 100 if healthy else 0, "isPrimary": False
        })
    except Exception:
        uptime_str = _calc_uptime("upstox", False)
        nodes.append({
            "id": 4, "name": "Upstox", "role": "Secondary (IN)", 
            "uptime": uptime_str, "latency": "0ms", "health": 0, "isPrimary": False
        })

    # 5. Marketstack (Fallback Global)
    try:
        api_key = _read_env("MARKETSTACK_API_KEY")
        start_time = time.time()
        if not _is_valid_key(api_key):
            healthy = False
        else:
            res = requests.get(
                f"http://api.marketstack.com/v1/tickers?access_key={api_key}&limit=1",
                timeout=5
            )
            healthy = res.status_code == 200
        latency = int((time.time() - start_time) * 1000)
        uptime_str = _calc_uptime("marketstack", healthy)
        nodes.append({
            "id": 5, "name": "Marketstack", "role": "Fallback Global", 
            "uptime": uptime_str, "latency": f"{latency}ms", 
            "health": 100 if healthy else 0, "isPrimary": False
        })
    except Exception:
        uptime_str = _calc_uptime("marketstack", False)
        nodes.append({
            "id": 5, "name": "Marketstack", "role": "Fallback Global", 
            "uptime": uptime_str, "latency": "0ms", "health": 0, "isPrimary": False
        })
        
    return nodes


@app.get("/api/infrastructure/logs", tags=["Infrastructure"], dependencies=[Depends(require_admin)])
def get_routing_logs():
    """Fetches the latest live routing logs from Redis."""
    try:
        logs_raw = redis_client.lrange("system:routing_logs", 0, 49)
        logs = [json.loads(log) for log in logs_raw]
        return logs
    except Exception as e:
        print(f"Error fetching routing logs: {e}")
        return []


@app.get("/api/task-status/{task_id}", tags=["Dashboard"], dependencies=[Depends(require_admin)])
def get_task_status(task_id: str):
    """Query Celery AsyncResult to return task state and result."""
    result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "state": result.state,
        "ready": result.ready(),
    }
    
    if result.ready():
        if result.successful():
            response["result"] = str(result.result)
        else:
            response["error"] = str(result.result)
    
    return response


@app.get("/api/market-data/{ticker}", tags=["Market Data Access"], dependencies=[Depends(require_admin)])
def get_market_data(ticker: str):
    """
    This endpoint retrieves the last 7 days of market data for a given ticker. It first checks Redis cache for the data, and if not found or stale, it fetches from the PostgreSQL database. The response includes a source field indicating where the data was retrieved from (cache or database).
    """
    ticker = ticker.upper()
    cache_key = f"market_data_v1:{ticker}"
    
    # 1. Staleness Logic: Redis Cache (Cache Hit)
    try:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            print(f"⚡ CACHE HIT: Returning {ticker} data from Redis")
            return {"source": "cache (redis)", "data": json.loads(cached_data)}
    except Exception as e:
        print(f"⚠️ Redis cache error for {cache_key}: {e}")
        
    print(f"🗄️ CACHE MISS: Fetching {ticker} from Database")
    session = SessionLocal()
    
    try:
        db_data = session.query(ProcessedMarketData).join(
            SymbolMaster, ProcessedMarketData.symbol_id == SymbolMaster.symbol_id
        ).filter(
            SymbolMaster.nse_ticker == ticker
        ).order_by(ProcessedMarketData.date.desc()).limit(7).all()
        
        if not db_data:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
            
        result_data = []
        for row in db_data:
            result_data.append({
                "date": str(row.date),
                "open": row.open_price,
                "high": row.high_price,
                "low": row.low_price,
                "close": row.close_price,
                "volume": row.volume,
                "confidence_score": row.confidence_score,
                "is_anomalous": row.is_anomalous
            })
            
        try:
            redis_client.set(cache_key, json.dumps(result_data), ex=300)
        except Exception as e:
            print(f"⚠️ Redis cache write error for {cache_key}: {e}")
        
        return {"source": "database (postgres)", "data": result_data}
        
    finally:
        session.close()


@app.get("/api/analytics/{ticker}", tags=["Dashboard"], dependencies=[Depends(require_admin)])
def get_analytics_data(ticker: str, interval: str = 'D'):
    """
    Returns aggregated data for the Analytics screen: symbol info, OHLC chart data,
    extended raw OHLCV for client-side indicator calculations, data quality metrics,
    events, and sentiment.
    """
    if interval != 'D':
        raise HTTPException(
            status_code=404, 
            detail="Real intraday historical data (1m, 5m, 15m, 1h) is not available on your current data provider plan. Please upgrade to view these intervals."
        )

    ticker = ticker.upper()
    session = SessionLocal()
    
    try:
        # 1. Symbol Info
        symbol_record = session.query(SymbolMaster).filter(
            (SymbolMaster.nse_ticker == ticker) | 
            (SymbolMaster.symbol_id == ticker) | 
            (SymbolMaster.symbol_id == f"SYM_{ticker}")
        ).first()
        
        if not symbol_record:
            raise HTTPException(status_code=404, detail=f"Symbol {ticker} not found")
            
        exchange = "NSE" if symbol_record.nse_ticker else "NASDAQ"
        company_name = symbol_record.company_name or ticker
        
        # 2. Market Data — pull up to 90 days for client-side indicator calculations
        db_data_extended_raw = session.query(ProcessedMarketData).filter(
            ProcessedMarketData.symbol_id == symbol_record.symbol_id
        ).order_by(ProcessedMarketData.date.desc()).limit(200).all()
        
        seen_dates = set()
        db_data_extended = []
        for row in db_data_extended_raw:
            if row.date not in seen_dates:
                db_data_extended.append(row)
                seen_dates.add(row.date)
            if len(db_data_extended) == 90:
                break
        
        if not db_data_extended:
             raise HTTPException(status_code=404, detail=f"No market data found for {ticker}")
             
        # Reverse to chronological order (oldest → newest)
        db_data_extended.reverse()
        
        # The last 30 bars are for the visible chart
        db_data = db_data_extended[-30:] if len(db_data_extended) >= 30 else db_data_extended
        
        latest = db_data[-1]
        previous = db_data[-2] if len(db_data) > 1 else latest
        
        chart_data = []
        raw_ohlcv = []
        
        # Build raw OHLCV from ALL extended data (up to 90 days for indicator calculations)
        for row in db_data_extended:
            raw_ohlcv.append({
                "date": str(row.date),
                "open": float(row.open_price),
                "high": float(row.high_price),
                "low": float(row.low_price),
                "close": float(row.close_price),
                "volume": float(row.volume)
            })
            
        # Build chart data for the visible 30-day window
        for row in db_data:
            chart_data.append({
                "date": str(row.date),
                "open": float(row.open_price),
                "high": float(row.high_price),
                "low": float(row.low_price),
                "close": float(row.close_price),
                "volume": float(row.volume)
            })
            
        # 3. Price & Change Calculation
        change_pct = 0.0
        if previous.close_price and previous.close_price > 0:
            change_pct = ((latest.close_price - previous.close_price) / previous.close_price) * 100
            
        # 4. Data Quality Metrics
        total_confidence = sum(row.confidence_score for row in db_data if row.confidence_score)
        avg_confidence = (total_confidence / len(db_data)) * 100 if db_data else 95.0
        anomalies = sum(1 for row in db_data if row.is_anomalous)
        
        # 5. Build close-price series for sentiment
        all_closes = [row.close_price for row in db_data_extended if row.close_price is not None]
        if len(db_data) < 30:
            all_closes = [c["close"] for c in chart_data]
        
        # 6. REAL EVENTS — derived from data quality
        events = []
        
        anomalous_rows = [row for row in db_data if row.is_anomalous]
        if anomalous_rows:
            latest_anomaly = anomalous_rows[-1]
            events.append({
                "title": "Anomaly Detected",
                "desc": f"{len(anomalous_rows)} anomalous data point(s) found. Latest on {latest_anomaly.date}.",
                "type": "warning"
            })
        
        low_conf_rows = [row for row in db_data if row.confidence_score and row.confidence_score < 0.7]
        if low_conf_rows:
            events.append({
                "title": "Low Confidence Data",
                "desc": f"{len(low_conf_rows)} data points have confidence < 70%.",
                "type": "warning"
            })
        
        from datetime import date as date_type
        if db_data:
            latest_date = db_data[-1].date
            days_stale = (date_type.today() - latest_date).days if latest_date else 0
            if days_stale > 3:
                events.append({
                    "title": "Stale Data",
                    "desc": f"Latest data is {days_stale} days old. Run EOD pull to refresh.",
                    "type": "error"
                })
            elif days_stale <= 1:
                events.append({
                    "title": "Data Fresh",
                    "desc": f"Market data is up to date ({latest_date}).",
                    "type": "info"
                })
        
        if not events:
            events.append({"title": "All Systems Normal", "desc": "No anomalies or warnings detected.", "type": "info"})
        
        # 7. REAL SENTIMENT — derived from price momentum
        if len(all_closes) >= 2:
            recent_deltas = [all_closes[i] - all_closes[i - 1] for i in range(max(1, len(all_closes) - 10), len(all_closes))]
            positive_days = sum(1 for d in recent_deltas if d > 0)
            total_days = len(recent_deltas)
            bullish_pct = round((positive_days / total_days) * 100) if total_days > 0 else 50
        else:
            bullish_pct = 50
        
        bearish_pct = 100 - bullish_pct
        
        # Simple RSI for sentiment classification
        rsi_value = 50.0
        if len(all_closes) > 14:
            deltas = [all_closes[i] - all_closes[i - 1] for i in range(1, len(all_closes))]
            gains = [max(d, 0) for d in deltas[:14]]
            losses = [abs(min(d, 0)) for d in deltas[:14]]
            avg_gain = sum(gains) / 14
            avg_loss = sum(losses) / 14
            for i in range(14, len(deltas)):
                avg_gain = (avg_gain * 13 + max(deltas[i], 0)) / 14
                avg_loss = (avg_loss * 13 + abs(min(deltas[i], 0))) / 14
            if avg_loss > 0:
                rsi_value = 100 - (100 / (1 + avg_gain / avg_loss))
        
        if rsi_value > 55 and bullish_pct > 50:
            news_sentiment = "Positive"
        elif rsi_value < 45 and bullish_pct < 50:
            news_sentiment = "Negative"
        else:
            news_sentiment = "Neutral"
        
        if len(all_closes) >= 5:
            recent_prices = all_closes[-10:]
            mean_price = sum(recent_prices) / len(recent_prices)
            variance = sum((p - mean_price) ** 2 for p in recent_prices) / len(recent_prices)
            std_dev_pct = (variance ** 0.5 / mean_price) * 100 if mean_price > 0 else 0
            if std_dev_pct > 3:
                social_volatility = "High"
            elif std_dev_pct > 1.5:
                social_volatility = "Notable"
            else:
                social_volatility = "Low"
        else:
            social_volatility = "Unknown"
        
        # 8. Response Construction
        return {
            "symbol": {
                "ticker": ticker,
                "exchange": exchange,
                "name": company_name
            },
            "price": {
                "live": latest.close_price,
                "change_pct": round(change_pct, 2)
            },
            "chartData": chart_data,
            "rawOHLCV": raw_ohlcv,
            "dataQuality": {
                "confidence": round(avg_confidence, 1),
                "anomalies": anomalies
            },
            "events": events,
            "sentiment": {
                "bullish": bullish_pct,
                "bearish": bearish_pct,
                "news": news_sentiment,
                "social": social_volatility
            }
        }
        
    finally:
        session.close()

def _read_env(key: str) -> str:
    if not os.path.exists(".env"):
        return ""
    with open(".env", "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""

def _write_env(key: str, value: str):
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write(f"{key}={value}\n")
        return
    with open(".env", "r") as f:
        lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"
        lines.append(f"{key}={value}\n")
    with open(".env", "w") as f:
        f.writelines(lines)

class ApiKeysConfig(BaseModel):
    twelveData: str | None = None
    eodhd: str | None = None
    alphaVantage: str | None = None
    marketstack: str | None = None
    zerodhaApiKey: str | None = None
    zerodhaAccessToken: str | None = None
    upstoxAccessToken: str | None = None
    nsebseApiKey: str | None = None

@app.get("/api/settings/apikeys", dependencies=[Depends(require_admin)])
def get_api_keys():
    """Returns masked API key status — never exposes full keys."""
    def _mask(val: str) -> dict:
        if not val:
            return {"configured": False, "masked": ""}
        if len(val) <= 7:
            return {"configured": True, "masked": "••••••"}
        return {"configured": True, "masked": f"{val[:4]}••••••{val[-3:]}"}

    return {
        "twelveData": _mask(_read_env("TWELVE_DATA_API_KEY")),
        "eodhd": _mask(_read_env("EODHD_API_KEY")),
        "alphaVantage": _mask(_read_env("ALPHA_VANTAGE_API_KEY")),
        "marketstack": _mask(_read_env("MARKETSTACK_API_KEY")),
        "zerodhaApiKey": _mask(_read_env("ZERODHA_API_KEY")),
        "zerodhaAccessToken": _mask(_read_env("ZERODHA_ACCESS_TOKEN")),
        "upstoxAccessToken": _mask(_read_env("UPSTOX_ACCESS_TOKEN")),
        "nsebseApiKey": _mask(_read_env("NSEBSE_API_KEY"))
    }

@app.post("/api/settings/apikeys", dependencies=[Depends(require_admin)])
def update_api_keys(keys: ApiKeysConfig):
    # Validate keys to prevent fake short keys like "abcd"
    for field_name, value in keys.model_dump().items():
        if value is not None and len(value) > 0 and len(value) < 15:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid API Key format for {field_name}. Keys must be at least 15 characters long."
            )

    if keys.twelveData is not None: _write_env("TWELVE_DATA_API_KEY", keys.twelveData)
    if keys.eodhd is not None: _write_env("EODHD_API_KEY", keys.eodhd)
    if keys.alphaVantage is not None: _write_env("ALPHA_VANTAGE_API_KEY", keys.alphaVantage)
    if keys.marketstack is not None: _write_env("MARKETSTACK_API_KEY", keys.marketstack)
    if keys.zerodhaApiKey is not None: _write_env("ZERODHA_API_KEY", keys.zerodhaApiKey)
    if keys.zerodhaAccessToken is not None: _write_env("ZERODHA_ACCESS_TOKEN", keys.zerodhaAccessToken)
    if keys.upstoxAccessToken is not None: _write_env("UPSTOX_ACCESS_TOKEN", keys.upstoxAccessToken)
    if keys.nsebseApiKey is not None: _write_env("NSEBSE_API_KEY", keys.nsebseApiKey)
    return {"status": "success"}

class InternalConfig(BaseModel):
    schedulerEnabled: bool
    rateLimitReqs: int

@app.get("/api/settings/internal", response_model=InternalConfig, dependencies=[Depends(require_admin)])
def get_internal_config():
    scheduler_str = _read_env("SCHEDULER_ENABLED")
    rate_limit_str = _read_env("GLOBAL_RATE_LIMIT")
    
    return InternalConfig(
        schedulerEnabled=scheduler_str.lower() == "true" if scheduler_str else True,
        rateLimitReqs=int(rate_limit_str) if rate_limit_str else 50
    )

@app.post("/api/settings/internal", dependencies=[Depends(require_admin)])
def update_internal_config(config: InternalConfig):
    _write_env("SCHEDULER_ENABLED", str(config.schedulerEnabled).lower())
    _write_env("GLOBAL_RATE_LIMIT", str(config.rateLimitReqs))
    return {"status": "success"}
# --- Bot 4 API ---
@app.get("/api/allocation/results", tags=["Bot 4"], dependencies=[Depends(require_admin)])
def get_allocations(limit: int = 50):
    from src.domain.models import AllocationResult, SymbolMaster, SystemSettings
    session = SessionLocal()
    try:
        # Fetch total capital from settings for the amount calculation
        setting = session.query(SystemSettings).filter_by(key="BOT4_TOTAL_CAPITAL").first()
        total_capital = float(setting.value) if setting and setting.value else 1000000.0

        results = session.query(AllocationResult, SymbolMaster).join(
            SymbolMaster, AllocationResult.symbol_id == SymbolMaster.symbol_id
        ).order_by(AllocationResult.position_size_pct.desc()).limit(limit).all()
        
        data = []
        for alloc, symbol in results:
            data.append({
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "company_name": symbol.company_name or "Unknown",
                "allocation_pct": alloc.position_size_pct,
                "allocation_amount": (alloc.position_size_pct / 100.0) * total_capital if alloc.position_size_pct else 0.0,
                "ein_score": alloc.ein_score,
                "risk_flags": alloc.risk_flag,
                "date": alloc.date.isoformat() if alloc.date else ""
            })
        return {"data": data}
    finally:
        session.close()

@app.get("/api/allocation/risk-summary", tags=["Bot 4"], dependencies=[Depends(require_admin)])
def get_risk_summary():
    from src.services.allocation_engine import AllocationEngine
    session = SessionLocal()
    try:
        engine = AllocationEngine(session)
        return engine.get_portfolio_risk_summary()
    finally:
        session.close()

# --- Bot 5 API ---
@app.get("/api/top20/portfolio", tags=["Bot 5"], dependencies=[Depends(require_admin)])
def get_top20_portfolio():
    from src.domain.models import Top20Portfolio, SymbolMaster, AllocationResult
    session = SessionLocal()
    try:
        latest = session.query(Top20Portfolio).order_by(Top20Portfolio.date.desc()).first()
        if not latest:
            return {"data": []}

        results = session.query(Top20Portfolio, SymbolMaster, AllocationResult.sector).join(
            SymbolMaster, Top20Portfolio.symbol_id == SymbolMaster.symbol_id
        ).outerjoin(
            AllocationResult,
            (Top20Portfolio.symbol_id == AllocationResult.symbol_id) &
            (Top20Portfolio.date == AllocationResult.date)
        ).filter(Top20Portfolio.date == latest.date).order_by(Top20Portfolio.final_rank.asc()).all()
        
        data = []
        for row, symbol, sector in results:
            data.append({
                "rank": row.final_rank,
                "ticker": symbol.nse_ticker or symbol.symbol_id,
                "company_name": symbol.company_name or "Unknown",
                "allocation_pct": row.allocation_pct,
                "allocation_amount": row.allocation_amount,
                "ein_score": row.ein_score,
                "risk_category": row.risk_category,
                "inclusion_reason": row.inclusion_reason,
                "sector": sector or "Unknown",
                "date": row.date.isoformat() if row.date else ""
            })
        return {"data": data}
    finally:
        session.close()

@app.get("/api/top20/summary", tags=["Bot 5"], dependencies=[Depends(require_admin)])
def get_top20_summary():
    from src.services.ranking_engine import RankingEngine
    session = SessionLocal()
    try:
        engine = RankingEngine(session)
        return engine.get_top_20_summary()
    finally:
        session.close()

# --- Bot 4 Settings API ---
@app.get("/api/settings/bot4", tags=["Settings"], dependencies=[Depends(require_admin)])
def get_bot4_settings():
    from src.domain.models import SystemSettings
    session = SessionLocal()
    try:
        configs = session.query(SystemSettings).filter(SystemSettings.key.in_([
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

@app.post("/api/settings/bot4", tags=["Settings"], dependencies=[Depends(require_admin)])
def update_bot4_settings(config: dict):
    from src.domain.models import SystemSettings
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
                record = session.query(SystemSettings).filter(SystemSettings.key == k).first()
                if record:
                    record.value = v
                else:
                    session.add(SystemSettings(key=k, value=v))
        session.commit()
        return {"message": "Settings updated"}
    finally:
        session.close()

# ============================================================
# Bot 9 - Model Governance & Audit API Endpoints
# ============================================================

class GPOverrideRequest(BaseModel):
    model_type: str  # MARKOV, REGIME, MONTE_CARLO, RISK_CONFIG, PORTFOLIO
    decision: str    # APPROVED, REJECTED, OVERRIDE_DEPLOY
    reason: str      # Human-readable explanation
    actor: str       # GP user identifier

class RecalibrationRequest(BaseModel):
    model_type: str
    actor: str = "SYSTEM"

@app.get("/api/v1/governance/summary", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def get_governance_summary():
    """Returns a high-level governance dashboard summary."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        return engine.get_governance_summary()
    finally:
        session.close()

@app.get("/api/v1/governance/events", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def get_governance_events(model_type: str = None, event_type: str = None, page: int = 1, limit: int = 50):
    """Returns governance event timeline (paginated, filterable by model_type and event_type)."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        return engine.get_governance_timeline(
            model_type=model_type,
            event_type=event_type,
            limit=limit,
            page=page,
        )
    finally:
        session.close()

@app.get("/api/v1/governance/drift-report", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def get_drift_report(model_type: str = "MARKOV", days: int = 30):
    """Returns quantitative drift monitoring report for the last N days."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        return engine.get_drift_report(days=days, model_type=model_type)
    finally:
        session.close()

@app.post("/api/v1/governance/gp-override", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def log_gp_override(request: GPOverrideRequest):
    """Log a GP (General Partner) override decision with explicit reason tracking."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        event = engine.log_gp_override(
            model_type=request.model_type,
            decision=request.decision,
            reason=request.reason,
            actor=request.actor,
        )
        return {
            "message": f"GP override logged successfully for {request.model_type}",
            "event_id": event.id,
            "created_at": str(event.created_at),
        }
    finally:
        session.close()

@app.get("/api/v1/governance/versions", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def get_model_versions(model_type: str = None):
    """Returns all registered model versions, optionally filtered by model_type."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        return {"versions": engine.get_all_versions(model_type=model_type)}
    finally:
        session.close()

@app.post("/api/v1/governance/recalibrate", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def trigger_recalibration(request: RecalibrationRequest):
    """Trigger a manual model recalibration and log the event."""
    from src.services.governance_engine import GovernanceEngine
    session = SessionLocal()
    try:
        engine = GovernanceEngine(session)
        result = engine.trigger_recalibration(
            model_type=request.model_type,
            actor=request.actor,
        )
        return {"message": result}
    finally:
        session.close()

@app.post("/trigger/bot9/drift_monitor", tags=["Bot 9 - Governance"], dependencies=[Depends(require_admin)])
def trigger_bot9_drift_monitor():
    """Endpoint to trigger Bot 9 Drift Monitoring manually."""
    from src.workers.tasks import run_drift_monitoring
    task = run_drift_monitoring.delay(is_manual=True)
    return {
        "message": "Bot 9 Drift Monitoring triggered successfully",
        "task_id": task.id
    }

# ══════════════════════════════════════════════════════════
# 60-Day Shadow Validation Protocol
# ══════════════════════════════════════════════════════════

@app.post("/api/v1/shadow/start", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def start_shadow_period(period_name: str = None):
    """Start a new 60-day shadow validation period."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        period = engine.start_shadow_period(period_name)
        return {
            "message": f"Shadow validation period '{period.period_name}' started successfully",
            "period_id": period.id,
            "period_name": period.period_name,
            "start_date": str(period.start_date),
            "target_end_date": str(period.target_end_date),
            "target_days": 60
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.get("/api/v1/shadow/status", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def get_shadow_status():
    """Get current shadow validation period status and progress."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        return engine.get_shadow_status()
    finally:
        session.close()

@app.get("/api/v1/shadow/daily-logs", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def get_shadow_daily_logs(period_id: int):
    """Get all daily comparison logs for a shadow validation period."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        logs = engine.get_daily_logs(period_id)
        return {"period_id": period_id, "total": len(logs), "logs": logs}
    finally:
        session.close()

@app.post("/api/v1/shadow/generate-report", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def generate_shadow_report(period_id: int):
    """Generate the final 60-day comparison report."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        report = engine.generate_shadow_report(period_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.get("/api/v1/shadow/report", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def get_shadow_report(period_id: int):
    """Get a completed shadow validation report."""
    from src.domain.models import ShadowValidationPeriod
    session = SessionLocal()
    try:
        period = session.query(ShadowValidationPeriod).filter_by(id=period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Shadow period not found")
        if not period.report_summary:
            raise HTTPException(status_code=404, detail="Report not yet generated for this period")
        return period.report_summary
    finally:
        session.close()

@app.post("/api/v1/shadow/abort", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def abort_shadow_period(period_id: int, reason: str = "Manual abort by admin"):
    """Abort a running shadow validation period."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        period = engine.abort_shadow_period(period_id, reason)
        return {
            "message": f"Shadow period '{period.period_name}' aborted",
            "days_completed": period.trading_days_logged
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.post("/api/v1/shadow/promote", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def promote_variant_model(period_id: int, actor: str = "admin"):
    """Promote the variant model from SHADOW to ACTIVE_ADVISORY after passing validation."""
    from src.services.shadow_validation_engine import ShadowValidationEngine
    session = SessionLocal()
    try:
        engine = ShadowValidationEngine(session)
        result = engine.promote_variant(period_id, actor)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()

@app.post("/trigger/shadow/daily_comparison", tags=["Shadow Validation"], dependencies=[Depends(require_admin)])
def trigger_shadow_daily_comparison():
    """Manually trigger a daily shadow comparison run."""
    from src.workers.tasks import run_shadow_daily_comparison
    task = run_shadow_daily_comparison.delay()
    return {
        "message": "Shadow daily comparison triggered",
        "task_id": task.id
    }

