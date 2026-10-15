"""Shared pytest fixtures for the AuditMind test suite.

The upload endpoints persist every accepted custom case to
``settings.data_dir / "custom_cases"`` (see ``src/api/server.py``).  Without
isolation each ``pytest`` run drops another JSON file into the developer's real
``data/cases/custom_cases/`` directory and registers it in the process-wide
``_DYNAMIC_CASES_STORE``.  Those files are gitignored, so the pollution is
invisible to ``git status`` but shows up in the product: the case sidebar lists
the same test company once per run, and the advertised case count drifts away
from the 28 authentic benchmark cases.

The fixture below redirects the data directory to a per-test temporary path and
restores the in-memory case store afterwards, so the suite is hermetic.
"""

import pytest

from src.api import server
from src.benchmark import test_cases


@pytest.fixture(autouse=True)
def isolate_case_data(tmp_path, monkeypatch):
    """Keep cases created by a test out of the real data directory and store."""
    monkeypatch.setattr(server.settings, "data_dir", tmp_path / "cases")
    (tmp_path / "cases" / "custom_cases").mkdir(parents=True, exist_ok=True)

    saved_store = dict(test_cases._DYNAMIC_CASES_STORE)
    test_cases._DYNAMIC_CASES_STORE.clear()
    try:
        yield
    finally:
        test_cases._DYNAMIC_CASES_STORE.clear()
        test_cases._DYNAMIC_CASES_STORE.update(saved_store)
