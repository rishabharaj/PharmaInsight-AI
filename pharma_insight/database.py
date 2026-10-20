"""SQLite schema, Pandas cleaning, and transactional import."""

import sqlite3
from pathlib import Path

import pandas as pd

from .generator import COLUMNS, PRODUCTS, REGIONS, REPS


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS products (
  product_id INTEGER PRIMARY KEY, product_name TEXT NOT NULL UNIQUE,
  therapy_area TEXT NOT NULL, list_price_inr INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS regions (
  region_id INTEGER PRIMARY KEY, region_name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS reps (
  rep_id INTEGER PRIMARY KEY, rep_name TEXT NOT NULL, region_id INTEGER NOT NULL,
  FOREIGN KEY (region_id) REFERENCES regions(region_id)
);
CREATE TABLE IF NOT EXISTS sales (
  sale_id TEXT PRIMARY KEY, sales_date TEXT NOT NULL,
  product_id INTEGER NOT NULL, region_id INTEGER NOT NULL, rep_id INTEGER NOT NULL,
  units INTEGER NOT NULL CHECK (units > 0), unit_price_inr INTEGER NOT NULL CHECK (unit_price_inr > 0),
  discount_pct INTEGER NOT NULL CHECK (discount_pct BETWEEN 0 AND 30),
  revenue_paise INTEGER NOT NULL CHECK (revenue_paise >= 0),
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (region_id) REFERENCES regions(region_id),
  FOREIGN KEY (rep_id) REFERENCES reps(rep_id)
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sales_date);
CREATE INDEX IF NOT EXISTS idx_sales_region_date ON sales(region_id, sales_date);
CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales(product_id, sales_date);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def clean_sales(csv_path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Validate identifiers, dates and integers before writing any row to SQLite."""
    raw = pd.read_csv(csv_path, dtype="string")
    missing = set(COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
    frame = raw[COLUMNS].copy()
    frame["sales_date"] = pd.to_datetime(frame["sales_date"], errors="coerce")
    for name in ("product_id", "region_id", "rep_id", "units", "unit_price_inr", "discount_pct"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")

    valid = frame["sale_id"].str.fullmatch(r"T\d{6}").fillna(False)
    valid &= frame["sales_date"].notna()
    for name in ("product_id", "region_id", "rep_id", "units", "unit_price_inr", "discount_pct"):
        valid &= frame[name].notna() & (frame[name] % 1 == 0)
    valid &= frame["product_id"].isin([p[0] for p in PRODUCTS])
    valid &= frame["region_id"].isin([r[0] for r in REGIONS])
    valid &= frame["rep_id"].isin([r[0] for r in REPS])
    valid &= frame["units"] > 0
    valid &= frame["unit_price_inr"] > 0
    valid &= frame["discount_pct"].between(0, 30)
    valid &= frame.apply(
        lambda row: pd.isna(row["rep_id"]) or pd.isna(row["region_id"])
        or next((r[2] for r in REPS if r[0] == row["rep_id"]), None) == row["region_id"],
        axis=1,
    )
    cleaned = frame.loc[valid].drop_duplicates(subset="sale_id", keep="first").copy()
    invalid_count = int((~valid).sum())
    duplicate_count = int(valid.sum() - len(cleaned))
    cleaned["sales_date"] = cleaned["sales_date"].dt.strftime("%Y-%m-%d")
    for name in ("product_id", "region_id", "rep_id", "units", "unit_price_inr", "discount_pct"):
        cleaned[name] = cleaned[name].astype("int64")
    cleaned["revenue_paise"] = (
        cleaned["units"] * cleaned["unit_price_inr"] * (100 - cleaned["discount_pct"])
    ).astype("int64")
    audit = {"raw_rows": len(raw), "accepted_rows": len(cleaned),
             "invalid_rows": invalid_count, "duplicate_rows": duplicate_count}
    return cleaned, audit


def load_database(csv_path: Path, db_path: Path) -> dict[str, int]:
    clean, audit = clean_sales(csv_path)
    if clean.empty:
        raise ValueError("No valid sales rows found; database was not changed")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
        # Rebuild atomically; all dimension keys are defined by the generator.
        connection.execute("DELETE FROM sales")
        connection.execute("DELETE FROM reps")
        connection.execute("DELETE FROM products")
        connection.execute("DELETE FROM regions")
        connection.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", PRODUCTS)
        connection.executemany("INSERT INTO regions VALUES (?, ?)", REGIONS)
        connection.executemany("INSERT INTO reps VALUES (?, ?, ?)", REPS)
        records = list(clean[COLUMNS + ["revenue_paise"]].itertuples(index=False, name=None))
        connection.executemany("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", records)
    return audit
