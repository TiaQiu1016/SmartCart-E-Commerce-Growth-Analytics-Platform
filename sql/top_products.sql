-- top_products.sql
-- Best-selling products by quantity and revenue.
-- Supports the descriptive side of product recommendation / cross-selling insights.
-- Run: sqlite3 data/smartcart.db < sql/top_products.sql

SELECT
    stock_code,
    MAX(description)                AS description,
    SUM(quantity)                   AS units_sold,
    COUNT(DISTINCT invoice)         AS invoices,
    ROUND(SUM(revenue), 2)          AS revenue
FROM transactions
GROUP BY stock_code
ORDER BY revenue DESC
LIMIT 20;
