"""
Registry of the MFA providers, by id.

The login flow only knows the MfaProvider interface: adding a method means adding a class
here (and allowing its id in SOGO_D_LOGIN_MFA_METHOD).
"""
from __future__ import annotations
from typing import Type

from app.module.auth.mfa.MfaProvider import MfaProvider
from app.module.auth.mfa.ProviderTotp import ProviderTotp

#ProviderExternalOtp is not registered until it is implemented
_REGISTRY: dict[str, Type[MfaProvider]] = {
    ProviderTotp.id: ProviderTotp,
}


def register_provider(provider_class: Type[MfaProvider]) -> Type[MfaProvider]:
    """
    Register a provider class under its id. Can be used as a decorator.

    :param provider_class: class inheriting MfaProvider with a non empty id
    :type provider_class: Type[MfaProvider]
    :raises ValueError: if the id is empty
    :return: the class itself
    :rtype: Type[MfaProvider]
    """
    if not provider_class.id:
        raise ValueError(f"MFA provider {provider_class.__name__} has no id")
    _REGISTRY[provider_class.id] = provider_class
    return provider_class


def unregister_provider(provider_id: str) -> None:
    """
    Remove a provider from the registry (mainly for tests)
    """
    _REGISTRY.pop(provider_id, None)


def get_provider_class(provider_id: str) -> Type[MfaProvider] | None:
    """
    Return the provider class registered under this id, None if unknown
    """
    return _REGISTRY.get(provider_id)


def registered_provider_ids() -> tuple[str, ...]:
    """
    Return the ids of all registered providers
    """
    return tuple(_REGISTRY)
