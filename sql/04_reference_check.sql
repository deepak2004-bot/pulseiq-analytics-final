-- Check 3: department-month D01, April 2025, against reference_summary_dept_month
SELECT 'D01_2025-04_employer_cost' AS check_name,
       ROUND(SUM(employer_cost)::numeric, 2) AS actual,
       21428108.75 AS expected
FROM dw.fact_payroll
WHERE department_id = 'D01' AND year = 2025 AND month = 4

UNION ALL

SELECT 'D01_2025-04_employees_paid' AS check_name,
       COUNT(DISTINCT employee_id) AS actual,
       145 AS expected
FROM dw.fact_payroll
WHERE department_id = 'D01' AND year = 2025 AND month = 4;