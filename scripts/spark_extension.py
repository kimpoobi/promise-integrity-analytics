"""Optional Spark implementation. Requires Java and pip install '.[spark]'.
Not part of the validated default pipeline; run locally before claiming Spark experience.
"""
from pathlib import Path
from pyspark.sql import SparkSession, functions as F
root=Path(__file__).resolve().parents[1]
spark=SparkSession.builder.master('local[2]').appName('PromiseIntegrityBenchmark').getOrCreate()
try:
    source=spark.read.option('header',True).option('inferSchema',True).csv(str(root/'reports/order_analysis.csv'))
    replay=source.crossJoin(spark.range(20).withColumnRenamed('id','replay_id'))
    result=replay.groupBy('customer_state').agg(F.count('*').alias('orders'),F.sum(F.col('on_time').cast('int')).alias('on_time_orders'))
    result.explain(mode='formatted')
    assert replay.count()==source.count()*20
    result.orderBy('customer_state').show(30,truncate=False)
    replay.write.mode('overwrite').partitionBy('customer_state').parquet(str(root/'data/benchmark/spark_replay'))
finally:
    spark.stop()
