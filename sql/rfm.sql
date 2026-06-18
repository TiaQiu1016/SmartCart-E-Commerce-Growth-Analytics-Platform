-- rfm.sql
-- Builds the RFM (Recency, Frequency, Monetary) feature table from the cleaned
-- transactions table. Run against data/smartcart.db.
--
-- Recency  = days between a customer's last purchase and the dataset's latest date
-- Frequency = number of distinct invoices (orders) per customer
-- Monetary  = total revenue (Quantity * Price) per customer

DROP TABLE IF EXISTS rfm;

CREATE TABLE rfm AS
WITH ref AS (
    SELECT julianday(MAX(invoice_date)) AS max_day
    FROM transactions
)
SELECT
    customer_id,
    CAST((SELECT max_day FROM ref) - julianday(MAX(invoice_date)) AS INTEGER) AS recency_days,
    COUNT(DISTINCT invoice)                                                    AS frequency,
    ROUND(SUM(revenue), 2)                                                     AS monetary
FROM transactions
GROUP BY customer_id;
