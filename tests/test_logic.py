from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import pytest
from promise_integrity.analytics import wilson, eta_scenarios, cost_scenarios, segment_table
from promise_integrity.model import temporal_splits, cost, NUMERIC, CATEGORICAL

def test_wilson_zero_denominator_is_unknown():
    assert wilson(0,0)==(None,None)

def test_small_segment_returns_typed_empty_table():
    frame=pd.DataFrame({'on_time':[True],'poor_review':[True],'category':['tiny']})
    result=segment_table(frame,'category',min_n=30)
    assert result.empty and 'hidden_failures' in result.columns

@pytest.mark.parametrize('k,n',[(0,10),(10,10),(4,10),(80,100)])
def test_wilson_bounds_contain_observed_rate(k,n):
    low,high=wilson(k,n)
    assert 0<=low<=k/n<=high<=1

def test_eta_change_relabels_without_changing_deliveries():
    df=pd.DataFrame({'lateness_days':[-1,0,1,4,8],'on_time':[True,True,False,False,False]})
    original=df.copy(deep=True)
    scenarios=eta_scenarios(df)
    assert scenarios.iloc[0].reclassified_orders==0
    assert scenarios.iloc[-1].reclassified_orders==2
    assert scenarios.rescored_on_time_rate.is_monotonic_increasing
    pd.testing.assert_frame_equal(df,original)

def test_cost_only_uses_on_time_observed_poor_reviews():
    df=pd.DataFrame({'on_time':[True,True,False,True],'poor_review':pd.array([True,False,True,None],dtype='boolean'),
                     'item_value_brl':[100,100,100,100]})
    result=cost_scenarios(df)
    assert result.hidden_failure_orders.eq(1).all()
    assert result.query('margin_assumed==0.1 and recovery_brl_assumed==25').negative_proxy_orders.iloc[0]==1

def test_error_cost_counts_only_false_decisions():
    assert cost([1,0,1,0],[0,1,1,0])==28

def test_model_features_exclude_future_outcomes():
    forbidden={'lateness_days','delivery_days','transit_days','review_score','poor_review','on_time','target'}
    assert not forbidden.intersection(NUMERIC+CATEGORICAL)

def test_temporal_split_drops_unavailable_training_labels():
    x=pd.DataFrame({'order_delivered_carrier_date':pd.to_datetime(['2018-03-01','2018-03-30','2018-04-01','2018-06-01']),
                    'order_delivered_customer_date':pd.to_datetime(['2018-03-05','2018-04-05','2018-04-03','2018-06-03'])})
    train,val,test=temporal_splits(x)
    assert train.index.tolist()==[0]
    assert val.index.tolist()==[2]
    assert test.index.tolist()==[3]

@pytest.fixture
def mart():
    c=duckdb.connect()
    orders=[]
    for oid,status,delivered,estimate in [('a','delivered','2018-01-05 23:59','2018-01-05'),
        ('b','delivered','2018-01-06','2018-01-05'),('c','canceled',None,'2018-01-05'),
        ('d','delivered','2018-01-04','2018-01-05'),('e','delivered','2017-12-31','2018-01-05')]:
        orders.append([oid,'customer',status,'2018-01-01','2018-01-01 01:00','2018-01-02',delivered,estimate])
    order_cols=['order_id','customer_id','order_status','order_purchase_timestamp','order_approved_at',
                'order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date']
    o=pd.DataFrame(orders,columns=order_cols)
    for col in order_cols[3:]:o[col]=pd.to_datetime(o[col],format='mixed')
    tables={'orders':o,
     'customers':pd.DataFrame([['customer','SP']],columns=['customer_id','customer_state']),
     'products':pd.DataFrame([['product','cat',500]],columns=['product_id','product_category_name','product_weight_g']),
     'sellers':pd.DataFrame([['seller','RJ']],columns=['seller_id','seller_state']),
     'translation':pd.DataFrame([['cat','category']],columns=['product_category_name','product_category_name_english']),
     'items':pd.DataFrame([[oid,'product','seller',100.,10.] for oid in ['a','a','b','c','d','e']],columns=['order_id','product_id','seller_id','price','freight_value'])}
    reviews=pd.DataFrame([['r1','a',1,'2018-01-07','2018-01-06'],['r2','a',5,'2018-01-08','2018-01-07'],
                          ['r3','b',1,'2018-01-03','2018-01-03']],
                        columns=['review_id','order_id','review_score','review_answer_timestamp','review_creation_date'])
    for col in ['review_answer_timestamp','review_creation_date']:reviews[col]=pd.to_datetime(reviews[col])
    tables['reviews']=reviews
    for name,frame in tables.items():
        c.register('incoming',frame);c.execute(f'CREATE TABLE raw_{name} AS SELECT * FROM incoming')
    c.execute((Path(__file__).parents[1]/'sql/01_mart.sql').read_text())
    yield c.execute('SELECT * FROM mart_orders ORDER BY order_id').df().set_index('order_id')
    c.close()

def test_join_grain_and_item_value(mart):
    assert len(mart)==5 and mart.index.is_unique
    assert mart.loc['a','item_value_brl']==200
    assert mart.item_value_brl.sum()==600

def test_same_calendar_day_counts_on_time(mart):
    assert mart.loc['a','on_time']
    assert not mart.loc['b','on_time']

def test_review_dedup_and_temporal_eligibility(mart):
    assert mart.loc['a','post_delivery_score']==1
    assert pd.isna(mart.loc['b','poor_review'])
    assert pd.isna(mart.loc['d','poor_review'])

def test_cancelled_and_impossible_dates_excluded(mart):
    assert not mart.loc['c','eligible']
    assert not mart.loc['e','eligible']
