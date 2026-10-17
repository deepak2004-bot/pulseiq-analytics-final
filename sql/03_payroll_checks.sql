-- Check 1: employer cost of run PR-2025-04 (expected 53363392.08)
SELECT 'employer_cost_PR-2025-04' AS check_name,
       ROUND(SUM(employer_cost)::numeric, 2) AS actual,
       53363392.08 AS expected
FROM dw.fact_payroll
WHERE run_id = 'PR-2025-04';

-- Check 2: employees paid in PR-2026-09 (expected 444)
SELECT 'employees_paid_PR-2026-09' AS check_name,
       COUNT(DISTINCT employee_id) AS actual,
       444 AS expected
FROM dw.fact_payroll
WHERE run_id = 'PR-2026-09';