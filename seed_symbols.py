import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.models import SymbolMaster

load_dotenv()

# Database Connection
db_user = os.getenv("POSTGRES_USER", "postgres")
db_pass = os.getenv("POSTGRES_PASSWORD", "password")
db_name = os.getenv("POSTGRES_DB", "einsoflite")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{db_user}:{db_pass}@127.0.0.1:5432/{db_name}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Legacy Sector Mapping to preserve known sectors
SECTOR_MAP = {
    "RELIANCE": "Energy", "TCS": "Technology", "INFY": "Technology",
    "HDFCBANK": "Finance", "ICICIBANK": "Finance", "HINDUNILVR": "FMCG",
    "SBIN": "Finance", "BHARTIARTL": "Telecom", "ITC": "FMCG",
    "KOTAKBANK": "Finance", "LT": "Infrastructure", "ASIANPAINT": "Consumer",
    "AXISBANK": "Finance", "MARUTI": "Automobile", "SUNPHARMA": "Pharma",
    "TITAN": "Consumer", "ULTRACEMCO": "Cement", "NESTLEIND": "FMCG",
    "WIPRO": "Technology", "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance",
    "TECHM": "Technology", "HCLTECH": "Technology", "POWERGRID": "Energy",
    "NTPC": "Energy", "TATAMOTORS": "Automobile", "TATASTEEL": "Metals",
    "ONGC": "Energy", "JSWSTEEL": "Metals", "ADANIENT": "Infrastructure",
}

# Legacy Tokens
LEGACY_TOKENS = {
    "INFY": {"zerodha": "408065", "upstox": "INE009A01021"},
    "TCS": {"zerodha": "2953217", "upstox": "INE467B01029"},
    "HDFCBANK": {"zerodha": "341249", "upstox": "INE040A01034"},
    "ICICIBANK": {"zerodha": "1270529", "upstox": "INE090A01021"},
    "SBIN": {"zerodha": "779521", "upstox": "INE062A01020"},
    "BHARTIARTL": {"zerodha": "2714625", "upstox": "INE397D01024"},
    "ITC": {"zerodha": "424961", "upstox": "INE154A01025"},
    "ASIANPAINT": {"zerodha": "60417", "upstox": "INE021A01026"},
    "HINDUNILVR": {"zerodha": "345089", "upstox": "INE030A01027"},
    "WIPRO": {"zerodha": "969473", "upstox": "INE075A01022"},
    "RELIANCE": {"zerodha": "738561", "upstox": "INE002A01018"},
}

# Key fallback/watchlist tickers
KEY_TICKERS = {"RELIANCE", "TCS", "INFY"}

def seed_database():
    session = SessionLocal()
    
    try:
        from src.domain.models import Base
        print("Recreating database schema (dropping all tables)...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        print("Schema recreated.")
        
        count = 0
        updated = 0
        
        existing_symbols = {sym.nse_ticker: sym for sym in session.query(SymbolMaster).all()}
        
        print("Processing main 11 symbols...")
        for nse_ticker, tokens in LEGACY_TOKENS.items():
            company_name = nse_ticker
            
            sector = SECTOR_MAP.get(nse_ticker, "Other")
            z_token = tokens.get("zerodha")
            u_token = tokens.get("upstox")
            is_key = nse_ticker in KEY_TICKERS
            
            symbol_id = f"SYM_{nse_ticker}"
            
            if nse_ticker in existing_symbols:
                sym = existing_symbols[nse_ticker]
                changed = False
                
                if sym.company_name != company_name:
                    sym.company_name = company_name
                    changed = True
                if sym.sector != sector:
                    sym.sector = sector
                    changed = True
                if sym.is_watchlist != is_key:
                    sym.is_watchlist = is_key
                    changed = True
                if sym.is_dashboard_fallback != is_key:
                    sym.is_dashboard_fallback = is_key
                    changed = True
                if z_token and sym.zerodha_token != z_token:
                    sym.zerodha_token = z_token
                    changed = True
                if u_token and sym.upstox_token != u_token:
                    sym.upstox_token = u_token
                    changed = True
                    
                if changed:
                    updated += 1
            else:
                new_symbol = SymbolMaster(
                    symbol_id=symbol_id,
                    nse_ticker=nse_ticker,
                    company_name=company_name,
                    sector=sector,
                    is_watchlist=is_key,
                    is_dashboard_fallback=is_key,
                    zerodha_token=z_token,
                    upstox_token=u_token,
                    active=True
                )
                session.add(new_symbol)
                count += 1
        
        session.commit()
        print(f"Successfully added {count} new companies and updated {updated} existing companies!")
    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    seed_database()