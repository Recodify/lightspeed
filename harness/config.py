"""Configuration loading and validation for the ClickHouse benchmarking harness."""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from harness.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ClickHouseConfig(BaseModel):
    """ClickHouse connection configuration."""

    host: str = "localhost"
    port: int = Field(default=8123, ge=1, le=65535)
    user: str = "default"
    password: str = ""
    database: str = "default"
    connection_pool_size: int = Field(default=20, ge=1, le=1000)
    timeout_seconds: int = Field(default=300, ge=1)


class SchemaConfig(BaseModel):
    """Schema loading configuration."""

    fail_on_error: bool = True
    fresh: bool = True


class DataLoadEntry(BaseModel):
    """Single data load entry."""

    table: str
    file: str
    format: str


class DataConfig(BaseModel):
    """Data loading configuration."""

    load_method: str = "http"
    truncate_before_load: bool = False
    load: list[DataLoadEntry] = Field(default_factory=list)


class QuerySpec(BaseModel):
    """Single query specification."""

    file: str
    weight: int = Field(ge=1, default=1)


class ParameterSpec(BaseModel):
    """Parameter specification for query parameterization."""

    type: str
    min: int | None = None
    max: int | None = None
    values: list[Any] | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ["random_int", "random_choice"]:
            raise ValueError(f"Invalid parameter type: {v}")
        return v


class WorkloadConfig(BaseModel):
    """Workload execution configuration."""

    name: str = "workload"
    path: str = "baseline"
    queries: list[QuerySpec] | None = None  # None means auto-discover
    concurrency: int = Field(ge=1, default=4)  # 4 concurrent workers by default
    duration_seconds: int = Field(ge=1, default=60)  # 60 second runs by default
    ramp_up_seconds: int = Field(ge=0, default=0)
    warmup_queries: int = Field(ge=0, default=0)
    think_time_ms: int = Field(ge=0, default=0)
    max_errors: int = Field(ge=0, default=100)
    query_timeout_seconds: int = Field(ge=1, default=60)
    parameters: dict[str, ParameterSpec] | None = None


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""

    use_query_log: bool = True
    query_log_wait_seconds: int = Field(ge=0, default=10)
    output_csv: str = "results/results.csv"
    output_md: str = "results/results.md"


class VariantConfig(BaseModel):
    """Variant-specific configuration overrides."""

    model_config = {"protected_namespaces": ()}

    description: str | None = None
    clickhouse: ClickHouseConfig | None = None
    schema: SchemaConfig | None = None
    data: DataConfig | None = None
    workload: WorkloadConfig | None = None
    metrics: MetricsConfig | None = None


class BenchmarkConfig(BaseModel):
    """Complete benchmark configuration."""

    model_config = {"protected_namespaces": ()}

    project: str
    variant: str = "default"
    clickhouse: ClickHouseConfig = Field(default_factory=ClickHouseConfig)
    schema: SchemaConfig = Field(default_factory=SchemaConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    workload: WorkloadConfig = Field(default_factory=WorkloadConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    variants: dict[str, VariantConfig] | None = None


def resolve_variant_config(base_config: BenchmarkConfig, variant_name: str) -> BenchmarkConfig:
    """
    Resolve variant configuration by applying variant overrides to base config.

    Args:
        base_config: Base configuration with optional variants section
        variant_name: Name of variant to resolve

    Returns:
        New BenchmarkConfig with variant-specific values applied

    Raises:
        ValidationError: If variant doesn't exist or config is invalid
    """
    # If no variants defined, use config as-is (backward compatibility)
    if base_config.variants is None:
        logger.debug(f"No variants section found, using config as-is with variant name: {variant_name}")
        # Create new config with updated variant name
        return BenchmarkConfig(
            project=base_config.project,
            variant=variant_name,
            clickhouse=base_config.clickhouse,
            schema=base_config.schema,
            data=base_config.data,
            workload=base_config.workload,
            metrics=base_config.metrics,
            variants=None
        )

    # Check if variant exists
    if variant_name not in base_config.variants:
        available = ", ".join(base_config.variants.keys())
        raise ValidationError(
            f"Variant '{variant_name}' not found. Available variants: {available}"
        )

    variant = base_config.variants[variant_name]
    logger.debug(f"Resolving variant: {variant_name}")
    if variant.description:
        logger.debug(f"  Description: {variant.description}")

    # Apply variant overrides (base + variant = desired state)
    resolved_clickhouse = variant.clickhouse if variant.clickhouse is not None else base_config.clickhouse
    resolved_schema = variant.schema if variant.schema is not None else base_config.schema
    resolved_data = variant.data if variant.data is not None else base_config.data
    resolved_workload = variant.workload if variant.workload is not None else base_config.workload
    resolved_metrics = variant.metrics if variant.metrics is not None else base_config.metrics

    return BenchmarkConfig(
        project=base_config.project,
        variant=variant_name,
        clickhouse=resolved_clickhouse,
        schema=resolved_schema,
        data=resolved_data,
        workload=resolved_workload,
        metrics=resolved_metrics,
        variants=base_config.variants  # Keep variants in resolved config
    )


def load_config(config_path: str | Path) -> BenchmarkConfig:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated BenchmarkConfig object

    Raises:
        ValidationError: If config file is invalid or doesn't exist
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise ValidationError(f"Config file not found: {config_path}")

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValidationError(f"Invalid YAML in config file: {e}")

    try:
        config = BenchmarkConfig(**data)
    except Exception as e:
        raise ValidationError(f"Invalid configuration: {e}")

    return config


def compute_project_root(config: BenchmarkConfig, base_dir: Path | None = None) -> Path:
    """
    Compute project root directory.

    Args:
        config: Benchmark configuration
        base_dir: Base directory (defaults to cwd/projects)

    Returns:
        Path to project root
    """
    if base_dir is None:
        base_dir = Path.cwd() / "projects"

    return base_dir / config.project


def compute_variant_root(config: BenchmarkConfig, base_dir: Path | None = None) -> Path:
    """
    Compute variant root directory.

    Args:
        config: Benchmark configuration
        base_dir: Base directory (defaults to cwd/projects)

    Returns:
        Path to variant root
    """
    project_root = compute_project_root(config, base_dir)
    return project_root / "variants" / config.variant


def validate_project_structure(config: BenchmarkConfig, base_dir: Path | None = None) -> None:
    """
    Validate that project and variant directories exist.

    Args:
        config: Benchmark configuration
        base_dir: Base directory (defaults to cwd/projects)

    Raises:
        ValidationError: If directories don't exist
    """
    project_root = compute_project_root(config, base_dir)
    variant_root = compute_variant_root(config, base_dir)

    if not project_root.exists():
        raise ValidationError(f"Project directory not found: {project_root}")

    if not variant_root.exists():
        raise ValidationError(f"Variant directory not found: {variant_root}")

    logger.debug(f"Project root: {project_root}")
    logger.debug(f"Variant root: {variant_root}")


def validate_schema_files(
    config: BenchmarkConfig, project_root: Path, variant_root: Path
) -> None:
    """
    Validate that schema files exist.

    Args:
        config: Benchmark configuration
        project_root: Project root directory
        variant_root: Variant root directory

    Raises:
        ValidationError: If required schema files don't exist
    """
    # Schema files are optional, so we just log what's found
    project_schemas = sorted((project_root / "schemas").glob("*.sql")) if (project_root / "schemas").exists() else []
    variant_schemas = sorted((variant_root / "schemas").glob("*.sql")) if (variant_root / "schemas").exists() else []

    logger.debug(f"Found {len(project_schemas)} project-wide schema files")
    logger.debug(f"Found {len(variant_schemas)} variant-specific schema files")

    if not project_schemas and not variant_schemas:
        logger.debug("No schema files found (this may be intentional)")


def validate_data_files(
    config: BenchmarkConfig, project_root: Path, variant_root: Path
) -> None:
    """
    Validate that data files exist per resolution rules.

    Project data is loaded first, variant data supplements it.
    At least one must exist.

    Args:
        config: Benchmark configuration
        project_root: Project root directory
        variant_root: Variant root directory

    Raises:
        ValidationError: If required data files don't exist
    """
    for entry in config.data.load:
        variant_path = variant_root / "data" / entry.file
        project_path = project_root / "data" / entry.file

        found_project = project_path.exists()
        found_variant = variant_path.exists()

        if found_project:
            logger.debug(f"Data file found (project): {project_path}")
        if found_variant:
            logger.debug(f"Data file found (variant): {variant_path}")

        if not found_project and not found_variant:
            raise ValidationError(
                f"Data file not found: {entry.file} "
                f"(checked {variant_path} and {project_path})"
            )


def validate_workload_files(
    config: BenchmarkConfig, project_root: Path, variant_root: Path
) -> None:
    """
    Validate that workload query files exist or can be auto-discovered.

    Args:
        config: Benchmark configuration
        project_root: Project root directory
        variant_root: Variant root directory

    Raises:
        ValidationError: If required query files don't exist
    """
    workload_path = config.workload.path

    if config.workload.queries:
        # Explicit mode - validate each query file
        for query in config.workload.queries:
            variant_query = variant_root / "workloads" / workload_path / query.file
            project_query = project_root / "workloads" / workload_path / query.file

            if variant_query.exists():
                logger.debug(f"Query file found (variant): {variant_query}")
            elif project_query.exists():
                logger.debug(f"Query file found (project): {project_query}")
            else:
                raise ValidationError(
                    f"Query file not found: {query.file} "
                    f"(checked {variant_query} and {project_query})"
                )
    else:
        # Auto-discovery mode - check if workload directories exist
        variant_workload_dir = variant_root / "workloads" / workload_path
        project_workload_dir = project_root / "workloads" / workload_path

        variant_queries = list(variant_workload_dir.glob("*.sql")) if variant_workload_dir.exists() else []
        project_queries = list(project_workload_dir.glob("*.sql")) if project_workload_dir.exists() else []

        total_queries = len(set([q.name for q in variant_queries + project_queries]))

        if total_queries == 0:
            raise ValidationError(
                f"No query files found in workload path: {workload_path} "
                f"(checked {variant_workload_dir} and {project_workload_dir})"
            )

        logger.debug(f"Auto-discovery mode: found {total_queries} unique query files")


def validate_config(
    config: BenchmarkConfig, base_dir: Path | None = None
) -> tuple[Path, Path]:
    """
    Run all validation checks on configuration.

    Args:
        config: Benchmark configuration
        base_dir: Base directory (defaults to cwd/projects)

    Returns:
        Tuple of (project_root, variant_root)

    Raises:
        ValidationError: If any validation check fails
    """
    # Validate project structure
    validate_project_structure(config, base_dir)

    # Compute roots
    project_root = compute_project_root(config, base_dir)
    variant_root = compute_variant_root(config, base_dir)

    # Validate files
    validate_schema_files(config, project_root, variant_root)
    validate_data_files(config, project_root, variant_root)
    validate_workload_files(config, project_root, variant_root)

    logger.debug("Configuration validation successful")

    return project_root, variant_root
