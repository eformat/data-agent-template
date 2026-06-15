"""Pytest plugin — auto-registers fixtures and markers."""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "trino_live: requires live Trino connection")
    config.addinivalue_line("markers", "mlflow_live: requires live MLflow connection")
    config.addinivalue_line("markers", "kfp_live: requires live KFP connection")
