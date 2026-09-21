"""Built-in checks for the warehouse data-quality framework."""

from etl.data_quality.checks.anomalies import anomaly_threshold_check
from etl.data_quality.checks.business_rules import sales_amount_rule_check
from etl.data_quality.checks.completeness import null_rate_check
from etl.data_quality.checks.freshness import freshness_check
from etl.data_quality.checks.integrity import duplicate_count_check, orphan_record_check
from etl.data_quality.checks.schema import columns_exist_check, nullability_check, table_exists_check

__all__ = [
    "anomaly_threshold_check",
    "columns_exist_check",
    "duplicate_count_check",
    "freshness_check",
    "null_rate_check",
    "nullability_check",
    "orphan_record_check",
    "sales_amount_rule_check",
    "table_exists_check",
]
