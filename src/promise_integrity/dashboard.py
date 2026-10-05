"""Generate a portable, offline dashboard with no server or account required."""
import json
from pathlib import Path
import pandas as pd
import duckdb
from plotly.offline import get_plotlyjs
from .analytics import wilson, segment_table

def build_dashboard(root):
    reports=root/'reports'
    with duckdb.connect() as con:
        df=con.execute('SELECT * FROM read_parquet(?)',[str(reports/'order_analysis.parquet')]).df()
    summary=json.loads((reports/'summary.json').read_text())
    quality=json.loads((reports/'quality.json').read_text())
    views={}
    for state in ['All states']+sorted(df.customer_state.unique().tolist()):
        d=df if state=='All states' else df[df.customer_state==state]
        r=d[d.on_time & d.poor_review.notna()]
        k=int(r.poor_review.sum()); n=len(r); ci=wilson(k,n)
        monthly=[]
        for month,m in d.groupby('purchase_month'):
            reviewed=m[m.on_time & m.poor_review.notna()]
            monthly.append({'month':str(month)[:10], 'on_time':float(m.on_time.mean()),
                            'hidden':float(reviewed.poor_review.mean()) if len(reviewed) else None,'n':len(m)})
        segments=segment_table(d,'category',min_n=30)
        views[state]={'n':len(d),'on_time':float(d.on_time.mean()),'reviewed':n,'hidden':k,
                      'rate':k/n if n else None,'ci':ci,'monthly':monthly,
                      'categories':segments.head(10).to_dict('records'),
                      'coverage':float(d.poor_review.notna().mean()),
                      'lateness':[int((d.lateness_days.between(a,b)).sum()) for a,b in [(-1000,0),(1,3),(4,7),(8,1000)]]}
    payload={'summary':summary,'quality':quality,'views':views,
             'eta':pd.read_csv(reports/'eta_scenarios.csv').to_dict('records'),
             'calibration':pd.read_csv(reports/'calibration.csv').to_dict('records'),
             'cost':pd.read_csv(reports/'cost_scenarios.csv').to_dict('records')}
    template=(root/'src/promise_integrity/dashboard_template.html').read_text(encoding='utf-8')
    (reports/'dashboard.html').write_text(template.replace('__DATA__',json.dumps(payload,default=str,allow_nan=False)),encoding='utf-8')
    (reports/'plotly.min.js').write_text(get_plotlyjs(),encoding='utf-8')
