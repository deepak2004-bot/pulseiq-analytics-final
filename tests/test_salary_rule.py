import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.validate_salary import check_negative_amounts


def test_negative_salary_is_rejected():
    df = pd.DataFrame({"structure_id": ["A", "B"], "monthly_amount": [8016, -500]})
    good, bad = check_negative_amounts(df)
    assert list(good["structure_id"]) == ["A"]
    assert list(bad["structure_id"]) == ["B"]
    assert bad["rejection_reason"].iloc[0] == "negative monthly_amount"


def test_zero_and_positive_are_kept():
    df = pd.DataFrame({"structure_id": ["A", "B"], "monthly_amount": [0, 1600]})
    good, bad = check_negative_amounts(df)
    assert len(good) == 2
    assert len(bad) == 0