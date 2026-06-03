from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa oficial dos modelos SQLAlchemy do Kovir."""


engine = create_engine(
    settings.resolved_database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict[str, object]:
    """Executa um healthcheck minimo sem depender de tabelas migradas."""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("select 1"))
            scalar_result = result.scalar_one()

        return {
            "online": scalar_result == 1,
            "database": "postgresql",
            "driver": "psycopg",
        }
    except Exception:  # pragma: no cover - resposta diagnostica segura
        return {
            "online": False,
            "database": "postgresql",
            "driver": "psycopg",
        }
