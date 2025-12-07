"""Schema loading for ClickHouse databases."""

import logging
import re
from pathlib import Path

from harness.clickhouse_client import ClickHouseClient
from harness.config import BenchmarkConfig
from harness.exceptions import SchemaLoadError
from harness.utils import compute_isolated_database_name

logger = logging.getLogger(__name__)


def apply_schema(
    config: BenchmarkConfig,
    client: ClickHouseClient,
    project_root: Path,
    variant_root: Path,
    run_name: str,
    config_name: str
) -> dict[str, int]:
    """Apply database schema from SQL files with isolation.

    Creates an isolated database for this run/variant combination.
    Database name: [projectName]_[configName]_[runName]_[variantName]
    Table names: Unchanged from schema files

    Executes schema files in order:
    1. If fresh=True, drop and recreate isolated database
    2. Execute project-wide schemas (project_root/schemas/*.sql)
    3. Execute variant-specific schemas (variant_root/schemas/*.sql)

    Args:
        config: Benchmark configuration
        client: ClickHouse client
        project_root: Project root directory
        variant_root: Variant root directory
        run_name: Run name for isolation (e.g., 'brave-penguin')
        config_name: Config file name (e.g., 'example_basic')

    Returns:
        Summary dict with counts: {"executed": N, "failed": N, "database": db_name}

    Raises:
        SchemaLoadError: If schema execution fails and fail_on_error=True
    """
    executed = 0
    failed = 0

    # Compute isolated database name
    isolated_database = compute_isolated_database_name(
        config.project, config_name, run_name, config.variant
    )
    logger.info(f"Using isolated database: {isolated_database}")

    # Fresh database if requested
    if config.schema.fresh:
        logger.debug("Fresh schema mode: dropping and recreating database")
        database = isolated_database

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
                schema_file, client, config.schema.fail_on_error, "project",
                isolated_database
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
                schema_file, client, config.schema.fail_on_error, "variant",
                isolated_database
            )
            executed += 1
            if not success:
                failed += 1
    else:
        logger.debug(f"No variant schemas directory: {variant_schemas_dir}")

    # Log summary
    logger.debug(f"Schema loading complete: {executed} executed, {failed} failed")

    return {"executed": executed, "failed": failed, "database": isolated_database}


def _execute_schema_file(
    schema_file: Path,
    client: ClickHouseClient,
    fail_on_error: bool,
    scope: str,
    isolated_database: str
) -> bool:
    """Execute a single schema file in the isolated database context.

    Transforms CREATE TABLE statements to include the isolated database name.

    Args:
        schema_file: Path to SQL file
        client: ClickHouse client
        fail_on_error: Whether to raise exception on failure
        scope: "project" or "variant" for logging
        isolated_database: Isolated database name

    Returns:
        True if successful, False if failed

    Raises:
        SchemaLoadError: If execution fails and fail_on_error=True
    """
    try:
        logger.debug(f"Executing {scope} schema: {schema_file.name}")
        sql = schema_file.read_text()

        # Transform CREATE TABLE statements to include database name
        # Pattern matches: CREATE TABLE [IF NOT EXISTS] table_name
        # Replaces with: CREATE TABLE [IF NOT EXISTS] database.table_name
        pattern = r'(CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)(\w+)(\s*\()'
        transformed_sql = re.sub(
            pattern,
            rf'\1{isolated_database}.\2\3',
            sql,
            flags=re.IGNORECASE
        )

        # Execute transformed SQL
        client.execute_no_result(transformed_sql)

        logger.debug(f"Successfully executed {schema_file.name}")
        return True

    except Exception as e:
        msg = f"Failed to execute {scope} schema {schema_file.name}: {e}"

        if fail_on_error:
            raise SchemaLoadError(msg)

        logger.warning(msg)
        return False
