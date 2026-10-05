"""Scale exercise using replayed records. Does not create new real-world observations."""
from pathlib import Path
import argparse
import json
import time
import duckdb

ROOT=Path(__file__).resolve().parents[1]
def main(repeats=20):
    if repeats<1 or repeats>100:
        raise ValueError('Use 1 to 100 repeats')
    c=duckdb.connect()
    path=(ROOT/'reports/order_analysis.csv').as_posix().replace("'","''")
    c.execute(f"CREATE TABLE source AS SELECT * FROM read_csv_auto('{path}')")
    start=time.perf_counter()
    c.execute(f'CREATE TABLE replay AS SELECT s.*, r.range AS replay_id FROM source s CROSS JOIN range({repeats}) r')
    build=time.perf_counter()-start
    query='SELECT customer_state,COUNT(*) n,SUM(on_time::INT) on_time_n FROM replay GROUP BY customer_state ORDER BY customer_state'
    start=time.perf_counter(); result=c.execute(query).df(); duration=time.perf_counter()-start
    baseline=c.execute('SELECT customer_state,COUNT(*) n,SUM(on_time::INT) on_time_n FROM source GROUP BY customer_state ORDER BY customer_state').df()
    assert result.n.tolist()==(baseline.n*repeats).tolist()
    assert result.on_time_n.tolist()==(baseline.on_time_n*repeats).tolist()
    plan=c.execute('EXPLAIN '+query).fetchall()
    report={'engine':'DuckDB','data':'replayed Olist analytical rows; NOT additional real orders',
            'repeats':repeats,'rows':int(result.n.sum()),'build_seconds':build,'query_seconds':duration,
            'aggregation_matches_baseline':True,'environment':'single-machine local execution; timings are not portable'}
    (ROOT/'reports/benchmark.json').write_text(json.dumps(report,indent=2))
    (ROOT/'reports/query_plan.txt').write_text('\n'.join(str(r) for r in plan),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repeats',type=int,default=20);main(p.parse_args().repeats)
