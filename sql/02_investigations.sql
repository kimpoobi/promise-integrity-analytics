-- 1. Customer-state prioritization. The threshold prevents tiny samples dominating a ranking.
SELECT customer_state, COUNT(*) AS eligible_orders,
 COUNT(poor_review) FILTER (WHERE on_time) AS reviewed_on_time,
 SUM(poor_review::INT) FILTER (WHERE on_time) AS hidden_failures,
 AVG(poor_review::INT) FILTER (WHERE on_time) AS hidden_failure_rate
FROM mart_orders WHERE eligible
GROUP BY customer_state HAVING reviewed_on_time >= 100
ORDER BY hidden_failures DESC;

-- 2. Item join inflation reconciliation. These two totals must agree.
SELECT (SELECT SUM(price) FROM raw_items) AS raw_item_value,
       (SELECT SUM(item_value_brl) FROM mart_orders) AS mart_item_value;

-- 3. Within-month rankings use a window over grouped data.
WITH rates AS (
 SELECT purchase_month, customer_state, COUNT(*) AS n, AVG(on_time::INT) AS on_time_rate
 FROM mart_orders WHERE eligible GROUP BY ALL HAVING COUNT(*) >= 100
)
SELECT *, DENSE_RANK() OVER (PARTITION BY purchase_month ORDER BY on_time_rate) AS reliability_rank
FROM rates ORDER BY purchase_month, reliability_rank;

-- 4. Quarantine review dates that precede delivery instead of calling them post-delivery evidence.
SELECT COUNT(*) AS pre_delivery_reviews
FROM mart_orders WHERE eligible AND review_answer_timestamp < order_delivered_customer_date;
