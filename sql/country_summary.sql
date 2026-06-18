-- country_summary.sql
-- Sales and customers by country, plus a UK vs non-UK split.
-- Supports the Customer Group Comparison & Statistical Testing module.
-- Run: sqlite3 data/smartcart.db < sql/country_summary.sql

-- Top countries by revenue
SELECT
    country,
    COUNT(DISTINCT customer_id)                       AS customers,
    COUNT(DISTINCT invoice)                           AS invoices,
    ROUND(SUM(revenue), 2)                            AS revenue,
    ROUND(SUM(revenue) / COUNT(DISTINCT invoice), 2)  AS avg_order_value
FROM transactions
GROUP BY country
ORDER BY revenue DESC
LIMIT 10;

-- UK vs non-UK comparison (two groups for statistical testing)
SELECT
    CASE WHEN country = 'United Kingdom' THEN 'UK' ELSE 'Non-UK' END AS region,
    COUNT(DISTINCT customer_id)                       AS customers,
    COUNT(DISTINCT invoice)                           AS invoices,
    ROUND(SUM(revenue), 2)                            AS revenue,
    ROUND(SUM(revenue) / COUNT(DISTINCT invoice), 2)  AS avg_order_value
FROM transactions
GROUP BY region;
