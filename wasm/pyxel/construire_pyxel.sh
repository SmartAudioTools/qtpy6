#!/bin/bash
# Roue Pyodide de Pyxel, sans réseau, par la recette de kitao elle-même (`make clean-wasm build-wasm`, Makefile de v2.9.9).
#   wasm/pyxel/construire_pyxel.sh <sources de Pyxel> <dossier de sortie> [racine]
#   ex. : construire_pyxel.sh /DATA/Python/FORKS/pyxel-wasm/src-2.9.9 /DATA/Python/qtpy6_essais/equipe/w575/roues
# Prérequis : telecharger_pyxel.sh (emsdk, Rust, crates, maturin dans <racine>, défaut /DATA/Python/FORKS/pyxel-wasm).
# Écrit la roue dans <sortie>, sa taille, son sha256 et la durée dans <sortie>/construire.log.
set -euo pipefail
SRC="$(cd "$1" && pwd)" OUT="$(mkdir -p "$2" && cd "$2" && pwd)" R="$(cd "${3:-/DATA/Python/FORKS/pyxel-wasm}" && pwd)"
export RUSTUP_HOME="$R/rustup" CARGO_HOME="$R/cargo" CARGO_NET_OFFLINE=true
export PATH="$R/.venv/bin:$CARGO_HOME/bin:$PATH"
set +u   # emsdk_env.sh lit des variables non définies
# shellcheck disable=SC1091
source "$R/emsdk/emsdk_env.sh" >/dev/null
set -u
# Cache d'emscripten (port SDL2) : emcc y pose un verrou même pour le lire, et telecharger_pyxel.sh l'a créé en 755
# depuis un autre compte. Une copie par compte, écrivable (727 Mo, une fois).
EM_CACHE="$R/cache-emscripten-$(id -un)"
export EM_CACHE
[ -d "$EM_CACHE" ] || cp -r "$EMSDK/upstream/emscripten/cache" "$EM_CACHE"
debut=$(date +%s)
make -C "$SRC" clean-wasm build-wasm
# shellcheck disable=SC2012
roue="$(ls -t "$SRC"/dist/*-emscripten_*.whl | head -1)"  # build-wasm vide dist/ ; par prudence, la plus récente
cp "$roue" "$OUT/"
{
  echo "$(date '+%F %T') $(git -C "$SRC" rev-parse --short HEAD 2>/dev/null) $(basename "$roue")"
  echo "duree $(( $(date +%s) - debut )) s, taille $(stat -c %s "$roue") octets, sha256 $(sha256sum "$roue" | cut -d' ' -f1)"
} | tee -a "$OUT/construire.log"
