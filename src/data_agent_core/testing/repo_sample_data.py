"""Synthetic sample data for the Repo Trading domain agent.

Loads 6 tables (trades, collateral, counterparties, rates, margin_calls,
substitutions) with realistic but fictional fixed-income secured financing data.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import duckdb

from data_agent_core.config.models import DomainConfig
from data_agent_core.testing.sample_data import register_sample_data_loader

BOOKS = ["NY", "LDN", "TKY"]
TRADE_TYPES = ["Repo", "ReverseRepo", "BuySellBack", "TriParty", "GCRepo"]
DIRECTIONS = ["BUY", "SELL"]
RATE_TYPES = ["FIXED", "VARIABLE", "INDEXED"]
DAY_COUNTS = ["ACT360", "ACT365"]
STATUSES = ["NORMAL", "SETTLED", "PENDING"]
SECURITY_TYPES = ["UST", "AgencyMBS", "IGCorp"]
HAIRCUT_BASES = ["PCT", "BPS"]
COUNTERPARTY_NAMES = [
    ("CP001", "Goldman Sachs"),
    ("CP002", "JPMorgan Chase"),
    ("CP003", "Morgan Stanley"),
    ("CP004", "Barclays"),
    ("CP005", "Deutsche Bank"),
    ("CP006", "Citadel Securities"),
    ("CP007", "BNP Paribas"),
    ("CP008", "HSBC"),
    ("CP009", "Nomura"),
    ("CP010", "State Street"),
    ("CP011", "BlackRock"),
    ("CP012", "Vanguard"),
]
SP_RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"]
MOODYS_RATINGS = ["Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1"]
FITCH_RATINGS = ["AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+"]
TENORS = ["ON", "1W", "2W", "1M", "3M", "6M", "1Y"]
COLLATERAL_TYPES = ["UST", "Agency", "IGCorp", "GC"]
BENCHMARKS = ["SOFR", "FedFunds", "TriPartyGC"]
MARGIN_DIRECTIONS = ["ISSUED", "RECEIVED"]
MARGIN_STATUSES = ["PENDING", "AGREED", "DISPUTED", "SETTLED"]
SUB_REASONS = ["UPGRADE", "DOWNGRADE", "COUPON_EVENT", "CLIENT_REQUEST"]
TRADERS = ["jsmith", "kwong", "apatel", "mgarcia", "tyamamoto", "lchen", "rjones", "nbrown"]
SECURITIES = [
    "UST-2Y-2024", "UST-5Y-2024", "UST-10Y-2024", "UST-30Y-2024",
    "UST-2Y-2025", "UST-5Y-2025", "UST-10Y-2025",
    "FNMA-30Y-4.0", "FNMA-30Y-4.5", "FNMA-15Y-3.5",
    "FHLMC-30Y-4.0", "GNMA-30Y-4.5",
    "AAPL-3Y-2027", "MSFT-5Y-2029", "JPM-10Y-2034", "GS-5Y-2029",
]


def _load_repo_sample_data(conn: duckdb.DuckDBPyConnection, config: DomainConfig) -> None:
    catalog = config.trino_catalog
    schema = config.trino_schema
    qs = f"{catalog}.{schema}"
    rng = random.Random(42)

    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{qs}"')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".counterparties (
            counterparty_id VARCHAR,
            name VARCHAR,
            sp_rating VARCHAR,
            moodys_rating VARCHAR,
            fitch_rating VARCHAR,
            collateral_agreement VARCHAR,
            netting_set VARCHAR,
            exposure_limit DECIMAL(18,2)
        )
    ''')
    for i, (cid, cname) in enumerate(COUNTERPARTY_NAMES):
        conn.execute(
            f'INSERT INTO "{qs}".counterparties VALUES (?,?,?,?,?,?,?,?)',
            [cid, cname, SP_RATINGS[i % len(SP_RATINGS)],
             MOODYS_RATINGS[i % len(MOODYS_RATINGS)],
             FITCH_RATINGS[i % len(FITCH_RATINGS)],
             f"CSA-{cid}", f"NS-{cid}",
             rng.randint(5, 50) * 100_000_000.0],
        )

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".trades (
            trade_id VARCHAR,
            trade_date DATE,
            value_date DATE,
            end_date DATE,
            direction VARCHAR,
            trade_type VARCHAR,
            counterparty VARCHAR,
            book VARCHAR,
            repo_rate DECIMAL(8,4),
            rate_type VARCHAR,
            day_count VARCHAR,
            cash_amount DECIMAL(18,2),
            status VARCHAR,
            trader VARCHAR
        )
    ''')

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".collateral (
            trade_id VARCHAR,
            collateral_id INTEGER,
            security_id VARCHAR,
            security_type VARCHAR,
            nominal DECIMAL(18,2),
            clean_price DECIMAL(10,6),
            dirty_price DECIMAL(10,6),
            accrued DECIMAL(10,6),
            haircut DECIMAL(8,4),
            haircut_basis VARCHAR,
            security_value DECIMAL(18,2),
            cash_value DECIMAL(18,2),
            fx_rate DECIMAL(10,6)
        )
    ''')

    base_date = date(2024, 1, 2)
    trade_id_counter = 1000
    tenor_days = {"ON": 1, "1W": 7, "2W": 14, "1M": 30, "3M": 91, "6M": 182, "1Y": 365}

    for day_offset in range(0, 365):
        trade_date = base_date + timedelta(days=day_offset)
        if trade_date.weekday() >= 5:
            continue
        num_trades = rng.randint(8, 25)
        for _ in range(num_trades):
            trade_id_counter += 1
            tid = f"RPT-{trade_id_counter:06d}"
            direction = rng.choice(DIRECTIONS)
            trade_type = rng.choices(TRADE_TYPES, weights=[40, 30, 10, 15, 5])[0]
            cpty = rng.choice(COUNTERPARTY_NAMES)[0]
            book = rng.choices(BOOKS, weights=[50, 35, 15])[0]
            rate_type = rng.choices(RATE_TYPES, weights=[60, 30, 10])[0]
            base_rate = rng.uniform(4.5, 5.8) if rate_type == "FIXED" else rng.uniform(4.3, 5.5)
            tenor_key = rng.choices(list(tenor_days.keys()), weights=[30, 20, 10, 15, 15, 7, 3])[0]
            days = tenor_days[tenor_key]
            value_date = trade_date + timedelta(days=rng.choice([0, 1, 2]))
            end_date = value_date + timedelta(days=days) if rng.random() > 0.1 else None
            cash = rng.randint(10, 500) * 1_000_000.0
            status = rng.choices(STATUSES, weights=[60, 30, 10])[0]

            conn.execute(
                f'INSERT INTO "{qs}".trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                [tid, trade_date, value_date, end_date, direction, trade_type,
                 cpty, book, round(base_rate, 4), rate_type,
                 rng.choice(DAY_COUNTS), cash, status, rng.choice(TRADERS)],
            )

            num_collateral = 1 if trade_type not in ("TriParty", "GCRepo") else rng.randint(2, 4)
            for col_idx in range(num_collateral):
                sec = rng.choice(SECURITIES)
                sec_type = "UST" if sec.startswith("UST") else ("AgencyMBS" if sec.startswith(("FNMA", "FHLMC", "GNMA")) else "IGCorp")
                nominal = cash * rng.uniform(1.01, 1.08)
                clean = rng.uniform(95.0, 105.0)
                accrued = rng.uniform(0.1, 2.5)
                dirty = clean + accrued
                haircut = rng.uniform(1.0, 5.0) if sec_type != "UST" else rng.uniform(0.5, 2.0)
                sec_val = nominal * dirty / 100.0
                cash_val = sec_val * (1 - haircut / 100.0)

                conn.execute(
                    f'INSERT INTO "{qs}".collateral VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    [tid, col_idx, sec, sec_type, round(nominal, 2),
                     round(clean, 6), round(dirty, 6), round(accrued, 6),
                     round(haircut, 4), "PCT", round(sec_val, 2),
                     round(cash_val, 2), 1.0],
                )

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".rates (
            rate_date DATE,
            collateral_type VARCHAR,
            tenor VARCHAR,
            rate DECIMAL(8,4),
            benchmark VARCHAR,
            spread DECIMAL(8,4)
        )
    ''')
    for day_offset in range(0, 365):
        rd = base_date + timedelta(days=day_offset)
        if rd.weekday() >= 5:
            continue
        for ct in COLLATERAL_TYPES:
            for tenor in TENORS:
                base = 5.30 + rng.uniform(-0.3, 0.3)
                tenor_adj = {"ON": -0.10, "1W": -0.05, "2W": 0.0, "1M": 0.05, "3M": 0.10, "6M": 0.15, "1Y": 0.20}[tenor]
                type_adj = {"UST": -0.05, "Agency": 0.0, "IGCorp": 0.15, "GC": -0.02}[ct]
                rate = base + tenor_adj + type_adj
                spread = rate - base
                bm = rng.choice(BENCHMARKS)
                conn.execute(
                    f'INSERT INTO "{qs}".rates VALUES (?,?,?,?,?,?)',
                    [rd, ct, tenor, round(rate, 4), bm, round(spread, 4)],
                )

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".margin_calls (
            call_id VARCHAR,
            call_date DATE,
            counterparty VARCHAR,
            collateral_agreement VARCHAR,
            direction VARCHAR,
            amount DECIMAL(18,2),
            status VARCHAR,
            settlement_date DATE
        )
    ''')
    call_counter = 5000
    for day_offset in range(0, 365):
        cd = base_date + timedelta(days=day_offset)
        if cd.weekday() >= 5:
            continue
        num_calls = rng.randint(2, 8)
        for _ in range(num_calls):
            call_counter += 1
            cpty = rng.choice(COUNTERPARTY_NAMES)[0]
            direction = rng.choice(MARGIN_DIRECTIONS)
            amount = rng.randint(1, 50) * 1_000_000.0
            status = rng.choices(MARGIN_STATUSES, weights=[15, 50, 10, 25])[0]
            settle = cd + timedelta(days=rng.randint(1, 3)) if status == "SETTLED" else None
            conn.execute(
                f'INSERT INTO "{qs}".margin_calls VALUES (?,?,?,?,?,?,?,?)',
                [f"MC-{call_counter:06d}", cd, cpty, f"CSA-{cpty}",
                 direction, amount, status, settle],
            )

    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS "{qs}".substitutions (
            sub_id VARCHAR,
            trade_id VARCHAR,
            sub_date DATE,
            original_security VARCHAR,
            replacement_security VARCHAR,
            reason VARCHAR,
            pre_value DECIMAL(18,2),
            post_value DECIMAL(18,2)
        )
    ''')
    sub_counter = 9000
    for day_offset in range(0, 365, 3):
        sd = base_date + timedelta(days=day_offset)
        if sd.weekday() >= 5:
            continue
        num_subs = rng.randint(0, 3)
        for _ in range(num_subs):
            sub_counter += 1
            tid = f"RPT-{rng.randint(1001, trade_id_counter):06d}"
            orig = rng.choice(SECURITIES)
            repl = rng.choice([s for s in SECURITIES if s != orig])
            pre_val = rng.randint(10, 200) * 1_000_000.0
            post_val = pre_val * rng.uniform(0.98, 1.02)
            conn.execute(
                f'INSERT INTO "{qs}".substitutions VALUES (?,?,?,?,?,?,?,?)',
                [f"SUB-{sub_counter:06d}", tid, sd, orig, repl,
                 rng.choice(SUB_REASONS), round(pre_val, 2), round(post_val, 2)],
            )

    counts = {}
    for tbl in ["trades", "collateral", "counterparties", "rates", "margin_calls", "substitutions"]:
        counts[tbl] = conn.execute(f'SELECT COUNT(*) FROM "{qs}".{tbl}').fetchone()[0]
    print(f"[dev] Loaded repo trading sample data: " + ", ".join(f"{c} {t}" for t, c in counts.items()), flush=True)


register_sample_data_loader("repo-trading", _load_repo_sample_data)
