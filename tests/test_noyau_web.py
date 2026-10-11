"""Jalon 8a : le noyau Jupyter de Spyder dans un Web Worker, vérifié en natif tant que cela se peut sans vrai js ni JSPI
(``subprocess.Popen`` doublé, canal zmq page<->Worker, préambule du Worker). Ce qui dépend du vrai navigateur
(``run_sync``, ``postMessage``, ``loadPyodide``) n'est pas ici : js et pyodide sont remplacés par de faux modules."""

import asyncio
import io
import os
import subprocess
import sys
import textwrap
import threading
import time
import types
from pathlib import Path

import pytest

from qtpy6.web import fils, psutil_web, sous_processus, travailleur, zmq_web

RACINE = Path(__file__).resolve().parents[1]
PREAMBULE = RACINE / "qtpy6" / "web" / "preambule.py"


def _preambule():
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location("_preambule_essai", PREAMBULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- 1. _commande : -X et -W tolérés, le dossier d'un -m --------------------------------------------------------------

@pytest.mark.parametrize("options", [["-X", "frozen_modules=off"], ["-Xfrozen_modules=off"], ["-W", "ignore"],
                                     ["-u", "-X", "utf8", "-W", "error"]])
def test_commande_tolere_x_et_w(options):
    assert travailleur._commande([*options, "-m", "a.b", "-f", "x.json"]) == ("a.b", ["-m", "a.b", "-f", "x.json"])


def test_commande_refuse_toujours_c():
    with pytest.raises(ValueError):
        travailleur._commande(["-c", "print(1)"])


def test_source_module_est_l_entree_du_sys_path_de_la_page(tmp_path, monkeypatch):
    """Toute l'entrée, pas le paquet seul : le noyau importe ses voisins (ipykernel, IPython…), mesuré au jalon 8a."""
    (tmp_path / "monpaquet").mkdir()
    (tmp_path / "monpaquet" / "__init__.py").write_text("")
    (tmp_path / "monpaquet" / "sous.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert travailleur._source_module("monpaquet.sous", "/cwd") == str(tmp_path)
    assert travailleur._source_module("introuvable_xyz.m", "/cwd") == "/cwd"


# --- 2. l'environnement de Popen arrive au Worker ----------------------------------------------------------------------

class FauxWorker:
    def __init__(self):
        self.postes = []

    def postMessage(self, message, transferts=()):
        self.postes.append(message)

    def terminate(self):
        pass


@pytest.fixture
def faux_js(monkeypatch):
    """Un ``js`` et un ``pyodide.ffi`` suffisants pour ``ProcessusWeb.start`` et ``_poster_zmq``."""
    worker = FauxWorker()
    js = types.ModuleType("js")
    js.Worker = types.SimpleNamespace(new=lambda *a, **k: worker)
    ffi = types.ModuleType("pyodide.ffi")
    ffi.create_proxy = lambda f: f
    ffi.to_js = lambda o, **k: types.SimpleNamespace(buffer=o) if isinstance(o, bytes) else o
    pyodide = types.ModuleType("pyodide")
    pyodide.ffi = ffi
    monkeypatch.setitem(sys.modules, "js", js)
    monkeypatch.setitem(sys.modules, "pyodide", pyodide)
    monkeypatch.setitem(sys.modules, "pyodide.ffi", ffi)
    monkeypatch.setattr(travailleur, "_objet", lambda m: m)
    monkeypatch.setattr(travailleur, "_index_url", lambda: "http://x/")
    monkeypatch.setattr(travailleur, "_roues", lambda: {})
    monkeypatch.setattr(travailleur, "_zipper", lambda *a, **k: b"zip")
    monkeypatch.setattr(travailleur, "_url_worker", lambda: "blob:x")
    return worker


def test_start_transmet_env_et_dossier_web(faux_js, tmp_path):
    p = travailleur.ProcessusWeb()
    p.setProcessEnvironment({"JPY_PARENT_PID": "40000", "JUPYTER_RUNTIME_DIR": "/rt"})
    p.setWorkingDirectory(str(tmp_path))
    p.start(sys.executable, ["-X", "frozen_modules=off", "-m", "json.tool"])
    lancer = faux_js.postes[0]["lancer"]
    assert lancer["env"] == {"JPY_PARENT_PID": "40000", "JUPYTER_RUNTIME_DIR": "/rt"}
    assert lancer["web"] == str(RACINE / "qtpy6" / "web")
    assert lancer["argv"] == ["-m", "json.tool"]


def test_set_process_environment_accepte_un_qprocessenvironment(faux_js):
    from qtpy6.QtCore import QProcessEnvironment  # noqa: PLC0415

    env = QProcessEnvironment()
    env.insert("A", "1=2")
    p = travailleur.ProcessusWeb()
    p.setProcessEnvironment(env)
    p.start(sys.executable, ["x.py"])
    assert faux_js.postes[0]["lancer"]["env"] == {"A": "1=2"}


# --- 3. subprocess.Popen doublé ---------------------------------------------------------------------------------------

class FauxProcessus(travailleur.ProcessusWeb):
    """Un ProcessusWeb sans navigateur : ``start`` note la commande, ``_arrive`` simule la sortie du Worker."""

    dernier = None

    def __init__(self):
        super().__init__()
        FauxProcessus.dernier = self
        self.appels, self.ecrit, self.entree_fermee, self.env, self.tue = [], [], False, None, False

    def start(self, programme="", arguments=(), *_):
        self.appels.append((programme, list(arguments)))

    def write(self, octets):
        self.ecrit.append(bytes(octets))
        return len(octets)

    def closeWriteChannel(self):
        self.entree_fermee = True

    def setProcessEnvironment(self, env):
        self.env = env

    def kill(self):
        self.tue = True
        self.finished.emit(0)  # le vrai le fait au tour suivant


@pytest.fixture
def popen(monkeypatch):
    psutil_web.reinitialiser()
    monkeypatch.setattr(sous_processus, "_fabrique", FauxProcessus)
    monkeypatch.setattr(sous_processus, "_pids", __import__("itertools").count(40000))
    return sous_processus.Popen


CMD = [sys.executable, "-Xfrozen_modules=off", "-m", "spyder_kernels.console", "-f", "c.json"]


def test_popen_programme_autre_que_python(popen):
    with pytest.raises(FileNotFoundError) as e:
        popen(["hg", "id"])
    assert e.value.filename == "hg"


def test_popen_lance_le_worker_avec_cwd_et_env(popen, tmp_path):
    p = popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(tmp_path),
              env={"A": "1"})
    proc = FauxProcessus.dernier
    assert proc.appels == [(sys.executable, CMD[1:])] and p.args == CMD
    assert proc.env == {"A": "1"} and proc.dossier_travail == str(tmp_path)
    assert p.pid == 40000 and psutil_web.pid_exists(40000) and p.poll() is None and p.returncode is None


def test_popen_pids_distincts(popen):
    assert [popen(CMD).pid, popen(CMD).pid] == [40000, 40001]


def test_popen_stdin(popen):
    p = popen(CMD, stdin=subprocess.PIPE)
    p.stdin.write(b"abc")
    p.stdin.flush()
    assert FauxProcessus.dernier.ecrit == [b"abc"] and not FauxProcessus.dernier.entree_fermee
    p.stdin.close()
    assert FauxProcessus.dernier.entree_fermee and p.stdin.closed
    assert popen(CMD, stdin=None).stdin is None


def test_popen_stdout_lectures_et_fin(popen):
    p = popen(CMD, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc = FauxProcessus.dernier
    proc._arrive("sortie", "ab\ncd")
    proc._arrive("sortie_erreur", "err")
    assert p.stdout.readline() == b"ab\n"
    assert p.stdout.read1(1) == b"c" and p.stdout.read1() == b"d" and p.stderr.read1() == b"err"
    proc._arrive("sortie", "fin")
    proc.finished.emit(3)
    assert p.stdout.read() == b"fin" and p.stdout.read1() == b"" and p.stdout.readline() == b""
    assert (p.poll(), p.returncode, p.wait()) == (3, 3, 3)
    assert not psutil_web.pid_exists(p.pid)


def test_popen_read1_suspend_par_attendre(popen, monkeypatch):
    p = popen(CMD, stdout=subprocess.PIPE)
    proc = FauxProcessus.dernier
    appels = []

    def attendre(condition, delai_ms=-1):
        appels.append(delai_ms)
        proc._arrive("sortie", "venu")
        return condition()

    monkeypatch.setattr(fils, "_attendre", attendre)
    assert p.stdout.read1() == b"venu" and appels == [-1]


def test_popen_wait_timeout(popen):
    p = popen(CMD)
    with pytest.raises(subprocess.TimeoutExpired):
        p.wait(timeout=0.01)


def test_popen_kill_et_terminate(popen):
    p, q = popen(CMD), popen(CMD)
    p.kill()
    assert FauxProcessus.dernier is q._p and p.returncode == -9 and not psutil_web.pid_exists(p.pid)
    q.terminate()
    assert q.returncode == -15 and not psutil_web.pid_exists(q.pid)


def test_popen_sigint_signale_sans_tuer(popen, faux_js):
    p = popen(CMD)
    p._p.worker = faux_js
    p.send_signal(2)
    assert p.returncode is None and not p._p.tue and faux_js.postes == [{"signal": 2}] and psutil_web.pid_exists(p.pid)


def test_popen_sorties_redirigees(popen):
    fichier = io.BytesIO()
    p = popen(CMD, stdout=fichier, stderr=subprocess.STDOUT)
    proc = FauxProcessus.dernier
    assert p.stdout is None and p.stderr is None and proc.fusion
    proc._arrive("sortie", "x")
    proc._arrive("sortie_erreur", "y")
    assert fichier.getvalue() == b"xy"
    q = popen(CMD, stdout=subprocess.DEVNULL)
    FauxProcessus.dernier._arrive("sortie", "jeté")  # ne lève pas
    assert q.stdout is None


def test_popen_contexte(popen):
    with popen(CMD, stdout=subprocess.PIPE, stdin=subprocess.PIPE) as p:
        FauxProcessus.dernier.finished.emit(0)
    assert p.stdout.closed and p.stdin.closed


def test_popen_doublee_dans_le_navigateur():
    from test_web import en_navigateur  # noqa: PLC0415

    sortie = en_navigateur("""
        import subprocess
        from qtpy6 import QtCore
        from qtpy6.web import sous_processus
        print(subprocess.Popen is sous_processus.Popen)
    """)
    assert sortie == "True"


# --- 4. le canal zmq côté page ----------------------------------------------------------------------------------------

def test_vers_python_ramene_les_octets_et_les_conteneurs():
    pre = _preambule()
    jsproxy = types.SimpleNamespace(to_py=lambda: memoryview(b"js"))
    resultat = pre._vers_python({"op": "vers_lie", "frames": [memoryview(b"a"), bytearray(b"b"), jsproxy, b"c"],
                                 "t": (1, "x"), "n": None, "d": {"k": memoryview(b"z")}})
    assert resultat == {"op": "vers_lie", "frames": [b"a", b"b", b"js", b"c"], "t": [1, "x"], "n": None,
                        "d": {"k": b"z"}}
    assert all(type(f) is bytes for f in resultat["frames"])


def test_page_recoit_zmq_du_worker():
    zmq_web.reinitialiser()
    p = travailleur.ProcessusWeb()
    p._recevoir(types.SimpleNamespace(data=types.SimpleNamespace(
        to_py=lambda: {"zmq": {"op": "bind", "port": 5555}})))
    assert zmq_web._distants == {5555: p}
    zmq_web.reinitialiser()


def test_page_poste_zmq_au_worker(faux_js):
    p = travailleur.ProcessusWeb()
    p.worker = faux_js
    p._poster_zmq({"op": "connect", "port": 1})
    assert faux_js.postes == [{"zmq": {"op": "connect", "port": 1}}]
    p.worker = None
    p._poster_zmq({"op": "x"})  # sans worker : rien


# --- 5. le préambule du Worker ----------------------------------------------------------------------------------------

def _sous_processus(code):
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], capture_output=True, text=True, timeout=30,
                       env={**os.environ, "PYTHONPATH": ""})
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


ENTETE_WORKER = f"""
import asyncio, importlib.util, sys, time, types
js = types.ModuleType("js"); js.posts = []; js.prets = []
js.postMessage = js.posts.append; js.Object = types.SimpleNamespace(fromEntries=None); js.zmq_pret = js.prets.append
ffi = types.ModuleType("pyodide.ffi"); pyodide = types.ModuleType("pyodide"); pyodide.ffi = ffi
_dormir = time.sleep  # le préambule double time.sleep, qui appelle run_sync
def run_sync(c):
    _dormir(0.01); c.close()
ffi.run_sync = run_sync; ffi.can_run_sync = lambda: True; ffi.to_js = lambda o, **k: o; ffi.create_proxy = lambda f: f
sys.modules.update(js=js, pyodide=pyodide, **{{"pyodide.ffi": ffi}})
spec = importlib.util.spec_from_file_location("_pre", {str(PREAMBULE)!r})
pre = importlib.util.module_from_spec(spec); spec.loader.exec_module(pre)
WEB = {str(RACINE / "qtpy6" / "web")!r}
"""


def test_preambule_installe_zmq_et_threading_sans_qt():
    sortie = _sous_processus(ENTETE_WORKER + """
import threading
pre.installer(WEB)
from qtpy6.web import zmq_web, threading_web
print(zmq_web.en_travailleur, threading.Thread is threading_web.Thread, "PySide6" in sys.modules, hasattr(sys.modules["qtpy6"], "API"))
print(len(js.prets), js.prets[0] is pre.recevoir_page)
""")
    assert sortie == "True True False False\n1 True"


def test_preambule_crochets_attendre_plus_tard_poster():
    sortie = _sous_processus(ENTETE_WORKER + """
pre.installer(WEB)
from qtpy6.web import threading_web, zmq_web
t = time.monotonic()
print(threading_web.attendre(lambda: False, 60), time.monotonic() - t >= 0.05, threading_web.attendre(lambda: True, 60))
zmq_web.poster(None, {"op": "bind", "port": 1})
print(js.posts)
touches = []
async def principal():
    threading_web.plus_tard(lambda: touches.append("tot"), 0)
    threading_web.plus_tard(lambda: touches.append("tard"), 30)
    await asyncio.sleep(0.1)
asyncio.run(principal(), loop_factory=asyncio.SelectorEventLoop)  # une boucle réelle : new_event_loop est doublée
print(touches)
""")
    assert sortie == "False True True\n[{'zmq': {'op': 'bind', 'port': 1}}]\n['tot', 'tard']"


def test_preambule_sleep_livre_les_signaux():
    sortie = _sous_processus(ENTETE_WORKER + """
class Signaux(list):
    length = property(len)
    def shift(self):
        return self.pop(0)
js.signaux = Signaux()
pre.installer(WEB)
time.sleep(0.01)  # rien en attente : rend normalement
js.signaux.append(2)
try:
    while True:
        time.sleep(0.01)
except KeyboardInterrupt:
    print("interrompu", len(js.signaux))
""")
    assert sortie == "interrompu 0"


def test_preambule_recevoir_page():
    sortie = _sous_processus(ENTETE_WORKER + """
pre.installer(WEB)
from qtpy6.web import zmq_web
pre.recevoir_page(types.SimpleNamespace(to_py=lambda: {"op": "bind", "port": 7777}))
print(zmq_web._distants)
""")
    assert sortie == "{7777: None}"


def test_preambule_garde_vie_run_forever_attend_stop():
    pre = _preambule()
    ffi = types.ModuleType("pyodide.ffi")
    def run_sync(futur):
        while not futur.done():
            time.sleep(0.005)

    ffi.run_sync = run_sync
    pyodide = types.ModuleType("pyodide")
    pyodide.ffi = ffi
    sys.modules.update({"pyodide": pyodide, "pyodide.ffi": ffi})
    try:
        class BoucleWeb(asyncio.SelectorEventLoop):  # la WebLoop de Pyodide : run_forever ne bloque pas, stop ne fait rien
            def run_forever(self):
                pass

            def stop(self):
                pass

        boucle = BoucleWeb()
        pre._garde_vie(boucle)
        for _ in range(2):  # et recommence après un stop
            threading.Timer(0.06, boucle.stop).start()
            debut = time.monotonic()
            boucle.run_forever()
            assert time.monotonic() - debut >= 0.05
        boucle.stop()  # sans run_forever en cours : sans effet
        boucle.close()
    finally:
        for nom in ("pyodide", "pyodide.ffi"):
            sys.modules.pop(nom, None)


def test_executer_vide_atexit_et_charge_le_preambule():
    """Vérifié sur le source seulement : ``_executer`` vit dans du Python lancé par le JS, hors de portée en natif."""
    js = (RACINE / "qtpy6" / "web" / "js" / "travailleur.js").read_text()
    assert "atexit._run_exitfuncs()" in js and js.index("atexit._run_exitfuncs()") < js.index("postMessage({ fin: code })")
    assert "preambule.installer" in js and "m.zmq" in js and "env" in js


def test_zipper_ajoute_des_fichiers_isoles(tmp_path):
    import zipfile  # noqa: PLC0415

    (tmp_path / "un.py").write_text("")
    noms = zipfile.ZipFile(io.BytesIO(travailleur._zipper([], None, [tmp_path / "un.py"]))).namelist()
    assert noms == [f"{os.path.relpath(tmp_path, '/')}/un.py"]


# --- 6. l'installation côté page --------------------------------------------------------------------------------------

def test_page_installe_les_crochets_zmq_et_threading():
    from test_web import en_navigateur  # noqa: PLC0415

    sortie = en_navigateur("""
        import threading
        from qtpy6 import QtCore
        from qtpy6.web import fils, threading_web, zmq_web
        print(threading.Thread is threading_web.Thread, threading_web._attendre_hote is fils._attendre,
              "zmq" in sys.modules or True)
        recu = []
        class Dest:
            def _poster_zmq(self, m): recu.append(m)
        zmq_web.poster(Dest(), {"op": "x"})
        zmq_web.poster(None, {"op": "bind", "port": 1})  # la page elle-même : rien à poster
        print(recu)
    """)
    assert sortie == "True True True\n[{'op': 'x'}]"
