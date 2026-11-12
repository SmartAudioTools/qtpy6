"""Doublure de ``keyring`` dans la page (4d, W559, 12/11/2026) : un navigateur n'a pas de trousseau, la vraie roue (et ses
jaraco.*) lèverait ``NoKeyringError`` à la première option secrète. Les mots de passe vivent ici en mémoire de la page,
le temps de la session : Spyder les lit et les écrit (``config/manager.py``, options ``secure``) sans erreur, et le
client distant (``remoteclient/widgets/container.py``) voit un trousseau qui fonctionne. Rien n'est persisté.
Posée par ``qtpy6.web.lancer`` ; rien en natif (le vrai keyring)."""

import sys
import types


class KeyringError(Exception):
    pass


class NoKeyringError(KeyringError, RuntimeError):  # comme le vrai keyring
    pass


class PasswordDeleteError(KeyringError):
    pass


class MemoireKeyring:
    """Trousseau en mémoire de la page."""
    priority = 1

    def __init__(self):
        self._mots = {}

    def get_password(self, service, nom):
        return self._mots.get((service, nom))

    def set_password(self, service, nom, mot):
        self._mots[(service, nom)] = mot

    def delete_password(self, service, nom):
        if self._mots.pop((service, nom), None) is None:
            raise PasswordDeleteError(f"{service}/{nom} absent")


class _Echec:
    """``keyring.backends.fail.Keyring`` : la classe existe pour les ``isinstance``, le trousseau servi n'en est pas une."""
    priority = 0


_TROUSSEAU = MemoireKeyring()


def _module(nom, **attrs):
    m = types.ModuleType(nom)
    m.__dict__.update(attrs)
    return m


def installer():
    if "keyring" in sys.modules:
        return
    errors = _module("keyring.errors", NoKeyringError=NoKeyringError, PasswordDeleteError=PasswordDeleteError,
                     KeyringError=KeyringError)
    fail = _module("keyring.backends.fail", Keyring=_Echec)
    backends = _module("keyring.backends", __path__=[], fail=fail)
    keyring = _module("keyring", __path__=[], errors=errors, backends=backends,
                      get_keyring=lambda: _TROUSSEAU, set_keyring=lambda k: None,
                      get_password=_TROUSSEAU.get_password, set_password=_TROUSSEAU.set_password,
                      delete_password=_TROUSSEAU.delete_password)
    sys.modules.update({"keyring": keyring, "keyring.errors": errors, "keyring.backends": backends,
                        "keyring.backends.fail": fail})
