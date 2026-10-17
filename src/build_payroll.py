import os

import pandas as pd
from sqlalchemy import create_engine

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://wos:wos@localhost:5433/pulseiq_wh")
CLEAN = os.getenv("CLEAN_DIR", "clean")


def build():
    items = pd.read_csv(f"{CLEAN}/payroll_items_clean.csv")

    # Grain: one row per employee per payroll run (one run per month)
    fact = items[[
        "run_id", "employee_id", "department_id", "role_id", "year", "month",
        "gross_pay", "overtime_pay", "net_pay", "employer_cost",
    ]].copy()
    fact = fact.drop_duplicates(subset=["run_id", "employee_id"], keep="last")

    engine = create_engine(DB_URL)
    fact.to_sql("fact_payroll", engine, schema="dw", if_exists="replace", index=False)

    print(f"fact_payroll rows: {len(fact)}")
    print(f"Employees paid in PR-2026-09: {fact[fact['run_id'] == 'PR-2026-09']['employee_id'].nunique()}")


if __name__ == "__main__":
    build()