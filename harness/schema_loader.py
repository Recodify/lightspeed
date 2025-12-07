"""Schema loading for ClickHouse databases."""

import logging
from pathlib import Path

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import SchemaLoadError

logger = logging.getLogger(__name__)


def apply_schema(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    project_root: Path,
    variant_root: Path
) -> dict[str, int]:
    """Apply database schema from SQL files.

    Executes schema files in order:
    1. If fresh=True, drop and recreate database
    2. Execute project-wide schemas (project_root/schemas/*.sql)
    3. Execute variant-specific schemas (variant_root/schemas/*.sql)

    Args:
        config: Benchmark configuration
        client: ClickHouse client
        project_root: Project root directory
        variant_root: Variant root directory

    Returns:
        Summary dict with counts: {"executed": N, "failed": N}

    Raises:
        SchemaLoadError: If schema execution fails and fail_on_error=True
    """
    executed = 0
    failed = 0

    # Fresh database if requested
    if config.schema.fresh:
        logger.debug("Fresh schema mode: dropping and recreating database")
        database = config.clickhouse.database

        # For DDL operations, we need to use a database-agnostic connection
        # Create temporary parameters without database specification
        try:
            query_params = {
                "user": config.clickhouse.user,
            }
            if config.clickhouse.password:
                query_params["password"] = config.clickhouse.password

            # Drop database
            response = client.client.post(
                client.base_url,
                params=query_params,
                content=f"DROP DATABASE IF EXISTS {database}",
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            logger.debug(f"Dropped database: {database}")
        except Exception as e:
            msg = f"Failed to drop database {database}: {e}"
            if config.schema.fail_on_error:
                raise SchemaLoadError(msg)
            logger.warning(msg)
            failed += 1

        try:
            # Create database
            response = client.client.post(
                client.base_url,
                params=query_params,
                content=f"CREATE DATABASE {database}",
                headers={"Content-Type": "text/plain"}
            )
            response.raise_for_status()
            logger.debug(f"Created database: {database}")
        except Exception as e:
            msg = f"Failed to create database {database}: {e}"
            if config.schema.fail_on_error:
                raise SchemaLoadError(msg)
            logger.warning(msg)
            failed += 1

    # Load project-wide schemas
    project_schemas_dir = project_root / "schemas"
    if project_schemas_dir.exists():
        schema_files = sorted(project_schemas_dir.glob("*.sql"))
        logger.debug(f"Found {len(schema_files)} project-wide schema files")

        for schema_file in schema_files:
            success = _execute_schema_file(
                schema_file, client, config.schema.fail_on_error, "project"
            )
            executed += 1
            if not success:
                failed += 1
    else:
        logger.debug(f"No project schemas directory: {project_schemas_dir}")

    # Load variant-specific schemas
    variant_schemas_dir = variant_root / "schemas"
    if variant_schemas_dir.exists():
        schema_files = sorted(variant_schemas_dir.glob("*.sql"))
        logger.debug(f"Found {len(schema_files)} variant-specific schema files")

        for schema_file in schema_files:
            success = _execute_schema_file(
                schema_file, client, config.schema.fail_on_error, "variant"
            )
            executed += 1
            if not success:
                failed += 1
    else:
        logger.debug(f"No variant schemas directory: {variant_schemas_dir}")

    # Log summary
    logger.debug(f"Schema loading complete: {executed} executed, {failed} failed")

    return {"executed": executed, "failed": failed}


def _execute_schema_file(
    schema_file: Path,
    client: ClickHouseClient,
    fail_on_error: bool,
    scope: str
) -> bool:
    """Execute a single schema file.

    Args:
        schema_file: Path to SQL file
        client: ClickHouse client
        fail_on_error: Whether to raise exception on failure
        scope: "project" or "variant" for logging

    Returns:
        True if successful, False if failed

    Raises:
        SchemaLoadError: If execution fails and fail_on_error=True
    """
    try:
        logger.debug(f"Executing {scope} schema: {schema_file.name}")
        sql = schema_file.read_text()

        # Execute entire file as single statement
        client.execute_no_result(sql)

        logger.debug(f"Successfully executed {schema_file.name}")
        return True

    except Exception as e:
        msg = f"Failed to execute {scope} schema {schema_file.name}: {e}"

        if fail_on_error:
            raise SchemaLoadError(msg)

        logger.warning(msg)
        return False
