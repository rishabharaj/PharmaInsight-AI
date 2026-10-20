"""Create repeatable, clearly fictional transaction data; no external dataset is used."""

import csv
import random
from datetime import date, timedelta
from pathlib import Path


PRODUCTS = [
    (1, "Cardivexa", "Cardiovascular", 780),
    (2, "Glycora", "Diabetes", 620),
    (3, "Respivon", "Respiratory", 540),
    (4, "Dermalyn", "Dermatology", 410),
    (5, "Neurovia", "Neurology", 980),
    (6, "Immunara", "Immunology", 1250),
]
REGIONS = [(1, "North"), (2, "South"), (3, "East"), (4, "West"), (5, "Central")]
REPS = [
    (1, "Aditi Mehra", 1), (2, "Karan Sethi", 1), (3, "Meera Kapoor", 1),
    (4, "Ananya Rao", 2), (5, "Vikram Nair", 2), (6, "Priya Iyer", 2),
    (7, "Riya Das", 3), (8, "Arjun Sen", 3), (9, "Neha Bose", 3),
    (10, "Ishita Shah", 4), (11, "Rahul Desai", 4), (12, "Dev Patel", 4),
    (13, "Simran Jain", 5), (14, "Aman Verma", 5), (15, "Nisha Singh", 5),
]
COLUMNS = ["sale_id", "sales_date", "product_id", "region_id", "rep_id", "units", "unit_price_inr", "discount_pct"]


def generate_csv(path: Path, count: int = 2400, seed: int = 42) -> Path:
    """Generate synthetic Indian pharma sales plus three intentional quality issues."""
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    start = date(2024, 1, 1)
    rows = []
    for number in range(1, count + 1):
        day = start + timedelta(days=rng.randrange(731))
        region_id = rng.choices([1, 2, 3, 4, 5], weights=[24, 24, 14, 23, 15])[0]
        product_id = rng.choices([1, 2, 3, 4, 5, 6], weights=[24, 22, 19, 16, 12, 7])[0]
        product = PRODUCTS[product_id - 1]
        rep_id = rng.choice([rep[0] for rep in REPS if rep[2] == region_id])
        growth = 1.13 if day.year == 2025 else 1.0
        region_factor = {1: 1.1, 2: 1.18, 3: 0.72, 4: 1.08, 5: 0.9}[region_id]
        winter_factor = 1.35 if product_id == 3 and day.month in (11, 12, 1, 2) else 1.0
        units = max(1, round(rng.randint(12, 90) * growth * region_factor * winter_factor))
        rows.append([f"T{number:06d}", day.isoformat(), product_id, region_id, rep_id,
                     units, product[3], rng.choice([0, 0, 3, 5, 10])])

    # These records make the ETL validation visible and testable.
    rows.append(rows[0].copy())
    rows.append([f"T{count+1:06d}", "2025-06-10", 1, 1, 1, "", 780, 0])
    rows.append([f"T{count+2:06d}", "2025-06-10", 999, 1, 1, 20, 780, 0])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return path
