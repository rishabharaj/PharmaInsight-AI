"""Parameterized SQL powers every dashboard measure and ranking."""

from datetime import date
from pathlib import Path
import sqlite3

import pandas as pd

from .database import connect


def filter_options(db_path: Path) -> dict:
    with connect(db_path) as connection:
        products = pd.read_sql_query("SELECT product_id, product_name FROM products ORDER BY product_name", connection)
        regions = pd.read_sql_query("SELECT region_id, region_name FROM regions ORDER BY region_name", connection)
        bounds = connection.execute("SELECT MIN(sales_date), MAX(sales_date) FROM sales").fetchone()
    if not bounds or bounds[0] is None:
        raise ValueError("The sales database is empty. Run python -m pharma_insight.setup.")
    return {"products": products, "regions": regions,
            "min_date": date.fromisoformat(bounds[0]), "max_date": date.fromisoformat(bounds[1])}


def _where(start: date, end: date, region_ids: list[int], product_ids: list[int]) -> tuple[str, list]:
    if start > end:
        raise ValueError("Start date must be on or before end date")
    clauses = ["s.sales_date BETWEEN ? AND ?"]
    params: list = [start.isoformat(), end.isoformat()]
    if region_ids:
        clauses.append(f"s.region_id IN ({','.join('?' for _ in region_ids)})")
        params.extend(region_ids)
    if product_ids:
        clauses.append(f"s.product_id IN ({','.join('?' for _ in product_ids)})")
        params.extend(product_ids)
    return " WHERE " + " AND ".join(clauses), params


def _read(connection: sqlite3.Connection, sql: str, params: list) -> pd.DataFrame:
    return pd.read_sql_query(sql, connection, params=params)


def query_dashboard(db_path: Path, start: date, end: date,
                    region_ids: list[int] | None = None,
                    product_ids: list[int] | None = None) -> dict[str, pd.DataFrame]:
    """Return SQL backed KPIs and five breakdowns using the same filters."""
    where, params = _where(start, end, region_ids or [], product_ids or [])
    with connect(db_path) as connection:
        result = {
            "kpis": _read(connection, f"""
                SELECT COUNT(*) AS transactions, COALESCE(SUM(s.units), 0) AS units,
                       COALESCE(SUM(s.revenue_paise), 0) / 100.0 AS revenue_inr
                FROM sales s {where}
            """, params),
            "monthly": _read(connection, f"""
                SELECT substr(s.sales_date, 1, 7) AS month,
                       SUM(s.revenue_paise) / 100.0 AS revenue_inr, SUM(s.units) AS units
                FROM sales s {where}
                GROUP BY substr(s.sales_date, 1, 7) ORDER BY month
            """, params),
            "products": _read(connection, f"""
                SELECT p.product_name, p.therapy_area, SUM(s.revenue_paise) / 100.0 AS revenue_inr,
                       SUM(s.units) AS units, COUNT(*) AS transactions
                FROM sales s JOIN products p ON p.product_id = s.product_id {where}
                GROUP BY p.product_id, p.product_name, p.therapy_area
                ORDER BY revenue_inr DESC, p.product_name
            """, params),
            "regions": _read(connection, f"""
                SELECT r.region_name, SUM(s.revenue_paise) / 100.0 AS revenue_inr,
                       SUM(s.units) AS units, COUNT(*) AS transactions
                FROM sales s JOIN regions r ON r.region_id = s.region_id {where}
                GROUP BY r.region_id, r.region_name
                ORDER BY revenue_inr DESC, r.region_name
            """, params),
            "reps": _read(connection, f"""
                WITH rep_totals AS (
                    SELECT rep.rep_name, r.region_name,
                           SUM(s.revenue_paise) / 100.0 AS revenue_inr,
                           SUM(s.units) AS units, COUNT(*) AS transactions
                    FROM sales s JOIN reps rep ON rep.rep_id = s.rep_id
                    JOIN regions r ON r.region_id = s.region_id {where}
                    GROUP BY rep.rep_id, rep.rep_name, r.region_name
                )
                SELECT ROW_NUMBER() OVER (ORDER BY revenue_inr DESC, rep_name) AS rank,
                       rep_name, region_name, revenue_inr, units, transactions
                FROM rep_totals ORDER BY rank
            """, params),
        }
    return result


def verified_facts(data: dict[str, pd.DataFrame]) -> dict:
    """Turn SQL results into a compact, auditable fact set for the insight layer."""
    kpi = data["kpis"].iloc[0]
    facts = {"revenue_inr": round(float(kpi["revenue_inr"]), 2),
             "units": int(kpi["units"]), "transactions": int(kpi["transactions"])}
    if facts["transactions"] == 0:
        return facts
    regions = data["regions"]
    products = data["products"]
    facts["regions_in_scope"] = len(regions)
    facts["strongest_region"] = str(regions.iloc[0]["region_name"])
    facts["strongest_region_revenue_inr"] = round(float(regions.iloc[0]["revenue_inr"]), 2)
    facts["weakest_region"] = str(regions.iloc[-1]["region_name"])
    facts["weakest_region_revenue_inr"] = round(float(regions.iloc[-1]["revenue_inr"]), 2)
    facts["top_product"] = str(products.iloc[0]["product_name"])
    facts["top_product_revenue_inr"] = round(float(products.iloc[0]["revenue_inr"]), 2)
    monthly = data["monthly"]
    if len(monthly) >= 2:
        latest = monthly.iloc[-1]
        previous = monthly.iloc[-2]
        facts["latest_month"] = str(latest["month"])
        facts["previous_month"] = str(previous["month"])
        facts["latest_month_revenue_inr"] = round(float(latest["revenue_inr"]), 2)
        facts["previous_month_revenue_inr"] = round(float(previous["revenue_inr"]), 2)
        if float(previous["revenue_inr"]) > 0:
            facts["month_change_pct"] = round(
                (float(latest["revenue_inr"]) / float(previous["revenue_inr"]) - 1) * 100, 1)
    return facts
