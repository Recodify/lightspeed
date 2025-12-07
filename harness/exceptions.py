"""Custom exceptions for the ClickHouse benchmarking harness."""


class HarnessError(Exception):
    """Base exception for all harness errors."""

    pass


class ValidationError(HarnessError):
    """Config or file validation failed."""

    pass


class SchemaLoadError(HarnessError):
    """Schema application failed."""

    pass


class DataLoadError(HarnessError):
    """Data loading failed."""

    pass


class WorkloadAbortedError(HarnessError):
    """Workload exceeded error threshold."""

    pass


class MetricsCollectionError(HarnessError):
    """Failed to collect metrics from query_log."""

    pass
