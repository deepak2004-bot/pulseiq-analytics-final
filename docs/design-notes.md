# Design Notes

## AI design (v1)
Tool used: Claude | Screenshot: design-v1.png

## What I changed
1. Made Current Headcount the first number in the top row, with Average Tenure, Joiners and Leavers beside it.
2. Used the colour-blind safe Okabe-Ito palette from the style guide.
3. Used the metric dictionary names as chart titles.
4. Added a one-line takeaway under every chart, written from the real numbers.
5. Set Joiners and Leavers to the last 12 months so they match the headcount trend.
6. Kept the layout simple so it stacks into one column on a phone.

## Data notes
- Headcount Trend is built from dim_employee because fact_headcount_monthly was empty.
- Departments and roles show source codes (D01, R002) because the source file has no names.
- A small D00 department probably means blank or unknown.
- The Department filter does not change charts built on other datasets.