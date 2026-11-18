"""
Fakes shared by the MFA tests: cache, database and process settings.
"""
import json

import pyotp

from app.config.settings.DomainSettings import AuthSettingsObj


VOUCHER_SECRET = "a" * 32


class FakeProcess:
    """Fake ProcessSetting: only what the MFA code reads."""
    SOGO_P_VOUCHER_SECRET = VOUCHER_SECRET

    def __getitem__(self, key):
        return getattr(self, key)

    def get_db_settings(self):
        return {}


class FakeCache:
    """In-memory stand-in for ClientRedis (decode_responses=True: hash values come back as str)."""

    def __init__(self):
        self.store: dict = {}
        self.hashes: dict = {}
        self.ttls: dict = {}
        self.closed = 0

    def set(self, key, value, ttl, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = value if isinstance(value, str) else json.dumps(value)
        self.ttls[key] = ttl
        return True

    def get(self, key, expected_type):
        value = self.store.get(key)
        if value is None:
            return None
        return value if expected_type is str else json.loads(value)

    def delete(self, *keys):
        count = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                count += 1
            if key in self.hashes:
                del self.hashes[key]
                count += 1
        return count

    def hashset(self, key, data, ttl):
        self.hashes.setdefault(key, {}).update({k: str(v) for k, v in data.items()})
        if ttl > 0:
            self.ttls[key] = ttl
        return True

    def hashget(self, key):
        return dict(self.hashes[key]) if key in self.hashes else {}

    def hash_incr(self, key, field, amount=1):
        hash_data = self.hashes.setdefault(key, {})
        hash_data[field] = str(int(hash_data.get(field, 0)) + amount)
        return int(hash_data[field])

    def incr(self, key, ttl):
        value = int(self.store.get(key, 0)) + 1
        self.store[key] = str(value)
        self.ttls.setdefault(key, ttl)
        return value

    def close(self):
        self.closed += 1


class FakeMfaDB:
    """Fake ClientSQL for the mfa_method column: uid -> stored value."""

    def __init__(self, methods=None):
        self.methods: dict = methods if methods is not None else {}

    def connect(self):
        return None

    def select_from_table(self, table, columns, condition=None):
        uid = condition.param_value
        if uid not in self.methods:
            return []
        return [(self.methods[uid],)]

    def update_in_table(self, table_name, column_tuple, values_list, condition):
        uid = condition.param_value
        if uid not in self.methods:
            return 0
        self.methods[uid] = values_list[0]
        return 1


def auth_settings(methods=("totp",), enabled=True, force=False, auth_type="plain", issuer="SOGo"):
    """Build the effective auth settings of a domain."""
    return AuthSettingsObj({
        "SOGO_D_AUTH_TYPE": auth_type,
        "SOGO_D_LOGIN_MFA": enabled,
        "SOGO_D_LOGIN_MFA_METHOD": list(methods),
        "SOGO_D_LOGIN_MFA_FORCE": force,
        "SOGO_D_LOGIN_MFA_TOTP_ISSUER": issuer,
    })


def totp_code(secret: str, at: float) -> str:
    """Code of a base32 secret at a given time."""
    return pyotp.TOTP(secret).at(int(at))
