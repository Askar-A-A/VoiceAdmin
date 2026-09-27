"""Create all tables in the configured database.

Quick bootstrap for local dev (proper migrations come via Alembic later):
    python -m app.init_db
"""
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  (registers every model on Base.metadata)


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tables created.")


if __name__ == "__main__":
    main()
