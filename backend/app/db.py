"""Database connection. Settings come from backend/.env (see .env.example)."""
import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()


def _cfg() -> dict:
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": os.getenv("DB_PORT", "3306"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "name": os.getenv("DB_NAME", "innovation_hub"),
    }


def server_url() -> str:
    c = _cfg()
    return f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}@{c['host']}:{c['port']}/?charset=utf8mb4"


def database_url() -> str:
    c = _cfg()
    return (
        f"mysql+pymysql://{c['user']}:{quote_plus(c['password'])}"
        f"@{c['host']}:{c['port']}/{c['name']}?charset=utf8mb4"
    )


def database_name() -> str:
    return _cfg()["name"]


class Base(DeclarativeBase):
    pass


engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
