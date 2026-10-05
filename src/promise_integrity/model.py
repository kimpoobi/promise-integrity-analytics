"""Temporal, outcome-matured evaluation of delay risk at carrier handoff."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.calibration import calibration_curve

NUMERIC = ['promise_remaining_days', 'handling_days', 'item_count', 'seller_count',
           'log_item_value', 'freight_charged_brl', 'mean_weight_g', 'interstate']
CATEGORICAL = ['customer_state', 'category']

def prepare(df):
    x=df[df.valid_stages & df.order_delivered_carrier_date.notna()].copy()
    x['promise_remaining_days']=(x.order_estimated_delivery_date.dt.normalize()+pd.Timedelta(days=1)-
                                  x.order_delivered_carrier_date).dt.total_seconds()/86400
    x['log_item_value']=np.log1p(x.item_value_brl)
    x['target']=(~x.on_time).astype(int)
    return x

def temporal_splits(x):
    handoff=x.order_delivered_carrier_date
    delivery=x.order_delivered_customer_date
    # Labels used for fitting/tuning must already exist by the next period's start.
    return (x[(handoff<'2018-04-01') & (delivery<'2018-04-01')],
            x[(handoff>='2018-04-01') & (handoff<'2018-06-01') & (delivery<'2018-06-01')],
            x[(handoff>='2018-06-01') & (handoff<'2018-08-01') & (delivery<'2018-09-01')])

def cost(y, pred, false_positive=3., false_negative=25.):
    y=np.asarray(y, dtype=bool); pred=np.asarray(pred,dtype=bool)
    return float(((pred & ~y)*false_positive + (~pred & y)*false_negative).sum())

def fit_evaluate(df, reports):
    train, val, test=temporal_splits(prepare(df))
    for label, part in [('train',train),('validation',val),('test',test)]:
        if len(part)<100 or part.target.nunique()!=2:
            raise ValueError(f'Insufficient outcome-matured rows/classes in {label}')
    medians=train[NUMERIC].median()
    train, val, test = [part.copy() for part in (train,val,test)]
    for part in (train,val,test):
        part[NUMERIC]=part[NUMERIC].fillna(medians)
        part[CATEGORICAL]=part[CATEGORICAL].fillna('unknown')
    transform=ColumnTransformer([
        ('numeric',StandardScaler(),NUMERIC),
        ('category',OneHotEncoder(handle_unknown='ignore', min_frequency=50),CATEGORICAL)])
    model=make_pipeline(transform,LogisticRegression(max_iter=1500,C=.3,random_state=42))
    model.fit(train[NUMERIC+CATEGORICAL],train.target)
    val_p=model.predict_proba(val[NUMERIC+CATEGORICAL])[:,1]
    thresholds=np.linspace(.01,.99,99)
    costs=[cost(val.target,val_p>=t) for t in thresholds]
    threshold=float(thresholds[int(np.argmin(costs))])
    p=model.predict_proba(test[NUMERIC+CATEGORICAL])[:,1]
    prevalence=float(train.target.mean())
    baseline=np.full(len(test),prevalence)
    rows=[]
    for label, probs, decisions in [('logistic',p,p>=threshold),
        ('training_prevalence',baseline,np.full(len(test), cost(val.target,np.ones(len(val)))<cost(val.target,np.zeros(len(val)))) )]:
        rows.append({'model':label,'roc_auc':float(roc_auc_score(test.target,probs)),
                     'average_precision':float(average_precision_score(test.target,probs)),
                     'brier_score':float(brier_score_loss(test.target,probs)),
                     'assumed_error_cost_brl':cost(test.target,decisions),
                     'alerts':int(decisions.sum()),
                     'precision':float(test.target[decisions].mean()) if decisions.any() else None,
                     'recall':float((test.target.to_numpy().astype(bool)&decisions).sum()/test.target.sum())})
    metrics={'splits':{k:len(v) for k,v in [('train',train),('validation',val),('test',test)]},
             'threshold':threshold, 'false_positive_cost_assumed':3,'false_negative_cost_assumed':25,
             'test_prevalence':float(test.target.mean()),'metrics':rows,
             'features':NUMERIC+CATEGORICAL,
             'limitation':'Static dataset and delivered-only population; not a production replay. Error costs are assumed, not realized savings.'}
    frac, mean=calibration_curve(test.target,p,n_bins=10,strategy='quantile')
    pd.DataFrame({'mean_prediction':mean,'observed_rate':frac}).to_csv(reports/'calibration.csv',index=False)
    coef=pd.DataFrame({'feature':transform.get_feature_names_out(),'coefficient':model[-1].coef_[0]})
    coef.sort_values('coefficient').to_csv(reports/'model_coefficients.csv',index=False)
    predictions=test[['order_id','order_delivered_carrier_date','target']].copy()
    predictions['probability']=p
    predictions['alert']=p>=threshold
    predictions.to_csv(reports/'model_predictions.csv',index=False)
    pd.DataFrame({'threshold':thresholds,'validation_assumed_error_cost':costs}).to_csv(reports/'thresholds.csv',index=False)
    return metrics
