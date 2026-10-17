import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import src.etl as etl

WORKBOOK = "01_LedgerForge_Python_Master_Dataset.xlsx"


@pytest.fixture
def run_pipeline(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    clean_dir = tmp_path / "clean"
    rejected_dir = tmp_path / "rejected"
    logs_dir = tmp_path / "logs"
    for folder in (data_dir, clean_dir, rejected_dir, logs_dir):
        folder.mkdir()

    monkeypatch.setattr(etl, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(etl, "CLEAN_DIR", str(clean_dir))
    monkeypatch.setattr(etl, "REJECTED_DIR", str(rejected_dir))
    monkeypatch.setattr(etl, "LOGS_DIR", str(logs_dir))

    def _run(rows):
        pd.DataFrame(rows).to_excel(
            data_dir / WORKBOOK, sheet_name="employees", index=False
        )
        etl.run_etl()
        clean = pd.read_csv(clean_dir / "employees_clean.csv")
        rejected = pd.read_csv(rejected_dir / "employees_rejected.csv")
        return clean, rejected, logs_dir / "etl_run.log"

    return _run


def test_joining_after_leaving_is_rejected(run_pipeline):
    clean, rejected, _ = run_pipeline([
        {"employee_id": "EMP-1", "hire_date": "2024-01-10", "exit_date": None},
        {"employee_id": "EMP-2", "hire_date": "2025-06-01", "exit_date": "2025-01-01"},
    ])
    assert list(clean["employee_id"]) == ["EMP-1"]
    assert list(rejected["employee_id"]) == ["EMP-2"]
    assert rejected["rejection_reason"].iloc[0] == "dates out of order"


def test_duplicate_employee_ids_are_kept_once(run_pipeline):
    clean, _, _ = run_pipeline([
        {"employee_id": "EMP-1", "hire_date": "2024-01-10", "exit_date": None},
        {"employee_id": "EMP-1", "hire_date": "2024-01-10", "exit_date": None},
    ])
    assert len(clean) == 1


def test_active_employee_tenure_uses_reference_date(run_pipeline):
    clean, _, _ = run_pipeline([
        {"employee_id": "EMP-1", "hire_date": "2026-01-01", "exit_date": None},
    ])
    assert clean["tenure_days"].iloc[0] == 272  # 1 Jan 2026 to 30 Sep 2026


def test_running_twice_gives_same_counts(run_pipeline):
    rows = [
        {"employee_id": "EMP-1", "hire_date": "2024-01-10", "exit_date": None},
        {"employee_id": "EMP-2", "hire_date": "2025-06-01", "exit_date": "2025-01-01"},
    ]
    first_clean, first_rejected, _ = run_pipeline(rows)
    second_clean, second_rejected, _ = run_pipeline(rows)
    assert len(first_clean) == len(second_clean) == 1
    assert len(first_rejected) == len(second_rejected) == 1


def test_run_log_is_written(run_pipeline):
    _, _, log_path = run_pipeline([
        {"employee_id": "EMP-1", "hire_date": "2024-01-10", "exit_date": None},
    ])
    text = log_path.read_text()
    assert "Rows In (Employees): 1" in text
    assert "Rows Rejected: 0" in text