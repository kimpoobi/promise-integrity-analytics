# Data dictionary and metric contract

## Source grains

| Input | Grain / key | Important use |
|---|---|---|
| Orders | one `order_id` | status, purchase, approval, carrier, delivery, estimate |
| Items | `order_id`, `order_item_id` | price, freight, seller, product |
| Reviews | review submission; may repeat an order | score, creation and answer timestamps |
| Customers | one `customer_id` | delivery state |
| Products | one `product_id` | category and weight |
| Sellers | one `seller_id` | seller state |
| Translation | one Portuguese category | English category label |

The ingestion step fails on duplicate/null dimension keys and duplicate item natural keys. Item rows are aggregated BEFORE joining to orders. Reviews are reduced to one selected row BEFORE the join. Output order count and item-value total are reconciled to raw controls.

## Mart fields

| Field | Type / units | Definition |
|---|---|---|
| order_id | text | Anonymous source order key; final mart grain |
| purchase_month | date | Calendar month of purchase; not delivery month |
| customer_state | text | Brazilian customer delivery state |
| category | text | Single category; `mixed_categories` for multiple; `unknown` if unmapped |
| item_count | integer | Number of item rows, not unique product count |
| seller_count | integer | Distinct sellers in the order |
| category_count | integer | Distinct non-null source categories |
| item_value_brl | BRL | Sum of merchandise prices; not platform revenue or accounting profit |
| freight_charged_brl | BRL | Sum of customer-facing freight charges; not actual logistics expense |
| mean_weight_g | grams | Mean product weight across item rows; training median fills missing model values |
| interstate | 0/1 | At least one seller state differs from customer state |
| promise_days | calendar days | Recorded estimate date minus purchase date |
| lateness_days | calendar days | Actual delivery date minus recorded estimate date; negative means early |
| delivery_days | fractional days | Elapsed purchase-to-delivery time |
| handling_days | fractional days | Elapsed approval-to-carrier handoff time |
| transit_days | fractional days | Elapsed carrier handoff-to-delivery time |
| eligible | nullable Boolean | Delivered status, valid purchase/estimate/delivery chronology, at least one item |
| valid_stages | Boolean | Handling and transit durations both non-negative and non-null |
| on_time | nullable Boolean | Eligible and lateness_days <= 0; same-day delivery is on time |
| review_score | integer 1-5 / null | Earliest answered review, ordered by response timestamp, ID, then score |
| post_delivery_score | integer / null | Selected review score only if answered at/after delivery |
| poor_review | nullable Boolean | post_delivery_score <= 2; missing/pre-delivery stays null |
| basket_band | text | `1 item`, `2+ items`, or `unknown` |

Source timestamps have no explicit timezone offsets. Calendar comparisons use the source's local timestamp representation; no UTC conversion is invented.

## Rate contracts

- Recorded-promise on-time rate = eligible on-time orders / all eligible orders.
- Review coverage = eligible orders with a selected post-delivery review / all eligible orders.
- Hidden-failure rate = eligible on-time orders with selected post-delivery score <= 2 / eligible on-time orders with a selected post-delivery score.
- Hidden-failure count is a proxy count, not confirmed delivery complaints or refund events.
- Monthly rates use summed counts. Never average monthly percentages to recover the global rate.
- Category dashboard minimum: 30 reviewed on-time orders. Global segment CSV minimum: 100. Rankings use hidden-failure counts, not smallest-sample rates.
- P90 delivery days includes eligible delivered orders only. Undelivered/cancelled orders are outside its population.

## Model-time fields

`promise_remaining_days` is recorded estimate date + one day minus actual carrier handoff, in fractional days. Adding one day expresses an end-of-date deadline. The outcome is lateness against the recorded date.

`log_item_value` is log(1 + item_value_brl). Numerical missing values use training-set medians; categories use `unknown`. Scaling and one-hot encoding fit on the training set only.

Item assignments and the recorded estimate are assumed available at handoff. Because source change history is absent, this is a retrospective approximation, not a certified point-in-time feature store.
