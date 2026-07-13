#!/usr/bin/env python3
"""
Script de test de connexion ManageSieve (ClientSieve).

Usage:
    python3 scripts/test_sieve_connection.py [OPTIONS]

Options:
    --server      Hostname ou IP du serveur Sieve (défaut: localhost)
    --port        Port ManageSieve (défaut: 4190)
    --encryption  Chiffrement : None | StartTLS | SSL/TLS  (défaut: None)
    --auth-mech   Mécanisme d'auth : plain | xoauth2 | none  (défaut: plain)
    --username    Nom d'utilisateur (demandé interactivement si absent)
    --password    Mot de passe (demandé interactivement si absent)

Exemples:
    # Connexion sans chiffrement
    python3 scripts/test_sieve_connection.py --server dovecot --username user@example.com

    # Connexion avec STARTTLS
    python3 scripts/test_sieve_connection.py --server mail.example.com --encryption StartTLS

    # Connexion SSL/TLS implicite
    python3 scripts/test_sieve_connection.py --server mail.example.com --port 5190 --encryption SSL/TLS
"""
import sys
import os

# Permet d'importer les modules du projet depuis la racine du workspace
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.manager.mail.ClientSieve import ClientSieve
from app.utils.exceptions import RequestException, BugException
from app.utils import constants as cs

SERVER = "dovecot"
PORT = 4190
ENCRYPTION = cs.SOCKET_ENC_PLAIN
AUTH_MECH = "plain"
USERNAME = "sogo-tests1@example.org"
PASSWORD = "sogo"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_separator(char: str = "-", width: int = 60) -> None:
    print(char * width)


def _print_section(title: str) -> None:
    _print_separator("=")
    print(f"  {title}")
    _print_separator("=")


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")


def _info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# Test steps
# ---------------------------------------------------------------------------

def step_connect(client: ClientSieve) -> bool:
    _print_section("Étape 1 – Initialisation du client (connect)")
    try:
        client.connect()
        _ok(f"Client initialisé pour {client.server}:{client.port} (encryption={client.encryption})")
        return True
    except BugException as e:
        _fail(f"BugException [{e.err()}]: {e}")
        return False


def step_login(client: ClientSieve, username: str, password: str) -> bool:
    _print_section("Étape 2 – Authentification (login)")
    try:
        client.login(username, password)
        _ok(f"Authentifié en tant que '{username}'")
        return True
    except RequestException as e:
        _fail(f"RequestException [{e.err()}]: {e}")
        return False
    except BugException as e:
        _fail(f"BugException [{e.err()}]: {e}")
        return False


def step_list_scripts(client: ClientSieve) -> bool:
    _print_section("Étape 3 – Listage des scripts (list_scripts)")
    try:
        active, scripts = client.list_scripts()
        _ok(f"Script actif   : {active!r}")
        _ok(f"Autres scripts : {scripts}")
        return True
    except RequestException as e:
        _fail(f"RequestException [{e.err()}]: {e}")
        return False
    except BugException as e:
        _fail(f"BugException [{e.err()}]: {e}")
        return False


def step_logout(client: ClientSieve) -> None:
    _print_section("Étape 4 – Déconnexion (logout)")
    try:
        client.logout()
        _ok("Déconnexion réussie")
    except (RequestException, BugException) as e:
        _info(f"Erreur lors du logout (non bloquante) : {e}")




def main() -> int:

    print()
    _print_separator("*")
    print("  Test de connexion ManageSieve – ClientSieve")
    _print_separator("*")
    _info(f"Serveur     : {SERVER}:{PORT}")
    _info(f"Chiffrement : {ENCRYPTION}")
    _info(f"Auth mech   : {AUTH_MECH}")
    _info(f"Utilisateur : {USERNAME}")
    print()

    client = ClientSieve(
        server=SERVER,
        port=PORT,
        encryption=ENCRYPTION,
        auth_mech=AUTH_MECH,
    )

    success = True

    if not step_connect(client):
        success = False

    if success and not step_login(client, USERNAME, PASSWORD):
        success = False

    if success:
        step_list_scripts(client)

    if client.connected:
        step_logout(client)

    print()
    _print_separator("*")
    if success:
        print("  Résultat : SUCCÈS")
    else:
        print("  Résultat : ÉCHEC")
    _print_separator("*")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
