"""First-run setup for the local sample database."""

from pathlib import Path

from .database import connect, load_database
from .generator import generate_csv


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "synthetic_pharma_sales.csv"
DB_PATH = ROOT / "data" / "pharma_sales.sqlite3"


def ensure_demo_data() -> dict | None:
    if DB_PATH.exists():
        try:
            with connect(DB_PATH) as connection:
                count = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
            if count == 0:
                raise ValueError("The existing database has no sales rows")
        except Exception as exc:
            raise ValueError(
                f"The existing database cannot be used: {DB_PATH}. "
                "Move it aside before rebuilding; no existing file was replaced."
            ) from exc
        return None
    if not CSV_PATH.exists():
        generate_csv(CSV_PATH)
    return load_database(CSV_PATH, DB_PATH)


if __name__ == "__main__":
    report = ensure_demo_data()
    print(report or f"Database already exists: {DB_PATH}")
