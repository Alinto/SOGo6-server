from __future__ import annotations
from typing import TYPE_CHECKING

import importlib
import json
import os

import app.module
from app.agent.Agent import agent
from app.agent.jobs.JobCanceller import JobCanceller
from app.agent.jobs.JobPersistency import JobPersistency
from app.manager.agent.ClientAgent import ClientAgent
from app.module.ModuleInitSogo import ModuleInitSogo
from app.module.admin.ModuleAdminConfig import ModuleAdminConfig
from app.utils.exceptions import AggravatedException, BugException
from app.utils.logger.logger import logger
from app.utils import constants as cs
from marshmallow import ValidationError

from .settings.ProcessSetting import process_config

if TYPE_CHECKING:
    from app.manager.cache.ClientRedis import ClientRedis
    from app.auth.User import User


def _load_json_file(path: str) -> dict | None:
    """
    Load and return a JSON file content, or None on error.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Init config file not found: %s", path)
    except json.JSONDecodeError as e:
        logger.error("Init config file is not valid JSON (%s): %s", path, e)
    except OSError as e:
        logger.error("Cannot read init config file (%s): %s", path, e)
    return None


def check_basic_config() -> bool:
    """
    Check if SOGo is already configured with a system config and default domain settings.

    If the database is empty and SOGO_INIT_*_SETTINGS_PATH are set, attempt to
    write those settings to the database. Returns True if settings are present
    (either pre-existing or just written successfully).

    :return: True if SOGo has a valid config
    :rtype: bool
    """
    config_module = ModuleAdminConfig(process_config)
    system_settings = config_module.get_system_settings()
    default_domain_settings = config_module.get_default_domain_settings()
    if system_settings and default_domain_settings:
        return True

    # Settings are missing – try to auto-initialize from JSON files if paths are set
    system_path = process_config.SOGO_INIT_SYSTEM_SETTINGS_PATH
    domain_path = process_config.SOGO_INIT_DOMAIN_SETTINGS_PATH

    if not system_path or not domain_path:
        logger.info("SOGo is not initialized and no JSON config paths are set. Skipping auto-initialization.")
        return False

    logger.info("SOGo is not initialized. Attempting auto-initialization from JSON files.")

    system_data = _load_json_file(system_path)
    domain_data = _load_json_file(domain_path)

    if system_data is None or domain_data is None:
        logger.error("Auto-initialization aborted: could not load one or both JSON config files.")
        return False

    if "settings" not in system_data or "settings" not in domain_data:
        logger.error("Auto-initialization aborted: JSON config files must have a top-level 'settings' key.")
        return False

    errors: list[str] = []

    try:
        config_module.update_system_settings(system_data["settings"])
        logger.info("System settings written from %s", system_path)
    except (ValidationError, AggravatedException, BugException) as e:
        errors.append(f"System settings invalid or could not be written: {e}")

    try:
        config_module.update_domain_default_settings(domain_data["settings"])
        logger.info("Default domain settings written from %s", domain_path)
    except (ValidationError, AggravatedException, BugException) as e:
        errors.append(f"Default domain settings invalid or could not be written: {e}")

    if errors:
        for err_msg in errors:
            logger.error("Auto-initialization error: %s", err_msg)
        return False

    logger.info("SOGo auto-initialization succeeded. Moving to SOGO_OK state.")
    return True

def init_infra() -> tuple[ClientRedis, JobPersistency]:
    """
    Check shared infrastructure (DB, Redis) and build the resources used by both
    the Flask server and the agent worker. Raises ``AggravatedException`` if any
    component is unreachable.
    """
    init_module = ModuleInitSogo(process_config)
    init_module.check_sogo_database()
    cache_client = init_module.check_redis()
    if init_module.errors:
        raise AggravatedException(f"Sogo cannot be initiated because: {init_module.errors}")
    persistency = JobPersistency(
        cache_client, ttl_seconds=process_config.SOGO_P_AGENT_JOB_STATE_TTL_SECONDS,
    )
    init_jobs()
    return cache_client, persistency


def init_sogo() -> tuple[int, ClientRedis, ClientAgent]:
    """
    Init sogo application
    return True if sogo is ok and already configured, False instead
    raise error if the initializaton has problems
    """
    cache_client, persistency = init_infra()
    agent_client = ClientAgent(
        agent, persistency, JobCanceller(agent, persistency), cache_client,
        agent.get_large_store(),
    )

    sogo_state = cs.SOGO_NOT_INIT
    #No errors, check if SOGo already has a configuration
    if check_basic_config():
        sogo_state = cs.SOGO_OK

    return sogo_state, cache_client, agent_client

def init_get_system_and_default_domain_settings() -> tuple[dict, dict]:
    """
    Return the sysem and default domain settings

    :return: (system_settings, default_dimain_settings)
    :rtype: tuple[dict, dict]
    """
    config_module = ModuleAdminConfig(process_config)
    return config_module.get_both_system_and_default_domain_settings()

def init_get_user_domain_settings(user: User) -> dict:
    """
    Return the sysem and default domain settings

    :return: (system_settings, default_dimain_settings)
    :rtype: tuple[dict, dict]
    """
    config_module = ModuleAdminConfig(process_config)
    return config_module.get_one_domain_setting(user.domain)["settings"]

def init_jobs() -> None:
    """Discover and register every Agent job, then wire them into the agent.

    Imports every ``app/module/<name>/jobs/`` submodule so each ``@agent_job``
    decorator registers its worker, then calls ``register_all_job_handlers``.
    Adding a job is purely additive: drop the file in a module's ``jobs/``
    package — no central list to edit.
    """
    _discover_job_modules()
    agent.register_all_job_handlers()


def _discover_job_modules() -> None:
    """Import every ``app/module/<name>/jobs/*.py`` module.

    Importing a worker triggers its ``@agent_job`` decorator (registration) and
    pulls its module-side dependencies. This runs once at boot, after the whole
    app package is loaded, so those imports resolve without a cycle. Importing a
    request DTO module alongside the worker is harmless.

    The scan walks the filesystem rather than ``pkgutil`` because the business
    modules under ``app/module`` are namespace packages (no ``__init__.py``),
    which ``pkgutil.iter_modules`` does not enumerate reliably.
    """
    for module_root in app.module.__path__:
        for module_name in os.listdir(module_root):
            jobs_dir = os.path.join(module_root, module_name, "jobs")
            if not os.path.isdir(jobs_dir):
                continue
            for file_name in os.listdir(jobs_dir):
                if file_name.endswith(".py") and not file_name.startswith("_"):
                    importlib.import_module(f"app.module.{module_name}.jobs.{file_name[:-3]}")
