"""
Unit tests for the selection and the execution of the database updates
"""
import importlib
import sys
from types import ModuleType

import pytest
from packaging.version import Version

import app.update
from app.update import LIST_UPDATE_VERSIONS, get_versions_to_update, run_update
from app.utils.exceptions import AggravatedException


@pytest.mark.parametrize("stored, current, expected", [
    ("6.0.0", "6.0.5", []),               # patch: no update
    ("6.0.0", "6.1.0", ["6.1"]),
    ("6.0.5", "6.1.3", ["6.1"]),          # stored version is not in the list
    ("6.1.0", "6.1.5", []),               # stored version is the last update
    ("6.1.0", "6.2.0", ["6.2"]),          # stored version is in the list: take the next one
    ("6.1.5", "6.2.0", ["6.2"]),          # update_6_1 was already applied
    ("6.0.0", "7.0.0", ["6.1", "6.2", "7.0"]),
    ("6.0.0", "6.2.0", ["6.1", "6.2"]),   # later versions are not applied
    ("7.0.0", "7.1.0", []),
    ("6.0.0a2", "6.1.0", ["6.1"]),
    ("6.0.0", "6.1.0a1", ["6.1"]),        # a pre-release needs the update of its version
    ("6.0.0", "6.1.0rc1", ["6.1"]),
    ("6.1.0rc1", "6.1.0", []),            # already applied by the pre-release
    ("6.1", "6.1.0", []),                 # stored after an update, right before the current version
])
def test_get_versions_to_update(monkeypatch, stored, current, expected):
    # Not in order on purpose
    monkeypatch.setattr(app.update, "LIST_UPDATE_VERSIONS", [Version("7.0"), Version("6.1"), Version("6.2")])
    assert get_versions_to_update(Version(stored), Version(current)) == [Version(v) for v in expected]


def test_list_update_versions_is_consistent():
    """Only major and minor versions, each one with its script"""
    for version in LIST_UPDATE_VERSIONS:
        assert version == Version(f"{version.major}.{version.minor}")
        assert callable(importlib.import_module(f"playground.update_{version.major}_{version.minor}").update)


def test_run_update(monkeypatch):
    calls = []
    script = ModuleType("app.update.update_6_1")
    script.update = lambda: calls.append("update")
    monkeypatch.setitem(sys.modules, "app.update.update_6_1", script)
    run_update(Version("6.1"))
    assert calls == ["update"]


def test_run_update_missing_script():
    with pytest.raises(AggravatedException, match="version 99.1 failed"):
        run_update(Version("99.1"))
