"""Generate deterministic synthetic bank CSVs for demo purposes.

Usage:
    python3 scripts/generate_sample_data.py

Writes sample_data/chase_sample.csv and sample_data/amex_sample.csv with
~205 transactions each, spread over the six months ending today, so the
demo looks fresh whenever it is regenerated.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sample_data"
ROWS_PER_FILE = 205

CHASE_HEADER = "Transaction Date,Post Date,Description,Category,Type,Amount"
AMEX_HEADER = "Date,Description,Amount"

EXPENSES = [
    ("STARBUCKS", 4.50, 9.50),
    ("CHIPOTLE", 8.25, 14.75),
    ("SQ *TACO TRUCK", 9.00, 16.00),
    ("DOORDASH", 15.00, 38.00),
    ("UBER EATS", 12.00, 31.00),
    ("NEIGHBORHOOD DINER", 18.00, 44.00),
    ("WHOLE FOODS", 22.00, 95.00),
    ("TRADER JOE'S", 18.00, 72.00),
    ("SAFEWAY", 25.00, 110.00),
    ("KROGER", 20.00, 88.00),
    ("SHELL OIL", 28.00, 65.00),
    ("CHEVRON", 30.00, 70.00),
    ("UBER", 7.50, 28.00),
    ("LYFT", 8.00, 26.00),
    ("NETFLIX", 15.99, 15.99),
    ("SPOTIFY", 11.99, 11.99),
    ("AMC THEATRES", 14.50, 32.00),
    ("STEAM GAMES", 9.99, 59.99),
    ("AMAZON", 8.00, 140.00),
    ("TST*AMAZON PRIME", 14.99, 14.99),
    ("TARGET", 15.00, 95.00),
    ("BEST BUY", 25.00, 220.00),
    ("IKEA", 30.00, 180.00),
    ("WALMART #2541", 30.00, 130.00),
    ("SQ *ETSY SELLER", 12.00, 60.00),
    ("CVS PHARMACY", 6.00, 40.00),
    ("WALGREENS", 7.00, 45.00),
    ("COMCAST", 79.99, 79.99),
    ("CITY WATER & SEWER", 42.00, 88.00),
    ("POWER & LIGHT CO", 65.00, 140.00),
    ("OAKWOOD APARTMENTS", 1450.00, 1450.00),
    ("DELTA AIR LINES", 180.00, 420.00),
    ("HILTON HOTEL", 90.00, 260.00),
    ("AIRBNB", 70.00, 240.00),
    ("MONTHLY SERVICE FEE", 12.00, 12.00),
    ("ATM WITHDRAWAL FEE", 3.00, 3.00),
    ("ZELLE TO ALEX", 20.00, 200.00),
    ("VENMO PAYMENT", 10.00, 120.00),
    ("PAYPAL *SPOTIFY CA", 11.99, 11.99),
    ("SUNOCO GAS STATION", 25.00, 60.00),
]

INCOME = [
    ("PAYROLL ACME CORP", 2250.00, 2250.00),
    ("DIRECT DEPOSIT PAYROLL", 2100.00, 2100.00),
    ("SIDE HUSTLE PAYOUT", 95.00, 320.00),
]


def _amount(value: tuple[str, float, float], month_index: int, rng: random.Random) -> str:
    amount = round(rng.uniform(value[1], value[2]), 2)
    if month_index % 11 == 0:
        return f"USD {amount:,.2f}"
    if month_index % 13 == 0:
        return f"({amount:,.2f})"
    return f"{amount:.2f}"


def _pick_date(rng: random.Random, day_offset: int) -> date:
    return date.today() - timedelta(days=day_offset)


def generate_chase(rows: int) -> list[str]:
    rng = random.Random(42)
    lines = [CHASE_HEADER]
    for index in range(rows):
        month_index = index // 36
        day_offset = rng.randint(0, 180)
        posted = _pick_date(rng, day_offset)
        post_date = posted + timedelta(days=rng.choice([0, 1]))
        if month_index % 4 == 0 and index % 30 == 0:
            merchant, value, _top = rng.choice(INCOME)
            amount = f"{rng.uniform(value, _top):.2f}"
            category, tx_type = "Paycheck", "Credit"
        else:
            merchant, value, _top = rng.choice(EXPENSES)
            amount = _amount((merchant, value, _top), index, rng)
            amount = f"-{amount}" if not amount.startswith("(") else amount
            category, tx_type = "Purchase", "Debit"
        if index % 17 == 0:
            merchant += " 543217"
        lines.append(
            f"{posted.strftime('%m/%d/%Y')},{post_date.strftime('%m/%d/%Y')},{merchant},{category},{tx_type},{amount}"
        )
    return lines


def generate_amex(rows: int) -> list[str]:
    rng = random.Random(1337)
    lines = [AMEX_HEADER]
    for index in range(rows):
        month_index = index // 36
        day_offset = rng.randint(0, 180)
        posted = _pick_date(rng, day_offset)
        merchant, value, _top = rng.choice(EXPENSES)
        magnitude = _amount((merchant, value, _top), index, rng)
        if magnitude.startswith("("):
            amount = magnitude
        elif magnitude.startswith("USD"):
            amount = f"USD -{magnitude[4:]}"
        else:
            amount = f"-{magnitude}"
        if index % 9 == 0:
            merchant = f"{merchant} NY"
        lines.append(f"{posted.strftime('%m/%d/%Y')},{merchant},{amount}")
    return lines


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chase_path = OUTPUT_DIR / "chase_sample.csv"
    amex_path = OUTPUT_DIR / "amex_sample.csv"
    chase_path.write_text("\n".join(generate_chase(ROWS_PER_FILE)) + "\n", encoding="utf-8")
    amex_path.write_text("\n".join(generate_amex(ROWS_PER_FILE)) + "\n", encoding="utf-8")
    print(f"wrote {chase_path} ({ROWS_PER_FILE} rows)")
    print(f"wrote {amex_path} ({ROWS_PER_FILE} rows)")


if __name__ == "__main__":
    main()
