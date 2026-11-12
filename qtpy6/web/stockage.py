"""Ce que le navigateur offre à l'application pour ses fichiers : ``localStorage`` (du texte, quelques Mio, propre à
l'origine de la page, qui survit au rechargement), un dossier rangé dans IndexedDB (``monter`` : des fichiers ordinaires,
binaires compris, sans autre limite que le quota de l'origine, que le navigateur recopie seul après chaque écriture) et le
téléchargement (le seul chemin vers le disque de l'utilisateur). Chaque fonction importe ``js`` à l'appel : le module
s'importe en natif, où rien ici n'a de sens. Une application n'a rien à importer d'ici pour ses fichiers :
``application(persistant=chemin)`` monte son dossier, et ``QFileDialog`` ouvre, télécharge."""

import os

_synchro = {"etat": None, "attente": []}  # etat : None, "en cours" ou "encore" (une écriture est venue pendant la copie)
_montes: set[str] = set()  # les dossiers montés par monter, dans IndexedDB ou sur le disque
_natifs: set[str] = set()  # ceux d'entre eux qui sont un dossier du disque autorisé par l'utilisateur (``disque``)


def lire(cle):
    """Le texte rangé sous ``cle``, ou None (le ``null`` de JavaScript arrive en ``jsnull`` sous Pyodide, pas en None)."""
    import js  # noqa: PLC0415

    texte = js.localStorage.getItem(cle)
    return texte if isinstance(texte, str) else None


def ecrire(cle, texte):
    """Range ``texte`` sous ``cle`` ; False si le navigateur refuse (stockage plein ou interdit : l'application continue)."""
    import js  # noqa: PLC0415

    try:
        js.localStorage.setItem(cle, texte)
    except Exception:  # noqa: BLE001 - QuotaExceededError, SecurityError : la raison n'y change rien
        return False
    return True


def effacer(cle):
    import js  # noqa: PLC0415

    js.localStorage.removeItem(cle)


def telecharger(nom, contenu, mime="application/octet-stream", lien=None):
    """Offre ``contenu`` (str ou bytes) au téléchargement sous le nom ``nom``. Sans ``lien``, le téléchargement part tout
    de suite ; avec un élément ``<a>`` de la page, celui-ci reçoit le fichier (href, download) et devient visible : c'est
    l'utilisateur qui clique, autant de fois qu'il veut, et un fichier suivant remplace le précédent."""
    import js  # noqa: PLC0415
    from pyodide.ffi import to_js  # noqa: PLC0415

    octets = contenu.encode("utf-8") if isinstance(contenu, str) else bytes(contenu)
    blob = js.Blob.new(to_js([to_js(octets)]), type=mime)
    a = js.document.createElement("a") if lien is None else lien
    if a.href and a.href.startswith("blob:"):
        js.URL.revokeObjectURL(a.href)
    a.href = js.URL.createObjectURL(blob)
    a.download = nom
    if lien is None:
        a.click()
    else:
        lien.hidden = False


def monter(dossier: str | os.PathLike[str], disque: bool = False) -> None:
    """Range le dossier ``dossier`` dans IndexedDB (IDBFS d'Emscripten) et y remet ce qu'une visite précédente y avait
    laissé : l'application continue d'y lire et d'y écrire des fichiers ordinaires, et le navigateur les recopie seul
    dans IndexedDB après chaque écriture (``autoPersist`` d'Emscripten : à la fermeture d'un fichier écrit, à une
    création, une suppression, un renommage ; une copie à la fois, lancée au tour de boucle suivant, les écritures venues
    pendant une copie en relancent une seule à sa fin). ``synchroniser(attendre=True)`` reste là pour qui doit être sûr
    que tout est copié. Le dossier doit être vide ou absent (le montage cache ce qu'il contenait : les
    fichiers livrés avec l'application vont ailleurs, et l'application les recopie au premier lancement). Demande aussi
    au navigateur de ne pas effacer ce stockage quand la place manque (``navigator.storage.persist``, que Firefox
    soumet à l'utilisateur). Suspend jusqu'à la fin de la restauration : à appeler d'une entrée suspendable (le script
    lancé par ``lancer``, un slot) ; ``OSError`` si IndexedDB refuse (navigation privée de certains navigateurs).
    C'est ce que ``application(persistant=chemin)`` fait pour l'application.

    Avec ``disque`` et un navigateur qui sait ouvrir un dossier du disque (File System Access : Chrome, Edge), le dossier
    peut être, au choix de l'utilisateur, un dossier RÉEL de son disque, lisible par tout autre programme : la page lui
    propose « Choisir un dossier sur le disque » ou « Garder dans le navigateur » au premier lancement, puis retrouve le
    dossier choisi aux lancements suivants (sa poignée est gardée dans IndexedDB, base ``qtpy6``) ; Chrome oubliant
    l'autorisation à sa fermeture, un bouton « Réautoriser le dossier » la redemande d'un clic (mesuré au jalon 5 bis).
    Chaque écriture y est recopiée sur le disque, regroupée : une recopie 200 ms après la dernière (``_ecrit``). Refus,
    Échap, navigateur sans cette API (Firefox) : IndexedDB comme ci-dessus, sans rien demander."""
    import js  # noqa: PLC0415
    import pyodide_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    from . import bloquant  # noqa: PLC0415

    fs = pyodide_js.FS
    if disque and getattr(js.window, "showDirectoryPicker", None) and _monter_sur_disque(str(dossier)):
        return
    os.makedirs(dossier, exist_ok=True)
    options = js.Object.new()
    options.autoPersist = True
    fs.mount(fs.filesystems.IDBFS, options, str(dossier))
    _montes.add(str(dossier))
    if getattr(js.navigator, "storage", None) and getattr(js.navigator.storage, "persist", None):
        js.navigator.storage.persist()
    erreur = bloquant._suspendre(lambda resoudre: fs.syncfs(True, create_once_callable(lambda e=None: resoudre(e))))
    if erreur:
        raise OSError(f"IndexedDB : {erreur}")


# Le choix du dossier, côté page : une fonction asynchrone qui rend la poignée du dossier autorisé, ou null pour rester
# dans IndexedDB. Les boutons sont des éléments HTML par-dessus le canevas de Qt : showDirectoryPicker et
# requestPermission exigent un geste réel de l'utilisateur dans la page. Un « Garder dans le navigateur » est mémorisé
# (localStorage) : la question ne revient pas à chaque lancement.
_DISQUE_JS = r"""
async (chemin) => {
  const cle = "qtpy6.disque:" + chemin;
  const bd = () => new Promise((ok, ko) => {
    const r = indexedDB.open("qtpy6", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("dossiers");
    r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error);
  });
  const requete = async (mode, faire) => { const b = await bd(); return new Promise((ok, ko) => {
    const r = faire(b.transaction("dossiers", mode).objectStore("dossiers"));
    r.onsuccess = () => ok(r.result); r.onerror = () => ko(r.error); }); };
  const choix = (texte, boutons) => new Promise((ok) => {
    const voile = document.createElement("div");
    voile.style.cssText = "position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;" +
      "justify-content:center;background:rgba(0,0,0,.35);font:15px sans-serif";
    const boite = document.createElement("div");
    boite.style.cssText = "background:#fff;color:#000;padding:20px;border-radius:8px;max-width:440px;text-align:center";
    const p = document.createElement("p"); p.textContent = texte; boite.append(p);
    for (const [libelle, valeur] of boutons) {
      const b = document.createElement("button"); b.textContent = libelle; b.dataset.qtpy6Disque = valeur;
      b.style.cssText = "margin:6px;padding:8px 14px;font:inherit;cursor:pointer";
      b.onclick = () => { voile.remove(); ok(valeur); }; boite.append(b);
    }
    voile.append(boite); document.body.append(voile);
  });
  let h = null;
  try { h = await requete("readonly", (s) => s.get(chemin)); } catch (e) { h = null; }
  let c;
  if (h) {
    if (await h.queryPermission({ mode: "readwrite" }) === "granted") return h;
    c = await choix(`Vos fichiers sont dans le dossier « ${h.name} » de votre disque.`,
      [["Réautoriser le dossier", "reautoriser"], ["Choisir un autre dossier", "choisir"],
       ["Garder dans le navigateur", "navigateur"]]);
    if (c === "reautoriser") {
      try { if (await h.requestPermission({ mode: "readwrite" }) === "granted") return h; } catch (e) {}
      return null;
    }
  } else {
    try { if (localStorage.getItem(cle) === "navigateur") return null; } catch (e) {}
    c = await choix("Où ranger vos fichiers ?",
      [["Choisir un dossier sur le disque", "choisir"], ["Garder dans le navigateur", "navigateur"]]);
  }
  if (c === "navigateur") {
    try { localStorage.setItem(cle, "navigateur"); } catch (e) {}
    try { await requete("readwrite", (s) => s.delete(chemin)); } catch (e) {}
    return null;
  }
  try { h = await showDirectoryPicker({ mode: "readwrite", id: "qtpy6" }); } catch (e) { return null; }
  try { await requete("readwrite", (s) => s.put(h, chemin)); } catch (e) {}
  try { localStorage.removeItem(cle); } catch (e) {}
  return h;
}
"""

# Après chaque écriture sous un dossier du disque : une recopie, différée de 200 ms après la DERNIÈRE écriture (un
# programme qui écrit cent fichiers ne paie qu'une recopie de 30 à 70 ms, pas cent). Les fonctions de FS d'Emscripten
# sont enveloppées : les appels système de Python passent par elles (fd_close → FS.close, unlink, rename…).
_ENVELOPPE_JS = r"""
(FS, natifs, recopier) => {  // natifs : un tableau JS que Python complète à chaque montage
  let minuterie = null;
  const sous = (p) => typeof p === "string" && natifs.some((d) => p === d || p.startsWith(d + "/"));
  const prevenir = () => { clearTimeout(minuterie); minuterie = setTimeout(recopier, 200); };
  for (const nom of ["close", "unlink", "rename", "mkdir", "rmdir", "symlink"]) {
    const avant = FS[nom];
    FS[nom] = function (...a) {
      const r = avant.apply(this, a);
      if (nom === "close" ? (a[0] && (a[0].flags & 3) && sous(a[0].path)) : a.some(sous)) prevenir();
      return r;
    };
  }
}
"""
_enveloppe: list = []  # [tableau JS des dossiers du disque, rappel gardé en vie], une fois les fonctions de FS enveloppées


def _monter_sur_disque(dossier: str) -> bool:
    """Le dossier autorisé de l'utilisateur monté sous ``dossier`` (``pyodide.mountNativeFS``), ses fichiers déjà lus ;
    False s'il a choisi le navigateur, refusé, ou si le montage a échoué (``dossier`` non vide, poignée perdue)."""
    import js  # noqa: PLC0415
    import pyodide_js  # noqa: PLC0415
    from pyodide.code import run_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable, create_proxy  # noqa: PLC0415

    from . import bloquant  # noqa: PLC0415

    def attendre(promesse):
        return bloquant._suspendre(lambda resoudre: promesse.then(
            create_once_callable(lambda v=None: resoudre((True, v))),
            create_once_callable(lambda e=None: resoudre((False, e)))))

    ok, poignee = attendre(run_js(_DISQUE_JS)(dossier))
    if not ok or not poignee:
        return False
    ok, erreur = attendre(pyodide_js.mountNativeFS(dossier, poignee))
    if not ok:
        print(f"qtpy6.web.stockage : dossier du disque non monté ({erreur}), fichiers gardés dans le navigateur")
        return False
    _montes.add(dossier)
    _natifs.add(dossier)
    if not _enveloppe:  # le tableau est lu par JavaScript seul : aucun appel de Python au milieu d'un appel système
        _enveloppe.extend([js.Array.new(), create_proxy(lambda: synchroniser())])
        run_js(_ENVELOPPE_JS)(pyodide_js.FS, *_enveloppe)
    _enveloppe[0].push(os.path.normpath(os.path.abspath(dossier)))  # absolu : ce que FS reçoit (stream.path, calculateAt)
    return True


def synchroniser(attendre: bool = False) -> None:
    """Recopie tout de suite dans IndexedDB les dossiers montés par ``monter``, sans attendre la copie que le navigateur
    fait seul après chaque écriture. La copie part et l'application continue ; une écriture qui arrive pendant une copie
    en relance une seule à sa fin. Avec ``attendre``, suspend jusqu'à ce que tout soit copié (entrée suspendable) : pour
    qui doit en être sûr avant de poursuivre. Un refus d'IndexedDB est écrit au journal."""
    from . import bloquant  # noqa: PLC0415

    if _synchro["etat"]:
        _synchro["etat"] = "encore"
    else:
        _copier()
    if attendre:
        bloquant._suspendre(_synchro["attente"].append)


def _copier():
    import pyodide_js  # noqa: PLC0415
    from pyodide.ffi import create_once_callable  # noqa: PLC0415

    _synchro["etat"] = "en cours"
    pyodide_js.FS.syncfs(False, create_once_callable(_copie_finie))


def _copie_finie(erreur=None):
    if erreur:
        print(f"qtpy6.web.stockage : IndexedDB a refusé la copie ({erreur})")
    if _synchro["etat"] == "encore":
        _copier()
        return
    _synchro["etat"] = None
    attente, _synchro["attente"] = _synchro["attente"], []
    for reprendre in attente:
        reprendre()
