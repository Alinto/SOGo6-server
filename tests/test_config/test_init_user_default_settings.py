"""
Unit tests for the initialization of the global default user preferences (app.config.init_config).
"""
import json

from marshmallow import ValidationError

from app.config import init_config
from app.utils.exceptions import BugException


class FakeModuleAdminConfig:
    """Fake ModuleAdminConfig recording the updates of the default user preferences."""

    def __init__(self, current=None, fail_first_with=None):
        self.current = current or {}
        self.fail_first_with = fail_first_with
        self.update_calls = []

    def get_user_default_settings(self):
        return self.current

    def update_user_default_settings(self, new_param):
        self.update_calls.append(new_param)
        if self.fail_first_with is not None and len(self.update_calls) == 1:
            raise self.fail_first_with
        return "S000000", new_param


def _set_init_path(monkeypatch, path):
    monkeypatch.setattr(init_config.process_config, "SOGO_INIT_USER_SETTINGS_PATH", path)


def test_already_filled_is_not_overwritten(monkeypatch):
    """Existing default user preferences are never overwritten at init."""
    _set_init_path(monkeypatch, "")
    module = FakeModuleAdminConfig(current={"USER_GENERAL": {"SOGO_U_LANGUAGE": "French"}})

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == []


def test_empty_without_path_uses_marshmallow_defaults(monkeypatch):
    """Without init file, the column is filled with the marshmallow defaults (empty patch)."""
    _set_init_path(monkeypatch, "")
    module = FakeModuleAdminConfig()

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == [{}]


def test_empty_with_file_uses_file(monkeypatch, tmp_path):
    """The init file content is used when the path is set."""
    settings = {"USER_GENERAL": {"SOGO_U_LANGUAGE": "French"}}
    init_file = tmp_path / "user_settings.json"
    init_file.write_text(json.dumps({"settings": settings}), encoding="utf-8")
    _set_init_path(monkeypatch, str(init_file))
    module = FakeModuleAdminConfig()

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == [settings]


def test_unusable_file_uses_marshmallow_defaults(monkeypatch, tmp_path):
    """A missing file or a file without 'settings' key falls back on the marshmallow defaults."""
    init_file = tmp_path / "user_settings.json"
    init_file.write_text(json.dumps({"no_settings": {}}), encoding="utf-8")
    _set_init_path(monkeypatch, str(init_file))
    module = FakeModuleAdminConfig()

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == [{}]


def test_invalid_file_content_falls_back_on_marshmallow_defaults(monkeypatch, tmp_path):
    """Invalid values in the init file never block the init: marshmallow defaults are stored."""
    settings = {"USER_GENERAL": {"SOGO_U_TIMEZONE": "Not/A_Timezone"}}
    init_file = tmp_path / "user_settings.json"
    init_file.write_text(json.dumps({"settings": settings}), encoding="utf-8")
    _set_init_path(monkeypatch, str(init_file))
    module = FakeModuleAdminConfig(fail_first_with=ValidationError({"field": ["Invalid value"]}))

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == [settings, {}]


def test_write_error_does_not_raise(monkeypatch):
    """A database error is logged and does not block the init."""
    _set_init_path(monkeypatch, "")
    module = FakeModuleAdminConfig(fail_first_with=BugException("rows updated: 0"))

    init_config._init_user_default_settings(module)  # pylint: disable=protected-access

    assert module.update_calls == [{}]
