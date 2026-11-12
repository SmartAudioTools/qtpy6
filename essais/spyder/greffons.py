"""Les greffons de SmartPythonEditor dans la page (W551, 12/11/2026) : spe.py avec le volet pylint gardé actif (le greffon
spyder_code_analysis s'appuie sur lui), puis, la fenêtre ouverte, un relevé par greffon : inscrit ou non, et son action
principale lancée. ``site/index.html?script=greffons.py`` ; sur le bureau : ``$P greffons.py``.

Instrumentation d'essai : le relevé imprimé (« greffon … ») est ce que lit la sonde, pas du code d'application."""

import os
import sys


def _dire(texte):
    """Le relevé va au journal de la page : la console interne de Spyder a pris sys.stdout (rapport de jalon7)."""
    print(texte, file=sys.__stdout__, flush=True)

ICI = os.path.dirname(os.path.abspath(__file__))
_source = open(os.path.join(ICI, "spe.py"), encoding="utf-8").read()
_avant = 'for section in "plots help onlinehelp historylog pylint completions".split():'
assert _source.count(_avant) == 1
_source = _source.replace(_avant, _avant.replace(" pylint", ""))  # garder le volet pylint : spyder_code_analysis l'emploie
_exec = 'exec(compile(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "jalon7.py")).read(), "jalon7.py", "exec"))'
assert _source.count(_exec) == 1
_source = _source.replace(_exec, "SUITE_SPE = SUITE\nSUITE = SUITE_GREFFONS\n" + _exec)

GREFFONS = {"smartos_code_analysis": "spyder_code_analysis", "smartteacher": "spyder_smartteacher",
            "spyder_collab": "spyder_collab", "python_tutor": "spyder_python_tutor", "smartos_stop": "spyder_stop_toolbar",
            "interpreter_toolbar": "spyder_interpreter_toolbar", "pyxel_game": "spyder_pyxel"}
ECHANTILLON = "def carre(x):\n    return x * x\n\n\nimport os\nprint(carre(3))\n"


def _essayer(nom, action):
    import traceback
    try:
        _dire(f"greffon {nom} : action -> {action()!r}")
    except Exception as e:  # noqa: BLE001 - le relevé veut la cause, quelle qu'elle soit
        _dire(f"greffon {nom} : action CASSE {type(e).__name__}: {e}")
        traceback.print_exc()


def SUITE_GREFFONS(main, rapport):  # noqa: N802
    import tempfile
    from qtpy6.QtCore import QTimer
    SUITE_SPE(main, lambda: None)  # noqa: F821 - défini par la source de spe.py
    for nom, paquet in GREFFONS.items():
        _dire(f"greffon {paquet} ({nom}) : {'INSCRIT' if main.get_plugin(nom, error=False) else 'ABSENT'}")
    collab = main.get_plugin("spyder_collab", error=False)
    if collab:  # avant editor.load, après lequel la page ne rend plus rien (item 14)
        _essayer("spyder_collab", lambda: _collab(collab))
    fichier = os.path.join(tempfile.mkdtemp(prefix="greffons-"), "essai.py")
    with open(fichier, "w", encoding="utf-8") as f:
        f.write(ECHANTILLON)
    QTimer.singleShot(3000, lambda: main.get_plugin("editor").load(fichier))  # l'échange du collab passe avant (W563)
    etapes = []
    analyse = main.get_plugin("smartos_code_analysis", error=False)
    if analyse:
        etapes.append(("spyder_code_analysis", analyse.run_code_analysis))
    tuteur = main.get_plugin("python_tutor", error=False)
    if tuteur:
        etapes.append(("spyder_python_tutor", lambda: _tuteur(main, tuteur)))
    st = main.get_plugin("smartteacher", error=False)
    if st:
        etapes.append(("spyder_smartteacher", lambda: _smartteacher(st)))

    def suivante():
        if etapes:
            nom, action = etapes.pop(0)
            _essayer(nom, action)
            QTimer.singleShot(6000, suivante)
        else:
            _bilan(main)
            rapport()
    QTimer.singleShot(4000, suivante)


def _tuteur(main, tuteur):
    """Ce que fait le bouton « Lancer » du volet : tracer le fichier courant (run_trace.py en QProcess), puis la vue web."""
    for nom in ("run_current_file", "_run_current_file", "trace_current_file", "_on_run"):
        for cible in (tuteur, tuteur.get_widget()):
            if hasattr(cible, nom):
                getattr(cible, nom)()
                return f"{type(cible).__name__}.{nom}"
    return "aucune méthode de lancement trouvée : " + ", ".join(n for n in dir(tuteur.get_widget()) if "run" in n.lower())


def _smartteacher(st):
    w = st.get_widget()
    return "méthodes : " + ", ".join(n for n in dir(w) if not n.startswith("__") and n.islower())[:600]


def _collab(collab):
    """QtNetwork dans la page (W563) : un octet QTcpSocket → QTcpServer, puis le transport du greffon lui-même (un
    CollabPeer hôte, un invité sur 127.0.0.1 : la trame hello décodée par l'hôte devient ``sig_join_request``)."""
    from qtpy.QtNetwork import QHostAddress, QTcpServer, QTcpSocket
    from spyder_collab.network import CollabPeer, local_addresses

    serveur, client = QTcpServer(collab), QTcpSocket(collab)
    ecoute = serveur.listen(QHostAddress.SpecialAddress.Any, 47830)

    def arrivee():
        bout = serveur.nextPendingConnection()
        bout.readyRead.connect(lambda: _dire(f"greffon spyder_collab : octet reçu {bytes(bout.readAll())!r}"))

    serveur.newConnection.connect(arrivee)
    client.connected.connect(lambda: client.write(b"x"))
    client.connectToHost("127.0.0.1", 47830)
    hote, invite = CollabPeer("hote", "Prof", collab), CollabPeer("invite", "Eleve", collab)
    hote.sig_join_request.connect(lambda site, nom, ip: _dire(f"greffon spyder_collab : demande de {nom} ({site}, {ip})"))
    invite.sig_error.connect(lambda m: _dire(f"greffon spyder_collab : erreur invité {m}"))
    heberge = hote.host(47831)
    invite.join("127.0.0.1", 47831)
    return f"écoute={ecoute}, hôte={heberge}, adresses={local_addresses()}"


def _bilan(main):
    pylint = main.get_plugin("pylint", error=False)
    if pylint is not None:
        w = pylint.get_widget()
        _dire(f"greffon spyder_code_analysis : pylint en cours={w.is_running()} ; "
              f"sortie={str(getattr(w, 'output', ''))[:400]!r}")
    tuteur = main.get_plugin("python_tutor", error=False)
    if tuteur is not None:
        w = tuteur.get_widget()
        _dire(f"greffon spyder_python_tutor : vue web={type(getattr(w, '_web', None)).__name__} "
              f"prête={getattr(w, '_web_ready', None)}")


exec(compile(_source, os.path.join(ICI, "spe.py"), "exec"))
