"""Transparent inference and scenario functions; observed and assumed evidence stay separate."""
import numpy as np
import pandas as pd
from scipy.stats import norm


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (None, None)
    p = k/n
    centre = (p + z*z/(2*n))/(1+z*z/n)
    radius = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return (0. if k==0 else max(0., centre-radius)), (1. if k==n else min(1., centre+radius))


def segment_table(df, column, min_n=100):
    rows = []
    for key, group in df[df.on_time & df.poor_review.notna()].groupby(column):
        n, k = len(group), int(group.poor_review.sum())
        if n >= min_n:
            lo, hi = wilson(k, n)
            rows.append({'segment': str(key), 'reviewed_on_time': n, 'hidden_failures': k,
                         'rate': k/n, 'ci_low': lo, 'ci_high': hi})
    return pd.DataFrame(rows,columns=['segment','reviewed_on_time','hidden_failures','rate','ci_low','ci_high']).sort_values('hidden_failures', ascending=False)


def cluster_bootstrap_gap(df, iterations=1000, seed=42):
    """Resample purchase weeks; preserves some within-week dependence. Late minus on-time."""
    x = df[df.poor_review.notna()].copy()
    x['week'] = x.order_purchase_timestamp.dt.to_period('W').astype(str)
    table = x.groupby(['week', 'on_time']).poor_review.agg(['sum', 'count']).unstack(fill_value=0)
    rng = np.random.default_rng(seed)
    gaps = []
    for _ in range(iterations):
        t = table.iloc[rng.integers(0, len(table), len(table))].sum()
        if t[('count', False)] and t[('count', True)]:
            gaps.append(t[('sum', False)]/t[('count', False)] - t[('sum', True)]/t[('count', True)])
    observed = float(x.loc[~x.on_time, 'poor_review'].mean() - x.loc[x.on_time, 'poor_review'].mean())
    return {'difference': observed, 'ci_low': float(np.quantile(gaps, .025)),
            'ci_high': float(np.quantile(gaps, .975)), 'iterations': iterations,
            'method': 'purchase-week cluster bootstrap; association, not causation'}


def standardization(df):
    """Compare single/multi-item hidden-failure rates using common customer-state weights."""
    x = df[df.on_time & df.poor_review.notna()]
    rates = x.groupby(['customer_state', 'basket_band']).poor_review.agg(['mean','count']).unstack()
    common = rates.dropna()
    common = common[(common['count']['1 item'] >= 30) & (common['count']['2+ items'] >= 30)]
    weights = common['count'].sum(axis=1)
    weights = weights/weights.sum()
    crude = x.groupby('basket_band').poor_review.mean()
    a = float((common['mean']['1 item']*weights).sum())
    b = float((common['mean']['2+ items']*weights).sum())
    gap = float(crude['2+ items']-crude['1 item'])
    return {'crude_single': float(crude['1 item']), 'crude_multi': float(crude['2+ items']),
            'standardized_single': a, 'standardized_multi': b, 'common_states': len(common),
            'sign_reversal': bool(gap*(b-a)<0),
            'note': 'Common-state direct standardization; no causal interpretation. Different populations for crude and standardized estimates.'}


def eta_scenarios(df):
    """Counterfactual re-scoring only: deliveries never move and no ETA events are invented."""
    return pd.DataFrame([{'extension_days_assumed': d, 'orders': len(df),
                          'recorded_on_time_rate': float(df.on_time.mean()),
                          'rescored_on_time_rate': float((df.lateness_days <= d).mean()),
                          'reclassified_orders': int(((df.lateness_days > 0)&(df.lateness_days <= d)).sum()),
                          'evidence': 'scenario_only'} for d in [0,1,2,3,5,7]])


def cost_scenarios(df):
    """Proxy contribution = assumed merchandise margin - assumed recovery cost.
    Freight charged is not treated as the carrier's cost. No real refunds are available.
    """
    x = df[df.on_time & df.poor_review.fillna(False)]
    rows=[]
    for margin in [.1,.2,.3]:
        for recovery in [10,25,50]:
            contribution=x.item_value_brl*margin-recovery
            rows.append({'margin_assumed':margin,'recovery_brl_assumed':recovery,
                         'hidden_failure_orders':len(x), 'recovery_exposure_brl':len(x)*recovery,
                         'negative_proxy_orders':int((contribution<0).sum()),
                         'proxy_contribution_brl':float(contribution.sum()),'evidence':'assumptions_only'})
    return pd.DataFrame(rows)


def sample_size(p1, p2, alpha=.05, power=.8):
    pooled=(p1+p2)/2
    return int(np.ceil(((norm.ppf(1-alpha/2)*np.sqrt(2*pooled*(1-pooled))+
                         norm.ppf(power)*np.sqrt(p1*(1-p1)+p2*(1-p2))) / abs(p2-p1))**2))
