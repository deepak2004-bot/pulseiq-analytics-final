import os

import pandas as pd
from sqlalchemy import create_engine

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://wos:wos@localhost:5433/pulseiq_wh")
CLEAN = os.getenv("CLEAN_DIR", "clean")


def build():
    att = pd.read_csv(f"{CLEAN}/attendance_clean.csv", parse_dates=["attendance_date"])

    att["present"] = att["status"].isin(["Present", "WFH"])
    att["late"] = att["late_flag"].eq("Y")
    att["leave"] = att["status"].eq("Leave") | att["leave_type_code"].notna()

    fact = (
        att.groupby(["year", "month", "department_id"])
        .agg(
            working_days=("attendance_id", "count"),
            present_days=("present", "sum"),
            leave_days=("leave", "sum"),
            late_days=("late", "sum"),
            overtime_hours=("overtime_hours", "sum"),
        )
        .reset_index()
    )
    fact["attendance_rate_pct"] = (100 * fact["present_days"] / fact["working_days"]).round(1)

    engine = create_engine(DB_URL)
    fact.to_sql("fact_attendance_monthly", engine, schema="dw", if_exists="replace", index=False)

    print(f"fact_attendance_monthly rows: {len(fact)}")
    print(f"Attendance rate, all months: {100 * att['present'].mean():.1f}%")
    print(f"Late arrivals: {int(att['late'].sum())}")


if __name__ == "__main__":
    build()