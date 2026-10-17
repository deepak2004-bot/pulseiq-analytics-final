import os

import pandas as pd
from sqlalchemy import create_engine, text

# Port 5433 is the host port we set in docker-compose.override.yml
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://wos:wos@localhost:5433/pulseiq_wh")
WORKBOOK = os.getenv("WORKBOOK_PATH", "data/01_LedgerForge_Python_Master_Dataset.xlsx")

COLUMNS = [
    "assignment_id", "employee_id", "department_id", "role_id",
    "job_level", "manager_id", "change_reason",
    "valid_from", "valid_to", "is_current",
]

UPSERT_SQL = text("""
    INSERT INTO dw.dim_employee (
        assignment_id, employee_id, department_id, role_id, job_level,
        manager_id, change_reason, valid_from, valid_to, is_current
    )
    VALUES (
        :assignment_id, :employee_id, :department_id, :role_id, :job_level,
        :manager_id, :change_reason, :valid_from, :valid_to, :is_current
    )
    ON CONFLICT (assignment_id) DO UPDATE SET
        employee_id   = EXCLUDED.employee_id,
        department_id = EXCLUDED.department_id,
        role_id       = EXCLUDED.role_id,
        job_level     = EXCLUDED.job_level,
        manager_id    = EXCLUDED.manager_id,
        change_reason = EXCLUDED.change_reason,
        valid_from    = EXCLUDED.valid_from,
        valid_to      = EXCLUDED.valid_to,
        is_current    = EXCLUDED.is_current
""")


def load():
    df = pd.read_excel(WORKBOOK, sheet_name="employee_assignments")

    df["valid_from"] = pd.to_datetime(df["effective_from"], errors="coerce").dt.date
    df["valid_to"] = pd.to_datetime(df["effective_to"], errors="coerce").dt.date
    df["is_current"] = df["valid_to"].isna()

    # A row without a start date cannot be placed in history, so skip it
    bad = df["valid_from"].isna()
    print(f"Rows in: {len(df)}, rows without a start date (skipped): {bad.sum()}")
    df = df[~bad][COLUMNS]

    # Convert pandas missing values to None so PostgreSQL stores NULL
    records = df.astype(object).where(pd.notna(df), None).to_dict(orient="records")

    engine = create_engine(DB_URL)
    with engine.begin() as conn:
        conn.execute(UPSERT_SQL, records)

    print(f"Upserted rows: {len(records)}")


if __name__ == "__main__":
    load()