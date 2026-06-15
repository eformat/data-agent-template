"""Synthetic sample data for the Retail enterprise authorization demo.

Loads data for all three departments (finance, sales, operations) into
a single DuckDB connection regardless of which department config is active.
SpiceDB permission checks control access, not data availability.
"""

from __future__ import annotations

import duckdb

from data_agent_core.config.models import DomainConfig
from data_agent_core.testing.sample_data import register_sample_data_loader

REGIONS = ["Northeast", "Southeast", "Midwest", "West", "International"]
PRODUCT_LINES = ["Apparel", "Electronics", "Home", "Grocery", "Sporting"]
DEPARTMENTS = ["Operations", "Sales", "Finance", "Marketing", "Technology"]
EXPENSE_CATEGORIES = ["payroll", "marketing", "logistics", "technology", "facilities"]
CHANNELS = ["retail", "online", "wholesale", "marketplace"]
CARRIERS = ["FedEx", "UPS", "USPS"]
WAREHOUSES = ["DC-Northeast", "DC-Southeast", "DC-Midwest", "DC-West", "DC-International"]
SEGMENTS = ["Enterprise", "Mid-Market", "SMB", "Consumer"]
RETURN_REASONS = ["defective", "wrong_item", "not_as_described", "changed_mind", "damaged_shipping"]
PIPELINE_STAGES = ["Prospect", "Qualified", "Proposal", "Negotiation", "Closed Won"]

# Revenue distribution weights (region × product_line → monthly base in $K)
# Total ~$3.3B/month → ~$40B/year
_REGION_WEIGHTS = {"Northeast": 0.20, "Southeast": 0.25, "Midwest": 0.15, "West": 0.30, "International": 0.10}
_PRODUCT_WEIGHTS = {"Grocery": 0.35, "Apparel": 0.25, "Electronics": 0.20, "Home": 0.12, "Sporting": 0.08}
_MONTHLY_BASE = 3_300_000  # $3.3B/month in USD thousands

# Seasonal multipliers by month (Q4 peak)
_SEASONALITY = {
    1: 0.80, 2: 0.82, 3: 0.90, 4: 0.92, 5: 0.95, 6: 0.98,
    7: 0.96, 8: 1.00, 9: 1.02, 10: 1.05, 11: 1.25, 12: 1.40,
}

# YoY growth by year
_GROWTH = {2021: 1.00, 2022: 1.06, 2023: 1.10, 2024: 1.13, 2025: 1.15}

# Gross margin by product line
_MARGINS = {"Apparel": 0.47, "Electronics": 0.18, "Home": 0.38, "Grocery": 0.23, "Sporting": 0.42}


def _create_schema(conn: duckdb.DuckDBPyConnection, catalog: str, schema: str) -> str:
    qs = f"{catalog}.{schema}"
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{qs}"')
    return qs


def _load_finance_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    qs = _create_schema(conn, "finance", "analytics")

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".revenue (
            year INTEGER, month INTEGER, region VARCHAR,
            product_line VARCHAR, revenue_usd_k DECIMAL(12,1)
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".expenses (
            year INTEGER, month INTEGER, department VARCHAR,
            category VARCHAR, amount_usd_k DECIMAL(12,1)
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".margins (
            year INTEGER, quarter INTEGER, product_line VARCHAR,
            revenue_usd_k DECIMAL(12,1), cogs_usd_k DECIMAL(12,1),
            gross_margin_pct DECIMAL(5,2)
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".forecasts (
            year INTEGER, quarter INTEGER, region VARCHAR,
            target_usd_k DECIMAL(12,1), actual_usd_k DECIMAL(12,1),
            variance_pct DECIMAL(5,2)
        )
    ''')

    rev_rows = 0
    for year in range(2021, 2026):
        for month in range(1, 13):
            for region in REGIONS:
                for pl in PRODUCT_LINES:
                    base = _MONTHLY_BASE * _REGION_WEIGHTS[region] * _PRODUCT_WEIGHTS[pl]
                    val = round(base * _SEASONALITY[month] * _GROWTH[year], 1)
                    conn.execute(
                        f'INSERT INTO "{qs}".revenue VALUES (?, ?, ?, ?, ?)',
                        [year, month, region, pl, val],
                    )
                    rev_rows += 1

    # Expenses: ~$35B/yr, distributed across departments and categories
    _dept_weights = {"Operations": 0.40, "Sales": 0.25, "Marketing": 0.15, "Finance": 0.10, "Technology": 0.10}
    _cat_weights = {"payroll": 0.50, "logistics": 0.20, "technology": 0.12, "marketing": 0.10, "facilities": 0.08}
    monthly_expense_base = 2_900_000
    for year in range(2021, 2026):
        for month in range(1, 13):
            for dept in DEPARTMENTS:
                for cat in EXPENSE_CATEGORIES:
                    val = round(monthly_expense_base * _dept_weights[dept] * _cat_weights[cat] * _GROWTH[year], 1)
                    conn.execute(
                        f'INSERT INTO "{qs}".expenses VALUES (?, ?, ?, ?, ?)',
                        [year, month, dept, cat, val],
                    )

    # Margins: quarterly by product line
    for year in range(2021, 2026):
        for quarter in range(1, 5):
            for pl in PRODUCT_LINES:
                q_months = range(quarter * 3 - 2, quarter * 3 + 1)
                q_rev = sum(
                    _MONTHLY_BASE * sum(_REGION_WEIGHTS.values()) * _PRODUCT_WEIGHTS[pl]
                    * _SEASONALITY[m] * _GROWTH[year]
                    for m in q_months
                )
                margin = _MARGINS[pl]
                cogs = round(q_rev * (1 - margin), 1)
                q_rev = round(q_rev, 1)
                margin_pct = round(margin * 100, 2)
                conn.execute(
                    f'INSERT INTO "{qs}".margins VALUES (?, ?, ?, ?, ?, ?)',
                    [year, quarter, pl, q_rev, cogs, margin_pct],
                )

    # Forecasts: quarterly by region, target = actual * (1 + random-ish variance)
    _variance = {
        (2021, 1): -2.1, (2021, 2): 1.5, (2021, 3): -0.8, (2021, 4): 3.2,
        (2022, 1): -1.4, (2022, 2): 2.8, (2022, 3): 0.5, (2022, 4): 4.1,
        (2023, 1): -3.2, (2023, 2): -0.9, (2023, 3): 1.2, (2023, 4): 2.5,
        (2024, 1): -1.8, (2024, 2): 0.7, (2024, 3): -0.3, (2024, 4): 3.8,
        (2025, 1): -2.5, (2025, 2): 1.1, (2025, 3): 0.9, (2025, 4): 2.2,
    }
    for year in range(2021, 2026):
        for quarter in range(1, 5):
            for region in REGIONS:
                q_months = range(quarter * 3 - 2, quarter * 3 + 1)
                actual = round(sum(
                    _MONTHLY_BASE * _REGION_WEIGHTS[region] * _SEASONALITY[m] * _GROWTH[year]
                    for m in q_months
                ), 1)
                var_pct = _variance.get((year, quarter), 0.0)
                target = round(actual * (1 + var_pct / 100), 1)
                conn.execute(
                    f'INSERT INTO "{qs}".forecasts VALUES (?, ?, ?, ?, ?, ?)',
                    [year, quarter, region, target, actual, var_pct],
                )

    print(f"[dev] Loaded retail finance data: {rev_rows} revenue rows", flush=True)


def _load_sales_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    qs = _create_schema(conn, "sales", "analytics")

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".orders (
            order_id VARCHAR, order_date DATE, customer_id VARCHAR,
            region VARCHAR, product_line VARCHAR, quantity INTEGER,
            revenue_usd DECIMAL(12,2), channel VARCHAR
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".pipeline (
            opportunity_id VARCHAR, stage VARCHAR, probability_pct DECIMAL(5,2),
            expected_revenue_usd DECIMAL(12,2), sales_rep VARCHAR,
            region VARCHAR, created_date DATE, expected_close_date DATE
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".customers (
            customer_id VARCHAR, segment VARCHAR, region VARCHAR,
            acquisition_date DATE, lifetime_value_usd DECIMAL(12,2),
            channel VARCHAR
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".acquisition_costs (
            year INTEGER, quarter INTEGER, channel VARCHAR,
            spend_usd_k DECIMAL(12,1), new_customers INTEGER,
            cac_usd DECIMAL(10,2)
        )
    ''')

    # Orders: ~500 orders spread across 2021-2025
    order_count = 0
    _channel_weights = [("retail", 0.40), ("online", 0.35), ("wholesale", 0.15), ("marketplace", 0.10)]
    for year in range(2021, 2026):
        for month in range(1, 13):
            base_orders = 8
            seasonal = _SEASONALITY[month]
            n_orders = int(base_orders * seasonal)
            for i in range(n_orders):
                order_count += 1
                oid = f"ORD-{year}{month:02d}-{order_count:05d}"
                cid = f"CUST-{(order_count * 7 + i) % 200 + 1:04d}"
                region = REGIONS[order_count % len(REGIONS)]
                pl = PRODUCT_LINES[order_count % len(PRODUCT_LINES)]
                qty = (order_count % 5) + 1
                rev = round(qty * (50 + (order_count % 200) * 2.5), 2)
                ch = _channel_weights[order_count % len(_channel_weights)][0]
                day = min((order_count % 28) + 1, 28)
                conn.execute(
                    f'INSERT INTO "{qs}".orders VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    [oid, f"{year}-{month:02d}-{day:02d}", cid, region, pl, qty, rev, ch],
                )

    # Pipeline: ~50 opportunities
    _stage_prob = {"Prospect": 10, "Qualified": 25, "Proposal": 50, "Negotiation": 75, "Closed Won": 100}
    reps = ["Alice Chen", "Bob Martinez", "Carol Kim", "Dave Patel", "Eva Johansson"]
    for i in range(50):
        opp_id = f"OPP-{i+1:04d}"
        stage = PIPELINE_STAGES[i % len(PIPELINE_STAGES)]
        prob = _stage_prob[stage]
        expected_rev = round(50000 + (i * 7919) % 450000, 2)
        rep = reps[i % len(reps)]
        region = REGIONS[i % len(REGIONS)]
        year = 2023 + (i % 3)
        month = (i % 12) + 1
        day = min((i % 28) + 1, 28)
        close_month = min(month + 3, 12)
        conn.execute(
            f'INSERT INTO "{qs}".pipeline VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [opp_id, stage, prob, expected_rev, rep, region,
             f"{year}-{month:02d}-{day:02d}", f"{year}-{close_month:02d}-28"],
        )

    # Customers: 200
    for i in range(200):
        cid = f"CUST-{i+1:04d}"
        segment = SEGMENTS[i % len(SEGMENTS)]
        region = REGIONS[i % len(REGIONS)]
        year = 2019 + (i % 7)
        month = (i % 12) + 1
        ltv = round(1000 + (i * 3571) % 99000, 2)
        ch = CHANNELS[i % len(CHANNELS)]
        conn.execute(
            f'INSERT INTO "{qs}".customers VALUES (?, ?, ?, ?, ?, ?)',
            [cid, segment, region, f"{year}-{month:02d}-15", ltv, ch],
        )

    # Acquisition costs: quarterly by channel
    _channel_spend = {"retail": 800, "online": 1200, "wholesale": 400, "marketplace": 600}
    _channel_new_cust = {"retail": 120, "online": 200, "wholesale": 40, "marketplace": 80}
    for year in range(2021, 2026):
        for quarter in range(1, 5):
            for ch in CHANNELS:
                spend = round(_channel_spend[ch] * _GROWTH[year], 1)
                new_cust = int(_channel_new_cust[ch] * _GROWTH[year])
                cac = round(spend * 1000 / new_cust, 2) if new_cust > 0 else 0
                conn.execute(
                    f'INSERT INTO "{qs}".acquisition_costs VALUES (?, ?, ?, ?, ?, ?)',
                    [year, quarter, ch, spend, new_cust, cac],
                )

    print(f"[dev] Loaded retail sales data: {order_count} orders, 50 pipeline, 200 customers", flush=True)


def _load_ops_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    qs = _create_schema(conn, "ops", "analytics")

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".inventory (
            date DATE, sku VARCHAR, warehouse VARCHAR,
            quantity_on_hand INTEGER, reorder_point INTEGER,
            days_of_supply DECIMAL(5,1)
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".shipments (
            shipment_id VARCHAR, order_id VARCHAR, warehouse VARCHAR,
            carrier VARCHAR, ship_date DATE, delivery_date DATE,
            transit_days INTEGER, status VARCHAR
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".warehouses (
            warehouse_id VARCHAR, region VARCHAR, year INTEGER,
            month INTEGER, capacity_pallets INTEGER,
            utilization_pct DECIMAL(5,2), operating_cost_usd_k DECIMAL(12,1)
        )
    ''')
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".returns (
            return_id VARCHAR, order_id VARCHAR, sku VARCHAR,
            return_date DATE, reason VARCHAR, refund_usd DECIMAL(10,2)
        )
    ''')

    # Inventory: 100 SKUs × 5 warehouses, latest snapshot (2025-01-15)
    skus = [f"SKU-{i+1:04d}" for i in range(100)]
    inv_count = 0
    for sku in skus:
        for wh in WAREHOUSES:
            sku_num = int(sku.split("-")[1])
            qty = 50 + (sku_num * 37 + hash(wh)) % 950
            reorder = 100 + (sku_num * 13) % 200
            dos = round(qty / max(reorder / 7, 1), 1)
            conn.execute(
                f'INSERT INTO "{qs}".inventory VALUES (?, ?, ?, ?, ?, ?)',
                [f"2025-01-15", sku, wh, qty, reorder, dos],
            )
            inv_count += 1

    # Shipments: ~300
    ship_count = 0
    statuses = ["delivered"] * 85 + ["in_transit"] * 10 + ["exception"] * 5
    for i in range(300):
        ship_count += 1
        sid = f"SHP-{ship_count:06d}"
        oid = f"ORD-{2024}{(i%12)+1:02d}-{(i%500)+1:05d}"
        wh = WAREHOUSES[i % len(WAREHOUSES)]
        carrier = CARRIERS[i % len(CARRIERS)]
        year = 2024 + (i // 200)
        month = (i % 12) + 1
        day = min((i % 28) + 1, 28)
        transit = 2 + (i % 5)
        status = statuses[i % len(statuses)]
        del_day = min(day + transit, 28)
        conn.execute(
            f'INSERT INTO "{qs}".shipments VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [sid, oid, wh, carrier, f"{year}-{month:02d}-{day:02d}",
             f"{year}-{month:02d}-{del_day:02d}", transit, status],
        )

    # Warehouses: 5 warehouses × 5 years × 12 months
    _wh_capacity = {
        "DC-Northeast": 12000, "DC-Southeast": 15000, "DC-Midwest": 10000,
        "DC-West": 18000, "DC-International": 8000,
    }
    _wh_region = {
        "DC-Northeast": "Northeast", "DC-Southeast": "Southeast", "DC-Midwest": "Midwest",
        "DC-West": "West", "DC-International": "International",
    }
    for wh in WAREHOUSES:
        for year in range(2021, 2026):
            for month in range(1, 13):
                cap = _wh_capacity[wh]
                util = round(65 + _SEASONALITY[month] * 20 + (year - 2021) * 1.5, 2)
                util = min(util, 98.0)
                cost = round(cap * 0.08 * _GROWTH[year], 1)
                conn.execute(
                    f'INSERT INTO "{qs}".warehouses VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [wh, _wh_region[wh], year, month, cap, util, cost],
                )

    # Returns: ~80
    for i in range(80):
        rid = f"RET-{i+1:05d}"
        oid = f"ORD-{2024}{(i%12)+1:02d}-{(i%500)+1:05d}"
        sku = skus[i % len(skus)]
        month = (i % 12) + 1
        day = min((i % 28) + 1, 28)
        reason = RETURN_REASONS[i % len(RETURN_REASONS)]
        refund = round(25 + (i * 31) % 475, 2)
        conn.execute(
            f'INSERT INTO "{qs}".returns VALUES (?, ?, ?, ?, ?, ?)',
            [rid, oid, sku, f"2024-{month:02d}-{day:02d}", reason, refund],
        )

    print(f"[dev] Loaded retail ops data: {inv_count} inventory, {ship_count} shipments, 80 returns", flush=True)


def _load_retail(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    """Load all three retail department schemas into one DuckDB connection."""
    _load_finance_data(conn, config)
    _load_sales_data(conn, config)
    _load_ops_data(conn, config)


register_sample_data_loader("retail", _load_retail)
