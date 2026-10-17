"""PulseIQ ETL pipeline (Task 1).

Extract -> Transform -> Validate -> Load (clean CSV files).

Rules:
- Structural problems (missing sheet or column) stop the run with a clear error.
- Bad rows never stop the run: they are written to rejected/<table>_rejected.csv
  with a rejection_reason column and counted in the run log.
- Same input always gives the same output; running twice does no harm
  (clean and rejected files are overwritten, the log gets a new entry).
- Exit code is 1 if any table rejects more than MAX_REJECT_PCT percent of rows,
  so a bad load fails loudly.
"""
import os
import sys
from datetime import datetime

import pandas as pd

try:
    import pandera.pandas as pa
except ImportError:  # older pandera versions
    import pandera as pa

DATA_DIR = os.getenv("DATA_DIR", "./data")
CLEAN_DIR = os.getenv("CLEAN_DIR", "./clean")
REJECTED_DIR = os.getenv("REJECTED_DIR", "./rejected")
LOGS_DIR = os.getenv("LOGS_DIR", "./logs")
SOURCE_FILE = os.getenv("SOURCE_FILE", "01_LedgerForge_Python_Master_Dataset.xlsx")
DEMO_TODAY = pd.Timestamp(os.getenv("DEMO_TODAY", "2026-09-30"))
MAX_REJECT_PCT = float(os.getenv("MAX_REJECT_PCT", "5"))


# ---------------------------------------------------------------- helpers
def to_dt(df, cols):
    for c in cols:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def to_num(df, cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def strip_strings(df):
    for c in df.columns:
        if pd.api.types.is_object_dtype(df[c]) or pd.api.types.is_string_dtype(df[c]):
            df[c] = df[c].apply(lambda v: v.strip() if isinstance(v, str) else v)
    return df


def title_case(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = df[c].apply(lambda v: v.title() if isinstance(v, str) else v)
    return df


def split_duplicates(df, subset, reason):
    """Keep the first copy, return (kept, duplicates_with_reason)."""
    mask = df.duplicated(subset=subset, keep="first")
    dups = df[mask].copy()
    dups["rejection_reason"] = reason
    return df[~mask].copy(), dups


def in_set(values, name):
    return pa.Check(lambda s: s.isin(values), name=name)


def dates_in_order(start_col, end_col):
    return pa.Check(
        lambda d: d[end_col].isna() | (d[start_col] <= d[end_col]),
        name="dates out of order",
    )


def non_negative():
    return pa.Check.ge(0, name="negative value")


def validate_rows(df, schema, table):
    """Return (clean_df, rejected_df). Structural errors raise."""
    df = df.reset_index(drop=True)
    empty_rej = df.iloc[0:0].copy()
    empty_rej["rejection_reason"] = pd.Series(dtype=str)
    try:
        schema.validate(df, lazy=True)
        return df, empty_rej
    except pa.errors.SchemaErrors as exc:
        fc = exc.failure_cases
        structural = fc[fc["index"].isna()]
        if len(structural):
            raise RuntimeError(
                f"[{table}] structural validation failure:\n{structural.to_string()}"
            ) from exc
        fc = fc.copy()
        fc["reason"] = fc.apply(
            lambda r: f"{r['column']}: {r['check']}" if isinstance(r["column"], str) else str(r["check"]),
            axis=1,
        )
        reasons = fc.groupby("index")["reason"].agg(lambda x: "; ".join(sorted(set(x))))
        bad_idx = reasons.index.astype(int)
        rejected = df.loc[bad_idx].copy()
        rejected["rejection_reason"] = reasons.values
        clean = df.drop(index=bad_idx)
        return clean, rejected


def require_columns(df, cols, table):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise RuntimeError(f"[{table}] missing columns in source: {missing}")


# ------------------------------------------------------------ table specs
def prep_employees(df):
    df = strip_strings(df)
    df = to_dt(df, ["date_of_birth", "hire_date", "exit_date", "resignation_date"])
    df = title_case(df, ["first_name", "last_name", "full_name"])
    if "work_email" in df.columns:
        df["work_email"] = df["work_email"].apply(lambda v: v.lower() if isinstance(v, str) else v)
    return df


def schema_employees(ctx):
    return pa.DataFrameSchema(
        {
            "employee_id": pa.Column(nullable=False),
            "hire_date": pa.Column(nullable=False),
        },
        checks=[dates_in_order("hire_date", "exit_date")],
    )


def finish_employees(df):
    df["tenure_days"] = (df["exit_date"].fillna(DEMO_TODAY) - df["hire_date"]).dt.days
    df["join_year"] = df["hire_date"].dt.year
    df["join_month"] = df["hire_date"].dt.month
    return df


def prep_assignments(df):
    df = strip_strings(df)
    return to_dt(df, ["effective_from", "effective_to"])


def schema_assignments(ctx):
    return pa.DataFrameSchema(
        {
            "assignment_id": pa.Column(nullable=False),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "effective_from": pa.Column(nullable=False),
        },
        checks=[dates_in_order("effective_from", "effective_to")],
    )


def prep_salary_structures(df):
    df = strip_strings(df)
    df = to_dt(df, ["effective_from", "effective_to"])
    return to_num(df, ["monthly_amount"])


def schema_salary_structures(ctx):
    return pa.DataFrameSchema(
        {
            "structure_id": pa.Column(nullable=False),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "monthly_amount": pa.Column(nullable=False, checks=non_negative()),
            "effective_from": pa.Column(nullable=False),
        },
        checks=[dates_in_order("effective_from", "effective_to")],
    )


def prep_salary_revisions(df):
    df = strip_strings(df)
    df = to_dt(df, ["effective_from", "created_at"])
    return to_num(df, ["previous_annual_fixed", "new_annual_fixed", "pct_change"])


def schema_salary_revisions(ctx):
    return pa.DataFrameSchema(
        {
            "revision_id": pa.Column(nullable=False),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "new_annual_fixed": pa.Column(nullable=False, checks=non_negative()),
            "previous_annual_fixed": pa.Column(nullable=True, checks=non_negative()),
            "effective_from": pa.Column(nullable=False),
        }
    )


def prep_attendance(df):
    df = strip_strings(df)
    df = to_dt(df, ["attendance_date"])
    return to_num(df, ["hours_worked", "overtime_hours"])


def schema_attendance(ctx):
    return pa.DataFrameSchema(
        {
            "attendance_id": pa.Column(nullable=False),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "attendance_date": pa.Column(nullable=False),
            "hours_worked": pa.Column(nullable=True, checks=non_negative()),
            "overtime_hours": pa.Column(nullable=True, checks=non_negative()),
        }
    )


def finish_attendance(df):
    df["year"] = df["attendance_date"].dt.year
    df["month"] = df["attendance_date"].dt.month
    return df


def prep_leave(df):
    df = strip_strings(df)
    df = to_dt(df, ["start_date", "end_date", "applied_on", "decided_on"])
    return to_num(df, ["days"])


def schema_leave(ctx):
    return pa.DataFrameSchema(
        {
            "leave_request_id": pa.Column(nullable=False),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "start_date": pa.Column(nullable=False),
            "end_date": pa.Column(nullable=False),
            "days": pa.Column(nullable=False, checks=non_negative()),
        },
        checks=[dates_in_order("start_date", "end_date")],
    )


def finish_leave(df):
    df["year"] = df["start_date"].dt.year
    df["month"] = df["start_date"].dt.month
    return df


def prep_runs(df):
    df = strip_strings(df)
    df = to_dt(df, ["period_start", "period_end", "pay_date", "created_at", "approved_at"])
    return to_num(
        df,
        ["employees_paid", "total_gross", "total_deductions", "total_net",
         "total_employer_contributions", "total_employer_cost"],
    )


def schema_runs(ctx):
    return pa.DataFrameSchema(
        {
            "run_id": pa.Column(nullable=False),
            "period_start": pa.Column(nullable=False),
            "period_end": pa.Column(nullable=False),
            "total_gross": pa.Column(nullable=False, checks=non_negative()),
            "total_net": pa.Column(nullable=False, checks=non_negative()),
            "total_employer_cost": pa.Column(nullable=False, checks=non_negative()),
        },
        checks=[dates_in_order("period_start", "period_end")],
    )


def finish_runs(df):
    df["year"] = df["period_start"].dt.year
    df["month"] = df["period_start"].dt.month
    return df


PAY_NUM = [
    "calendar_days", "days_employed", "lop_days", "payable_days", "monthly_fixed_gross",
    "basic", "hra", "conveyance", "medical", "special_allowance", "earned_fixed_pay",
    "overtime_hours_paid", "overtime_pay", "variable_pay", "gross_pay", "pf_employee",
    "esi_employee", "professional_tax", "tds", "other_deductions", "total_deductions",
    "net_pay", "pf_employer", "esi_employer", "employer_cost",
]


def prep_items(df):
    df = strip_strings(df)
    df = to_dt(df, ["period_start", "period_end"])
    return to_num(df, PAY_NUM)


def schema_items(ctx):
    return pa.DataFrameSchema(
        {
            "payroll_item_id": pa.Column(nullable=False),
            "run_id": pa.Column(nullable=False, checks=in_set(ctx["run_ids"], "run_id not in payroll_runs")),
            "employee_id": pa.Column(nullable=False, checks=in_set(ctx["emp_ids"], "employee_id not in employees")),
            "period_start": pa.Column(nullable=False),
            "gross_pay": pa.Column(nullable=False, checks=non_negative()),
            "net_pay": pa.Column(nullable=False, checks=non_negative()),
            "employer_cost": pa.Column(nullable=False, checks=non_negative()),
            "overtime_pay": pa.Column(nullable=True, checks=non_negative()),
            "lop_days": pa.Column(nullable=True, checks=non_negative()),
        },
        checks=[dates_in_order("period_start", "period_end")],
    )


def finish_items(df):
    df["year"] = df["period_start"].dt.year
    df["month"] = df["period_start"].dt.month
    return df


# name, sheet, output name, prep, schema, finish, duplicate key
# Order matters: employees first, payroll_runs before payroll_items.
TABLES = [
    ("employees", "employees", "employees", prep_employees, schema_employees, finish_employees, ["employee_id"]),
    ("employee_assignments", "employee_assignments", "employee_assignments", prep_assignments, schema_assignments, None, ["assignment_id"]),
    ("salary_structures", "salary_structures", "salary_structures", prep_salary_structures, schema_salary_structures, None, ["structure_id"]),
    ("salary_revisions", "salary_revisions", "salary_revisions", prep_salary_revisions, schema_salary_revisions, None, ["revision_id"]),
    ("attendance", "attendance", "attendance", prep_attendance, schema_attendance, finish_attendance, ["attendance_id"]),
    ("leave_requests", "leave_requests", "leave_requests", prep_leave, schema_leave, finish_leave, ["leave_request_id"]),
    ("payroll_runs", "payroll_runs", "payroll_runs", prep_runs, schema_runs, finish_runs, ["run_id"]),
    ("payroll_items", "payroll_items", "payroll_items", prep_items, schema_items, finish_items, ["payroll_item_id"]),
]


# ------------------------------------------------------------------- main
def run_etl():
    start_time = datetime.now()
    log = [f"ETL run started: {start_time}"]
    print("--- Starting PulseIQ ETL Pipeline ---")

    for d in (CLEAN_DIR, REJECTED_DIR, LOGS_DIR):
        os.makedirs(d, exist_ok=True)

    path = os.path.join(DATA_DIR, SOURCE_FILE)
    try:
        xls = pd.ExcelFile(path)
    except Exception as e:
        print(f"Error reading source file {path}: {e}")
        sys.exit(2)

    ctx = {}
    summary_rows = []

    for name, sheet, out_name, prep, schema_fn, finish, dup_key in TABLES:
        if sheet not in xls.sheet_names:
            raise RuntimeError(f"[{name}] sheet '{sheet}' not found in workbook")
        df_raw = xls.parse(sheet)
        rows_in = len(df_raw)
        log.append(f"Extracted '{name}': {rows_in} rows")
        print(f"Extracted '{name}': {rows_in} rows")

        df = prep(df_raw.copy())
        df, dups = split_duplicates(df, dup_key, f"duplicate {dup_key[0]}")
        schema = schema_fn(ctx)
        require_columns(df, list(schema.columns.keys()), name)
        df, bad = validate_rows(df, schema, name)
        if finish is not None:
            df = finish(df)

        rejected = pd.concat([bad, dups], ignore_index=True)

        # Publish ids that later tables must point to.
        if name == "employees":
            ctx["emp_ids"] = set(df["employee_id"])
        if name == "payroll_runs":
            ctx["run_ids"] = set(df["run_id"])

        df.to_csv(os.path.join(CLEAN_DIR, f"{out_name}_clean.csv"), index=False)
        rejected.to_csv(os.path.join(REJECTED_DIR, f"{out_name}_rejected.csv"), index=False)

        pct = 100.0 * len(rejected) / rows_in if rows_in else 0.0
        summary_rows.append((name, rows_in, len(df), len(rejected), pct))
        line = f"'{name}': in={rows_in} out={len(df)} rejected={len(rejected)} ({pct:.2f}%)"
        log.append(line)
        print(line)
        if len(rejected):
            top = rejected["rejection_reason"].value_counts().head(5)
            for reason, n in top.items():
                log.append(f"    {n} x {reason}")

    end_time = datetime.now()
    failed = [r for r in summary_rows if r[4] > MAX_REJECT_PCT]
    log.append(f"ETL run finished: {end_time}")
    if failed:
        msg = "; ".join(f"{r[0]} rejected {r[4]:.2f}%" for r in failed)
        log.append(f"FAILED: more than {MAX_REJECT_PCT}% rejected -> {msg}")
        print(f"FAILED: more than {MAX_REJECT_PCT}% rejected -> {msg}")
    else:
        log.append("Status: OK")
        print("--- ETL Completed Successfully ---")

    with open(os.path.join(LOGS_DIR, "etl_run.log"), "a") as f:
        f.write("\n".join(log) + "\n\n")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run_etl()