import os

import pandas as pd
from sqlalchemy import create_engine

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://wos:wos@localhost:5433/pulseiq_wh")
CLEAN = os.getenv("CLEAN_DIR", "clean")
END = pd.Timestamp("2026-09-30")  # DEMO_TODAY


def build():
    emp = pd.read_csv(f"{CLEAN}/employees_clean.csv", parse_dates=["hire_date", "exit_date"])
    asg = pd.read_csv(
        f"{CLEAN}/employee_assignments_clean.csv",
        parse_dates=["effective_from", "effective_to"],
    )

    # One row per employee per month end
    months = pd.DataFrame({"month_end": pd.date_range("2012-01-31", END, freq="ME")})
    emp = emp[["employee_id", "hire_date", "exit_date"]].assign(k=1)
    grid = emp.merge(months.assign(k=1), on="k").drop(columns="k")

    # Active on month end: hired by then and not yet exited
    active = grid[
        (grid["hire_date"] <= grid["month_end"])
        & (grid["exit_date"].isna() | (grid["exit_date"] > grid["month_end"]))
    ]

    # Department on month end, from the assignment that covers that date
    m = active.merge(asg[["employee_id", "effective_from", "effective_to", "department_id"]],
                     on="employee_id", how="left")
    covers = m["effective_from"].le(m["month_end"]) & (
        m["effective_to"].isna() | m["effective_to"].ge(m["month_end"])
    )
    m = m[covers | m["department_id"].isna()]
    m = m.drop_duplicates(subset=["employee_id", "month_end"], keep="last")
    m["department_id"] = m["department_id"].fillna("UNKNOWN")

    fact = (
        m.groupby(["month_end", "department_id"])
        .size()
        .reset_index(name="headcount")
    )
    fact["month_end"] = fact["month_end"].dt.date

    dim = (
        asg[["department_id"]].drop_duplicates().sort_values("department_id")
        .reset_index(drop=True)
    )
    dim["department_name"] = dim["department_id"]  # replace with real names later

    engine = create_engine(DB_URL)
    dim.to_sql("dim_department", engine, schema="dw", if_exists="replace", index=False)
    fact.to_sql("fact_headcount_monthly", engine, schema="dw", if_exists="replace", index=False)

    print(f"dim_department rows: {len(dim)}")
    print(f"fact_headcount_monthly rows: {len(fact)}")
    latest = fact[fact["month_end"] == END.date()]
    print(f"Headcount at 30 Sep 2026: {latest['headcount'].sum()}")


if __name__ == "__main__":
    build()