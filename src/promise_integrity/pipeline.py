"""Run with python -m promise_integrity.pipeline from the repository root."""
from pathlib import Path
import json
import hashlib
import argparse
import time
import duckdb
import pandas as pd
from .analytics import (segment_table, wilson, cluster_bootstrap_gap, standardization,
                        eta_scenarios, cost_scenarios, sample_size)
from .model import fit_evaluate

ROOT=Path(__file__).resolve().parents[2]
TABLES={'orders':'olist_orders_dataset.csv','items':'olist_order_items_dataset.csv',
        'reviews':'olist_order_reviews_dataset.csv','customers':'olist_customers_dataset.csv',
        'products':'olist_products_dataset.csv','sellers':'olist_sellers_dataset.csv',
        'translation':'product_category_name_translation.csv'}

def load_raw(con, raw):
    counts={}
    for name, filename in TABLES.items():
        path=raw/filename
        if not path.exists():
            raise FileNotFoundError(f'{path} missing. Run python scripts/download_data.py')
        frame=pd.read_csv(path)
        for column in frame:
            if column.endswith(('_timestamp','_date')) or column=='order_approved_at':
                frame[column]=pd.to_datetime(frame[column],errors='coerce')
        counts[name]=len(frame)
        con.register('incoming',frame)
        con.execute(f'CREATE OR REPLACE TABLE raw_{name} AS SELECT * FROM incoming')
    # Stop before joins if grain contracts fail, rather than silently multiplying values.
    for name,key in [('orders','order_id'),('customers','customer_id'),('products','product_id'),
                     ('sellers','seller_id'),('translation','product_category_name')]:
        bad=con.execute(f'SELECT COUNT(*)-COUNT(DISTINCT {key}) FROM raw_{name}').fetchone()[0]
        if bad:
            raise ValueError(f'Null or duplicate dimension key in raw_{name}: {key}')
    if con.execute('SELECT COUNT(*) FROM (SELECT order_id,order_item_id,COUNT(*) n FROM raw_items GROUP BY ALL HAVING n>1)').fetchone()[0]:
        raise ValueError('Duplicate item natural key')
    return counts

def quality_checks(con, counts):
    n=con.execute('SELECT COUNT(*) FROM mart_orders').fetchone()[0]
    distinct=con.execute('SELECT COUNT(DISTINCT order_id) FROM mart_orders').fetchone()[0]
    raw_total=con.execute('SELECT SUM(price) FROM raw_items').fetchone()[0]
    mart_total=con.execute('SELECT SUM(item_value_brl) FROM mart_orders').fetchone()[0]
    assert n==distinct==counts['orders'], 'Order-grain reconciliation failed'
    assert abs(raw_total-mart_total)<.01, 'Item revenue reconciliation failed'
    assert con.execute('SELECT COUNT(*) FROM raw_reviews WHERE review_score NOT BETWEEN 1 AND 5').fetchone()[0]==0
    checks={'raw_counts':counts,'order_grain_pass':True,'item_value_reconciled':True,
            'item_value_difference_brl':round(raw_total-mart_total,6)}
    for key,query in {
        'ineligible_orders':'SELECT COUNT(*) FROM mart_orders WHERE NOT COALESCE(eligible,FALSE)',
        'missing_review_eligible':'SELECT COUNT(*) FROM mart_orders WHERE eligible AND review_score IS NULL',
        'pre_delivery_reviews':'SELECT COUNT(*) FROM mart_orders WHERE eligible AND review_answer_timestamp < order_delivered_customer_date',
        'invalid_stage_eligible':'SELECT COUNT(*) FROM mart_orders WHERE eligible AND NOT valid_stages',
        'extra_review_rows':'SELECT COUNT(*)-COUNT(DISTINCT order_id) FROM raw_reviews',
        'items_missing_product':'SELECT COUNT(*) FROM raw_items i LEFT JOIN raw_products p USING(product_id) WHERE p.product_id IS NULL',
        'orders_missing_customer':'SELECT COUNT(*) FROM raw_orders o LEFT JOIN raw_customers c USING(customer_id) WHERE c.customer_id IS NULL'
    }.items():
        checks[key]=con.execute(query).fetchone()[0]
    return checks

def run(root=ROOT):
    start=time.perf_counter()
    reports=root/'reports'; reports.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect(str(root/'data/warehouse.duckdb'))
    counts=load_raw(con,root/'data/raw')
    con.execute((root/'sql/01_mart.sql').read_text(encoding='utf-8'))
    quality=quality_checks(con,counts)
    df=con.execute('SELECT * FROM mart_orders WHERE eligible ORDER BY order_purchase_timestamp, order_id').df()
    reviewed=df[df.poor_review.notna()]
    ontime=reviewed[reviewed.on_time]
    k=int(ontime.poor_review.sum()); lo,hi=wilson(k,len(ontime))
    summary={'source':'Olist public dataset, 2016-2018; historical snapshot',
             'raw_orders':counts['orders'],'eligible_orders':len(df),
             'purchase_min':str(df.order_purchase_timestamp.min()),'purchase_max':str(df.order_purchase_timestamp.max()),
             'on_time_orders':int(df.on_time.sum()),'on_time_rate':float(df.on_time.mean()),
             'reviewed_orders':len(reviewed),'review_coverage':len(reviewed)/len(df),
             'reviewed_on_time':len(ontime),'hidden_failure_orders':k,
             'hidden_failure_rate':k/len(ontime),'hidden_failure_ci':[lo,hi],
             'poor_review_rate_late':float(reviewed.loc[~reviewed.on_time,'poor_review'].mean()),
             'p90_delivery_days':float(df.delivery_days.quantile(.9)),
             'bootstrap_gap':cluster_bootstrap_gap(df), 'standardization':standardization(df),
             'experiment_sample_per_arm':sample_size(k/len(ontime),k/len(ontime)*.8)}
    sensitivity=[]
    for label,part in [('on_time',df[df.on_time]),('late',df[~df.on_time])]:
        any_review=part[part.review_score.notna()]
        post=part[part.poor_review.notna()]
        sensitivity.append({'group':label,'eligible_orders':len(part),
            'post_delivery_review_coverage':len(post)/len(part),
            'post_delivery_poor_rate':float(post.poor_review.mean()),
            'any_timing_review_n':len(any_review),
            'any_timing_poor_rate':float((any_review.review_score<=2).mean())})
    summary['review_sensitivity']=sensitivity
    pd.DataFrame(sensitivity).to_csv(reports/'review_sensitivity.csv',index=False)
    monthly=con.execute('SELECT * FROM monthly_kpis ORDER BY purchase_month').df()
    monthly.to_csv(reports/'monthly_kpis.csv',index=False)
    for col,name in [('customer_state','states'),('category','categories'),('basket_band','baskets')]:
        segment_table(df,col).to_csv(reports/f'{name}.csv',index=False)
    eta_scenarios(df).to_csv(reports/'eta_scenarios.csv',index=False)
    cost_scenarios(df).to_csv(reports/'cost_scenarios.csv',index=False)
    summary['model']=fit_evaluate(df,reports)
    # Portable BI export excludes customer identities, review text, and unnecessary raw fields.
    columns=['order_id','purchase_month','customer_state','category','basket_band','item_count',
             'item_value_brl','freight_charged_brl','promise_days','lateness_days','delivery_days',
             'handling_days','transit_days','valid_stages','on_time','post_delivery_score','poor_review']
    df[columns].to_csv(reports/'order_analysis.csv',index=False)
    export_frame=df[columns]
    con.register('export_frame',export_frame)
    parquet_path=(reports/'order_analysis.parquet').as_posix().replace("'","''")
    con.execute(f"COPY export_frame TO '{parquet_path}' (FORMAT PARQUET)")
    processed=root/'data/processed'; processed.mkdir(parents=True,exist_ok=True)
    # Immutable month files overwritten deterministically. Source is a full snapshot, not a CDC feed.
    for month,part in df[columns].groupby('purchase_month'):
        con.register('month_frame',part)
        part_path=(processed/f'orders_{month:%Y-%m}.parquet').as_posix().replace("'","''")
        con.execute(f"COPY month_frame TO '{part_path}' (FORMAT PARQUET)")
    quality['runtime_seconds']=round(time.perf_counter()-start,2)
    for name,data in [('summary',summary),('quality',quality)]:
        (reports/f'{name}.json').write_text(json.dumps(data,indent=2,default=str,allow_nan=False),encoding='utf-8')
    # Copy verifiable source hashes, not raw source data, into versionable reports.
    manifest={'source_url':'https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce',
              'license':'CC BY-NC-SA 4.0','sha256':{f:hashlib.sha256((root/'data/raw'/f).read_bytes()).hexdigest() for f in TABLES.values()}}
    (reports/'data_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    con.close()
    from .dashboard import build_dashboard
    build_dashboard(root)
    print(json.dumps({'eligible_orders':len(df),'hidden_failures':k,'runtime_seconds':quality['runtime_seconds']},indent=2))
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=ROOT)
    run(parser.parse_args().root)
