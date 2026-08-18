from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from app.factory.share.RepositoryAcl import AclEntry, RepositoryAcl
from app.utils import errors as err
from app.utils.exceptions import RequestException

if TYPE_CHECKING:
    from app.manager.db.ClientSQL import ClientSQL


class Share(ABC):
    """Base class for all resource sharing (calendars, addressbooks, mail folders, ...).

    Backed by the single, decentralized ``sogo6_acl`` table (see
    ``app.config.db.tables.TABLE_ACL``): one row per ``(resource_type, key, to_user)``, storing
    that user's rights as a JSON blob whose shape is defined by each concrete subclass.

    Concrete subclasses (one per shareable resource type) must:
    - set the ``resource_type`` class attribute (the discriminant stored in the "type" column)
    - implement ``_rights_satisfy`` to interpret their own rights blob
    """

    #: Discriminant stored in the "type" column of sogo6_acl - must be set by subclasses.
    resource_type: str

    def __init__(self, db: ClientSQL) -> None:
        self._repo: RepositoryAcl = RepositoryAcl(db)

    @abstractmethod
    def _rights_satisfy(self, rights: dict, rights_needed: Any) -> bool:
        """Return True if the stored ``rights`` blob satisfies ``rights_needed``.

        ``rights_needed`` shape is defined by the subclass (e.g. a CalendarPermissionAction for
        calendars). Left abstract because each resource type has its own permission model.
        """

    def check_permissions(self, for_user: str, on_key: str, rights_needed: Any) -> bool:
        """Return True if for_user has rights_needed on the resource identified by on_key.

        A missing ACL entry (resource never shared with for_user) always denies.

        :param for_user: uid of the user whose access is being checked.
        :param on_key: opaque key of the shared resource.
        :param rights_needed: resource-specific description of the required access (see the
            concrete subclass' ``_rights_satisfy`` for its shape).
        """
        entry: AclEntry | None = self._repo.find_one(self.resource_type, on_key, for_user)
        if entry is None:
            return False
        return self._rights_satisfy(entry.rights, rights_needed)

    def get_permissions(self, on_key: str) -> list[AclEntry]:
        """Return every ACL entry (one per user) granted on the resource identified by on_key."""
        return self._repo.find_all_for_key(self.resource_type, on_key)

    def get_entry(self, for_user: str, on_key: str) -> AclEntry | None:
        """Return the single ACL entry for (for_user, on_key), or None if never shared."""
        return self._repo.find_one(self.resource_type, on_key, for_user)

    def get_keys_shared_with(self, for_user: str) -> list[AclEntry]:
        """Return every ACL entry (one per resource) granted to for_user, across all resources.

        Used to resolve the resources shared *with* a user (as opposed to get_permissions, which
        resolves the users a given resource is shared *with*).
        """
        return self._repo.find_all_for_to_user(self.resource_type, for_user)

    def add_permissions(self, for_user: str, on_key: str, owner: str, rights: dict) -> None:
        """Grant (or overwrite) for_user's rights on the resource identified by on_key.

        :param for_user: uid of the user receiving the rights.
        :param on_key: opaque key of the shared resource.
        :param owner: uid of the resource owner, stored alongside the entry for reverse lookups.
        :param rights: resource-specific rights blob (see the concrete subclass documentation).
        :raises RequestException: ERROR_SHARE_CANNOT_SHARE_WITH_SELF when for_user == owner.
        """
        if for_user == owner:
            raise RequestException(error=err.ERROR_SHARE_CANNOT_SHARE_WITH_SELF)
        self._repo.upsert(AclEntry(resource_type=self.resource_type, key=on_key, owner=owner, to_user=for_user, rights=rights))

    def update_permissions(self, for_user: str, on_key: str, rights: dict) -> None:
        """Update for_user's existing rights on the resource identified by on_key.

        :raises RequestException: ERROR_SHARE_NOT_FOUND when for_user has no existing entry
            (use add_permissions to create the first grant).
        """
        existing: AclEntry | None = self._repo.find_one(self.resource_type, on_key, for_user)
        if existing is None:
            raise RequestException(error=err.ERROR_SHARE_NOT_FOUND)
        existing.rights = rights
        self._repo.upsert(existing)

    def remove_permissions(self, for_user: str, on_key: str) -> None:
        """Revoke for_user's access to the resource identified by on_key. No-op if absent."""
        self._repo.delete(self.resource_type, on_key, for_user)

    def remove_all_permissions_for_key(self, on_key: str) -> None:
        """Revoke every user's access to the resource identified by on_key.

        Used when the shared resource itself is deleted, to clean up its sogo6_acl rows.
        """
        self._repo.delete_all_for_key(self.resource_type, on_key)
