"""Create the MySQL database, tables and dummy data.

    python init_db.py            create database and tables, seed only if empty
    python init_db.py --reset    drop all tables, recreate and reseed

Schema changes are managed with Alembic (`alembic upgrade head`). This script
remains the quickest way to stand up a fresh development database; it stamps
Alembic at head afterwards so migrations stay usable.
"""
import sys

from sqlalchemy import create_engine, text

from app import models_all  # noqa: F401  (registers every table, LMS included)
from app.db import Base, SessionLocal, database_name, engine, server_url
from app.models import User
from seed import seed


def _stamp_alembic() -> None:
    """Mark a freshly created schema as being at the latest migration."""
    try:
        from alembic import command
        from alembic.config import Config
    except ImportError:
        print("Alembic is not installed; skipping the version stamp.")
        return
    from pathlib import Path
    ini = Path(__file__).resolve().parent / "alembic.ini"
    if not ini.exists():
        return
    try:
        config = Config(str(ini))
        command.stamp(config, "head")
        print("Stamped Alembic at head.")
    except Exception as exc:  # pragma: no cover - informational only
        print(f"Could not stamp Alembic: {exc}")


def main(reset: bool) -> None:
    name = database_name()
    server = create_engine(server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}` "
                          "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    if reset:
        Base.metadata.drop_all(engine)
        print("Dropped existing tables.")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.query(User).count() == 0:
            seed(db)
            print("Seeded dummy data.")
        else:
            print("Data already present. Use --reset to start again.")
    _stamp_alembic()
    print(f"Database '{name}' is ready.")


if __name__ == "__main__":
    main("--reset" in sys.argv)
