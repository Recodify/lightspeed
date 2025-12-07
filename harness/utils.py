"""Utility functions for the ClickHouse benchmarking harness."""

import logging


def setup_logging(verbose: bool) -> None:
    """Configure logging for the harness.

    Args:
        verbose: If True, set log level to DEBUG; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Use different format for verbose vs normal mode
    # Verbose: show module names, Normal: clean output
    if verbose:
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    else:
        log_format = "%(message)s"

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Suppress noisy third-party loggers unless in verbose mode
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def format_bytes(bytes_count: int) -> str:
    """Format bytes as human-readable string.

    Args:
        bytes_count: Number of bytes

    Returns:
        Formatted string (e.g., "1.2 MB", "45 KB")
    """
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.2f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def format_duration(ms: float) -> str:
    """Convert milliseconds to human-readable duration string.

    Args:
        ms: Duration in milliseconds

    Returns:
        Formatted string (e.g., "1.2s", "45ms", "1.5m")
    """
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:  # Less than 1 minute
        return f"{ms / 1000:.2f}s"
    else:
        return f"{ms / 60000:.2f}m"


def sanitize_name(name: str) -> str:
    """Sanitize a name for use in ClickHouse identifiers.

    Replaces hyphens with underscores and removes other invalid characters.

    Args:
        name: Name to sanitize

    Returns:
        Sanitized name safe for ClickHouse
    """
    return name.replace('-', '_')


def compute_isolated_database_name(project: str, config_name: str, run_name: str, variant_name: str) -> str:
    """Compute isolated database name using the pattern: [projectName]_[configName]_[runName]_[variantName]

    Args:
        project: Project name
        config_name: Config file name (without extension)
        run_name: Run name (e.g., 'brave-penguin')
        variant_name: Variant name

    Returns:
        Database name (e.g., 'myproject_baseline_brave_penguin_optimized')
    """
    safe_project = sanitize_name(project)
    safe_config = sanitize_name(config_name)
    safe_run = sanitize_name(run_name)
    safe_variant = sanitize_name(variant_name)
    return f"{safe_project}_{safe_config}_{safe_run}_{safe_variant}"
