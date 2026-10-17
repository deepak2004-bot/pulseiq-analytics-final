-- Task 2: employee dimension with history (one row per version)
-- Source: employee_assignments (effective_from / effective_to)

CREATE TABLE IF NOT EXISTS dw.dim_employee (
    employee_key   SERIAL PRIMARY KEY,
    assignment_id  VARCHAR(20) NOT NULL,
    employee_id    VARCHAR(20) NOT NULL,
    department_id  VARCHAR(10),
    role_id        VARCHAR(10),
    job_level      INTEGER,
    manager_id     VARCHAR(20),
    change_reason  VARCHAR(100),
    valid_from     DATE NOT NULL,
    valid_to       DATE,
    is_current     BOOLEAN NOT NULL,
    UNIQUE (assignment_id)
);

CREATE INDEX IF NOT EXISTS idx_dim_employee_id
    ON dw.dim_employee (employee_id);

CREATE INDEX IF NOT EXISTS idx_dim_employee_dates
    ON dw.dim_employee (employee_id, valid_from, valid_to);