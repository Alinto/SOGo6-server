"""
Updates of the SOGo database between versions

Each version of LIST_UPDATE_VERSIONS has a script update_MAJOR_MINOR.py with a method update()
"""
from importlib import import_module

from packaging.version import Version

from app.utils.exceptions import AggravatedException
from app.utils.logger.logger import logger

# Versions which need an update of the database. Only major and minor versions, never a patch (6.1 OK, 6.1.5 KO)
#LIST_UPDATE_VERSIONS: list[Version] = []
LIST_UPDATE_VERSIONS: list[Version] = [Version("6.0")]


def _major_minor(version: Version) -> tuple[int, int]:
    """
    Return the part of a version which decides if an update applies. A pre-release of a version has
    the updates of this version (6.1.0rc1 needs update_6_1), which comparing whole versions would miss
    as 6.1.0rc1 < 6.1
    """
    return version.major, version.minor


def get_versions_to_update(stored_version: Version, current_version: Version) -> list[Version]:
    """
    Return the versions which need an update to go from the stored version to the current one, in order

    :param stored_version: Version stored in the database
    :type stored_version: Version
    :param current_version: Current version of SOGo
    :type current_version: Version
    :return: Versions to update, empty if there is not
    :rtype: list[Version]
    """
    return sorted(version for version in LIST_UPDATE_VERSIONS
                  if _major_minor(stored_version) < _major_minor(version) <= _major_minor(current_version))


def run_update(version: Version) -> None:
    """
    Execute the update script of a version

    :param version: Version of LIST_UPDATE_VERSIONS
    :type version: Version
    :raises AggravatedException: if the update failed, whatever the reason
    """
    try:
        import_module(f"{__name__}.update_{version.major}_{version.minor}").update()
    except Exception as e:
        logger.error("Update of the database to version %s failed: %s", version, repr(e))
        raise AggravatedException(f"Update of the database to version {version} failed: {e}") from e
