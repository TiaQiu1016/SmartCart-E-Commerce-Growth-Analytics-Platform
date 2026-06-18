-- rfm_segments.sql
-- Quick, transparent RFM scoring in pure SQL (a baseline before K-Means).
-- Each customer gets a 1-4 score on Recency, Frequency, Monetary via quartiles (NTILE),
-- where higher is better. Recency is reversed (fewer days since last order = better).
-- Run: sqlite3 data/smartcart.db < sql/rfm_segments.sql
-- Requires the `rfm` table (build it first with sql/rfm.sql).

DROP TABLE IF EXISTS rfm_scored;

CREATE TABLE rfm_scored AS
WITH scored AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        5 - NTILE(4) OVER (ORDER BY recency_days)        AS r_score,  -- low recency = high score
        NTILE(4) OVER (ORDER BY frequency)               AS f_score,
        NTILE(4) OVER (ORDER BY monetary)                AS m_score
    FROM rfm
)
SELECT
    *,
    (r_score + f_score + m_score) AS rfm_total,
    CASE
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Champions'
        WHEN r_score >= 3 AND f_score >= 2                  THEN 'Loyal'
        WHEN r_score >= 3                                   THEN 'Recent / Promising'
        WHEN r_score <= 2 AND f_score >= 3                  THEN 'At Risk (was active)'
        ELSE 'Hibernating'
    END AS segment
FROM scored;

-- Segment sizes and average value
SELECT
    segment,
    COUNT(*)                       AS customers,
    ROUND(AVG(recency_days), 1)    AS avg_recency_days,
    ROUND(AVG(frequency), 1)       AS avg_frequency,
    ROUND(AVG(monetary), 2)        AS avg_monetary
FROM rfm_scored
GROUP BY segment
ORDER BY avg_monetary DESC;
