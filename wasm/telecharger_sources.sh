#!/bin/bash
# Étape 0 de PySide6 en WebAssembly : tout ce qui demande le réseau, d'un coup (le bac à sable de Claude ne l'a pas).
# Lancé par l'utilisateur, depuis son compte. Rejouable : ce qui est déjà là n'est pas retéléchargé.
#   wasm/telecharger_sources.sh [dossier]      (défaut : /DATA/Python/outils_wasm/pyside6/sources)
# Écrit les empreintes de ce qu'il a pris dans wasm/versions.txt. Ne compile rien, sauf les ports zlib et bzip2
# d'emscripten (embuilder ne sait pas les télécharger sans les construire, quelques secondes).
set -euo pipefail
DEP="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-/DATA/Python/outils_wasm/pyside6/sources}"
EMSDK=/DATA/Python/outils_wasm/emsdk
QT=6.10.2 PYSIDE=6.10.2 PYODIDE=0.29.3 PYTHON=3.13.2
PYTHON_SHA256=b8d79530e3b7c96a5cb2d40d431ddb512af4a563e863728d8713039aa50203f9  # Makefile.envs de Pyodide 0.29.3
LIBFFI_COMMIT=f08493d249d2067c8b3207ba46693dd858f95db3 HIWIRE_COMMIT=6a1e67280a15d929ebeceee54a6358c9c8d5f697  # cpython/Makefile
mkdir -p "$SRC" && cd "$SRC"

prendre() {  # prendre <url> : dans le dossier courant, sauf s'il y est déjà
  local f="${1##*/}"
  [ -s "$f" ] && return
  curl -fL --retry 3 -# -o "$f.part" "$1"
  mv "$f.part" "$f"
}
commit() {  # commit <dossier> <dépôt> <commit> : un seul commit, sans historique
  [ -d "$1/.git" ] || { git init -q "$1" && git -C "$1" fetch -q --depth 1 "$2" "$3" && git -C "$1" checkout -q FETCH_HEAD; }
}

echo "== Qt $QT (qtbase, qtsvg)"
B=https://download.qt.io/official_releases/qt/${QT%.*}/$QT/submodules
prendre "$B/md5sums.txt"
for m in qtbase qtsvg; do
  prendre "$B/$m-everywhere-src-$QT.tar.xz"
  grep " $m-everywhere-src-$QT.tar.xz\$" md5sums.txt | md5sum -c -
done

echo "== pyside-setup $PYSIDE"
prendre "https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-$PYSIDE-src/pyside-setup-everywhere-src-$PYSIDE.tar.xz"

echo "== Pyodide $PYODIDE (et son sous-module pyodide-build)"
[ -d pyodide/.git ] || git clone -q --depth 1 --branch "$PYODIDE" --recurse-submodules --shallow-submodules \
  https://github.com/pyodide/pyodide.git pyodide
mkdir -p pyodide/cpython/downloads
(cd pyodide/cpython/downloads && prendre "https://www.python.org/ftp/python/$PYTHON/Python-$PYTHON.tgz" &&
 echo "$PYTHON_SHA256  Python-$PYTHON.tgz" | sha256sum -c -)
commit libffi https://github.com/libffi/libffi "$LIBFFI_COMMIT"
commit hiwire https://github.com/pyodide/hiwire "$HIWIRE_COMMIT"
echo "== npm ci (la partie JavaScript de Pyodide)"
[ -d pyodide/src/js/node_modules ] || (cd pyodide/src/js && for i in 1 2 3; do npm ci --no-audit --no-fund --fetch-retries=5 && break; [ $i -lt 3 ] || exit 1; echo "npm ci : nouvel essai"; done)

echo "== Recette de Pyodide-Qt (MIT)"
[ -d pyodide-with-pyqt6/.git ] || git clone -q --depth 1 https://github.com/JarrettSJohnson/pyodide-with-pyqt6.git
# Pas emdawnwebgpu, que la recette prend aussi : Qt n'a aucun symbole wgpu (llvm-nm), construire.sh ne le lie pas.

echo "== Ports emscripten (zlib, bzip2), dans un cache à part que la compilation recopiera"
EM_CONFIG="$EMSDK/.emscripten" EM_CACHE="$SRC/em_cache" "$EMSDK/upstream/emscripten/embuilder" build zlib bzip2

echo "== Empreintes"
{
  echo "# wasm/telecharger_sources.sh, $(date -I)"
  sha256sum ./*.tar.xz pyodide/cpython/downloads/*.tgz
  for d in pyodide pyodide/pyodide-build libffi hiwire pyodide-with-pyqt6; do echo "git $(git -C "$d" rev-parse HEAD)  $d"; done
  ls em_cache/ports/
} | tee "$DEP/wasm/versions.txt"
du -sh "$SRC"
echo "== Terminé"
