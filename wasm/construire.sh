#!/bin/bash
# PySide6 en WebAssembly : la construction, hors réseau (les sources viennent de wasm/telecharger_sources.sh).
#   wasm/construire.sh <phase>...    phases, dans l'ordre : emsdk qthote qt shiboken cpython pyside pyodide dynamique paquet
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

qt_hote() {  # qt_hote <module> <témoin> : un module de Qt hôte (outils moc, qsb, qmltyperegistrar...), Release, ni exemples ni tests (qt-configure-module ne connaît pas -nomake : options cmake)
  [ -e "$QTHOTE/$2" ] && return
  deballer "$SRC/$1-everywhere-src-$QT.tar.xz" "$RACINE/src/$1"
  mkdir -p "$RACINE/build/$1-hote" && cd "$RACINE/build/$1-hote"
  [ -f build.ninja ] || "$QTHOTE/bin/qt-configure-module" "$RACINE/src/$1" -- -DQT_BUILD_EXAMPLES=OFF -DQT_BUILD_TESTS=OFF
  cmake --build . --parallel
  cmake --install .
}

phase_qthote() {
  # Qt hôte : il faut le MÊME 6.10.2 que la cible (le Qt système est en 6.11, refusé par -qt-host-path) pour moc,
  # rcc, uic, et pour lier le générateur shiboken. qtbase en Release, sans exemples ni tests ; puis, pour compiler
  # qtdeclarative en croisé, les OUTILS hôte de qtshadertools (qsb) et de qtdeclarative (qmltyperegistrar, qmlcachegen,
  # qmlimportscanner...), que -qt-host-path va chercher ici. Une garde par témoin, pas une garde globale.
  if ! [ -f "$QTHOTE/bin/qmake6" ] && ! [ -f "$QTHOTE/bin/qmake" ]; then
    deballer "$SRC/qtbase-everywhere-src-$QT.tar.xz" "$RACINE/src/qtbase"
    mkdir -p "$RACINE/build/qtbase-hote" && cd "$RACINE/build/qtbase-hote"
    [ -f build.ninja ] || "$RACINE/src/qtbase/configure" -prefix "$QTHOTE" -release -opensource -confirm-license \
      -nomake examples -nomake tests -no-pch -no-dbus -- -DQT_BUILD_TESTS_BY_DEFAULT=OFF
    cmake --build . --parallel
    cmake --install .
  fi
  qt_hote qtshadertools bin/qsb
  qt_hote qtdeclarative libexec/qmltyperegistrar
}

qt_wasm() {  # qt_wasm <module> <bibliothèque installée> : un module de Qt-WASM, avec les options de qtbase (statique, sans fils)
  [ -f "$QTWASM/lib/$2" ] && return
  deballer "$SRC/$1-everywhere-src-$QT.tar.xz" "$RACINE/src/$1"
  compgen -G "$DEP/wasm/patches/$1-*.patch" >/dev/null && patcher "$1" "$RACINE/src/$1"  # qtmultimedia : portail « fils » levé pour emscripten
  mkdir -p "$RACINE/build/$1-wasm" && cd "$RACINE/build/$1-wasm"
  [ -f build.ninja ] || "$QTWASM/bin/qt-configure-module" "$RACINE/src/$1" -- -DQT_BUILD_EXAMPLES=OFF -DQT_BUILD_TESTS=OFF
  cmake --build . --parallel
  cmake --install .
}

phase_qt() {
  # Qt pour WebAssembly : exactement la configuration de Pyodide-Qt (build.sh, build_qt), qtbase puis qtsvg ; depuis le
  # 10/10/2026 qtshadertools, qtdeclarative (Qml, Quick, Controls), qtmultimedia et qtcharts, dans l'ordre de leurs
  # dépendances. Les options de qtbase (-static, sans fils, exceptions wasm) sont héritées par qt-configure-module.
  emsdk_env
  if ! [ -f "$QTWASM/lib/libQt6Core.a" ]; then
    deballer "$SRC/qtbase-everywhere-src-$QT.tar.xz" "$RACINE/src/qtbase"
    mkdir -p "$RACINE/build/qtbase-wasm" && cd "$RACINE/build/qtbase-wasm"
    [ -f build.ninja ] || "$RACINE/src/qtbase/configure" -qt-host-path "$QTHOTE" -platform wasm-emscripten -static \
      -prefix "$QTWASM" -no-feature-thread -feature-wasm-exceptions -opensource -confirm-license \
      -nomake examples -nomake tests -no-warnings-are-errors
    cmake --build . --parallel
    cmake --install .
  fi
  qt_wasm qtsvg libQt6Svg.a
  qt_wasm qtshadertools libQt6ShaderTools.a
  qt_wasm qtdeclarative libQt6Quick.a
  qt_wasm qtmultimedia libQt6Multimedia.a
  qt_wasm qtcharts libQt6Charts.a
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
# Les cinq de Pyodide-Qt (l'agrégat), puis les quinze à la demande (10/10/2026), chargés par pyodide-qt.mjs : un module
# latéral par liaison (phase dynamique). L'ordre est celui des dépendances (PySideHelpers.cmake). MODULES en dérive.
MODULES_DEMANDE="PrintSupport Network Sql Xml Concurrent OpenGL OpenGLWidgets Test Qml Quick QuickWidgets QuickControls2 Multimedia MultimediaWidgets Charts"  # ceux qui ont leur propre .so, dans l'ordre de CHARGEMENT
MODULES="Core;Gui;Widgets;Svg;SvgWidgets;${MODULES_DEMANDE// /;}"

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
  # Reconfiguré si la liste des modules a changé (le cache garde l'ancienne) ; les cibles déjà construites restent.
  grep -qs "^MODULES:[A-Z]*=$MODULES$" "$RACINE/build/pyside-wasm/CMakeCache.txt" || "$QTWASM/bin/qt-cmake" -S "$RACINE/src/pyside-setup" \
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
  # Étape 4 : Pyodide amont (plus embind, patches/pyodide-pyside6.patch), avec les paquets Python purs PySide6 et
  # shiboken6 dans sa bibliothèque standard. Qt et PySide6 n'y sont pas liés : ils vont dans le module latéral de la
  # phase dynamique, dont on prépare ici les objets (les cibles PySide sont des modules latéraux .so : on archive
  # leurs objets).
  emsdk_env; pyodide_env
  local lien="$RACINE/build/pyodide-lien" lib="$PYCIBLE/lib/python${PYTHON%.*}" c m
  local site="$RACINE/pyside-wasm/lib/python${PYTHON%.*}/site-packages"
  dossier "$lien"
  for c in libshiboken pyside6 pyside6qml shibokenmodule Qt${MODULES//;/ Qt}; do  # Qt<M> pour chaque module
    rm -f "$lien/$c.a"  # emar qc : ajout sans remplacement par nom de fichier, xargs peut l'appeler plusieurs fois
    find "$RACINE/build/pyside-wasm" -path "*/CMakeFiles/$c.dir/*" -name '*.o' -print0 | xargs -0 emar qc "$lien/$c.a"
    emranlib "$lien/$c.a"
  done
  em++ -fPIC -std=gnu++17 -DQT_STATIC -I"$QTWASM/include" -I"$QTWASM/include/QtCore" \
    -c "$DEP/wasm/qt_statique.cpp" -o "$lien/qt_statique.o"
  patcher pyodide "$PYODIDE"
  # Les paquets Python purs dans la bibliothèque standard, zippée par make : sans annotations .pyi, ni modules latéraux
  # .so, qui sont dans pyside_agrege.so (90 Mo de zip que rien ne charge).
  for m in PySide6 shiboken6; do
    rm -rf "${lib:?}/$m"; cp -r "$site/$m" "$lib/"; find "$lib/$m" \( -name '*.pyi' -o -name '*.so' \) -delete
  done
  # npm ci a été fait par telecharger_sources.sh (réseau) : on marque l'installation que make rejouerait sinon.
  [ -e "$PYODIDE/node_modules/.installed" ] || { ln -sfn src/js/node_modules/ "$PYODIDE/node_modules"
    touch "$PYODIDE/node_modules/.installed"; }
  make -C "$PYODIDE" all-but-packages
  # Un pyodide-lock.json vide : PySide6 vient de pyside_agrege.so, il n'y a aucun paquet à charger.
  [ -f "$PYODIDE/dist/pyodide-lock.json" ] || "$HOTEPY" -c 'import json, sys
json.dump({"info": {"arch": "wasm32", "platform": "emscripten_4_0_9", "version": sys.argv[1], "python": sys.argv[2],
           "abi_version": "2025_0"}, "packages": {}}, open(sys.argv[3], "w"), indent=2)' \
    "$(sed -n 's/.*"version": "\(.*\)".*/\1/p' "$PYODIDE/src/js/package.json")" "$PYTHON" "$PYODIDE/dist/pyodide-lock.json"
}

phase_dynamique() {
  # Étape 5 : Qt et PySide6 en modules latéraux que pyodide-qt.mjs charge dans une page seulement : pyside_agrege.so
  # (les cinq modules du départ, en parallèle de Python) et, depuis le 10/10/2026, un pyside_Qt<M>.so par module de
  # MODULES_DEMANDE, téléchargé et chargé au premier import. Mesuré sous Firefox le 05/10/2026 contre l'ancien
  # tout-statique (Qt lié dans le module principal) : Pyodide-Qt chargé 0,45 s au lieu de 0,53, worker prêt 0,97 s au
  # lieu de 1,16 (il ne compile plus Qt), mémoire du processus −100 à −140 Mo. Sortie dans $RACINE/build/dynamique/dist,
  # que phase_paquet empaquette.
  emsdk_env; pyodide_env
  local lien="$RACINE/build/pyodide-lien" dyn="$RACINE/build/dynamique" q="$QTWASM/lib" g="$QTWASM/plugins" f m greffon
  local FOURNISSEURS="Network OpenGLWidgets Qml Quick Multimedia"  # les modules dont un module chargé après eux importe la bibliothèque Qt
  local options=(-sSIDE_MODULE=1 -Oz -g0 -s WASM_BIGINT -fwasm-exceptions -sSUPPORT_LONGJMP)
  # L'agrégat : archives PySide entières (--whole-archive), rien dans le module principal ne les référence ; Qt au
  # besoin. Pas du port emdawnwebgpu de la recette Pyodide-Qt : aucun symbole wgpu dans Qt (llvm-nm). Chaque bibliothèque
  # Qt vit à UN endroit (son état statique ne se duplique pas) : ici celles dont dépend le port wasm de Qt, libQt6OpenGL
  # comprise (QOpenGLTextureBlitter) ; les autres de MODULES_DEMANDE dans leur module.
  local agrege=(-Wl,--whole-archive "$lien"/{libshiboken,pyside6,shibokenmodule}.a "$lien"/Qt{Core,Gui,Widgets,Svg,SvgWidgets}.a
    "$lien/qt_statique.o" -Wl,--no-whole-archive)
  local qt=("$q"/libQt6{Widgets,Gui,Core,Svg,SvgWidgets,OpenGL}.a "$q"/libQt6Bundled{Harfbuzz,Freetype,Libpng,Libjpeg,Pcre2}.a
    "$g"/platforms/libqwasm.a "$g"/iconengines/libqsvgicon.a "$g"/imageformats/libq{gif,ico,jpeg,svg}.a
    "$q"/objects-Release/{Gui,Widgets,QWasmIntegrationPlugin}_resources_*/.qt/rcc/*.o)
  dossier "$dyn/dist"
  # 1. Les modules à la demande : la liaison PySide entière, sa bibliothèque Qt (sauf OpenGL, dans l'agrégat), ses
  # greffons (sqlite embarqué pour Sql, lecture des certificats pour Network), importés par un Q_IMPORT_PLUGIN, et une
  # copie des interfaces de métatype des types de base de QtCore (metatypes_qtcore.cpp dit pourquoi).
  em++ -fPIC -std=gnu++17 -DQT_STATIC -Oz -fwasm-exceptions -I"$QTWASM/include" -I"$QTWASM/include/QtCore" \
    -c "$DEP/wasm/metatypes_qtcore.cpp" -o "$dyn/metatypes_qtcore.o"
  # Chaque archive et chaque objet n'a qu'UN propriétaire (l'état statique de Qt ne se duplique pas) : deja.txt les liste,
  # amorcé par l'agrégat, complété module après module (dans l'ordre de chargement). Les .prl de Qt disent quels objets de
  # ressources (qrc_*.o) une bibliothèque ou un greffon QML tire : des objets, pas des archives, donc à lier explicitement.
  local deja="$dyn/deja.txt" PREFIXE="$QTWASM"
  printf '%s\n' "${qt[@]}" > "$deja"
  neuf() { local l; while read -r l; do grep -qxF -- "$l" "$deja" || { echo "$l" >> "$deja"; echo "$l"; }; done; }
  prl_objets() { sed -n 's/^QMAKE_PRL_LIBS = //p' "$1" | tr ' ' '\n' | grep '\.cpp\.o$' |
    sed "s#\$\$\[QT_INSTALL_PREFIX\]#$PREFIXE#;s#\$\$\[QT_INSTALL_QML\]#$PREFIXE/qml#;s#\$\$\[QT_INSTALL_LIBS\]#$PREFIXE/lib#"; }
  qtlib() { local n; for n; do echo "$q/libQt6$n.a"; prl_objets "$q/libQt6$n.prl"; done; }
  qml_greffon() {  # qml_greffon <dossier de qml/> <greffon> : l'objet qui l'importe (nommé d'après la cible, pas la bibliothèque), l'archive et ses ressources
    ls "$QTWASM/qml/$1"/objects-Release/*_init/*_init.cpp.o; echo "$QTWASM/qml/$1/lib$2.a"; prl_objets "$QTWASM/qml/$1/lib$2.prl"; }
  for m in $MODULES_DEMANDE; do
    local libs=() importes="" entier=("$lien/Qt$m.a")
    case $m in
      OpenGL) ;;
      Sql) libs=("$q/libQt6Sql.a" "$g/sqldrivers/libqsqlite.a"); importes="Q_IMPORT_PLUGIN(QSQLiteDriverPlugin)" ;;
      Network) libs=("$q/libQt6Network.a" "$g/tls/libqcertonlybackend.a"); importes="Q_IMPORT_PLUGIN(QTlsBackendCertOnly)" ;;
      Qml) libs=($({ qtlib Qml QmlMeta QmlModels; qml_greffon QtQml qmlplugin; qml_greffon QtQml/Models modelsplugin; } | neuf))
           entier+=("$lien/pyside6qml.a" "$q"/libQt6{Qml,QmlMeta,QmlModels}.a) ;;  # entières : Quick en importe des membres que rien ne référence ici
      Quick) libs=($({ qtlib Quick QuickLayouts QuickTemplates2; qml_greffon QtQuick qtquick2plugin; qml_greffon QtQuick/Window quickwindowplugin
                       qml_greffon QtQuick/Layouts qquicklayoutsplugin; qml_greffon QtQuick/Templates qtquicktemplates2plugin; } | neuf))
             entier+=("$q"/libQt6{Quick,QuickLayouts,QuickTemplates2}.a) ;;
      QuickControls2) libs=($({ qtlib QuickControls2 QuickControls2Impl QuickControls2Basic QuickControls2BasicStyleImpl QuickControls2Fusion QuickControls2FusionStyleImpl
                                qml_greffon QtQuick/Controls qtquickcontrols2plugin; qml_greffon QtQuick/Controls/impl qtquickcontrols2implplugin
                                qml_greffon QtQuick/Controls/Basic qtquickcontrols2basicstyleplugin; qml_greffon QtQuick/Controls/Basic/impl qtquickcontrols2basicstyleimplplugin
                                qml_greffon QtQuick/Controls/Fusion qtquickcontrols2fusionstyleplugin; qml_greffon QtQuick/Controls/Fusion/impl qtquickcontrols2fusionstyleimplplugin; } | neuf)) ;;
      Multimedia) entier+=("$q/libQt6Multimedia.a")
                  libs=($({ qtlib Multimedia; echo "$q/libQt6BundledTLSF.a"; echo "$g/multimedia/objects-Release/QWasmMediaPlugin_init/QWasmMediaPlugin_init.cpp.o"
                            echo "$g/multimedia/libwasmmediaplugin.a"; prl_objets "$g/multimedia/libwasmmediaplugin.prl"; } | neuf)) ;;
      *) libs=("$q/libQt6$m.a") ;;
    esac
    printf '%s\n' "${libs[@]}" | neuf > /dev/null  # propriétaire des archives des cas simples aussi
    [ -z "$importes" ] || printf '#include <QtPlugin>\n%s\n' "$importes" | em++ -fPIC -std=gnu++17 -DQT_STATIC \
      -I"$QTWASM/include" -I"$QTWASM/include/QtCore" -x c++ -c - -o "$dyn/greffons_$m.o"
    printf '%s\n' -Wl,--whole-archive "${entier[@]}" "$dyn/metatypes_qtcore.o" $([ -z "$importes" ] || echo "$dyn/greffons_$m.o") \
      -Wl,--no-whole-archive "${libs[@]}" > "$dyn/lien_$m.rsp"  # relu par le second lien (2 bis)
    em++ -o "$dyn/dist/pyside_Qt$m.so" "${options[@]}" "@$dyn/lien_$m.rsp"
  done
  # 2. Ce que ces modules importent, l'agrégat doit l'exporter (lien final après 2 bis) : ses symboles Qt sont hidden, que --export-dynamic
  # (SIDE_MODULE) ignore, et il ne tire d'une archive que ce qu'il référence. Un premier lien --export-all, archives Qt
  # entières, donne tout ce qu'il PEUT définir ; symboles.py en retire ce que le module principal fournit (exports et
  # bibliothèque JavaScript) et ce que les modules se fournissent eux-mêmes ; le lien final n'exporte que cette liste
  # (--export=<sym> tire l'objet qui le définit, comme --undefined) : des exports en plus, pas tout Qt.
  em++ -o "$dyn/agrege_tout.so" "${options[@]}" -Wl,--export-all "${agrege[@]}" -Wl,--whole-archive "${qt[@]}" -Wl,--no-whole-archive
  # 2 bis. Un module qui porte une bibliothèque Qt l'exporte, lui aussi, à ceux qui la lient et se chargent après lui
  # (Network pour Qml et Multimedia, Qml pour Quick, Quick pour les Controls, OpenGLWidgets pour Charts...) : ses
  # symboles Qt sont hidden. Deuxième lien de ces fournisseurs en --export-all (dans tout/), symboles.py croises dit
  # ce que chacun doit exporter, et le lien final le fait. Les autres modules n'ont pas besoin de second lien.
  dossier "$dyn/tout"
  for f in $FOURNISSEURS; do em++ -o "$dyn/tout/pyside_Qt$f.so" "${options[@]}" -Wl,--export-all "@$dyn/lien_$f.rsp"; done
  "$HOTEPY" "$DEP/wasm/symboles.py" croises "$PYODIDE/dist/pyodide.asm.wasm" "$dyn/agrege_tout.so" "$dyn/tout" \
    $(for m in $MODULES_DEMANDE; do echo "$dyn/dist/pyside_Qt$m.so"; done) > "$dyn/croises.txt"
  for f in $FOURNISSEURS; do
    sed -n "s#^pyside_Qt$f.so #-Wl,--export=#p" "$dyn/croises.txt" > "$dyn/exports_$f.rsp"
    em++ -o "$dyn/dist/pyside_Qt$f.so" "${options[@]}" "@$dyn/lien_$f.rsp" "@$dyn/exports_$f.rsp"
  done
  # L'agrégat en dernier : ce qu'il exporte se lit sur les modules DÉFINITIFS (le second lien d'un fournisseur importe
  # cinq symboles de plus que le premier : QImage::fill(QColor), QAbstractItemModel::hasChildren... mesuré).
  "$HOTEPY" "$DEP/wasm/symboles.py" manquants "$PYODIDE/dist/pyodide.asm.wasm" "$dyn/agrege_tout.so" \
    "$dyn"/dist/pyside_Qt*.so | sed 's/^/-Wl,--export=/' > "$dyn/exports.rsp"
  em++ -o "$dyn/dist/pyside_agrege.so" "${options[@]}" "@$dyn/exports.rsp" "${agrege[@]}" "${qt[@]}"
  # 3. Chaque import de chaque module résolu (principal, agrégat, module chargé avant lui) : sinon Emscripten pose un
  # bouchon qui échoue au premier appel, sans rien dire au chargement (Pyodide est sans ASSERTIONS).
  "$HOTEPY" "$DEP/wasm/symboles.py" verifier "$PYODIDE/dist/pyodide.asm.wasm" "$dyn/dist/pyside_agrege.so" \
    $(for m in $MODULES_DEMANDE; do echo "$dyn/dist/pyside_Qt$m.so"; done) || { echo "phase dynamique : imports non résolus" >&2; return 1; }
  for f in package.json pyodide.asm.js pyodide.asm.wasm pyodide.js pyodide-lock.json python_stdlib.zip test.html; do
    cp "$PYODIDE/dist/$f" "$dyn/dist/"
  done
  cp "$PYODIDE/dist/pyodide.mjs" "$dyn/dist/pyodide-base.mjs"
  cp "$DEP/wasm/pyodide-qt.mjs" "$dyn/dist/pyodide.mjs"
  ls -l "$dyn/dist"
}

phase_paquet() {
  # Le zip que sert l'hébergement (hebergement/telecharger.sh, versions.json « pyodide_pyside6 ») : les fichiers que
  # charge une page, sous pyodide-qt/ comme la release de Pyodide-Qt, avec la licence. Python et non zip (absent ici).
  # Son empreinte change à chaque fois (py-compile inscrit la date d'extraction dans chaque .pyc) : à reporter.
  # La bibliothèque standard en .pyc (pyodide py-compile, l'outil de la variante pyc/ du CDN de Pyodide) : −1,1 s à
  # chaque chargement, mesuré (notes/2026-09-30 - PySide6 en WebAssembly.md, « Démarrage »). Prix : les traces
  # d'erreur n'affichent plus la ligne de code des modules de la bibliothèque standard.
  local pyc="$RACINE/build/paquet"
  dossier "$pyc"; cp "$RACINE/build/dynamique/dist/python_stdlib.zip" "$pyc/"
  /DATA/Python/outils_wasm/venv-pyodide/bin/pyodide py-compile --silent --compression-level 9 "$pyc/python_stdlib.zip"
  "$HOTEPY" - "$RACINE/build/dynamique/dist" "$pyc/python_stdlib.zip" "$DEP/hebergement/LICENSE-Pyodide-PySide6.txt" "$RACINE/pyodide-pyside6-0.29.3.2.zip" <<'PY'
import hashlib, sys, zipfile
from pathlib import Path
dist, stdlib, licence, sortie = map(Path, sys.argv[1:])
fichiers = [dist / n for n in ("package.json", "pyodide.asm.js", "pyodide.asm.wasm", "pyodide.js", "pyodide-lock.json",
                               "pyodide-base.mjs", "pyodide.mjs", "test.html")] + sorted(dist.glob("pyside_*.so")) + [stdlib, licence]
with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in fichiers:
        z.write(f, f"pyodide-qt/{'LICENSE.txt' if f == licence else f.name}")
print(sortie, sortie.stat().st_size, "octets ; sha256", hashlib.sha256(sortie.read_bytes()).hexdigest())
PY
}

for p in "$@"; do "phase_$p" 2>&1 | tee -a "$JOURNAUX/$p.log"; done
