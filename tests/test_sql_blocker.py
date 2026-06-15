"""Tests for SQL write-operation blocker."""

from data_agent_core.tools.sql_blocker import is_blocked


def test_blocks_insert():
    assert is_blocked("INSERT INTO t VALUES (1)")


def test_blocks_update():
    assert is_blocked("UPDATE t SET x = 1")


def test_blocks_delete():
    assert is_blocked("DELETE FROM t WHERE id = 1")


def test_blocks_drop():
    assert is_blocked("DROP TABLE t")


def test_blocks_alter():
    assert is_blocked("ALTER TABLE t ADD COLUMN x INT")


def test_blocks_create():
    assert is_blocked("CREATE TABLE t (id INT)")


def test_blocks_truncate():
    assert is_blocked("TRUNCATE TABLE t")


def test_blocks_merge():
    assert is_blocked("MERGE INTO t USING s ON t.id = s.id")


def test_blocks_grant():
    assert is_blocked("GRANT SELECT ON t TO user1")


def test_blocks_revoke():
    assert is_blocked("REVOKE SELECT ON t FROM user1")


def test_allows_select():
    assert not is_blocked("SELECT * FROM t")


def test_allows_select_with_join():
    assert not is_blocked("SELECT a.x, b.y FROM a JOIN b ON a.id = b.id")


def test_allows_case_insensitive_select():
    assert not is_blocked("select count(*) from t where year = 2023")


def test_blocks_case_insensitive_drop():
    assert is_blocked("drop table t")
