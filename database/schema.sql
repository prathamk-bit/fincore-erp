-- ============================================================================
-- ERP System - Complete Database Schema (SQLite-compatible)
-- Generated to match SQLAlchemy models exactly.
-- ============================================================================

-- Enable foreign key enforcement (SQLite requires this per connection)
PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. USERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        VARCHAR(50)  NOT NULL UNIQUE,
    email           VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'accountant',  -- admin | accountant | hr_manager | inventory_manager
    is_active       BOOLEAN      NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at      DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_users_id       ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_users_email    ON users (email);

-- ============================================================================
-- 2. DEPARTMENTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_departments_id ON departments (id);

-- ============================================================================
-- 3. DESIGNATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS designations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_designations_id ON designations (id);

-- ============================================================================
-- 4. EMPLOYEES
-- ============================================================================

CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER        PRIMARY KEY AUTOINCREMENT,
    employee_code   VARCHAR(20)    NOT NULL UNIQUE,
    first_name      VARCHAR(50)    NOT NULL,
    last_name       VARCHAR(50)    NOT NULL,
    email           VARCHAR(100)   NOT NULL UNIQUE,
    phone           VARCHAR(20),
    date_of_joining DATE           NOT NULL,
    salary          NUMERIC(15, 2) NOT NULL DEFAULT 0,
    is_active       BOOLEAN        NOT NULL DEFAULT 1,
    department_id   INTEGER        NOT NULL,
    designation_id  INTEGER        NOT NULL,
    created_at      DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at      DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (department_id)  REFERENCES departments (id),
    FOREIGN KEY (designation_id) REFERENCES designations (id)
);

CREATE INDEX IF NOT EXISTS ix_employees_id            ON employees (id);
CREATE INDEX IF NOT EXISTS ix_employees_employee_code ON employees (employee_code);

-- ============================================================================
-- 5. ACCOUNTS (Chart of Accounts - self-referential hierarchy)
-- ============================================================================

CREATE TABLE IF NOT EXISTS accounts (
    id                INTEGER        PRIMARY KEY AUTOINCREMENT,
    code              VARCHAR(20)    NOT NULL UNIQUE,
    name              VARCHAR(150)   NOT NULL,
    account_type      VARCHAR(20)    NOT NULL,  -- asset | liability | equity | revenue | expense
    balance           NUMERIC(15, 2) NOT NULL DEFAULT 0,
    is_active         BOOLEAN        NOT NULL DEFAULT 1,
    parent_account_id INTEGER,
    created_at        DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at        DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (parent_account_id) REFERENCES accounts (id)
);

CREATE INDEX IF NOT EXISTS ix_accounts_id   ON accounts (id);
CREATE INDEX IF NOT EXISTS ix_accounts_code ON accounts (code);

-- ============================================================================
-- 6. JOURNAL ENTRIES (Header)
-- ============================================================================

CREATE TABLE IF NOT EXISTS journal_entries (
    id             INTEGER        PRIMARY KEY AUTOINCREMENT,
    entry_number   VARCHAR(30)    NOT NULL UNIQUE,
    date           DATE           NOT NULL,
    description    TEXT,
    reference_type VARCHAR(50),
    reference_id   INTEGER,
    status         VARCHAR(20)    NOT NULL DEFAULT 'draft',  -- draft | posted
    total_debit    NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_credit   NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at     DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at     DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_journal_entries_id           ON journal_entries (id);
CREATE INDEX IF NOT EXISTS ix_journal_entries_entry_number ON journal_entries (entry_number);
CREATE INDEX IF NOT EXISTS ix_journal_entries_reference_id ON journal_entries (reference_id);

-- ============================================================================
-- 7. JOURNAL ENTRY LINES (Debit / Credit postings)
-- ============================================================================

CREATE TABLE IF NOT EXISTS journal_entry_lines (
    id               INTEGER        PRIMARY KEY AUTOINCREMENT,
    journal_entry_id INTEGER        NOT NULL,
    account_id       INTEGER        NOT NULL,
    debit            NUMERIC(15, 2) NOT NULL DEFAULT 0,
    credit           NUMERIC(15, 2) NOT NULL DEFAULT 0,
    description      TEXT,
    created_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id),
    FOREIGN KEY (account_id)       REFERENCES accounts (id)
);

CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_id               ON journal_entry_lines (id);
CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_journal_entry_id ON journal_entry_lines (journal_entry_id);
CREATE INDEX IF NOT EXISTS ix_journal_entry_lines_account_id       ON journal_entry_lines (account_id);

-- ============================================================================
-- 8. PAYROLLS
-- ============================================================================

CREATE TABLE IF NOT EXISTS payrolls (
    id               INTEGER        PRIMARY KEY AUTOINCREMENT,
    employee_id      INTEGER        NOT NULL,
    pay_period_start DATE           NOT NULL,
    pay_period_end   DATE           NOT NULL,
    basic_salary     NUMERIC(15, 2) NOT NULL DEFAULT 0,
    gross_salary     NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_deductions NUMERIC(15, 2) NOT NULL DEFAULT 0,
    net_salary       NUMERIC(15, 2) NOT NULL DEFAULT 0,
    status           VARCHAR(20)    NOT NULL DEFAULT 'draft',  -- draft | approved | paid | cancelled
    journal_entry_id INTEGER,
    created_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (employee_id)      REFERENCES employees (id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)
);

CREATE INDEX IF NOT EXISTS ix_payrolls_id          ON payrolls (id);
CREATE INDEX IF NOT EXISTS ix_payrolls_employee_id ON payrolls (employee_id);

-- ============================================================================
-- 9. PAYROLL COMPONENTS (earnings / deductions line items)
-- ============================================================================

CREATE TABLE IF NOT EXISTS payroll_components (
    id             INTEGER        PRIMARY KEY AUTOINCREMENT,
    payroll_id     INTEGER        NOT NULL,
    component_name VARCHAR(100)   NOT NULL,
    component_type VARCHAR(20)    NOT NULL,  -- earnings | deductions
    amount         NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at     DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at     DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (payroll_id) REFERENCES payrolls (id)
);

CREATE INDEX IF NOT EXISTS ix_payroll_components_id         ON payroll_components (id);
CREATE INDEX IF NOT EXISTS ix_payroll_components_payroll_id ON payroll_components (payroll_id);

-- ============================================================================
-- 10. FINANCIAL TRANSACTIONS (cross-module audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS financial_transactions (
    id               INTEGER        PRIMARY KEY AUTOINCREMENT,
    transaction_date DATE           NOT NULL,
    transaction_type VARCHAR(20)    NOT NULL,  -- income | expense
    category         VARCHAR(100),
    amount           NUMERIC(15, 2) NOT NULL DEFAULT 0,
    description      TEXT,
    reference_type   VARCHAR(50),
    reference_id     INTEGER,
    journal_entry_id INTEGER,
    created_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)
);

CREATE INDEX IF NOT EXISTS ix_financial_transactions_id           ON financial_transactions (id);
CREATE INDEX IF NOT EXISTS ix_financial_transactions_reference_id ON financial_transactions (reference_id);

-- ============================================================================
-- 11. ITEM CATEGORIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS item_categories (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at  DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_item_categories_id ON item_categories (id);

-- ============================================================================
-- 12. WAREHOUSES
-- ============================================================================

CREATE TABLE IF NOT EXISTS warehouses (
    id         INTEGER      PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(100) NOT NULL UNIQUE,
    location   TEXT,
    is_active  BOOLEAN      NOT NULL DEFAULT 1,
    created_at DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_warehouses_id ON warehouses (id);

-- ============================================================================
-- 13. ITEMS (Inventory SKUs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER        PRIMARY KEY AUTOINCREMENT,
    code            VARCHAR(30)    NOT NULL UNIQUE,
    name            VARCHAR(150)   NOT NULL,
    description     TEXT,
    unit_of_measure VARCHAR(20)    NOT NULL DEFAULT 'pcs',
    reorder_level   NUMERIC(15, 2) NOT NULL DEFAULT 0,
    current_stock   NUMERIC(15, 2) NOT NULL DEFAULT 0,
    unit_price      NUMERIC(15, 2) NOT NULL DEFAULT 0,
    category_id     INTEGER,
    created_at      DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at      DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (category_id) REFERENCES item_categories (id)
);

CREATE INDEX IF NOT EXISTS ix_items_id   ON items (id);
CREATE INDEX IF NOT EXISTS ix_items_code ON items (code);

-- ============================================================================
-- 14. STOCK LEDGER (inventory movement audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS stock_ledger (
    id               INTEGER        PRIMARY KEY AUTOINCREMENT,
    item_id          INTEGER        NOT NULL,
    warehouse_id     INTEGER        NOT NULL,
    transaction_type VARCHAR(10)    NOT NULL,  -- IN | OUT
    quantity         NUMERIC(15, 2) NOT NULL,
    reference_type   VARCHAR(50),
    reference_id     INTEGER,
    balance_after    NUMERIC(15, 2) NOT NULL DEFAULT 0,
    transaction_date DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    created_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at       DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (item_id)      REFERENCES items (id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX IF NOT EXISTS ix_stock_ledger_id           ON stock_ledger (id);
CREATE INDEX IF NOT EXISTS ix_stock_ledger_item_id      ON stock_ledger (item_id);
CREATE INDEX IF NOT EXISTS ix_stock_ledger_warehouse_id ON stock_ledger (warehouse_id);
CREATE INDEX IF NOT EXISTS ix_stock_ledger_reference_id ON stock_ledger (reference_id);

-- ============================================================================
-- 14b. WAREHOUSE STOCK (Per-warehouse stock tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS warehouse_stock (
    id           INTEGER        PRIMARY KEY AUTOINCREMENT,
    item_id      INTEGER        NOT NULL,
    warehouse_id INTEGER        NOT NULL,
    quantity     NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at   DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at   DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (item_id)      REFERENCES items (id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX IF NOT EXISTS ix_warehouse_stock_id           ON warehouse_stock (id);
CREATE INDEX IF NOT EXISTS ix_warehouse_stock_item_id      ON warehouse_stock (item_id);
CREATE INDEX IF NOT EXISTS ix_warehouse_stock_warehouse_id ON warehouse_stock (warehouse_id);

-- ============================================================================
-- 15. SUPPLIERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER      PRIMARY KEY AUTOINCREMENT,
    name           VARCHAR(150) NOT NULL,
    contact_person VARCHAR(100),
    email          VARCHAR(100),
    phone          VARCHAR(20),
    address        TEXT,
    is_active      BOOLEAN      NOT NULL DEFAULT 1,
    created_at     DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at     DATETIME     NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS ix_suppliers_id ON suppliers (id);

-- ============================================================================
-- 16. PURCHASE ORDERS (Header)
-- ============================================================================

CREATE TABLE IF NOT EXISTS purchase_orders (
    id                     INTEGER        PRIMARY KEY AUTOINCREMENT,
    po_number              VARCHAR(30)    NOT NULL UNIQUE,
    supplier_id            INTEGER        NOT NULL,
    order_date             DATE           NOT NULL,
    expected_delivery_date DATE,
    status                 VARCHAR(20)    NOT NULL DEFAULT 'draft',  -- draft | approved | received | cancelled
    total_amount           NUMERIC(15, 2) NOT NULL DEFAULT 0,
    journal_entry_id       INTEGER,
    created_at             DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at             DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (supplier_id)      REFERENCES suppliers (id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries (id)
);

CREATE INDEX IF NOT EXISTS ix_purchase_orders_id          ON purchase_orders (id);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_po_number   ON purchase_orders (po_number);
CREATE INDEX IF NOT EXISTS ix_purchase_orders_supplier_id ON purchase_orders (supplier_id);

-- ============================================================================
-- 17. PURCHASE ORDER ITEMS (Line Items)
-- ============================================================================

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id                INTEGER        PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER        NOT NULL,
    item_id           INTEGER        NOT NULL,
    quantity          NUMERIC(15, 3) NOT NULL DEFAULT 0,
    received_quantity NUMERIC(15, 3) NOT NULL DEFAULT 0,
    unit_price        NUMERIC(15, 2) NOT NULL DEFAULT 0,
    total_price       NUMERIC(15, 2) NOT NULL DEFAULT 0,
    created_at        DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at        DATETIME       NOT NULL DEFAULT (CURRENT_TIMESTAMP),

    FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id),
    FOREIGN KEY (item_id)           REFERENCES items (id)
);

CREATE INDEX IF NOT EXISTS ix_purchase_order_items_id                ON purchase_order_items (id);
CREATE INDEX IF NOT EXISTS ix_purchase_order_items_purchase_order_id ON purchase_order_items (purchase_order_id);
CREATE INDEX IF NOT EXISTS ix_purchase_order_items_item_id           ON purchase_order_items (item_id);

-- ============================================================================
-- SEED DATA: Default admin user
-- Password hash below is bcrypt for 'admin123' -- CHANGE IN PRODUCTION
-- ============================================================================

INSERT INTO users (username, email, hashed_password, role, is_active)
VALUES (
    'admin',
    'admin@erp.local',
    '$2b$12$LJ3m4ys3Lz0QqXvYvKjXxOZg1Wz8RkZhF4v7n5D1XpKjyYmW5Kqe6',
    'admin',
    1
);

-- ============================================================================
-- SEED DATA: Sample Chart of Accounts
-- ============================================================================

-- Root asset accounts
INSERT INTO accounts (code, name, account_type, balance, is_active, parent_account_id) VALUES
    ('1000', 'Assets',                    'asset',     0, 1, NULL),
    ('1100', 'Cash and Bank',             'asset',     0, 1, 1),
    ('1110', 'Cash in Hand',              'asset',     0, 1, 2),
    ('1120', 'Bank Account',              'asset',     0, 1, 2),
    ('1200', 'Accounts Receivable',       'asset',     0, 1, 1),
    ('1300', 'Inventory',                 'asset',     0, 1, 1),
    ('1400', 'Fixed Assets',              'asset',     0, 1, 1);

-- Root liability accounts
INSERT INTO accounts (code, name, account_type, balance, is_active, parent_account_id) VALUES
    ('2000', 'Liabilities',               'liability', 0, 1, NULL),
    ('2100', 'Accounts Payable',          'liability', 0, 1, 8),
    ('2200', 'Salaries Payable',          'liability', 0, 1, 8),
    ('2300', 'Tax Payable',               'liability', 0, 1, 8);

-- Root equity accounts
INSERT INTO accounts (code, name, account_type, balance, is_active, parent_account_id) VALUES
    ('3000', 'Equity',                    'equity',    0, 1, NULL),
    ('3100', 'Owner''s Capital',          'equity',    0, 1, 12),
    ('3200', 'Retained Earnings',         'equity',    0, 1, 12);

-- Root revenue accounts
INSERT INTO accounts (code, name, account_type, balance, is_active, parent_account_id) VALUES
    ('4000', 'Revenue',                   'revenue',   0, 1, NULL),
    ('4100', 'Sales Revenue',             'revenue',   0, 1, 15),
    ('4200', 'Service Revenue',           'revenue',   0, 1, 15);

-- Root expense accounts
INSERT INTO accounts (code, name, account_type, balance, is_active, parent_account_id) VALUES
    ('5000', 'Expenses',                  'expense',   0, 1, NULL),
    ('5100', 'Salary Expense',            'expense',   0, 1, 18),
    ('5200', 'Rent Expense',              'expense',   0, 1, 18),
    ('5300', 'Utilities Expense',         'expense',   0, 1, 18),
    ('5400', 'Office Supplies Expense',   'expense',   0, 1, 18),
    ('5500', 'Cost of Goods Sold',        'expense',   0, 1, 18);
