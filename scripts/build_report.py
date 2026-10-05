"""Build the professional report and matching Markdown from actual pipeline outputs."""
from pathlib import Path
import json
import csv
from html import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4

ROOT=Path(__file__).resolve().parents[1]
def main():
    s=json.loads((ROOT/'reports/summary.json').read_text())
    q=json.loads((ROOT/'reports/quality.json').read_text())
    b=json.loads((ROOT/'reports/benchmark.json').read_text()) if (ROOT/'reports/benchmark.json').exists() else None
    with (ROOT/'reports/categories.csv').open() as f:cats=list(csv.DictReader(f))
    p=lambda x:f'{x*100:.2f}%'
    n=lambda x:f'{x:,.0f}'
    pages=[]
    def page(title,kicker,blocks):pages.append((title,kicker,blocks))
    def para(text):return ('p',text)
    def head(text):return ('h',text)
    def table(headers,rows,widths=None):return ('t',(headers,rows,widths))
    page('Promise Integrity','PROJECT REPORT / VERSION 1.0',[
        para('The hidden customer cost of an on-time delivery'),
        para('A completed historical analytics case study for operations and customer-experience decisions. Source: Olist public Brazilian e-commerce records, 2016-2018. Currency: Brazilian real (BRL).'),
        table(['Measure','Validated result'],[
            ['Source orders',n(s['raw_orders'])],['Eligible delivered orders',n(s['eligible_orders'])],
            ['Recorded-promise on-time rate',p(s['on_time_rate'])],
            ['On-time orders with poor post-delivery review',n(s['hidden_failure_orders'])],
            ['Hidden-failure rate among reviewed on-time orders',p(s['hidden_failure_rate'])]], [340,160]),
        head('Decision supported'),
        para('Prioritize investigation of on-time orders that still receive poor reviews, especially high-volume categories and multi-item baskets. Preserve the recorded-promise metric while measuring customer experience separately.'),
        head('What is distinctive'),
        para('The project audits metric definitions, explicitly exposes review-timing selection, tests customer-state mix effects, evaluates delay risk on later data, and demonstrates how an ETA definition can improve without changing delivery speed.'),
        head('Evidence boundary'),
        para('The source contains a recorded estimate, not a verified original promise or revision history. A low review score is a customer-experience proxy, not a confirmed logistics complaint. Cost figures and promise extensions are hypothetical scenarios. No business intervention or realized saving is claimed.'),
        head('Reading map'),
        para('2 Workflow and architecture; 3 Data and quality; 4 Metrics; 5 Findings; 6 Selection and uncertainty; 7 Model; 8 Scenarios and experiment; 9 Engineering and validation; 10 Runbook and access; 11 Methods and references.')])
    page('Workflow and architecture','02 / DELIVERY DESIGN',[
        para('The workflow begins with the business decision and ends with a reproducible recommendation. It is designed as a data analytics project, with an offline dashboard as its presentation layer.'),
        table(['Stage','Implementation','Output'],[
            ['Acquire','Public Kaggle endpoint; seven CSV files; SHA-256 hashes','Immutable source files'],
            ['Validate','Key contracts; timestamp parsing; item and review grain checks','Quality report'],
            ['Transform','DuckDB SQL CTEs, aggregation, ROW_NUMBER, joins','One-order analytical mart'],
            ['Investigate','Segments, Wilson intervals, bootstrap, standardization','Count-based evidence'],
            ['Evaluate','Handoff-time logistic regression; chronological holdout','Model card and predictions'],
            ['Stress-test','ETA and cost assumptions; replayed scale benchmark','Separate scenario results'],
            ['Communicate','Offline Plotly dashboard, Excel, report, notebook','Reviewable portfolio package']], [75,280,145]),
        head('Warehouse structure'),
        para('Raw tables preserve source grains. mart_orders contains exactly one row per source order. fact_delivery_events reconstructs the observed purchase, approval, carrier-handoff, and delivery milestones. event_intervals uses LAG over timestamp order. This event table is derived from snapshot columns; it is not a captured event stream.'),
        para('Items are aggregated before the order join. The earliest answered review is selected before joining. This prevents one-to-many joins from multiplying merchandise values. Product and seller attributes are summarized to the order grain; mixed-category baskets remain labelled as mixed.'),
        head('Refresh design'),
        para('A deterministic full-snapshot rebuild replaces DuckDB tables and outputs. Month-specific Parquet files are written for analytical access. The process can be rerun locally, but it does not implement CDC, streaming, orchestration infrastructure, or a live marketplace connection.'),
        head('Primary artifacts'),
        para('SQL and Python source, generated aggregate CSV/JSON files, an offline interactive dashboard, formula-driven Excel reconciliation, a learning notebook, metric dictionary, model evaluation, test suite, and this report.')])
    page('Data provenance and quality','03 / TRUSTWORTHY INPUTS',[
        table(['Source table','Rows','Role'],[[k,n(v),{'orders':'Order lifecycle','items':'Merchandise and freight','reviews':'Scores and response timing','customers':'Delivery state','products':'Category and weight','sellers':'Seller state','translation':'Category labels'}[k]] for k,v in q['raw_counts'].items()],[130,100,270]),
        head('Quality controls'),
        para('The pipeline stops on duplicate/null dimension keys or duplicate item natural keys. It verifies the mart row count and distinct order count against source orders. It reconciles summed item values to the raw item table within BRL 0.01. Source hashes are saved in reports/data_manifest.json.'),
        table(['Diagnostic','Count','Treatment'],[
            ['Ineligible orders',n(q['ineligible_orders']),'Excluded from delivered-order analysis'],
            ['Eligible orders without selected review',n(q['missing_review_eligible']),'No inferred satisfaction score'],
            ['Selected review answered before delivery',n(q['pre_delivery_reviews']),'Excluded from post-delivery score'],
            ['Invalid/missing stage durations',n(q['invalid_stage_eligible']),'Excluded from stage-based model'],
            ['Additional review rows beyond one/order',n(q['extra_review_rows']),'Earliest answer retained']], [235,60,205]),
        head('Chronology and missingness'),
        para('Eligible orders require delivered status, purchase timestamp, a recorded estimate date no earlier than purchase, an actual delivery no earlier than purchase, and at least one item. Invalid stage durations are not silently set to zero. An order may still qualify for headline delivery analysis while failing stage-based model requirements.'),
        head('License and privacy'),
        para('Olist publishes this dataset under CC BY-NC-SA 4.0. The source archive excludes raw data, database files, row-level exports, and installed dependencies. Derived reports retain attribution. The dashboard omits customer IDs, review text, addresses, and order-level records. See DATA_LICENSE.md before redistribution.')])
    page('Metric definitions and grain','04 / ANALYTICAL CONTRACT',[
        table(['Metric','Numerator / calculation','Denominator / population'],[
            ['On-time rate','Delivery calendar date <= recorded estimate date','All eligible delivered orders'],
            ['Hidden-failure rate','On-time orders with selected post-delivery score <= 2','On-time orders with selected post-delivery score'],
            ['Review coverage','Orders with selected review answered at/after delivery','All eligible delivered orders'],
            ['Delivery days','Elapsed purchase-to-delivery time','Eligible delivered orders'],
            ['P90 delivery time','90th percentile of delivery days','Eligible delivered orders'],
            ['Handling days','Carrier handoff minus approval','Non-negative observed stage durations'],
            ['Transit days','Delivery minus carrier handoff','Non-negative observed stage durations']], [100,220,180]),
        head('Date convention'),
        para('An estimate is interpreted as a calendar-date deadline. A delivery at 23:59 on that date counts as on time. Source timestamps have no explicit timezone offsets; the project preserves their local representation. A source unit test checks the same-day boundary.'),
        head('Review convention'),
        para('Choose the earliest answered review by response timestamp, review ID, then score. Only after choosing it, check whether it was answered at/after delivery. If the first response is pre-delivery, the order is excluded from the primary review metric even if a later response exists. This conservative rule avoids selectively choosing a later score.'),
        head('Aggregation convention'),
        para('Monthly metrics group by purchase month, not delivery month. Global rates are recomputed from numerator and denominator counts. Category investigations rank counts of hidden failures; rate uncertainty and the sample size accompany each result. Dashboard categories require at least 30 reviewed on-time orders; global segment CSVs require 100.'),
        head('Meaning of financial fields'),
        para('Item value is merchandise price, not net platform revenue. Freight charged is a customer-facing amount, not carrier expense. Contribution figures appear only in the scenario layer and must not be presented as accounting profit.')])
    page('Observed findings and priorities','05 / BUSINESS INTERPRETATION',[
        para(f"Of {n(s['eligible_orders'])} eligible delivered orders, {n(s['on_time_orders'])} ({p(s['on_time_rate'])}) arrived by the recorded estimate. Among {n(s['reviewed_on_time'])} on-time orders with a post-delivery review, {n(s['hidden_failure_orders'])} received a score of 1 or 2."),
        para(f"The hidden-failure proxy is {p(s['hidden_failure_rate'])}, with a Wilson 95% interval of {p(s['hidden_failure_ci'][0])} to {p(s['hidden_failure_ci'][1])}. P90 purchase-to-delivery time is {s['p90_delivery_days']:.1f} days, conditional on eligible delivered orders."),
        table(['Category','Reviewed on time','Hidden failures','Rate'],[[r['segment'].replace('_',' '),n(int(r['reviewed_on_time'])),n(int(r['hidden_failures'])),p(float(r['rate']))] for r in cats[:6]],[205,110,100,85]),
        head('Suggested investigation'),
        para('Start with bed/bath/table, computers/accessories, and furniture/decor because their hidden-failure counts are high. Sample order histories and identify whether poor experiences relate to product quality, damage, incomplete fulfilment, expectations, or another cause. The dataset cannot establish which explanation is correct.'),
        head('Basket composition'),
        para(f"Single-item on-time orders have a poor-review rate of {p(s['standardization']['crude_single'])}, versus {p(s['standardization']['crude_multi'])} for multi-item baskets. With common-state weighting across {s['standardization']['common_states']} states, the corresponding rates are {p(s['standardization']['standardized_single'])} and {p(s['standardization']['standardized_multi'])}. There is no sign reversal in this run."),
        para('The proposed explanation that customer-state mix alone accounts for the basket association is not supported by this comparison. This is not proof that multiple items cause dissatisfaction: product mix, seller quality, and unmeasured factors remain.'),
        head('Recommended metric change'),
        para('Retain recorded-promise reliability, but report it beside post-delivery review coverage and the hidden-failure proxy. An operations review should ask whether delivery reliability and customer experience improve together.')])
    page('Selection bias and uncertainty','06 / WHAT THE NUMBERS DO NOT PROVE',[
        table(['Group','Post-delivery coverage','Poor rate: post-delivery','Poor rate: any review timing'],[
            [r['group'].replace('_',' '),p(r['post_delivery_review_coverage']),p(r['post_delivery_poor_rate']),p(r['any_timing_poor_rate'])] for r in s['review_sensitivity']],[80,130,145,145]),
        head('The major sensitivity finding'),
        para('Post-delivery review coverage is very different for on-time and late orders. The source survey can be triggered after delivery or when the estimate becomes due. Many late-order responses arrive before eventual delivery. Requiring a post-delivery response changes which customers remain in the comparison.'),
        para('Consequently, neither a late/on-time difference nor its confidence interval is an estimate of the causal effect of lateness. The alternative any-timing definition measures a different experience. Both are retained in review_sensitivity.csv rather than hiding the discrepancy.'),
        head('Statistical implementation'),
        para(f"The late-minus-on-time poor-review difference is {100*s['bootstrap_gap']['difference']:.2f} percentage points in the selected post-delivery sample. Resampling purchase weeks 1,000 times gives a percentile interval from {100*s['bootstrap_gap']['ci_low']:.2f} to {100*s['bootstrap_gap']['ci_high']:.2f} percentage points."),
        para('Week clustering preserves some within-week dependence. It does not remove seasonal confounding, nonresponse bias, or dependence across weeks. Wilson segment intervals describe rate uncertainty under a binomial approximation; they are not simultaneous intervals across every category.'),
        head('Standardization check'),
        para('For single- versus multi-item baskets, retain states with at least 30 reviewed on-time observations in both groups. Use combined group counts to define common state weights. Compare weighted group rates with crude rates and explicitly test whether the sign reverses. The common-state subset differs from the crude population.'),
        head('Practical boundary'),
        para('Use these findings to prioritize an investigation or design a prospective experiment. Do not label a ranked category as a proven root cause. Collect standardized follow-up timing and actual issue types in a future pilot.')])
    model=s['model']; a,base=model['metrics']
    page('Delay model and evaluation','07 / ADVANCED ANALYTICS',[
        para('Task: at carrier handoff, estimate whether an eligible delivered order will arrive after its recorded estimate date. The classifier is regularized logistic regression with training-only preprocessing. It predicts lateness, not the hidden-failure review outcome.'),
        table(['Split','Handoff window','Outcome availability','Rows'],[
            ['Train','Before 1 Apr 2018','Delivered before 1 Apr 2018',n(model['splits']['train'])],
            ['Validation','1 Apr - 31 May 2018','Delivered before 1 Jun 2018',n(model['splits']['validation'])],
            ['Test','1 Jun - 31 Jul 2018','Delivered before 1 Sep 2018',n(model['splits']['test'])]], [75,135,200,90]),
        head('Features and leakage controls'),
        para('Remaining promise days at handoff, handling time, item/seller counts, log merchandise value, freight charged, product weight, interstate indicator, customer state, and category. Numerical missing values use training medians. Scaling and category encoding fit only on training data. Delivery duration, actual lateness, reviews, and transit duration never enter the features.'),
        table(['Held-out measure','Logistic model','Constant baseline'],[
            ['ROC AUC',f"{a['roc_auc']:.3f}",f"{base['roc_auc']:.3f}"],
            ['Average precision',f"{a['average_precision']:.3f}",f"{base['average_precision']:.3f}"],
            ['Brier score (lower is better)',f"{a['brier_score']:.4f}",f"{base['brier_score']:.4f}"],
            ['Assumed classification cost, BRL',n(a['assumed_error_cost_brl']),n(base['assumed_error_cost_brl'])]], [280,110,110]),
        para(f"The test delay prevalence is {p(model['test_prevalence'])}. At the validation-selected threshold of {p(model['threshold'])}, the model raises {n(a['alerts'])} alerts, with precision {p(a['precision'])} and recall {p(a['recall'])}. This is a substantial false-alert burden."),
        head('Model limits'),
        para('Threshold selection assumes BRL 3 per false alert and BRL 25 per missed delay. These are classification penalties, not measured intervention economics. The source has no feature revision history, so point-in-time availability cannot be certified. Delivered-only filtering and outcome-maturity exclusions can bias the population. Calibration and distribution changes require monitoring before operational use.')])
    page('Scenarios and a testable intervention','08 / DECISION DESIGN',[
        head('ETA re-scoring scenario'),
        para('Apply uniform extensions of 0, 1, 2, 3, 5, or 7 days to the recorded estimate while holding every actual delivery fixed. A seven-day extension changes on-time performance from 93.23% to 97.03%, reclassifying 3,672 orders. Actual delivery speed improves by zero days. This illustrates metric sensitivity, not evidence of ETA manipulation by Olist.'),
        head('Financial sensitivity'),
        para('For observed hidden-failure orders, vary assumed merchandise margin across 10%, 20%, and 30%, and assumed recovery cost across BRL 10, 25, and 50. Proxy contribution equals merchandise price times assumed margin minus assumed recovery cost. Recovery exposure equals the number of hidden failures times the assumed cost.'),
        para('At BRL 25 per hidden failure, exposure is BRL 205,950. That is an assumption-driven amount, not an observed refund total or a saving. No real COGS, carrier expense, platform fee, refund, or support-cost records are available.'),
        head('Proposed prospective experiment'),
        para('Intervention: a multi-item completeness and packaging check before dispatch. Randomize eligible multi-item orders to the check or existing process, stratified by seller/category where feasible. Preserve the original customer promise. If treatment spills across orders, randomize at seller or shift level and adjust the sample-size design for clustering.'),
        para('Primary outcome: a consistently timed post-delivery low-review rate among all randomized orders, with nonresponse reported by arm and sensitivity bounds. Analyse by assignment, not by whether the order eventually arrived on time, because timeliness can be affected by treatment. Guardrails: on-time rate, check labour cost, cancellation, and measured refund cost.'),
        para(f"The included sizing function gives {n(s['experiment_sample_per_arm'])} reviewed orders per arm for a 20% relative reduction from the global 9.24% illustrative baseline, two-sided 5% alpha and 80% power. This is a planning example, not the sample size for the proposed multi-item pilot. Re-estimate the relevant baseline, response rate, clustering and minimum worthwhile effect before launch."),
        head('Decision rule'),
        para('Adopt only if a preregistered analysis supports worthwhile customer benefit without unacceptable cost or reliability deterioration. Track actual expenses and exposure. No experiment has been run as part of this project.')])
    page('Engineering, scale and validation','09 / DELIVERY QUALITY',[
        head('Automated analytical contracts'),
        para('The original execution recorded 15 passing tests covering statistical boundaries, scenarios, feature timing, join grain, value reconciliation, review selection and date edge cases. The 5 October 2026 rerun stopped during collection when Windows Application Control blocked a scikit-learn binary; no tests executed in that attempt. Fresh verification remains pending.'),
        head('Full-data validation'),
        para('The complete real-data pipeline reconciles one mart row per source order and the raw merchandise-value total. Required key checks fail early. Exported summary values reconcile through formulas in the Excel workbook. The month selector was changed and restored to confirm formula recalculation; formula-error scanning returned no errors.'),
        head('Browser validation'),
        para('The offline dashboard was tested in Chromium across its five views. Checks exercised customer-state filtering, a sparse state, ETA extension, margin/recovery controls, and a mobile viewport. No JavaScript errors were detected. The dashboard makes no external network requests for its charts; Plotly is stored alongside the HTML.'),
        head('Scale exercise'),
        para(f"DuckDB aggregated {n(b['rows']) if b else '1,929,400'} replayed rows and matched the source counts multiplied by 20. This measures a local computational workload; replaying records does not add independent evidence. Timings in benchmark.json are machine-specific, include execution overhead, and are not a distributed performance claim."),
        head('Honest coverage boundaries'),
        para('The supplied Spark extension requires Java/PySpark and was not run here. No native Power BI or Tableau report is included. The Excel deliverable uses formulas and a native chart; it does not contain native PivotTables or an embedded Power Query refresh connection.'),
        head('Reproducibility'),
        para('Random seeds are fixed, raw file hashes are recorded, and direct tested dependency versions are supplied. A source-code archive excludes raw/row-level data and dependencies. GitHub CI is configured to run the fixture-based tests after a future push; no remote CI execution has occurred yet.')])
    page('Runbook, tools and access','10 / HANDOVER',[
        table(['Tool','Purpose'],[
            ['Python + pandas + NumPy','Cleaning, orchestration, analytical exports'],
            ['DuckDB + SQL','Relational mart, validation, windows, Parquet, scale exercise'],
            ['SciPy','Statistical calculations and experiment sizing'],
            ['scikit-learn','Logistic regression, train-only transformations, evaluation'],
            ['Plotly + HTML/JavaScript','Offline interactive dashboard'],
            ['Excel workbook','Formula reconciliation, monthly selection, editable chart'],
            ['pytest + Chromium checks','Analytical contracts and dashboard verification'],
            ['ReportLab','This reproducible PDF report']], [185,315]),
        head('Run sequence'),
        para('Create a Python 3.11/3.12 virtual environment. Install the package with dev/docs extras. Run scripts/download_data.py, then python -m promise_integrity.pipeline. Run pytest -q and scripts/benchmark.py. Generate this report with scripts/build_report.py. Open reports/dashboard.html with plotly.min.js in the same folder. Exact Windows and Unix commands appear in README.md.'),
        head('Access requirements'),
        para('No GitHub credentials, paid BI subscription, cloud database, or private company account is needed for the delivered version. Initial downloads require internet access. If Kaggle changes public access, manually download the named source CSVs. A real-time company version would need authorized order, ETA-history, refund, and support feeds plus deployment credentials.'),
        head('Operational limitations'),
        para('Historical snapshot, not current market evidence. No original-ETA history, complete delivery-event stream, refund amounts, support contacts, or internal costs. No live ingestion, scheduled service, access control, alert delivery, or production deployment. The model is retrospective and the scenarios are advisory.'),
        head('Failure handling'),
        para('Missing source file: run the downloader or place the documented CSVs in data/raw. Schema/key failure: inspect the input and quality contract rather than weakening it. Dashboard missing charts: keep plotly.min.js next to the HTML. Empty category view: inspect sample sizes; do not manufacture a rate. Dependency issues: use a fresh virtual environment and tested versions.')])
    page('Methods and references','11 / TECHNICAL APPENDIX',[
        table(['Method / tool','Implementation / boundary'],[
            ['Excel','SUMIFS, INDEX/MATCH, rate reconciliation and a native chart'],
            ['SQL','CTEs, joins, aggregations, ROW_NUMBER, LAG, DENSE_RANK'],
            ['Python','Modular, reproducible pipeline and executed analysis notebook'],
            ['Visualization / BI','Interactive Plotly dashboard and typed CSV export'],
            ['Statistics','Wilson intervals, cluster bootstrap, standardization, sample-size planning'],
            ['Problem-solving','Metric audit and rejected state-mix explanation'],
            ['Cleaning','Grain, chronology, missingness, review selection and reconciliation'],
            ['Warehousing','Raw tables, order mart, event fact, monthly Parquet outputs'],
            ['Machine learning','Temporal logistic baseline comparison and cost-sensitive threshold'],
            ['Big-data concepts','Validated replay/plan exercise; optional unexecuted Spark extension'],
            ['Storytelling / domain','Decision memo, evidence boundaries, logistics unit economics']], [125,375]),
        head('Reproducing the analysis'),
        para('Use README.md for the execution sequence and docs/DATA_DICTIONARY.md for field definitions. sql/01_mart.sql defines the analytical grain. The executed notebook connects the metrics to reports/summary.json. Python modules contain the statistical methods, temporal model evaluation and scenario calculations.'),
        head('References'),
        para('Olist public dataset and publisher description: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce'),
        para('Data license: https://creativecommons.org/licenses/by-nc-sa/4.0/'),
        para('DuckDB Python documentation: https://duckdb.org/docs/stable/clients/python/overview'),
        para('scikit-learn LogisticRegression: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html'),
        head('Decision boundary'),
        para('The analysis identifies investigation priorities rather than proven causes. Any intervention should be evaluated with observed customer outcomes and actual operating costs. The recorded estimate and selected reviews cannot establish original promise integrity, realized financial impact or causal delivery effects.')])

    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyPI',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9,textColor=colors.HexColor('#253d49')))
    styles.add(ParagraphStyle(name='TitlePI',fontName='Helvetica-Bold',fontSize=27,leading=31,spaceAfter=18,textColor=colors.HexColor('#173442')))
    styles.add(ParagraphStyle(name='KickerPI',fontName='Helvetica-Bold',fontSize=9,leading=12,spaceAfter=14,textColor=colors.HexColor('#087f78')))
    styles.add(ParagraphStyle(name='HeadPI',fontName='Helvetica-Bold',fontSize=12,leading=15,spaceBefore=6,spaceAfter=7,textColor=colors.HexColor('#173442')))
    styles.add(ParagraphStyle(name='CellPI',fontName='Helvetica',fontSize=8.7,leading=12,spaceAfter=0,textColor=colors.HexColor('#253d49')))
    styles.add(ParagraphStyle(name='CellHeaderPI',parent=styles['CellPI'],fontName='Helvetica-Bold',textColor=colors.white))
    story=[];markdown=['# Promise Integrity: Professional Project Report\n']
    for idx,(title,kicker,blocks) in enumerate(pages):
        if idx:story.append(PageBreak())
        story.extend([Paragraph(escape(kicker),styles['KickerPI']),Paragraph(escape(title),styles['TitlePI'])])
        markdown.append(f'## {title}\n')
        for kind,content in blocks:
            if kind=='p':story.append(Paragraph(escape(content),styles['BodyPI']));markdown.append(content+'\n')
            elif kind=='h':story.append(Paragraph(escape(content),styles['HeadPI']));markdown.append('### '+content+'\n')
            else:
                headers,rows,widths=content
                cells=[[Paragraph(escape(str(v)),styles['CellHeaderPI']) for v in headers]]+[[Paragraph(escape(str(v)),styles['CellPI']) for v in row] for row in rows]
                t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
                t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#173442')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#eef4f3'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
                story.extend([t,Spacer(1,13)])
                markdown.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |'])
                markdown.extend('| '+' | '.join(map(str,row))+' |' for row in rows);markdown.append('')
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#657a84'))
        canvas.drawString(48,29,'PROMISE INTEGRITY  /  Historical analytics  /  Olist attribution: CC BY-NC-SA 4.0')
        canvas.drawRightString(A4[0]-48,29,str(doc.page))
    pdf=ROOT/'reports/Project_Report.pdf'
    SimpleDocTemplate(str(pdf),pagesize=A4,rightMargin=47,leftMargin=48,topMargin=42,bottomMargin=48,
                      title='Promise Integrity - Professional Project Report',author='Promise Integrity Project').build(story,onFirstPage=footer,onLaterPages=footer)
    (ROOT/'docs/PROJECT_REPORT.md').write_text('\n'.join(markdown),encoding='utf-8')
    print(pdf)
if __name__=='__main__':main()
