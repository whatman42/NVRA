"""Shared pytest config — Phase 3B-C markers."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "windows_integration: requires real Windows host + optional MT4/MT5 (skipped on Linux CI)",
    )
