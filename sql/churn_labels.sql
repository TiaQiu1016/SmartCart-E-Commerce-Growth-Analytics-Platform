-- churn_labels.sql
-- Defines a behavioural churn label from the RFM table: a customer is "churned"
-- if they have not purchased within an inactivity window (default 90 days)
-- relative to the dataset's latest date. Feeds the churn-prediction model.
-- Run: sqlite3 data/smartcart.db < sql/churn_labels.sql
-- Requires the `rfm` table (build it first with sql/rfm.sql).

DROP TABLE IF EXISTS churn_labels;

CREATE TABLE churn_labels AS
SELECT
    customer_id,
    recency_days,
    frequency,
    monetary,
    CASE WHEN recency_days > 90 THEN 1 ELSE 0 END AS churned   -- 1 = churned, 0 = active
FROM rfm;

-- Churn rate overview
SELECT
    churned,
    COUNT(*)                                   AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM churn_labels
GROUP BY churned;
