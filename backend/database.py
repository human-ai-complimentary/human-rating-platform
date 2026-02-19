from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Get database URL from environment variable, or use SQLite as default
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Handle various database URL formats
    if DATABASE_URL.startswith("postgres://"):
        # Render's postgres:// URL format (SQLAlchemy requires postgresql://)
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    elif DATABASE_URL.startswith("mysql://"):
        # MySQL: use pymysql driver if not specified
        DATABASE_URL = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Default to SQLite for local development
    # Use /data on Render (persistent disk), otherwise local data folder
    if os.path.exists("/data"):
        DATABASE_DIR = "/data"
    else:
        DATABASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(DATABASE_DIR, exist_ok=True)

    DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'rating_platform.db')}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    # Enable foreign key support for SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
