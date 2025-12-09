"""ClickHouse HTTP client for executing queries and loading data."""

import logging
from typing import Any, BinaryIO

import httpx

from harness.config import ClickHouseConfig

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """HTTP client for ClickHouse operations.

    Uses httpx for HTTP communication with ClickHouse server.
    Supports query execution, data loading, and connection testing.
    """

    def __init__(self, config: ClickHouseConfig, timeout_seconds: int | None = None):
        """Initialize ClickHouse client.

        Args:
            config: ClickHouse connection configuration
            timeout_seconds: Optional timeout override (uses config.timeout_seconds if not provided)
        """
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"

        # Use provided timeout or fall back to config
        timeout = timeout_seconds if timeout_seconds is not None else config.timeout_seconds

        # Create httpx client with connection pooling and timeout
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=config.connection_pool_size,
                max_keepalive_connections=config.connection_pool_size
            )
        )

        # Base query parameters for all requests
        self.base_params = {
            "user": config.user,
            "database": config.database,
        }

        if config.password:
            self.base_params["password"] = config.password

        logger.debug(
            f"Created ClickHouse client: {self.base_url}, "
            f"timeout={timeout}s, pool_size={config.connection_pool_size}"
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise with enriched context and redacted URL."""
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            safe_url = str(exc.request.url)
            if self.config.password:
                safe_url = safe_url.replace(f"password={self.config.password}", "password=***")
            body_preview = response.text[:500]
            logger.error(
                "ClickHouse HTTP error %s for %s: %s",
                response.status_code,
                safe_url,
                body_preview or "<empty response body>",
            )
            raise

    def execute(
        self,
        sql: str,
        settings: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute SQL query and return results as list of dicts.

        Args:
            sql: SQL query to execute
            settings: Optional ClickHouse settings (e.g., {"query_id": "..."})

        Returns:
            List of row dictionaries

        Raises:
            httpx.HTTPError: If request fails
            httpx.TimeoutException: If query exceeds timeout
        """
        query_params = self.base_params.copy()

        # Add settings as query parameters
        if settings:
            for key, value in settings.items():
                query_params[key] = str(value)

        # Add FORMAT JSON for structured response
        if not sql.strip().upper().endswith("FORMAT JSON"):
            sql = f"{sql.strip()} FORMAT JSON"

        logger.debug(f"Executing query: {sql[:100]}...")

        response = self.client.post(
            self.base_url,
            params=query_params,
            content=sql,
            headers={"Content-Type": "text/plain"}
        )
        self._raise_for_status(response)

        # Parse JSON response
        result = response.json()
        return result.get("data", [])

    def execute_no_result(
        self,
        sql: str,
        settings: dict[str, Any] | None = None
    ) -> None:
        """Execute SQL query without expecting results (DDL, DML).

        Args:
            sql: SQL query to execute
            settings: Optional ClickHouse settings

        Raises:
            httpx.HTTPError: If request fails
            httpx.TimeoutException: If query exceeds timeout
        """
        query_params = self.base_params.copy()

        # Add settings as query parameters
        if settings:
            for key, value in settings.items():
                query_params[key] = str(value)

        logger.debug(f"Executing non-query: {sql[:100]}...")

        response = self.client.post(
            self.base_url,
            params=query_params,
            content=sql,
            headers={"Content-Type": "text/plain"}
        )
        self._raise_for_status(response)

    def insert_stream(
        self,
        table: str,
        file_handle: BinaryIO,
        fmt: str,
        settings: dict[str, Any] | None = None
    ) -> None:
        """Stream file data into ClickHouse table.

        Args:
            table: Target table name
            file_handle: File-like object opened in binary mode
            fmt: ClickHouse format (e.g., "CSVWithNames", "Parquet")
            settings: Optional ClickHouse settings

        Raises:
            httpx.HTTPError: If request fails
            httpx.TimeoutException: If insert exceeds timeout
        """
        query_params = self.base_params.copy()

        # Add settings as query parameters
        if settings:
            for key, value in settings.items():
                query_params[key] = str(value)

        # Build INSERT query
        query = f"INSERT INTO {table} FORMAT {fmt}"

        logger.info(query)
        query_params["query"] = query

        logger.debug(f"Streaming data to {table} in {fmt} format")

        response = self.client.post(
            self.base_url,
            params=query_params,
            content=file_handle,
            headers={"Content-Type": "application/octet-stream"}
        )
        self._raise_for_status(response)

    def test_connection(self) -> bool:
        """Test ClickHouse connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test connection using system database (always exists)
            query_params = {
                "user": self.config.user,
                "database": "system",  # Use system database for connection test
            }
            if self.config.password:
                query_params["password"] = self.config.password

            response = self.client.post(
                self.base_url,
                params=query_params,
                content="SELECT 1 FORMAT JSON",
                headers={"Content-Type": "text/plain"}
            )
            self._raise_for_status(response)
            result = response.json()
            return len(result.get("data", [])) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit - cleanup client."""
        self.client.close()
        logger.debug("ClickHouse client closed")
