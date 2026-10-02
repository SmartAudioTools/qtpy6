#!/bin/bash
# PySide6 en WebAssembly : la construction, hors réseau (les sources viennent de wasm/telecharger_sources.sh).
#   wasm/construire.sh <phase>...    phases, dans l'ordre : emsdk qthote qt shiboken cpython pyside pyodide paquet
# Chaque phase est rejouable et saute ce qui est déjà fait. Arbre de travail : $RACINE (hors dépôt, ~40 Go).
set -euo pipefail
DEP="$(cd "$(dirname "$0")/.." && pwd)"
RACINE="${RACINE:-/DATA/Python/outils_wasm/pyside6}"
SRC="$RACINE/sources"
QT=6.10.2 PYSIDE=6.10.2 PYTHON=3.13.2
PYODIDE="$SRC/pyodide"
EMSDK="$PYODIDE/emsdk/emsdk"           # la copie corrigée que Pyodide attend à cet endroit
QTHOTE="$RACINE/qt-hote"               # Qt 6.10.2 natif : moc, rcc, uic et QtCore pour le générateur shiboken
QTWASM="$RACINE/qt-wasm"               # Qt 6.10.2 statique pour WebAssembly
HOTEPY=/DATA/Python/SmartPython/CachyOS/versions/SmartPython/bin/python  # 3.13, comme le CPython de Pyodide
JOURNAUX="$RACINE/journaux"
mkdir -p "$JOURNAUX"
git() { command git -c safe.directory='*' "$@"; }  # sources récupérées par un autre compte
log() { echo "==> $*"; }
emsdk_env() {
  export EMSDK EM_CONFIG="$EMSDK/.emscripten" PATH="$EMSDK/upstream/emscripten:$EMSDK/upstream/bin:$EMSDK/node/24.19.0_64bit/bin:$PATH"
  unset EM_CACHE  # le cache de la copie (emscripten/cache), construit avec ses correctifs
  # L'environnement de session exporte CFLAGS=-march=native (réglage CachyOS), qu'emscripten refuse
  # (« unsupported option '-march=' for target wasm32 ») : ces drapeaux sont pour l'hôte, pas pour la cible.
  unset CFLAGS CXXFLAGS FFLAGS LDFLAGS
}
remplacer() {  # remplacer <fichier> <expression sed> : sur place sans sed -i, qui échoue à recopier les droits ici
  local t; t=$(sed "$2" "$1"); printf '%s\n' "$t" > "$1"
}
dossier() {  # dossier <chemin>... : crée avec MON groupe et sans setgid. Le groupe hérité d'outils_wasm n'est pas
  # mappé dans le bac à sable : patch (et cp -a) y échouent à recopier propriétaire et droits. L'ACL par défaut
  # continue de donner l'accès au compte principal.
  local d; for d; do [ -d "$d" ] || { mkdir -p "$d" && chgrp claude "$d" && chmod g-s "$d"; }; done
}
deballer() {  # deballer <archive> <dossier> : une seule fois
  [ -d "$2" ] || { mkdir -p "$2.tmp" && tar xf "$1" -C "$2.tmp" --strip-components=1 && mv "$2.tmp" "$2"; }
}

patcher() {  # patcher <préfixe> [arbre] : applique wasm/patches/<préfixe>-*.patch à l'arbre (pyside-setup par
  # défaut), une seule fois (déjà appliqué si l'inverse s'applique). git apply et non patch : voir phase_emsdk.
  local c; for c in "$DEP"/wasm/patches/"$1"-*.patch; do
    (cd "${2:-$RACINE/src/pyside-setup}" && { git apply -R --check "$c" 2>/dev/null || git apply "$c"; })
  done
}

phase_emsdk() {
  # Pyodide construit son propre emsdk 4.0.9 et y applique emsdk/patches/*.patch (relocations dylink, ordre des
  # promesses...). L'emsdk partagé d'outils_wasm est le même 4.0.9 SANS ces correctifs : on le recopie ici et on les
  # applique, sans réseau, plutôt que de modifier celui dont dépend la roue serializejson.
  [ -f "$PYODIDE/emsdk/emsdk/.complete" ] && return
  rm -rf "$EMSDK"
  cp -r --preserve=timestamps,links /DATA/Python/outils_wasm/emsdk "$EMSDK"  # pas les droits : l ACL par défaut du dossier les refuse
  rm -rf "$EMSDK/upstream/emscripten/cache"  # bibliothèques construites sans les correctifs : à refaire
  # git apply et non patch : patch veut recopier le propriétaire des fichiers, ce que le bac à sable refuse
  (cd "$EMSDK/upstream/emscripten" && git apply "$PYODIDE"/emsdk/patches/*.patch)
  mkdir -p "$EMSDK/upstream/emscripten/cache"
  cp -r "$SRC/em_cache/ports" "$EMSDK/upstream/emscripten/cache/"  # zlib et bzip2, téléchargés par l'utilisateur
  # La ligne ccache de pyodide_env.sh, comme la recette de Pyodide-Qt
  remplacer "$PYODIDE/pyodide_env.sh" 's|^export _EMCC_CCACHE=1|command -v ccache >/dev/null 2>\&1 \&\& export _EMCC_CCACHE=1|'
  git diff --no-index --ignore-all-space "$EMSDK/upstream/emscripten/src/struct_info_generated.json" \
    "$PYODIDE/src/js/struct_info_generated.json" >/dev/null
  touch "$EMSDK/.complete"
  emsdk_env; emcc --version | head -1
}

phase_qthote() {
  # Qt hôte : il faut le MÊME 6.10.2 que la cible (le Qt système est en 6.11, refusé par -qt-host-path) pour moc,
  # rcc, uic, et pour lier le générateur shiboken. qtbase seul, en Release, sans exemples ni tests.
  [ -f "$QTHOTE/bin/qmake6" ] || [ -f "$QTHOTE/bin/qmake" ] && return
  deballer "$SRC/qtbase-everywhere-src-$QT.tar.xz" "$RACINE/src/qtbase"
  mkdir -p "$RACINE/build/qtbase-hote" && cd "$RACINE/build/qtbase-hote"
  [ -f build.ninja ] || "$RACINE/src/qtbase/configure" -prefix "$QTHOTE" -release -opensource -confirm-license \
    -nomake examples -nomake tests -no-pch -no-dbus -- -DQT_BUILD_TESTS_BY_DEFAULT=OFF
  cmake --build . --parallel
  cmake --install .
}

phase_qt() {
  # Qt pour WebAssembly : exactement la configuration de Pyodide-Qt (build.sh, build_qt), qtbase puis qtsvg.
  [ -f "$QTWASM/lib/libQt6Svg.a" ] && return
  emsdk_env
  deballer "$SRC/qtbase-everywhere-src-$QT.tar.xz" "$RACINE/src/qtbase"
  deballer "$SRC/qtsvg-everywhere-src-$QT.tar.xz" "$RACINE/src/qtsvg"
  mkdir -p "$RACINE/build/qtbase-wasm" && cd "$RACINE/build/qtbase-wasm"
  [ -f build.ninja ] || "$RACINE/src/qtbase/configure" -qt-host-path "$QTHOTE" -platform wasm-emscripten -static \
    -prefix "$QTWASM" -no-feature-thread -feature-wasm-exceptions -opensource -confirm-license \
    -nomake examples -nomake tests -no-warnings-are-errors
  cmake --build . --parallel
  cmake --install .
  mkdir -p "$RACINE/build/qtsvg-wasm" && cd "$RACINE/build/qtsvg-wasm"
  [ -f build.ninja ] || "$QTWASM/bin/qt-configure-module" "$RACINE/src/qtsvg"
  cmake --build . --parallel
  cmake --install .
}

phase_shiboken() {
  # Générateur shiboken6, NATIF (PYSIDE-802 : outils hôte, bibliothèques cible). libclang du système (22.1.8, la
  # version des binaires de Qt), Qt hôte 6.10.2 pour QtCore. Les bibliothèques (libshiboken) seront croisées.
  # Rejouable : patchs puis reconstruction incrémentale. patches/shiboken-clang22 : noms de types qualifiés
  # (PYSIDE-3286) ; patches/shiboken-lien-statique : symboles internes, les modules étant liés ensemble.
  local gen="$RACINE/shiboken-hote/bin/shiboken6" avant
  patcher shiboken
  mkdir -p "$RACINE/build"
  [ -f "$RACINE/build/shiboken-hote/build.ninja" ] || LLVM_INSTALL_DIR=/usr cmake \
    -S "$RACINE/src/pyside-setup/sources/shiboken6" -B "$RACINE/build/shiboken-hote" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$QTHOTE" -DCMAKE_INSTALL_PREFIX="$RACINE/shiboken-hote" \
    -DSHIBOKEN_BUILD_LIBS=OFF -DSHIBOKEN_BUILD_TOOLS=ON -DBUILD_TESTS=OFF -DPython_EXECUTABLE="$HOTEPY"
  avant=$(stat -c %Y "$gen" 2>/dev/null || echo 0)
  cmake --build "$RACINE/build/shiboken-hote" --parallel
  cmake --install "$RACINE/build/shiboken-hote"
  # Nouveau générateur : la règle de génération de PySide ne dépend pas du binaire hôte, on efface son témoin.
  [ "$(stat -c %Y "$gen")" = "$avant" ] || [ ! -d "$RACINE/build/pyside-wasm" ] ||
    find "$RACINE/build/pyside-wasm" -name mjb_rejected_classes.log -delete
  "$gen" --version
}

pyodide_env() {  # l'environnement des Makefile de Pyodide : python3.13 hôte en tête, git qui lit les clones d'un autre compte
  # shasum, exigé par la vérification de Pyodide, est dans le dossier perl d'Arch, hors du PATH.
  export PYODIDE_ROOT="$PYODIDE" PATH="$(dirname "$HOTEPY"):$PATH:/usr/bin/core_perl"
  unset CFLAGS CXXFLAGS FFLAGS LDFLAGS  # -march=native de la session : voir emsdk_env
  export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*' \
    GIT_CONFIG_KEY_1=uploadpack.allowAnySHA1InWant GIT_CONFIG_VALUE_1=true
}

phase_cpython() {
  # Le CPython 3.13.2 de Pyodide (en-têtes et libpython.a pour PySide, bibliothèque standard pour l'étape 4).
  # cpython/Makefile clone libffi et hiwire par git fetch : on lui donne les clones locaux d'telecharger_sources.sh.
  local lib="$PYODIDE/cpython/installs/python-$PYTHON/lib/python${PYTHON%.*}"
  [ -d "$lib" ] && return
  pyodide_env
  dossier "$PYODIDE/cpython/build" "$PYODIDE/cpython/installs"
  make -C "$PYODIDE" "$lib" LIBFFIREPO="$SRC/libffi" HIWIREREPO="$SRC/hiwire"
}

PYCIBLE="$PYODIDE/cpython/installs/python-$PYTHON"  # le CPython de Pyodide : en-têtes et libpython3.13.a
MODULES="Core;Gui;Widgets;Svg;SvgWidgets"

phase_pyside() {
  # libshiboken, libpyside et les modules, compilés en croisé par le générateur hôte (QFP_SHIBOKEN_HOST_PATH),
  # avec la chaîne de Qt-WASM (qt-cmake), en -fPIC comme les modules PyQt6 de Pyodide-Qt. La chaîne
  # emscripten restreint find_package à sa racine (sauf si on le fixe avant elle) : il faut aussi y voir le
  # Shiboken6Config de l'arbre de construction. libclang HÔTE donné au générateur sans find_package(Clang).
  # Le générateur ne connaît pas la plateforme « Emscripten » : il retomberait sur i586-linux et, en mode g++, mettrait
  # les en-têtes intégrés du clang SYSTÈME avant la libc++ d'emscripten (« <cstddef> tried including <stddef.h> »).
  # --compiler=clang reprend l'ordre exact d'em++, et la vraie cible définit __EMSCRIPTEN__ comme à la compilation.
  emsdk_env
  patcher pyside
  dossier "$RACINE/build/pyside-wasm"
  [ -f "$RACINE/build/pyside-wasm/build.ninja" ] || "$QTWASM/bin/qt-cmake" -S "$RACINE/src/pyside-setup" \
    -B "$RACINE/build/pyside-wasm" -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$RACINE/pyside-wasm" \
    -DCMAKE_C_FLAGS="-fPIC" -DCMAKE_CXX_FLAGS="-fPIC" \
    -DQFP_SHIBOKEN_HOST_PATH="$RACINE/shiboken-hote" \
    -DPython_ROOT_DIR="$PYCIBLE" -DPython_INCLUDE_DIR="$PYCIBLE/include/python${PYTHON%.*}" \
    -DPython_LIBRARY="$PYCIBLE/lib/libpython${PYTHON%.*}.a" -DPython_SOABI=cpython-313-wasm32-emscripten \
    -DQFP_PYTHON_HOST_PATH="$HOTEPY" \
    -DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=BOTH -DSHIBOKEN_WRAPPER_HOST_CLANG_LIB_PATH=/usr/lib \
    "-DSHIBOKEN_GENERATOR_EXTRA_FLAGS=--compiler=clang;--clang-option=--target=wasm32-unknown-emscripten" \
    -DMODULES="$MODULES" -DNO_QT_TOOLS=yes -DBUILD_TESTS=OFF -DFORCE_LIMITED_API=no
  cmake --build "$RACINE/build/pyside-wasm" --parallel
  cmake --install "$RACINE/build/pyside-wasm"
}

phase_pyodide() {
  # Étape 4 : Pyodide relié avec Qt et PySide6 dedans, sur le modèle de la recette Pyodide-Qt (build_pyodide).
  # Les cibles PySide sont des modules latéraux .so : on archive leurs objets pour les lier statiquement.
  emsdk_env; pyodide_env
  local lien="$RACINE/build/pyodide-lien" lib="$PYCIBLE/lib/python${PYTHON%.*}" c m
  local site="$RACINE/pyside-wasm/lib/python${PYTHON%.*}/site-packages"
  dossier "$lien"
  for c in libshiboken pyside6 shibokenmodule QtCore QtGui QtWidgets QtSvg QtSvgWidgets; do
    rm -f "$lien/$c.a"  # emar qc : ajout sans remplacement par nom de fichier, xargs peut l'appeler plusieurs fois
    find "$RACINE/build/pyside-wasm" -path "*/CMakeFiles/$c.dir/*" -name '*.o' -print0 | xargs -0 emar qc "$lien/$c.a"
    emranlib "$lien/$c.a"
  done
  em++ -fPIC -std=gnu++17 -DQT_STATIC -I"$QTWASM/include" -I"$QTWASM/include/QtCore" \
    -c "$DEP/wasm/qt_statique.cpp" -o "$lien/qt_statique.o"
  # Lu par Makefile.envs (patches/pyodide-pyside6.patch). wasm-ld résout les archives sans ordre imposé.
  # Pas de QtXml ni du port emdawnwebgpu de la recette : aucun symbole wgpu dans Qt (llvm-nm), QtXml non construit.
  local q="$QTWASM/lib" g="$QTWASM/plugins"
  PYSIDE6_LDFLAGS="$(echo "$lien"/*.a "$lien/qt_statique.o" \
    "$q"/libQt6{Widgets,Gui,Core,Svg,SvgWidgets,OpenGL}.a "$q"/libQt6Bundled{Harfbuzz,Freetype,Libpng,Libjpeg,Pcre2}.a \
    "$g"/platforms/libqwasm.a "$g"/iconengines/libqsvgicon.a "$g"/imageformats/libq{gif,ico,jpeg,svg}.a \
    "$q"/objects-Release/{Gui,Widgets,QWasmIntegrationPlugin}_resources_*/.qt/rcc/*.o)"
  export PYSIDE6_LDFLAGS
  patcher pyodide "$PYODIDE"
  # Les paquets Python purs dans la bibliothèque standard, zippée par make : sans annotations .pyi, ni modules latéraux
  # .so, déjà liés statiquement dans pyodide.asm.wasm (90 Mo de zip que rien ne charge).
  for m in PySide6 shiboken6; do
    rm -rf "${lib:?}/$m"; cp -r "$site/$m" "$lib/"; find "$lib/$m" \( -name '*.pyi' -o -name '*.so' \) -delete
  done
  # npm ci a été fait par telecharger_sources.sh (réseau) : on marque l'installation que make rejouerait sinon.
  [ -e "$PYODIDE/node_modules/.installed" ] || { ln -sfn src/js/node_modules/ "$PYODIDE/node_modules"
    touch "$PYODIDE/node_modules/.installed"; }
  # make ne connaît pas les archives de Qt et de PySide : sans cela, une phase pyside rejouée ne serait pas reliée.
  rm -f "$PYODIDE/dist/pyodide.asm.js"
  make -C "$PYODIDE" all-but-packages
  # Un pyodide-lock.json vide : PySide6 est intégré, il n'y a aucun paquet à charger.
  [ -f "$PYODIDE/dist/pyodide-lock.json" ] || "$HOTEPY" -c 'import json, sys
json.dump({"info": {"arch": "wasm32", "platform": "emscripten_4_0_9", "version": sys.argv[1], "python": sys.argv[2],
           "abi_version": "2025_0"}, "packages": {}}, open(sys.argv[3], "w"), indent=2)' \
    "$(sed -n 's/.*"version": "\(.*\)".*/\1/p' "$PYODIDE/src/js/package.json")" "$PYTHON" "$PYODIDE/dist/pyodide-lock.json"
}

phase_paquet() {
  # Le zip que sert l'hébergement (hebergement/telecharger.sh, versions.json « pyodide_pyside6 ») : les fichiers que
  # charge une page, sous pyodide-qt/ comme la release de Pyodide-Qt, avec la licence. Python et non zip (absent ici).
  # Son empreinte change à chaque fois (py-compile inscrit la date d'extraction dans chaque .pyc) : à reporter.
  # La bibliothèque standard en .pyc (pyodide py-compile, l'outil de la variante pyc/ du CDN de Pyodide) : −1,1 s à
  # chaque chargement, mesuré (notes/2026-09-30 - PySide6 en WebAssembly.md, « Démarrage »). Prix : les traces
  # d'erreur n'affichent plus la ligne de code des modules de la bibliothèque standard.
  local pyc="$RACINE/build/paquet"
  dossier "$pyc"; cp "$PYODIDE/dist/python_stdlib.zip" "$pyc/"
  /DATA/Python/outils_wasm/venv-pyodide/bin/pyodide py-compile --silent --compression-level 9 "$pyc/python_stdlib.zip"
  "$HOTEPY" - "$PYODIDE/dist" "$pyc/python_stdlib.zip" "$DEP/hebergement/LICENSE-Pyodide-PySide6.txt" "$RACINE/pyodide-pyside6-0.29.3.0.zip" <<'PY'
import hashlib, sys, zipfile
from pathlib import Path
dist, stdlib, licence, sortie = map(Path, sys.argv[1:])
fichiers = [dist / n for n in ("package.json", "pyodide.asm.js", "pyodide.asm.wasm", "pyodide.js", "pyodide-lock.json",
                               "pyodide.mjs", "test.html")] + [stdlib, licence]
with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in fichiers:
        z.write(f, f"pyodide-qt/{'LICENSE.txt' if f == licence else f.name}")
print(sortie, sortie.stat().st_size, "octets ; sha256", hashlib.sha256(sortie.read_bytes()).hexdigest())
PY
}

for p in "$@"; do "phase_$p" 2>&1 | tee -a "$JOURNAUX/$p.log"; done
