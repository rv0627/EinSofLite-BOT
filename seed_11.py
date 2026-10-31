import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.models import SymbolMaster

db_user = os.getenv("POSTGRES_USER", "postgres")
db_pass = os.getenv("POSTGRES_PASSWORD", "password")
db_name = os.getenv("POSTGRES_DB", "einsoflite")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{db_user}:{db_pass}@127.0.0.1:5432/{db_name}")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

LEGACY_TOKENS = {
    "INFY": {"zerodha": "408065", "upstox": "INE009A01021", "sector": "Technology"},
    "TCS": {"zerodha": "2953217", "upstox": "INE467B01029", "sector": "Technology"},
    "HDFCBANK": {"zerodha": "341249", "upstox": "INE040A01034", "sector": "Finance"},
    "ICICIBANK": {"zerodha": "1270529", "upstox": "INE090A01021", "sector": "Finance"},
    "SBIN": {"zerodha": "779521", "upstox": "INE062A01020", "sector": "Finance"},
    "BHARTIARTL": {"zerodha": "2714625", "upstox": "INE397D01024", "sector": "Telecom"},
    "ITC": {"zerodha": "424961", "upstox": "INE154A01025", "sector": "FMCG"},
    "ASIANPAINT": {"zerodha": "60417", "upstox": "INE021A01026", "sector": "Consumer"},
    "HINDUNILVR": {"zerodha": "345089", "upstox": "INE030A01027", "sector": "FMCG"},
    "WIPRO": {"zerodha": "969473", "upstox": "INE075A01022", "sector": "Technology"},
    "RELIANCE": {"zerodha": "738561", "upstox": "INE002A01018", "sector": "Energy"},
}
KEY_TICKERS = {"RELIANCE", "TCS", "INFY"}

def seed():
    session = SessionLocal()
    for nse_ticker, data in LEGACY_TOKENS.items():
        is_key = nse_ticker in KEY_TICKERS
        sym = session.query(SymbolMaster).filter_by(nse_ticker=nse_ticker).first()
        if not sym:
            sym = SymbolMaster(
                symbol_id=f"SYM_{nse_ticker}",
                nse_ticker=nse_ticker,
                company_name=nse_ticker,
                sector=data["sector"],
                is_watchlist=is_key,
                is_dashboard_fallback=is_key,
                zerodha_token=data["zerodha"],
                upstox_token=data["upstox"],
                active=True
            )
            session.add(sym)
    session.commit()
    print("Seeded 11 symbols!")

if __name__ == "__main__":
    seed()
