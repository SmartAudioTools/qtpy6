"""Les avertissements que Qt-WASM émet par construction, sans faute de l'application : ``qInstallMessageHandler`` les
retire avant de passer la main au gestionnaire de l'application (12/10/2026).

Qt-WASM est construit sans ICU : ``QCollator`` y retombe sur l'implémentation POSIX, qui avertit à chaque réglage
qu'elle ne sait pas honorer. ``QFileSystemModel`` le règle lui-même (tri sans casse, numérique) : tout explorateur de
fichiers les émet, et Spyder, qui affiche les messages Qt dans son rapport d'erreur, ouvrait « problème interne »."""

from __future__ import annotations

from typing import Any, Callable

BRUIT = ("Case insensitive sorting unsupported in the posix collation implementation",
         "Numeric mode unsupported in the posix collation implementation")


def doubler(espace: dict[str, Any]) -> None:
    """Remplace ``qInstallMessageHandler`` dans qtpy6.QtCore et dans le QtCore du binding, et pose d'emblée le filtre seul (sans
    gestionnaire d'application, Qt écrirait ces lignes sur la sortie d'erreur)."""
    import importlib  # noqa: PLC0415
    import sys  # noqa: PLC0415

    from qtpy6 import _binding  # noqa: PLC0415
    module = importlib.import_module(f"{_binding.API_NAME}.QtCore")
    original = module.qInstallMessageHandler

    def qInstallMessageHandler(gestionnaire: Callable[..., Any] | None) -> Any:  # noqa: N802
        suite = gestionnaire or (lambda type_, contexte, message: sys.stderr.write(message + "\n"))

        def filtre(type_: Any, contexte: Any, message: str) -> Any:
            return None if message in BRUIT else suite(type_, contexte, message)
        return original(filtre)

    espace["qInstallMessageHandler"] = qInstallMessageHandler
    module.qInstallMessageHandler = qInstallMessageHandler  # aussi pour qui lit le binding directement (qtpy, dont Spyder)
    qInstallMessageHandler(None)
