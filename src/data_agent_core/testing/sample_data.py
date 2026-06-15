"""Synthetic sample data loader for DuckDB dev mode.

Creates tables matching domain schemas with realistic but synthetic data
so agents can answer meaningful queries without a Trino cluster.

Domains register loaders via ``register_sample_data_loader``.  Unregistered
domains fall back to the built-in NNDSS loader for backward compatibility.
"""

from __future__ import annotations

from typing import Callable

import duckdb

from data_agent_core.config.models import DomainConfig

_LOADERS: dict[str, Callable[[duckdb.DuckDBPyConnection, DomainConfig], None]] = {}


def register_sample_data_loader(
    domain_name: str,
    loader_fn: Callable[[duckdb.DuckDBPyConnection, DomainConfig], None],
) -> None:
    """Register a domain-specific sample data loader."""
    _LOADERS[domain_name] = loader_fn

STATES = ["ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"]

POPULATION = {
    ("ACT", 2021): 432000, ("ACT", 2022): 457000, ("ACT", 2023): 466000, ("ACT", 2024): 476000, ("ACT", 2025): 485000,
    ("NSW", 2021): 8190000, ("NSW", 2022): 8260000, ("NSW", 2023): 8370000, ("NSW", 2024): 8480000, ("NSW", 2025): 8590000,
    ("NT", 2021): 250000, ("NT", 2022): 252000, ("NT", 2023): 253000, ("NT", 2024): 255000, ("NT", 2025): 257000,
    ("QLD", 2021): 5260000, ("QLD", 2022): 5380000, ("QLD", 2023): 5540000, ("QLD", 2024): 5700000, ("QLD", 2025): 5860000,
    ("SA", 2021): 1800000, ("SA", 2022): 1830000, ("SA", 2023): 1850000, ("SA", 2024): 1870000, ("SA", 2025): 1900000,
    ("TAS", 2021): 542000, ("TAS", 2022): 558000, ("TAS", 2023): 572000, ("TAS", 2024): 575000, ("TAS", 2025): 578000,
    ("VIC", 2021): 6640000, ("VIC", 2022): 6750000, ("VIC", 2023): 6870000, ("VIC", 2024): 6990000, ("VIC", 2025): 7100000,
    ("WA", 2021): 2760000, ("WA", 2022): 2860000, ("WA", 2023): 2960000, ("WA", 2024): 3060000, ("WA", 2025): 3160000,
}

NOTIFICATIONS = {
    "Influenza (laboratory confirmed)": {
        ("ACT", 2021): 120, ("ACT", 2022): 4500, ("ACT", 2023): 5800, ("ACT", 2024): 6200, ("ACT", 2025): 5100,
        ("NSW", 2021): 800, ("NSW", 2022): 52000, ("NSW", 2023): 95000, ("NSW", 2024): 88000, ("NSW", 2025): 76000,
        ("NT", 2021): 30, ("NT", 2022): 1200, ("NT", 2023): 2100, ("NT", 2024): 1900, ("NT", 2025): 1600,
        ("QLD", 2021): 300, ("QLD", 2022): 38000, ("QLD", 2023): 55000, ("QLD", 2024): 48000, ("QLD", 2025): 42000,
        ("SA", 2021): 150, ("SA", 2022): 12000, ("SA", 2023): 18000, ("SA", 2024): 16500, ("SA", 2025): 14000,
        ("TAS", 2021): 40, ("TAS", 2022): 3200, ("TAS", 2023): 4800, ("TAS", 2024): 4200, ("TAS", 2025): 3600,
        ("VIC", 2021): 500, ("VIC", 2022): 42000, ("VIC", 2023): 72000, ("VIC", 2024): 65000, ("VIC", 2025): 58000,
        ("WA", 2021): 200, ("WA", 2022): 18000, ("WA", 2023): 28000, ("WA", 2024): 25000, ("WA", 2025): 21000,
    },
    "Invasive meningococcal disease": {
        ("ACT", 2021): 1, ("ACT", 2022): 2, ("ACT", 2023): 3, ("ACT", 2024): 2, ("ACT", 2025): 1,
        ("NSW", 2021): 18, ("NSW", 2022): 32, ("NSW", 2023): 45, ("NSW", 2024): 38, ("NSW", 2025): 30,
        ("NT", 2021): 1, ("NT", 2022): 2, ("NT", 2023): 3, ("NT", 2024): 2, ("NT", 2025): 1,
        ("QLD", 2021): 12, ("QLD", 2022): 22, ("QLD", 2023): 30, ("QLD", 2024): 25, ("QLD", 2025): 20,
        ("SA", 2021): 4, ("SA", 2022): 8, ("SA", 2023): 11, ("SA", 2024): 9, ("SA", 2025): 7,
        ("TAS", 2021): 1, ("TAS", 2022): 2, ("TAS", 2023): 3, ("TAS", 2024): 2, ("TAS", 2025): 2,
        ("VIC", 2021): 15, ("VIC", 2022): 28, ("VIC", 2023): 40, ("VIC", 2024): 35, ("VIC", 2025): 28,
        ("WA", 2021): 5, ("WA", 2022): 10, ("WA", 2023): 15, ("WA", 2024): 12, ("WA", 2025): 10,
    },
    "Invasive pneumococcal disease": {
        ("ACT", 2021): 8, ("ACT", 2022): 15, ("ACT", 2023): 18, ("ACT", 2024): 16, ("ACT", 2025): 14,
        ("NSW", 2021): 180, ("NSW", 2022): 350, ("NSW", 2023): 420, ("NSW", 2024): 380, ("NSW", 2025): 340,
        ("NT", 2021): 12, ("NT", 2022): 18, ("NT", 2023): 22, ("NT", 2024): 20, ("NT", 2025): 18,
        ("QLD", 2021): 120, ("QLD", 2022): 240, ("QLD", 2023): 290, ("QLD", 2024): 260, ("QLD", 2025): 230,
        ("SA", 2021): 45, ("SA", 2022): 85, ("SA", 2023): 105, ("SA", 2024): 95, ("SA", 2025): 82,
        ("TAS", 2021): 10, ("TAS", 2022): 20, ("TAS", 2023): 25, ("TAS", 2024): 22, ("TAS", 2025): 19,
        ("VIC", 2021): 160, ("VIC", 2022): 310, ("VIC", 2023): 380, ("VIC", 2024): 340, ("VIC", 2025): 300,
        ("WA", 2021): 60, ("WA", 2022): 120, ("WA", 2023): 150, ("WA", 2024): 135, ("WA", 2025): 115,
    },
    "Salmonellosis": {
        ("ACT", 2021): 85, ("ACT", 2022): 95, ("ACT", 2023): 110, ("ACT", 2024): 105, ("ACT", 2025): 100,
        ("NSW", 2021): 2800, ("NSW", 2022): 3200, ("NSW", 2023): 3600, ("NSW", 2024): 3400, ("NSW", 2025): 3100,
        ("NT", 2021): 180, ("NT", 2022): 200, ("NT", 2023): 230, ("NT", 2024): 220, ("NT", 2025): 210,
        ("QLD", 2021): 3500, ("QLD", 2022): 3900, ("QLD", 2023): 4200, ("QLD", 2024): 4000, ("QLD", 2025): 3700,
        ("SA", 2021): 850, ("SA", 2022): 950, ("SA", 2023): 1050, ("SA", 2024): 1000, ("SA", 2025): 920,
        ("TAS", 2021): 120, ("TAS", 2022): 135, ("TAS", 2023): 155, ("TAS", 2024): 145, ("TAS", 2025): 130,
        ("VIC", 2021): 2200, ("VIC", 2022): 2500, ("VIC", 2023): 2800, ("VIC", 2024): 2650, ("VIC", 2025): 2400,
        ("WA", 2021): 1100, ("WA", 2022): 1250, ("WA", 2023): 1400, ("WA", 2024): 1300, ("WA", 2025): 1200,
    },
}


def load_sample_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    """Load synthetic sample data into DuckDB matching the domain's table schemas.

    Dispatches by ``config.domain_name`` to a registered loader.
    Falls back to the built-in NNDSS loader for unregistered domains.
    """
    for key, loader in _LOADERS.items():
        if config.domain_name == key or config.domain_name.startswith(key + "-"):
            return loader(conn, config)

    return _load_nndss_sample_data(conn, config)


def _load_nndss_sample_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    """Load NNDSS sample data (original built-in loader)."""
    catalog = config.trino_catalog
    schema = config.trino_schema

    # DuckDB doesn't have catalogs like Trino, so we create schema "lakehouse.nndss"
    # as a workaround. The agent's SQL references lakehouse.nndss.notifications etc.
    # We create a schema named "{catalog}.{schema}" and use it.
    qualified_schema = f"{catalog}.{schema}"

    # Create schema (DuckDB uses dots in schema names literally when quoted)
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{qualified_schema}"')

    # Create notifications table
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qualified_schema}".notifications (
            year INTEGER,
            state VARCHAR,
            disease VARCHAR,
            notifications INTEGER
        )
    ''')

    # Create population table
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qualified_schema}".population (
            year INTEGER,
            state VARCHAR,
            population INTEGER
        )
    ''')

    # Insert notifications
    for disease, data in NOTIFICATIONS.items():
        for (state, year), count in data.items():
            conn.execute(
                f'INSERT INTO "{qualified_schema}".notifications VALUES (?, ?, ?, ?)',
                [year, state, disease, count],
            )

    # Insert population
    for (state, year), pop in POPULATION.items():
        conn.execute(
            f'INSERT INTO "{qualified_schema}".population VALUES (?, ?, ?)',
            [year, state, pop],
        )

    total_notif = conn.execute(f'SELECT COUNT(*) FROM "{qualified_schema}".notifications').fetchone()[0]
    total_pop = conn.execute(f'SELECT COUNT(*) FROM "{qualified_schema}".population').fetchone()[0]
    print(f"[dev] Loaded sample data: {total_notif} notification rows, {total_pop} population rows", flush=True)
