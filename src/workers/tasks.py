import os
import json
import hashlib
from datetime import date, timedelta, datetime
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from celery.schedules import crontab

from src.domain.models import RawPayload, SymbolMaster, SourceHealthEvent, ProcessedMarketData, ScoringDataset, SystemSettings
from src.services.normalizer import MarketDataNormalizer
from src.adapters.twelvedata import TwelveDataAdapter
from src.services.router import MarketDataRouter
from src.services.scoring_engine import ScoringEngine
from src.services.allocation_engine import AllocationEngine
from src.services.ranking_engine import RankingEngine
from src.services.stress_testing_engine import StressTestingEngine

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/einsoflite")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery setup
celery_app = Celery('ein_sof_tasks', broker=REDIS_URL, backend=REDIS_URL)

# --- Celery Beat Schedule Automate schedule ---

celery_app.conf.timezone = 'Asia/Kolkata' 

celery_app.conf.beat_schedule = {
# One of the most critical tasks: Pull EOD data for all active symbols every weekday at 4 PM IST, right after the market closes. This ensures we have fresh data to work with for our analysis and bots.
    'fetch-eod-daily-at-4pm': {
        'task': 'pull_all_eod_data',
        'schedule': crontab(hour=16, minute=0, day_of_week='1-5'), 
    },
    
# For our watchlist of priority symbols, we want to pull live data every 5 minutes during market hours (9:15 AM to 3:30 PM IST) on weekdays. This allows us to have near real-time data for our most important stocks and can be used for intraday analysis and alerts.
    'fetch-live-every-5-mins': {
        'task': 'pull_live_data',
        'schedule': crontab(minute='*/5', hour='9-15', day_of_week='1-5'),
    },
    
# To ensure our raw data is processed and normalized in a timely manner, we can schedule the processing task to run every hour. This way, as soon as new raw data comes in (either from EOD pulls or live data), it will be processed within an hour, keeping our processed market data up-to-date for our bots and API.
    'process-raw-data-hourly': {
        'task': 'process_raw_data',
        'schedule': crontab(minute=30), # Runs at the 30th minute of every hour
    },
}

# Bot 3 Scoring Engine: Runs daily at 6 PM, but the task checks DB to skip if set to 'weekly'
celery_app.conf.beat_schedule['calculate-ein-scores'] = {
    'task': 'calculate_ein_scores',
    'schedule': crontab(hour=18, minute=0),
}

# Bot 4 Allocation & Risk Management: Runs daily at 6:30 PM (after Bot 3)
celery_app.conf.beat_schedule['calculate-allocations'] = {
    'task': 'calculate_allocations',
    'schedule': crontab(hour=18, minute=30),
}

# Bot 5 Ranking Engine + Top 20 Generation: Runs daily at 7:00 PM (after Bot 4)
celery_app.conf.beat_schedule['generate-top-20'] = {
    'task': 'generate_top_20',
    'schedule': crontab(hour=19, minute=0),
}

# Bot 6 Stress Testing Engine: Runs daily at 7:30 PM (after Bot 5)
celery_app.conf.beat_schedule['run-stress-test'] = {
    'task': 'run_stress_test',
    'schedule': crontab(hour=19, minute=30),
}

# Bot 7 & 8 Reporting Engine: Runs daily at 8:00 PM (after Bot 6)
celery_app.conf.beat_schedule['generate-daily-report'] = {
    'task': 'generate_daily_report',
    'schedule': crontab(hour=20, minute=0),
}

# Bot 9 Model Governance: Drift monitoring runs daily at 8:30 PM (after Reporting)
celery_app.conf.beat_schedule['run-drift-monitoring'] = {
    'task': 'run_drift_monitoring',
    'schedule': crontab(hour=20, minute=30),
}

# Shadow Validation Protocol: Runs daily at 9:00 PM (after Drift monitoring)
celery_app.conf.beat_schedule['run-shadow-daily-comparison'] = {
    'task': 'run_shadow_daily_comparison',
    'schedule': crontab(hour=21, minute=0),
}

# ── .env reader utilities (for dynamic BOT Control settings) ──────────
def _read_env(key: str) -> str:
    """Read a value directly from the .env file on disk (not cached os.getenv)."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if not os.path.exists(env_path):
        return ""
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""

def _is_scheduler_enabled() -> bool:
    """Check if the scheduler is enabled via BOT Control settings."""
    val = _read_env("SCHEDULER_ENABLED")
    # Default to True if not set
    if not val:
        return True
    return val.lower() == "true"

def _get_rate_limit_delay() -> float:
    """Get the delay between API calls based on GLOBAL_RATE_LIMIT (req/s).
    Returns delay in seconds. e.g. 50 req/s → 0.02s delay, 10 req/s → 0.1s delay.
    """
    val = _read_env("GLOBAL_RATE_LIMIT")
    try:
        reqs_per_sec = int(val) if val else 50
        if reqs_per_sec <= 0:
            reqs_per_sec = 1
        return 1.0 / reqs_per_sec
    except (ValueError, ZeroDivisionError):
        return 0.02  # default ~50 req/s


@celery_app.task(name="fetch_single_symbol_eod", rate_limit="8/m")
def fetch_single_symbol_eod(ticker: str, symbol_id: str, instrument_token: str, upstox_token: str):
    session = SessionLocal()
    router = MarketDataRouter()
    
    try:
        print(f"[{ticker}] Processing EOD data pull in background...")
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        
        historical_data = router.fetch_eod_data(
            ticker=ticker,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        
        if historical_data:
            payload_dict = {"sources": historical_data}
            c_hash = hashlib.sha256(json.dumps(payload_dict, sort_keys=True).encode()).hexdigest()
            
            # Prevent duplicate insertion
            exists = session.query(RawPayload).filter(RawPayload.content_hash == c_hash).first()
            if exists:
                return f"Skipped: Data already exists for {ticker}"
                
            payload_record = RawPayload(
                run_id=f"run_eod_{date.today().strftime('%Y%m%d')}",
                symbol_id=symbol_id,
                source="Router_Aggregated",
                data_type="eod",
                payload=payload_dict,
                content_hash=c_hash,
                status="pending"
            )
            session.add(payload_record)
            session.commit()
            return f"Success for {ticker}"
        return f"No data for {ticker}"
        
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

# This task will pull EOD data sequentially for all active symbols with a delay to respect rate limits.
# Because it blocks, the frontend will correctly show 'Running...' until all data is fetched.
@celery_app.task(name="pull_all_eod_data")
def pull_all_eod_data(is_manual=False):
    import time
    
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    
    session = SessionLocal()
    try:
        active_symbols = session.query(SymbolMaster).filter(SymbolMaster.active == True).all()
        
        # ── BOT Control: Get rate limit delay ──
        rate_delay = _get_rate_limit_delay()
        
        success_count = 0
        no_data_count = 0
        failed_count = 0
        task_count = 0
        total_symbols = len(active_symbols)
        
        for symbol in active_symbols:
            token = symbol.zerodha_token or ""
            u_token = symbol.upstox_token or ""
            
            try:
                # Call the python function synchronously, not as a celery task
                result = fetch_single_symbol_eod(
                    ticker=symbol.nse_ticker,
                    symbol_id=symbol.symbol_id,
                    instrument_token=token,
                    upstox_token=u_token
                )
                if result and "Success" in result:
                    success_count += 1
                else:
                    no_data_count += 1
            except Exception as e:
                failed_count += 1
                print(f"[{symbol.nse_ticker}] Fetch failed: {e}")
            
            task_count += 1
            # ── BOT Control: Apply rate limit delay between API calls ──
            if task_count < total_symbols:
                time.sleep(rate_delay)
                
        if total_symbols > 0 and failed_count == total_symbols:
            raise Exception(f"CRITICAL: All {total_symbols} symbols failed to fetch. API might be down.")
            
        return f"Finished {total_symbols} symbols: {success_count} success, {no_data_count} empty, {failed_count} failed."
    finally:
        session.close()

# @celery_app.task(name="pull_eod_data")
# def pull_eod_data():
#     session = SessionLocal()
#     router = MarketDataRouter() # create Router
    
#     try:
#         active_symbols = session.query(SymbolMaster).filter(SymbolMaster.active == True).all()
        
#         for symbol in active_symbols:
#             print(f"Fetching data for {symbol.nse_ticker}...")
            
            
#             historical_data = router.fetch_eod_data(
#                 ticker=symbol.nse_ticker,
#                 instrument_token="738561", 
#                 start_date="2026-05-10",
#                 end_date="2026-05-18"
#             )
            
#             if historical_data:
#                 payload_record = RawPayload(
#                     run_id=f"run_eod_{date.today().strftime('%Y%m%d')}",
#                     symbol_id=symbol.symbol_id,
#                     source="Router", 
#                     data_type="eod",
#                     payload={"values": historical_data}
#                 )
#                 session.add(payload_record)
                
#         session.commit()
#         return "Success"
        
#     except Exception as e:
#         session.rollback()
#         print(f"Error: {e}")
#         return "Failed"
#     finally:
#         session.close()


@celery_app.task(name="process_raw_data")
def process_raw_data(is_manual=False):
    """Bot 2: Process raw payloads and normalize them into ProcessedMarketData format"""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    
    session  = SessionLocal()
    
    # Fetch bot1_config for dynamic parameters
    bot1_config = session.query(SystemSettings).filter_by(key="bot1_config").first()
    config_vals = bot1_config.value if bot1_config and bot1_config.value else {}
    
    anomaly_threshold_pct = float(config_vals.get("anomaly_threshold_pct", 0.20))
    primary_deviation_threshold = float(config_vals.get("primary_deviation_threshold", 0.03))
    confidence_min_threshold = float(config_vals.get("confidence_min_threshold", 0.55))
    
    conf_weights = config_vals.get("confidence_weights", {
        "agreement": 0.5,
        "recency": 0.2,
        "health": 0.2,
        "consistency": 0.1
    })
    
    normalizer = MarketDataNormalizer(max_price_jump_pct=anomaly_threshold_pct)
    processed_count = 0

    try:
        # Get unprocessed raw payloads
        seven_days_ago = date.today() - timedelta(days=7)
        unprocessed_raws = session.query(RawPayload).filter(
            RawPayload.fetched_at >= seven_days_ago,
            RawPayload.data_type == "eod",
            RawPayload.status == "pending"
        ).all()

        if not unprocessed_raws:
            print("[BOT2] No Raw Payloads to Process")
            return "No Raw Payloads to Process"
        
        print(f"[BOT2] Found {len(unprocessed_raws)} raw payloads to process.")
        
        for raw in unprocessed_raws:
            payload = raw.payload
            print(f"   -> Processing payload for symbol_id: {raw.symbol_id}")

            if isinstance(payload, dict) and "sources" in payload:
                sources_data = payload["sources"]
                
                # Gather all unique dates from all sources
                all_dates = set()
                for source, daily_data_list in sources_data.items():
                    for daily_data in daily_data_list:
                        if daily_data.get("datetime"):
                            all_dates.add(daily_data.get("datetime"))
                
                # Sort dates chronologically to calculate prev_close correctly
                sorted_dates = sorted(list(all_dates))
                prev_close = None
                
                # Source weights
                source_weights = {"twelvedata": 0.85, "marketstack": 0.75, "nsebse": 0.90}
                
                for dt in sorted_dates:
                    valid_records = {} # source -> (processed_record, health_score)
                    
                    for source, daily_data_list in sources_data.items():
                        daily_data = next((d for d in daily_data_list if d.get("datetime") == dt), None)
                        if daily_data:
                            processed_record, health = normalizer.process_raw_payload(
                                raw_data=daily_data,
                                symbol_id=raw.symbol_id,
                                prev_close=prev_close
                            )
                            if processed_record and not processed_record.is_anomalous:
                                valid_records[source] = (processed_record, health)
                    
                    if not valid_records:
                        continue
                        
                    # Prepare data for weighted medians
                    opens, highs, lows, closes, volumes = [], [], [], [], []
                    for src, (rec, h) in valid_records.items():
                        w = source_weights.get(src, 0.5) * h
                        opens.append((rec.open_price, w))
                        highs.append((rec.high_price, w))
                        lows.append((rec.low_price, w))
                        closes.append((rec.close_price, w))
                        volumes.append((rec.volume, w))
                        
                    def weighted_median(vw_list):
                        if not vw_list: return 0.0
                        sorted_vw = sorted(vw_list, key=lambda x: x[0])
                        total_weight = sum(w for v, w in sorted_vw)
                        cumulative = 0.0
                        for v, w in sorted_vw:
                            cumulative += w
                            if cumulative >= total_weight / 2.0:
                                return v
                        return sorted_vw[-1][0]

                    med_open = weighted_median(opens)
                    med_high = weighted_median(highs)
                    med_low = weighted_median(lows)
                    med_close = weighted_median(closes)
                    med_vol = int(weighted_median(volumes))

                    primary_src = "twelvedata"
                    best_record = None

                    if primary_src in valid_records:
                        best_record, p_health = valid_records[primary_src]
                        
                        dev_open = abs(best_record.open_price - med_open) / med_open if med_open else 0
                        dev_high = abs(best_record.high_price - med_high) / med_high if med_high else 0
                        dev_low = abs(best_record.low_price - med_low) / med_low if med_low else 0
                        dev_close = abs(best_record.close_price - med_close) / med_close if med_close else 0
                        
                        max_dev = max(dev_open, dev_high, dev_low, dev_close)
                        agreement = max(0.0, 1.0 - max_dev)
                        
                        # Use dynamic weights
                        confidence = (conf_weights["agreement"] * agreement) + (conf_weights["recency"] * 1.0) + (conf_weights["health"] * p_health) + (conf_weights["consistency"] * 1.0)
                        
                        if max_dev > primary_deviation_threshold or confidence < confidence_min_threshold:
                            best_record.is_anomalous = True
                            confidence = min(confidence, 0.50) # Force DNT
                            print(f"      [WARN] Primary deviated >{primary_deviation_threshold*100}% or low conf! (Conf: {confidence:.2f}) -> DNT Flagged")
                        else:
                            print(f"      [OK] Primary Validated. (Conf: {confidence:.2f})")
                            
                        best_record.confidence_score = confidence

                    else:
                        # Fallback / Composite
                        print(f"      [WARN] Primary down. Using Composite Fallback.")
                        p_health = sum(h for r, h in valid_records.values()) / len(valid_records)
                        confidence = (conf_weights["agreement"] * 1.0) + (conf_weights["recency"] * 1.0) + (conf_weights["health"] * p_health) + (conf_weights["consistency"] * 1.0) - 0.15 # Penalty
                        confidence = max(0.0, confidence)
                        
                        # Take the first record as a template and overwrite with medians
                        first_record = list(valid_records.values())[0][0]
                        best_record = first_record
                        best_record.open_price = med_open
                        best_record.high_price = med_high
                        best_record.low_price = med_low
                        best_record.close_price = med_close
                        best_record.volume = med_vol
                        best_record.confidence_score = confidence
                        if confidence < confidence_min_threshold:
                            best_record.is_anomalous = True

                    if best_record:
                        existing = session.query(ProcessedMarketData).filter_by(
                            symbol_id = raw.symbol_id,
                            date = best_record.date
                        ).first()

                        if not existing:
                            session.add(best_record)
                            processed_count += 1

                        prev_close = best_record.close_price

            elif isinstance(payload, dict) and "values" in payload:
                daily_data_list = payload["values"]
                daily_data_list.reverse()
                prev_close = None
                for daily_data in daily_data_list:
                    processed_record, confidence = normalizer.process_raw_payload(
                        raw_data=daily_data,
                        symbol_id=raw.symbol_id,
                        prev_close=prev_close
                    )
                    if processed_record:
                        processed_record.confidence_score = confidence
                        existing = session.query(ProcessedMarketData).filter_by(
                            symbol_id = raw.symbol_id,
                            date = processed_record.date
                        ).first()
                        if not existing:
                            session.add(processed_record)
                            processed_count += 1
                        prev_close = processed_record.close_price

        for raw in unprocessed_raws:
            raw.status = "processed"

        session.commit()
        return f"Success: Processed {processed_count} records"
    
    except Exception as e:
        session.rollback()
        print(f"Processing Failed: {str(e)}")
        raise e
    finally:
        session.close()


# get live data for watchlist 
@celery_app.task(name="pull_live_data")
def pull_live_data(is_manual=False):
    import time
    
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    
    session = SessionLocal()
    router = MarketDataRouter() # create Router
    
    # ── BOT Control: Get rate limit delay ──
    rate_delay = _get_rate_limit_delay()

    try:
        priority_symbols = session.query(SymbolMaster).filter(
            SymbolMaster.is_watchlist == True,
            SymbolMaster.active == True
        ).all()

        task_count = 0
        for symbol in priority_symbols:
            print(f"[{symbol.nse_ticker}] Fetching live data...")
            
            token = symbol.zerodha_token or ""

            live_data = router.fetch_live_data(
                ticker=symbol.nse_ticker,
                instrument_token=token
            )

            # ── BOT Control: Apply rate limit delay between API calls ──
            if task_count > 0:
                time.sleep(rate_delay)
            
            if live_data:
                payload_dict = {"values": live_data}
                c_hash = hashlib.sha256(json.dumps(payload_dict, sort_keys=True).encode()).hexdigest()
                
                exists = session.query(RawPayload).filter(RawPayload.content_hash == c_hash).first()
                if not exists:
                    payload_record = RawPayload(
                        run_id=f"run_live_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        symbol_id=symbol.symbol_id,
                        source="Router",
                        data_type="live",
                        payload=payload_dict,
                        content_hash=c_hash,
                        status="pending"
                    )
                    session.add(payload_record)
                    task_count += 1

        session.commit()
        return f"Successfully fetched live data for {task_count} symbols."

    except Exception as e:
        print(f"Error: {e}")
        raise e
    finally:
        session.close()

@celery_app.task(name="calculate_ein_scores")
def calculate_ein_scores(is_manual=False):
    """Bot 3: Scoring Engine calculates factors and the EIN score for active symbols."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    
    from src.domain.models import SystemSettings
    session = SessionLocal()
    
    try:
        # Check Schedule mode from DB
        setting = session.query(SystemSettings).filter_by(key="bot3_config").first()
        schedule_mode = "daily"
        if setting and setting.value and "schedule" in setting.value:
            schedule_mode = setting.value["schedule"]
            
        if schedule_mode == "weekly":
            # If today is not Friday (weekday 4), skip execution
            if date.today().weekday() != 4:
                return "Skipped: Bot 3 is set to weekly mode and today is not Friday."

        scoring_engine = ScoringEngine(session)
        
        active_symbols = session.query(SymbolMaster).filter(SymbolMaster.active == True).all()
        
        if not active_symbols:
            return "No active symbols to score."
            
        print(f"[BOT3] Calculating EIN Scores for {len(active_symbols)} symbols...")
        
        datasets = []
        for symbol in active_symbols:
            dataset = scoring_engine.calculate_scores_for_symbol(symbol)
            if dataset:
                datasets.append(dataset)
                
        # Rank and save
        scoring_engine.rank_and_save_datasets(datasets)
        
        return f"Success: Calculated and ranked scores for {len(datasets)} symbols."
        
    except Exception as e:
        session.rollback()
        print(f"Bot 3 Error: {e}")
        raise e
    finally:
        session.close()


@celery_app.task(name="calculate_allocations")
def calculate_allocations(is_manual=False):
    """Bot 4: Allocation & Risk Management Engine - calculates risk-adjusted portfolio allocations."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        engine = AllocationEngine(session)
        result = engine.calculate_allocations()
        return result
    except Exception as e:
        session.rollback()
        print(f"Bot 4 Error: {e}")
        raise e
    finally:
        session.close()


@celery_app.task(name="generate_top_20")
def generate_top_20(is_manual=False):
    """Bot 5: Ranking Engine + Top 20 Generation - curates the final Top 20 portfolio."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        engine = RankingEngine(session)
        result = engine.generate_top_20()
        return result
    except Exception as e:
        session.rollback()
        print(f"Bot 5 Error: {e}")
        raise e
    finally:
        session.close()

@celery_app.task(name="run_stress_test")
def run_stress_test(is_manual=False):
    """Bot 6: Stress Testing Engine - validates the Top 20 portfolio against market shocks."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        engine = StressTestingEngine(session)
        result = engine.run_stress_test()
        return result
    except Exception as e:
        session.rollback()
        print(f"Bot 6 Error: {e}")
        raise e
    finally:
        session.close()

@celery_app.task(name="generate_daily_report")
def generate_daily_report(is_manual=False):
    """Bot 7 & 8: Reporting Engine - automatically generates the daily PDF report."""
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        from src.services.reporting_engine import ReportingEngine
        engine = ReportingEngine(session)
        pdf_bytes = engine.generate_daily_pdf_report()
        
        # Save it to a local 'reports' directory
        import os
        from datetime import date
        os.makedirs("reports", exist_ok=True)
        report_path = f"reports/daily_portfolio_report_{date.today().strftime('%Y%m%d')}.pdf"
        with open(report_path, "wb") as f:
            f.write(bytes(pdf_bytes))
            
        return f"Success: Daily report generated at {report_path}"
    except Exception as e:
        session.rollback()
        print(f"Bot 7 Error: {e}")
        raise e
    finally:
        session.close()

@celery_app.task(name="run_drift_monitoring")
def run_drift_monitoring(is_manual=False):
    """Bot 9: Model Governance - runs daily drift monitoring for all active models."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        from src.services.governance_engine import GovernanceEngine
        engine = GovernanceEngine(session)
        result = engine.run_drift_monitoring()
        return f"Success: Drift monitoring completed. Models checked: {list(result.keys())}"
    except Exception as e:
        session.rollback()
        print(f"Bot 9 Error: {e}")
        raise e
    finally:
        session.close()

@celery_app.task(name="run_shadow_daily_comparison")
def run_shadow_daily_comparison(is_manual=False):
    """60-Day Shadow Validation: Runs daily dual-path comparison."""
    # ── BOT Control: Check if scheduler is enabled ──
    if not is_manual and not _is_scheduler_enabled():
        return "Skipped: Scheduler is disabled via BOT Control settings."
    session = SessionLocal()
    
    try:
        from src.services.shadow_validation_engine import ShadowValidationEngine
        engine = ShadowValidationEngine(session)
        
        # Check if period is active
        period = engine.get_active_period()
        if not period:
            return "Skipped: No active shadow validation period running."
            
        log = engine.run_daily_comparison()
        if log:
            return f"Success: Shadow comparison Day {log.day_number} complete. Control={log.control_deployment_pct}%, Variant={log.variant_deployment_pct}%"
        return "Success: Nothing to run or already ran for today."
    except Exception as e:
        session.rollback()
        print(f"Shadow Validation Error: {e}")
        raise e
    finally:
        session.close()