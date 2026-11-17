# Roue Pyodide de Pyxel (W575, 17/11/2026)

La roue que charge le noyau Pyxel de SmartPythonEditor web (`essais/spyder/spe_monkey.py`, `ROUE`) est
`pyxel-2.9.9-cp311-abi3-emscripten_5_0_3_wasm32.whl`, publiée par kitao. Pour un Pyxel modifié (branche
`qtpy6-vsync`, `pyxel.step()` de W574), il faut la rebâtir : cette recette est **celle de kitao**, rejouée
telle quelle (`make clean-wasm build-wasm` du Makefile de v2.9.9), avec ses prérequis privés et épinglés.

## Versions (lues dans les sources de kitao/pyxel v2.9.9, 17/11/2026)

| quoi | version | d'où |
|---|---|---|
| Pyxel | tag `v2.9.9` | `Makefile`, `rust-toolchain.toml` |
| emscripten | 5.0.3 (emsdk, privé) | en-tête du Makefile : « Requires Emscripten 5.0.3 (the version Pyodide uses) » ; = `platform` du `pyodide-lock.json` du site (Pyodide Python 3.14.2, ABI 2026_0) |
| Rust | `nightly-2026-08-12` + `rust-src` + cible `wasm32-unknown-emscripten` (rustup privé) | `rust-toolchain.toml` ; `-Zbuild-std=std,panic_abort` exige nightly et rust-src |
| maturin | `>=1.0,<2.0` (version prise notée dans `versions.txt`) | `python/pyproject.toml` |
| ruff | dernière | `scripts/generate_docs` lance `ruff format` |
| SDL2 | port emscripten, `embuilder build sdl2 --pic` | première ligne de `build-wasm` |

Tout vit sous `/DATA/Python/FORKS/pyxel-wasm/` (`emsdk/`, `rustup/`, `cargo/`, `.venv/`, `src-2.9.9/`), séparé
de l'emsdk 4.0.9 de la recette Qt (`wasm/README.md`) : les deux versions d'emscripten ne se mélangent pas.

## Recette

1. **Le réseau, une fois, depuis le compte de l'utilisateur** (le bac à sable de Claude n'en a pas) :
   `wasm/pyxel/telecharger_pyxel.sh` — clone, emsdk 5.0.3 et port SDL2, rustup et nightly, crates de Pyxel et de
   la bibliothèque standard (`cargo fetch`), venv avec maturin et ruff ; écrit `versions.txt`.
2. **La construction, sans réseau** (`CARGO_NET_OFFLINE=true`) :
   `wasm/pyxel/construire_pyxel.sh <sources> <sortie>` — `make clean-wasm build-wasm` (qui vérifie aussi
   qu'aucun chemin `/home/` ne reste dans la roue), copie la roue, note durée, taille, sha256 dans
   `<sortie>/construire.log`.
3. **La branche de W574**, sans réseau (mêmes crates) :
   `git clone -q src-2.9.9 src-vsync && python3 /DATA/Python/qtpy6_essais/equipe/w574/patch_pyxel/appliquer_patch.py src-vsync`
   puis `construire_pyxel.sh src-vsync /DATA/Python/qtpy6_essais/equipe/w575/roues`.
4. **Vérification** : la roue à la place de celle de kitao dans `qtpy6_essais/equipe/w575/site/roues/`, puis
   `w575/verifier.sh <nom>` (sonde hors écran jusqu'à `fini`, jeu Monkey, compte des lignes CADENCE et VSYNC).

## Mesuré

- Départ, roue de kitao (sha256 `a6f45776…`) : sonde `fini` en 53 s, CADENCE 68, VSYNC 38 (`w575/depart_kitao.*`).
- Durée de construction et taille de la roue rebâtie : à mesurer (pas de réseau la nuit du 17/11, étape 1 non jouée).
