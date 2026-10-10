"""Les symboles d'un module WebAssembly (sections import et export), pour la phase dynamique de construire.sh : ce
qu'un module latéral importe doit être fourni par le module principal, par l'agrégat ou par un module chargé avant
lui, sinon Emscripten pose un bouchon qui échoue au PREMIER APPEL (Pyodide est lié sans ASSERTIONS : rien ne le dit au
chargement). Un seul outil, trois usages :
  symboles.py exportes <module>            les symboles exportés, un par ligne
  symboles.py manquants <principal.wasm> <agrege.so> <module.so>...
       ce que les modules importent et que ni le module principal ni les modules eux-mêmes ne fournissent : la liste
       que l'agrégat doit exporter (lu sur un agrégat lié --export-all, qui exporte tout ce qu'il définit)
  symboles.py croises <principal.wasm> <agrege_tout.so> <tout/> <module.so>...
       <module.so>... dans l'ordre de CHARGEMENT ; <tout/> contient, sous le même nom de fichier, le même module lié
       --export-all. Un module qui porte une bibliothèque Qt (Network, Qml, Quick, Multimedia) doit exporter ce que les
       modules chargés après lui en importent : ses symboles Qt sont hidden, que SIDE_MODULE n'exporte pas. Écrit
       « <fichier> <symbole> » : ce que chaque module doit exporter en plus (et que ni le principal ni l'agrégat ne fournit).
  symboles.py verifier <principal.wasm> <agrege.so> <module.so>...
       chaque import de chaque module résolu par le principal, l'agrégat ou un module avant lui (ordre de chargement) ;
       code 1 et la liste des manquants sinon.
Le module principal fournit ses exports et sa bibliothèque JavaScript entière (MAIN_MODULE=1 l'inclut toute : fetch,
GL... que resolveGlobalSymbol de dynlink prend dans wasmImports), lue dans le pyodide.asm.js voisin du wasm : son wasm
n'importe que ce que son propre code appelle, et Qt dynamique n'y appelle plus rien d'OpenGL."""

from __future__ import annotations

import sys
from pathlib import Path


def _leb(donnees: bytes, i: int) -> tuple[int, int]:
    valeur = decalage = 0
    while True:
        octet = donnees[i]
        i += 1
        valeur |= (octet & 0x7F) << decalage
        decalage += 7
        if not octet & 0x80:
            return valeur, i


def _nom(donnees: bytes, i: int) -> tuple[str, int]:
    n, i = _leb(donnees, i)
    return donnees[i : i + n].decode("utf-8", "replace"), i + n


def sections(chemin: Path) -> dict[int, bytes]:
    donnees = Path(chemin).read_bytes()
    assert donnees[:4] == b"\0asm", chemin
    i, trouvees = 8, {}
    while i < len(donnees):
        ident = donnees[i]
        taille, i = _leb(donnees, i + 1)
        trouvees.setdefault(ident, donnees[i : i + taille])
        i += taille
    return trouvees


def importes(chemin: Path) -> dict[str, set[str]]:
    """Par module d'import (env, GOT.mem, GOT.func...), les noms importés."""
    s = sections(chemin).get(2, b"\0")
    n, i = _leb(s, 0)
    par_module: dict[str, set[str]] = {}
    for _ in range(n):
        module, i = _nom(s, i)
        nom, i = _nom(s, i)
        genre = s[i]
        i += 1
        if genre == 0:  # fonction : index de type
            _, i = _leb(s, i)
        elif genre == 1:  # table : type de référence, limites
            i = _limites(s, i + 1)
        elif genre == 2:  # mémoire
            i = _limites(s, i)
        elif genre == 3:  # global : type, mutabilité
            i += 2
        elif genre == 4:  # tag : attribut, index de type
            _, i = _leb(s, i + 1)
        par_module.setdefault(module, set()).add(nom)
    return par_module


def _limites(s: bytes, i: int) -> int:
    drapeaux = s[i]
    _, i = _leb(s, i + 1)
    if drapeaux & 1:
        _, i = _leb(s, i)
    return i


def exportes(chemin: Path) -> set[str]:
    s = sections(chemin).get(7, b"\0")
    n, i = _leb(s, 0)
    noms = set()
    for _ in range(n):
        nom, i = _nom(s, i)
        _, i = _leb(s, i + 1)
        noms.add(nom)
    return noms


def besoins(chemin: Path) -> set[str]:
    """Les symboles qu'un module latéral attend des autres : fonctions (env) et adresses (GOT.mem, GOT.func)."""
    par_module = importes(chemin)
    return par_module.get("env", set()) | par_module.get("GOT.mem", set()) | par_module.get("GOT.func", set())


_PROPRES = {"memory", "__indirect_function_table", "__memory_base", "__table_base", "__stack_pointer", "__heap_base"}


def fournis_par_principal(chemin: Path) -> set[str]:
    glu = chemin.with_suffix(".js").read_text(encoding="utf-8", errors="replace")
    objet = glu[glu.index("wasmImports={") + len("wasmImports={"):]
    bibliotheque = {entree.split(":")[0].strip() for entree in objet[:objet.index("}")].split(",")}
    return exportes(chemin) | importes(chemin).get("env", set()) | bibliotheque


def main(arguments: list[str]) -> int:
    usage, *chemins = arguments
    fichiers = [Path(c) for c in chemins]
    if usage == "exportes":
        print("\n".join(sorted(exportes(fichiers[0]))))
        return 0
    if usage == "croises":
        principal, agrege_tout, tout, *modules = fichiers
        deja = fournis_par_principal(principal) | _PROPRES | exportes(agrege_tout)
        for i, m in enumerate(modules[:-1]):
            attendus = set().union(*(besoins(suivant) for suivant in modules[i + 1:])) - deja - exportes(m)
            if (tout / m.name).exists():
                for nom in sorted(attendus & exportes(tout / m.name)):
                    print(m.name, nom)
        return 0
    principal, agrege, *modules = fichiers
    fournis = fournis_par_principal(principal) | _PROPRES
    if usage == "manquants":
        # Tout ce qu'un module importe et que le principal ne fournit pas : l'agrégat l'exporte s'il le définit, que
        # d'autres modules l'exportent ou non (Qml importe QAbstractItemModel::hasChildren, que Quick exporte aussi : il
        # n'est servi que par l'agrégat et par ceux chargés AVANT lui, pas par ses suivants).
        attendus = set().union(*(besoins(m) for m in modules)) - fournis
        # Ce qui n'est ni au principal ni aux modules : l'agrégat, s'il le définit ; sinon un symbole pour lequel
        # Emscripten posera un bouchon — à dire, sans échouer, verifier tranche.
        exports_agrege = exportes(agrege)
        print("\n".join(sorted(attendus & exports_agrege)))
        for nom in sorted(attendus - exports_agrege - set().union(*(exportes(m) for m in modules))):
            print(f"introuvable : {nom}", file=sys.stderr)  # (ni agrégat ni module : ce que croises et verifier tranchent)
        return 0
    if usage == "verifier":
        fournis |= exportes(agrege)
        manquants = []
        for m in modules:
            fournis |= exportes(m)  # un module prend aussi l'adresse de ses propres fonctions par GOT.func
            manquants += [f"{m.name} : {nom}" for nom in sorted(besoins(m) - fournis)]
        print("\n".join(manquants))
        return 1 if manquants else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
