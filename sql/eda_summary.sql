-- eda_summary.sql
-- Dataset-level KPIs computed directly in SQL (reproduces the data-check numbers).
-- Run: sqlite3 data/smartcart.db < sql/eda_summary.sql

SELECT
    COUNT(*)                                   AS rows,
    COUNT(DISTINCT customer_id)                AS customers,
    COUNT(DISTINCT invoice)                    AS invoices,
    COUNT(DISTINCT stock_code)                 AS products,
    MIN(invoice_date)                          AS first_date,
    MAX(invoice_date)                          AS last_date,
    ROUND(SUM(revenue), 2)                     AS total_revenue
FROM transactions;

-- Repeat-purchase rate (% of customers with more than one invoice)
SELECT
    ROUND(100.0 * SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS repeat_customer_pct
FROM (
    SELECT customer_id, COUNT(DISTINCT invoice) AS orders
    FROM transactions
    GROUP BY customer_id
);

-- Multi-item invoice rate (% of invoices with more than one distinct product)
SELECT
    ROUND(100.0 * SUM(CASE WHEN items > 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS multi_item_invoice_pct
FROM (
    SELECT invoice, COUNT(DISTINCT stock_code) AS items
    FROM transactions
    GROUP BY invoice
);
