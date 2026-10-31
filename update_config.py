import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.domain.models import SystemSettings

db_user = os.getenv("POSTGRES_USER", "postgres")
db_pass = os.getenv("POSTGRES_PASSWORD", "password")
db_name = os.getenv("POSTGRES_DB", "einsoflite")
DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://{db_user}:{db_pass}@127.0.0.1:5432/{db_name}")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

config = session.query(SystemSettings).filter_by(key='bot6_config').first()
if not config:
    config = SystemSettings(key='bot6_config', value={'min_history_days': 60, 'pref_history_days': 90, 'block_length': 10, 'simulations': 1000})
    session.add(config)
else:
    config.value = {'min_history_days': 60, 'pref_history_days': 90, 'block_length': 10, 'simulations': 1000}

session.commit()
session.close()
print('Config updated!')
