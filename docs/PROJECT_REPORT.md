# Promise Integrity: Professional Project Report

## Promise Integrity

The hidden customer cost of an on-time delivery

A completed historical analytics case study for operations and customer-experience decisions. Source: Olist public Brazilian e-commerce records, 2016-2018. Currency: Brazilian real (BRL).

| Measure | Validated result |
| --- | --- |
| Source orders | 99,441 |
| Eligible delivered orders | 96,470 |
| Recorded-promise on-time rate | 93.23% |
| On-time orders with poor post-delivery review | 8,238 |
| Hidden-failure rate among reviewed on-time orders | 9.24% |

### Decision supported

Prioritize investigation of on-time orders that still receive poor reviews, especially high-volume categories and multi-item baskets. Preserve the recorded-promise metric while measuring customer experience separately.

### What is distinctive

The project audits metric definitions, explicitly exposes review-timing selection, tests customer-state mix effects, evaluates delay risk on later data, and demonstrates how an ETA definition can improve without changing delivery speed.

### Evidence boundary

The source contains a recorded estimate, not a verified original promise or revision history. A low review score is a customer-experience proxy, not a confirmed logistics complaint. Cost figures and promise extensions are hypothetical scenarios. No business intervention or realized saving is claimed.

### Reading map

2 Workflow and architecture; 3 Data and quality; 4 Metrics; 5 Findings; 6 Selection and uncertainty; 7 Model; 8 Scenarios and experiment; 9 Engineering and validation; 10 Runbook and access; 11 Methods and references.

## Workflow and architecture

The workflow begins with the business decision and ends with a reproducible recommendation. It is designed as a data analytics project, with an offline dashboard as its presentation layer.

| Stage | Implementation | Output |
| --- | --- | --- |
| Acquire | Public Kaggle endpoint; seven CSV files; SHA-256 hashes | Immutable source files |
| Validate | Key contracts; timestamp parsing; item and review grain checks | Quality report |
| Transform | DuckDB SQL CTEs, aggregation, ROW_NUMBER, joins | One-order analytical mart |
| Investigate | Segments, Wilson intervals, bootstrap, standardization | Count-based evidence |
| Evaluate | Handoff-time logistic regression; chronological holdout | Model card and predictions |
| Stress-test | ETA and cost assumptions; replayed scale benchmark | Separate scenario results |
| Communicate | Offline Plotly dashboard, Excel, report, notebook | Reviewable portfolio package |

### Warehouse structure

Raw tables preserve source grains. mart_orders contains exactly one row per source order. fact_delivery_events reconstructs the observed purchase, approval, carrier-handoff, and delivery milestones. event_intervals uses LAG over timestamp order. This event table is derived from snapshot columns; it is not a captured event stream.

Items are aggregated before the order join. The earliest answered review is selected before joining. This prevents one-to-many joins from multiplying merchandise values. Product and seller attributes are summarized to the order grain; mixed-category baskets remain labelled as mixed.

### Refresh design

A deterministic full-snapshot rebuild replaces DuckDB tables and outputs. Month-specific Parquet files are written for analytical access. The process can be rerun locally, but it does not implement CDC, streaming, orchestration infrastructure, or a live marketplace connection.

### Primary artifacts

SQL and Python source, generated aggregate CSV/JSON files, an offline interactive dashboard, formula-driven Excel reconciliation, a learning notebook, metric dictionary, model evaluation, test suite, and this report.

## Data provenance and quality

| Source table | Rows | Role |
| --- | --- | --- |
| orders | 99,441 | Order lifecycle |
| items | 112,650 | Merchandise and freight |
| reviews | 99,224 | Scores and response timing |
| customers | 99,441 | Delivery state |
| products | 32,951 | Category and weight |
| sellers | 3,095 | Seller state |
| translation | 71 | Category labels |

### Quality controls

The pipeline stops on duplicate/null dimension keys or duplicate item natural keys. It verifies the mart row count and distinct order count against source orders. It reconciles summed item values to the raw item table within BRL 0.01. Source hashes are saved in reports/data_manifest.json.

| Diagnostic | Count | Treatment |
| --- | --- | --- |
| Ineligible orders | 2,971 | Excluded from delivered-order analysis |
| Eligible orders without selected review | 646 | No inferred satisfaction score |
| Selected review answered before delivery | 4,768 | Excluded from post-delivery score |
| Invalid/missing stage durations | 1,388 | Excluded from stage-based model |
| Additional review rows beyond one/order | 551 | Earliest answer retained |

### Chronology and missingness

Eligible orders require delivered status, purchase timestamp, a recorded estimate date no earlier than purchase, an actual delivery no earlier than purchase, and at least one item. Invalid stage durations are not silently set to zero. An order may still qualify for headline delivery analysis while failing stage-based model requirements.

### License and privacy

Olist publishes this dataset under CC BY-NC-SA 4.0. The source archive excludes raw data, database files, row-level exports, and installed dependencies. Derived reports retain attribution. The dashboard omits customer IDs, review text, addresses, and order-level records. See DATA_LICENSE.md before redistribution.

## Metric definitions and grain

| Metric | Numerator / calculation | Denominator / population |
| --- | --- | --- |
| On-time rate | Delivery calendar date <= recorded estimate date | All eligible delivered orders |
| Hidden-failure rate | On-time orders with selected post-delivery score <= 2 | On-time orders with selected post-delivery score |
| Review coverage | Orders with selected review answered at/after delivery | All eligible delivered orders |
| Delivery days | Elapsed purchase-to-delivery time | Eligible delivered orders |
| P90 delivery time | 90th percentile of delivery days | Eligible delivered orders |
| Handling days | Carrier handoff minus approval | Non-negative observed stage durations |
| Transit days | Delivery minus carrier handoff | Non-negative observed stage durations |

### Date convention

An estimate is interpreted as a calendar-date deadline. A delivery at 23:59 on that date counts as on time. Source timestamps have no explicit timezone offsets; the project preserves their local representation. A source unit test checks the same-day boundary.

### Review convention

Choose the earliest answered review by response timestamp, review ID, then score. Only after choosing it, check whether it was answered at/after delivery. If the first response is pre-delivery, the order is excluded from the primary review metric even if a later response exists. This conservative rule avoids selectively choosing a later score.

### Aggregation convention

Monthly metrics group by purchase month, not delivery month. Global rates are recomputed from numerator and denominator counts. Category investigations rank counts of hidden failures; rate uncertainty and the sample size accompany each result. Dashboard categories require at least 30 reviewed on-time orders; global segment CSVs require 100.

### Meaning of financial fields

Item value is merchandise price, not net platform revenue. Freight charged is a customer-facing amount, not carrier expense. Contribution figures appear only in the scenario layer and must not be presented as accounting profit.

## Observed findings and priorities

Of 96,470 eligible delivered orders, 89,936 (93.23%) arrived by the recorded estimate. Among 89,151 on-time orders with a post-delivery review, 8,238 received a score of 1 or 2.

The hidden-failure proxy is 9.24%, with a Wilson 95% interval of 9.05% to 9.43%. P90 purchase-to-delivery time is 23.1 days, conditional on eligible delivered orders.

| Category | Reviewed on time | Hidden failures | Rate |
| --- | --- | --- | --- |
| bed bath table | 8,262 | 958 | 11.60% |
| computers accessories | 6,011 | 673 | 11.20% |
| furniture decor | 5,586 | 601 | 10.76% |
| health beauty | 7,881 | 572 | 7.26% |
| sports leisure | 6,908 | 504 | 7.30% |
| watches gifts | 5,013 | 479 | 9.56% |

### Suggested investigation

Start with bed/bath/table, computers/accessories, and furniture/decor because their hidden-failure counts are high. Sample order histories and identify whether poor experiences relate to product quality, damage, incomplete fulfilment, expectations, or another cause. The dataset cannot establish which explanation is correct.

### Basket composition

Single-item on-time orders have a poor-review rate of 7.51%, versus 24.69% for multi-item baskets. With common-state weighting across 18 states, the corresponding rates are 7.49% and 24.80%. There is no sign reversal in this run.

The proposed explanation that customer-state mix alone accounts for the basket association is not supported by this comparison. This is not proof that multiple items cause dissatisfaction: product mix, seller quality, and unmeasured factors remain.

### Recommended metric change

Retain recorded-promise reliability, but report it beside post-delivery review coverage and the hidden-failure proxy. An operations review should ask whether delivery reliability and customer experience improve together.

## Selection bias and uncertainty

| Group | Post-delivery coverage | Poor rate: post-delivery | Poor rate: any review timing |
| --- | --- | --- | --- |
| on time | 99.13% | 9.24% | 9.26% |
| late | 29.16% | 19.42% | 62.36% |

### The major sensitivity finding

Post-delivery review coverage is very different for on-time and late orders. The source survey can be triggered after delivery or when the estimate becomes due. Many late-order responses arrive before eventual delivery. Requiring a post-delivery response changes which customers remain in the comparison.

Consequently, neither a late/on-time difference nor its confidence interval is an estimate of the causal effect of lateness. The alternative any-timing definition measures a different experience. Both are retained in review_sensitivity.csv rather than hiding the discrepancy.

### Statistical implementation

The late-minus-on-time poor-review difference is 10.18 percentage points in the selected post-delivery sample. Resampling purchase weeks 1,000 times gives a percentile interval from 8.14 to 12.51 percentage points.

Week clustering preserves some within-week dependence. It does not remove seasonal confounding, nonresponse bias, or dependence across weeks. Wilson segment intervals describe rate uncertainty under a binomial approximation; they are not simultaneous intervals across every category.

### Standardization check

For single- versus multi-item baskets, retain states with at least 30 reviewed on-time observations in both groups. Use combined group counts to define common state weights. Compare weighted group rates with crude rates and explicitly test whether the sign reverses. The common-state subset differs from the crude population.

### Practical boundary

Use these findings to prioritize an investigation or design a prospective experiment. Do not label a ranked category as a proven root cause. Collect standardized follow-up timing and actual issue types in a future pilot.

## Delay model and evaluation

Task: at carrier handoff, estimate whether an eligible delivered order will arrive after its recorded estimate date. The classifier is regularized logistic regression with training-only preprocessing. It predicts lateness, not the hidden-failure review outcome.

| Split | Handoff window | Outcome availability | Rows |
| --- | --- | --- | --- |
| Train | Before 1 Apr 2018 | Delivered before 1 Apr 2018 | 60,309 |
| Validation | 1 Apr - 31 May 2018 | Delivered before 1 Jun 2018 | 11,422 |
| Test | 1 Jun - 31 Jul 2018 | Delivered before 1 Sep 2018 | 11,353 |

### Features and leakage controls

Remaining promise days at handoff, handling time, item/seller counts, log merchandise value, freight charged, product weight, interstate indicator, customer state, and category. Numerical missing values use training medians. Scaling and category encoding fit only on training data. Delivery duration, actual lateness, reviews, and transit duration never enter the features.

| Held-out measure | Logistic model | Constant baseline |
| --- | --- | --- |
| ROC AUC | 0.828 | 0.500 |
| Average precision | 0.302 | 0.018 |
| Brier score (lower is better) | 0.0169 | 0.0193 |
| Assumed classification cost, BRL | 4,768 | 5,075 |

The test delay prevalence is 1.79%. At the validation-selected threshold of 14.00%, the model raises 803 alerts, with precision 12.08% and recall 47.78%. This is a substantial false-alert burden.

### Model limits

Threshold selection assumes BRL 3 per false alert and BRL 25 per missed delay. These are classification penalties, not measured intervention economics. The source has no feature revision history, so point-in-time availability cannot be certified. Delivered-only filtering and outcome-maturity exclusions can bias the population. Calibration and distribution changes require monitoring before operational use.

## Scenarios and a testable intervention

### ETA re-scoring scenario

Apply uniform extensions of 0, 1, 2, 3, 5, or 7 days to the recorded estimate while holding every actual delivery fixed. A seven-day extension changes on-time performance from 93.23% to 97.03%, reclassifying 3,672 orders. Actual delivery speed improves by zero days. This illustrates metric sensitivity, not evidence of ETA manipulation by Olist.

### Financial sensitivity

For observed hidden-failure orders, vary assumed merchandise margin across 10%, 20%, and 30%, and assumed recovery cost across BRL 10, 25, and 50. Proxy contribution equals merchandise price times assumed margin minus assumed recovery cost. Recovery exposure equals the number of hidden failures times the assumed cost.

At BRL 25 per hidden failure, exposure is BRL 205,950. That is an assumption-driven amount, not an observed refund total or a saving. No real COGS, carrier expense, platform fee, refund, or support-cost records are available.

### Proposed prospective experiment

Intervention: a multi-item completeness and packaging check before dispatch. Randomize eligible multi-item orders to the check or existing process, stratified by seller/category where feasible. Preserve the original customer promise. If treatment spills across orders, randomize at seller or shift level and adjust the sample-size design for clustering.

Primary outcome: a consistently timed post-delivery low-review rate among all randomized orders, with nonresponse reported by arm and sensitivity bounds. Analyse by assignment, not by whether the order eventually arrived on time, because timeliness can be affected by treatment. Guardrails: on-time rate, check labour cost, cancellation, and measured refund cost.

The included sizing function gives 3,504 reviewed orders per arm for a 20% relative reduction from the global 9.24% illustrative baseline, two-sided 5% alpha and 80% power. This is a planning example, not the sample size for the proposed multi-item pilot. Re-estimate the relevant baseline, response rate, clustering and minimum worthwhile effect before launch.

### Decision rule

Adopt only if a preregistered analysis supports worthwhile customer benefit without unacceptable cost or reliability deterioration. Track actual expenses and exposure. No experiment has been run as part of this project.

## Engineering, scale and validation

### Automated analytical contracts

The original execution recorded 15 passing tests covering statistical boundaries, scenarios, feature timing, join grain, value reconciliation, review selection and date edge cases. The 5 October 2026 rerun stopped during collection when Windows Application Control blocked a scikit-learn binary; no tests executed in that attempt. Fresh verification remains pending.

### Full-data validation

The complete real-data pipeline reconciles one mart row per source order and the raw merchandise-value total. Required key checks fail early. Exported summary values reconcile through formulas in the Excel workbook. The month selector was changed and restored to confirm formula recalculation; formula-error scanning returned no errors.

### Browser validation

The offline dashboard was tested in Chromium across its five views. Checks exercised customer-state filtering, a sparse state, ETA extension, margin/recovery controls, and a mobile viewport. No JavaScript errors were detected. The dashboard makes no external network requests for its charts; Plotly is stored alongside the HTML.

### Scale exercise

DuckDB aggregated 1,929,400 replayed rows and matched the source counts multiplied by 20. This measures a local computational workload; replaying records does not add independent evidence. Timings in benchmark.json are machine-specific, include execution overhead, and are not a distributed performance claim.

### Honest coverage boundaries

The supplied Spark extension requires Java/PySpark and was not run here. No native Power BI or Tableau report is included. The Excel deliverable uses formulas and a native chart; it does not contain native PivotTables or an embedded Power Query refresh connection.

### Reproducibility

Random seeds are fixed, raw file hashes are recorded, and direct tested dependency versions are supplied. A source-code archive excludes raw/row-level data and dependencies. GitHub CI is configured to run the fixture-based tests after a future push; no remote CI execution has occurred yet.

## Runbook, tools and access

| Tool | Purpose |
| --- | --- |
| Python + pandas + NumPy | Cleaning, orchestration, analytical exports |
| DuckDB + SQL | Relational mart, validation, windows, Parquet, scale exercise |
| SciPy | Statistical calculations and experiment sizing |
| scikit-learn | Logistic regression, train-only transformations, evaluation |
| Plotly + HTML/JavaScript | Offline interactive dashboard |
| Excel workbook | Formula reconciliation, monthly selection, editable chart |
| pytest + Chromium checks | Analytical contracts and dashboard verification |
| ReportLab | This reproducible PDF report |

### Run sequence

Create a Python 3.11/3.12 virtual environment. Install the package with dev/docs extras. Run scripts/download_data.py, then python -m promise_integrity.pipeline. Run pytest -q and scripts/benchmark.py. Generate this report with scripts/build_report.py. Open reports/dashboard.html with plotly.min.js in the same folder. Exact Windows and Unix commands appear in README.md.

### Access requirements

No GitHub credentials, paid BI subscription, cloud database, or private company account is needed for the delivered version. Initial downloads require internet access. If Kaggle changes public access, manually download the named source CSVs. A real-time company version would need authorized order, ETA-history, refund, and support feeds plus deployment credentials.

### Operational limitations

Historical snapshot, not current market evidence. No original-ETA history, complete delivery-event stream, refund amounts, support contacts, or internal costs. No live ingestion, scheduled service, access control, alert delivery, or production deployment. The model is retrospective and the scenarios are advisory.

### Failure handling

Missing source file: run the downloader or place the documented CSVs in data/raw. Schema/key failure: inspect the input and quality contract rather than weakening it. Dashboard missing charts: keep plotly.min.js next to the HTML. Empty category view: inspect sample sizes; do not manufacture a rate. Dependency issues: use a fresh virtual environment and tested versions.

## Methods and references

| Method / tool | Implementation / boundary |
| --- | --- |
| Excel | SUMIFS, INDEX/MATCH, rate reconciliation and a native chart |
| SQL | CTEs, joins, aggregations, ROW_NUMBER, LAG, DENSE_RANK |
| Python | Modular, reproducible pipeline and executed analysis notebook |
| Visualization / BI | Interactive Plotly dashboard and typed CSV export |
| Statistics | Wilson intervals, cluster bootstrap, standardization, sample-size planning |
| Problem-solving | Metric audit and rejected state-mix explanation |
| Cleaning | Grain, chronology, missingness, review selection and reconciliation |
| Warehousing | Raw tables, order mart, event fact, monthly Parquet outputs |
| Machine learning | Temporal logistic baseline comparison and cost-sensitive threshold |
| Big-data concepts | Validated replay/plan exercise; optional unexecuted Spark extension |
| Storytelling / domain | Decision memo, evidence boundaries, logistics unit economics |

### Reproducing the analysis

Use README.md for the execution sequence and docs/DATA_DICTIONARY.md for field definitions. sql/01_mart.sql defines the analytical grain. The executed notebook connects the metrics to reports/summary.json. Python modules contain the statistical methods, temporal model evaluation and scenario calculations.

### References

Olist public dataset and publisher description: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Data license: https://creativecommons.org/licenses/by-nc-sa/4.0/

DuckDB Python documentation: https://duckdb.org/docs/stable/clients/python/overview

scikit-learn LogisticRegression: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html

### Decision boundary

The analysis identifies investigation priorities rather than proven causes. Any intervention should be evaluated with observed customer outcomes and actual operating costs. The recorded estimate and selected reviews cannot establish original promise integrity, realized financial impact or causal delivery effects.
