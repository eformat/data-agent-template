"""SQL write-operation blocker."""

import re

BLOCKED_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def is_blocked(sql: str) -> bool:
    """Return True if the SQL contains a blocked write operation."""
    return bool(BLOCKED_SQL.search(sql))
