import os
import sys

import pandas as pd

CLEAN = os.getenv("CLEAN_DIR", "clean")
REJECTED = os.getenv("REJECTED_DIR", "rejected")


def check_negative_amounts(df):
    bad = df[df["monthly_amount"] < 0].copy()
    bad["rejection_reason"] = "negative monthly_amount"
    good = df[df["monthly_amount"] >= 0]
    return good, bad


def main():
    path = os.path.join(CLEAN, "salary_structures_clean.csv")
    df = pd.read_csv(path)
    good, bad = check_negative_amounts(df)

    os.makedirs(REJECTED, exist_ok=True)
    bad.to_csv(os.path.join(REJECTED, "salary_structures_negative.csv"), index=False)

    print(f"salary_structures: rows in={len(df)} ok={len(good)} negative={len(bad)}")
    if len(bad):
        print("FAILED: negative salary amounts found. See rejected/salary_structures_negative.csv")
        sys.exit(1)
    print("Salary rule: OK")


if __name__ == "__main__":
    main()