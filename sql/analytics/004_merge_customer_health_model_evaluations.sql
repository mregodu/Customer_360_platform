-- Merges model evaluation results for Customer Health scoring.
-- Expected staging table: CUSTOMER360_DB.ANALYTICS.stage_customer_health_model_evaluations

use role SYSADMIN;
use database CUSTOMER360_DB;
use schema ANALYTICS;

create table if not exists stage_customer_health_model_evaluations (
    model_version varchar not null,
    algorithm varchar not null,
    trained_at timestamp_ntz not null,
    training_rows number(18, 0),
    validation_rows number(18, 0),
    accuracy number(10, 6),
    macro_f1 number(10, 6),
    metrics variant,
    load_batch_id varchar
);

merge into CUSTOMER360_DB.ANALYTICS.customer_health_model_evaluations target
using CUSTOMER360_DB.ANALYTICS.stage_customer_health_model_evaluations source
on target.model_version = source.model_version
   and target.algorithm = source.algorithm
   and target.trained_at = source.trained_at
when matched then update set
    training_rows = source.training_rows,
    validation_rows = source.validation_rows,
    accuracy = source.accuracy,
    macro_f1 = source.macro_f1,
    metrics = source.metrics,
    load_batch_id = source.load_batch_id
when not matched then insert (
    model_version,
    algorithm,
    trained_at,
    training_rows,
    validation_rows,
    accuracy,
    macro_f1,
    metrics,
    load_batch_id
) values (
    source.model_version,
    source.algorithm,
    source.trained_at,
    source.training_rows,
    source.validation_rows,
    source.accuracy,
    source.macro_f1,
    source.metrics,
    source.load_batch_id
);
