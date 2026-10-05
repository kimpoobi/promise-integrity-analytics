-- Grain: exactly one row per order. Aggregate items and select one review BEFORE joining.
CREATE OR REPLACE TABLE mart_orders AS
WITH item_summary AS (
 SELECT i.order_id, COUNT(*) AS item_count, COUNT(DISTINCT i.seller_id) AS seller_count,
        SUM(i.price) AS item_value_brl, SUM(i.freight_value) AS freight_charged_brl,
        COUNT(DISTINCT p.product_category_name) AS category_count,
        CASE WHEN COUNT(DISTINCT p.product_category_name) > 1 THEN 'mixed_categories'
             ELSE COALESCE(MAX(t.product_category_name_english), 'unknown') END AS category,
        AVG(p.product_weight_g) AS mean_weight_g,
        MAX(CASE WHEN s.seller_state <> c.customer_state THEN 1 ELSE 0 END) AS interstate
 FROM raw_items i
 LEFT JOIN raw_products p USING(product_id)
 LEFT JOIN raw_translation t USING(product_category_name)
 LEFT JOIN raw_sellers s USING(seller_id)
 JOIN raw_orders o USING(order_id)
 LEFT JOIN raw_customers c USING(customer_id)
 GROUP BY i.order_id
), first_review AS (
 SELECT order_id, review_score, review_answer_timestamp, review_creation_date
 FROM raw_reviews
 WHERE review_score BETWEEN 1 AND 5 AND review_answer_timestamp IS NOT NULL
 QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp, review_id, review_score) = 1
), joined AS (
 SELECT o.*, c.customer_state, i.* EXCLUDE(order_id),
        r.review_score, r.review_answer_timestamp, r.review_creation_date,
        date_trunc('month', order_purchase_timestamp)::DATE AS purchase_month,
        date_diff('day', order_purchase_timestamp::DATE, order_estimated_delivery_date::DATE) AS promise_days,
        date_diff('day', order_estimated_delivery_date::DATE, order_delivered_customer_date::DATE) AS lateness_days,
        epoch(order_delivered_customer_date-order_purchase_timestamp)/86400.0 AS delivery_days,
        epoch(order_delivered_carrier_date-order_approved_at)/86400.0 AS handling_days,
        epoch(order_delivered_customer_date-order_delivered_carrier_date)/86400.0 AS transit_days,
        (order_status = 'delivered'
          AND order_purchase_timestamp IS NOT NULL
          AND order_estimated_delivery_date >= order_purchase_timestamp::DATE
          AND order_delivered_customer_date >= order_purchase_timestamp
          AND i.item_count > 0) AS eligible
 FROM raw_orders o
 LEFT JOIN raw_customers c USING(customer_id)
 LEFT JOIN item_summary i USING(order_id)
 LEFT JOIN first_review r USING(order_id)
)
SELECT *,
 CASE WHEN eligible THEN lateness_days <= 0 END AS on_time,
 CASE WHEN eligible AND review_answer_timestamp >= order_delivered_customer_date
      THEN review_score END AS post_delivery_score,
 CASE WHEN eligible AND review_answer_timestamp >= order_delivered_customer_date
      THEN review_score <= 2 END AS poor_review,
 CASE WHEN item_count = 1 THEN '1 item' WHEN item_count > 1 THEN '2+ items' ELSE 'unknown' END AS basket_band,
 CASE WHEN handling_days >= 0 AND transit_days >= 0 THEN TRUE ELSE FALSE END AS valid_stages
FROM joined;

CREATE OR REPLACE TABLE fact_delivery_events AS
SELECT order_id, 'purchase' AS event_type, order_purchase_timestamp AS event_time FROM raw_orders
UNION ALL SELECT order_id, 'approved', order_approved_at FROM raw_orders WHERE order_approved_at IS NOT NULL
UNION ALL SELECT order_id, 'carrier_handoff', order_delivered_carrier_date FROM raw_orders WHERE order_delivered_carrier_date IS NOT NULL
UNION ALL SELECT order_id, 'delivered', order_delivered_customer_date FROM raw_orders WHERE order_delivered_customer_date IS NOT NULL;

CREATE OR REPLACE VIEW event_intervals AS
SELECT *, LAG(event_type) OVER w AS previous_event,
 epoch(event_time-LAG(event_time) OVER w)/3600.0 AS hours_since_previous
FROM fact_delivery_events WINDOW w AS (PARTITION BY order_id ORDER BY event_time, event_type);

CREATE OR REPLACE VIEW monthly_kpis AS
SELECT purchase_month, COUNT(*) AS orders,
 SUM(on_time::INT) AS on_time_orders, SUM((NOT on_time)::INT) AS late_orders,
 COUNT(poor_review) AS reviewed_orders,
 COUNT(*) FILTER (WHERE on_time AND poor_review IS NOT NULL) AS reviewed_on_time,
 COUNT(*) FILTER (WHERE on_time AND poor_review) AS hidden_failure_orders,
 AVG(on_time::INT) AS on_time_rate,
 AVG(poor_review::INT) FILTER (WHERE on_time) AS hidden_failure_rate,
 quantile_cont(delivery_days, 0.9) AS p90_delivery_days
FROM mart_orders WHERE eligible GROUP BY purchase_month;
