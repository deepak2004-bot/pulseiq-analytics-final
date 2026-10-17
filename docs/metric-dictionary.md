# Metric Dictionary

| Metric ID | Metric Name | Plain Meaning | Formula / Logic | Source Table | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **M01** | Total Headcount | Count of active employees at a given point in time | `COUNT(employee_id) WHERE status = 'Active'` | `dim_employee` | HR |
| **M02** | New Joiners | Total employees joined within a specific month/period | `COUNT(employee_id) WHERE joining_date IN month` | `dim_employee` | HR |
| **M03** | Total Leavers / Exits | Total employees who left the company within a month | `COUNT(employee_id) WHERE exit_date IN month` | `dim_employee` | HR |
| **M04** | Monthly Attrition Rate | Percentage of workforce that left during the month | `(Exits in Month / Headcount at Start of Month) * 100` | `fact_headcount_monthly` | HR |
| **M05** | Rolling 12-Month Attrition | Average annual attrition rate over the last 12 months | `(Total Exits in 12 Months / Average Monthly Headcount) * 100` | `fact_headcount_monthly` | HR |