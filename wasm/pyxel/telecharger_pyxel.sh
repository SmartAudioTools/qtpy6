#!/bin/bash
# Roue Pyodide de Pyxel, étape 0 : tout ce qui demande le réseau, d'un coup (le bac à sable de Claude ne l'a pas).
# Lancé par l'utilisateur, depuis son compte. Rejouable : ce qui est déjà là n'est pas retéléchargé.
#   wasm/pyxel/telecharger_pyxel.sh [racine]     (défaut : /DATA/Python/FORKS/pyxel-wasm)
# Reproduit les prérequis de la recette de kitao (Makefile de v2.9.9, cible build-wasm) : emscripten 5.0.3,
# Rust nightly-2026-08-12 + rust-src + cible wasm32-unknown-emscripten, maturin 1.x, port SDL2 PIC d'emscripten.
# Ensuite : wasm/pyxel/construire_pyxel.sh, sans réseau.
set -euo pipefail
R="$(mkdir -p "${1:-/DATA/Python/FORKS/pyxel-wasm}" && cd "${1:-/DATA/Python/FORKS/pyxel-wasm}" && pwd)"
PYXEL=v2.9.9 EMSCRIPTEN=5.0.3 RUST=nightly-2026-08-12 RUSTUP_INIT_VERSION=1.28.2
export RUSTUP_HOME="$R/rustup" CARGO_HOME="$R/cargo"
mkdir -p "$R" && cd "$R"

echo "== Pyxel $PYXEL (kitao/pyxel)"
[ -d src-2.9.9/.git ] || git clone -q --depth 1 --branch "$PYXEL" https://github.com/kitao/pyxel.git src-2.9.9

echo "== emsdk, emscripten $EMSCRIPTEN (« the version Pyodide uses », en-tête du Makefile)"
[ -d emsdk/.git ] || git clone -q https://github.com/emscripten-core/emsdk.git emsdk
emsdk/emsdk install "$EMSCRIPTEN" && emsdk/emsdk activate "$EMSCRIPTEN" >/dev/null
set +u   # emsdk_env.sh lit des variables non définies
# shellcheck disable=SC1091
source emsdk/emsdk_env.sh >/dev/null
set -u
embuilder build sdl2 --pic   # télécharge le port SDL2 et le construit (première ligne de build-wasm)

echo "== Rust $RUST (rust-toolchain.toml de Pyxel), privé : $RUSTUP_HOME"
if [ ! -x "$CARGO_HOME/bin/rustup" ]; then
  curl -fL --retry 3 -o rustup-init \
    "https://static.rust-lang.org/rustup/archive/$RUSTUP_INIT_VERSION/x86_64-unknown-linux-gnu/rustup-init"
  chmod +x rustup-init && ./rustup-init -y -q --no-modify-path --default-toolchain none --profile minimal
fi
export PATH="$CARGO_HOME/bin:$PATH"
(cd src-2.9.9 && rustup toolchain install "$RUST" --profile minimal --component rust-src --target wasm32-unknown-emscripten)  # depuis les sources : rust-toolchain.toml

echo "== crates de Pyxel et de la bibliothèque standard (-Zbuild-std la recompile)"
(cd src-2.9.9/crates && cargo "+$RUST" fetch)
SYSROOT="$(rustc "+$RUST" --print sysroot)"
cargo "+$RUST" fetch --manifest-path "$SYSROOT/lib/rustlib/src/rust/library/Cargo.toml"

echo "== venv privé, maturin (python/pyproject.toml : maturin>=1.0,<2.0)"
[ -x .venv/bin/python ] || python3.14 -m venv .venv
.venv/bin/pip install -q "maturin>=1.0,<2.0" ruff   # ruff : scripts/generate_docs le lance (ruff format)

{
  echo "telecharge le $(date '+%F %T')"
  echo "pyxel $PYXEL $(git -C src-2.9.9 rev-parse HEAD)"
  echo "emscripten $(emcc --version | head -1)"
  echo "emsdk $(git -C emsdk rev-parse HEAD)"
  echo "rust $(rustc "+$RUST" --version)"
  echo "$(.venv/bin/maturin --version), $(.venv/bin/ruff --version)"
  echo "python $(.venv/bin/python --version)"
} | tee "$R/versions.txt"
echo "OK : tout est là, construire_pyxel.sh peut tourner sans réseau"
