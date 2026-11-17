# Roue Pyodide du fork de Pyxel, recette (W575, 17/11/2026)

**Demande** (le professeur, 17/11/2026 02:45, fenêtre du Superviseur) : « lance des worker pour avancer au maximum sur ce
sujet cette nuit, tu peux forker et compiler pyxel. » Sujet : les jeux Pyxel saccadent dans SmartPythonEditor web ; W574
ajoute `pyxel.step()` (cadencement externe) ; il faut la roue Pyodide de cette branche pour que le web en profite.

## FAIT
- Recette lue dans les sources de kitao/pyxel v2.9.9 par l'agent web-fetch (URLs ouvertes : `Makefile`,
  `rust-toolchain.toml`, `python/pyproject.toml`, `crates/Cargo.toml`, `crates/Cargo.lock`, `scripts/check_wasm_wheel`,
  `scripts/install_wasm_wheel`, `scripts/generate_docs`, `scripts/generate_pyi_docstrings`, `.github/workflows/build.yml`
  et `release.yml`, `emscripten-core/emsdk` `emscripten-releases-tags.json`). La roue wasm n'est PAS faite par la CI :
  kitao la construit à la main par `make clean-wasm build-wasm`, emsdk 5.0.3 activé.
- `wasm/pyxel/telecharger_pyxel.sh` (réseau, compte de l'utilisateur) et `wasm/pyxel/construire_pyxel.sh` (sans réseau,
  rejoue `make clean-wasm build-wasm`), `wasm/pyxel/README.md` (versions, recette, étape de la branche W574).
- Site privé `qtpy6_essais/equipe/w575/site` (copie de `w572/site`, `roues/` devenu un vrai dossier pour y substituer
  la roue sans toucher `essais/spyder/roues`) et `w575/verifier.sh` (sonde hors écran, compte CADENCE/VSYNC).

## POURQUOI
- La recette de kitao plutôt qu'une écrite à neuf (brief : « l'existant d'abord ») : ses drapeaux (`-sSIDE_MODULE=2`,
  `-fwasm-exceptions`, `+simd128`, `-Zbuild-std`, SDL2 PIC) font la compatibilité avec le Pyodide du site ; les recopier
  dans un script à nous les ferait diverger au premier changement de version. On appelle donc son `make`.
- Deux temps (réseau / sans réseau), comme `wasm/telecharger_sources.sh` : le bac à sable n'a pas de réseau.
- Alternative écartée : `pyodide build` (pyodide-build) — kitao ne s'en sert pas, et il imposerait une version de
  pyodide-build accordée à Pyodide 3.14.2 sans rien apporter à une roue abi3 que maturin sait déjà étiqueter
  `emscripten_5_0_3`.
- Emsdk privé sous `/DATA/Python/FORKS/pyxel-wasm/`, séparé du 4.0.9 de la recette Qt (brief).

## VÉRIFIÉ
- **Mesuré** : le site privé avec la roue de kitao (sha256 `a6f45776…`) : sonde `fini` en 53 s, CADENCE 68 lignes,
  VSYNC 38 (`w575/depart_kitao.*`) — la vérification d'arrivée est donc prête et vue verte au départ.
- **Mesuré** : aucun réseau dans le bac la nuit du 17/11 (« Proxy CONNECT aborted » sur github.com, pypi.org,
  static.rust-lang.org, storage.googleapis.com) : ni emsdk, ni rustup, ni crates ; la construction n'a pas été jouée.
- **Lu dans les sources** : versions et commandes ci-dessus ; `shellcheck` propre sur les deux scripts.
- **Supposé, à vérifier au premier passage** : que le `rustup component add` / `target add` du Makefile passe sans réseau
  quand composant et cible sont déjà installés ; que `cargo fetch` sur `library/Cargo.toml` suffit à `-Zbuild-std`
  hors ligne ; que `clean-wasm` ne purge pas le cache d'emscripten (port SDL2) ; que le nom de la roue rebâtie est
  identique (`…-cp311-abi3-emscripten_5_0_3_wasm32.whl`). Relecteur (sonnet) : ces points relevés « plausibles » ;
  corrigés dans les scripts : `set -u` levé autour d'`emsdk_env.sh` (stderr visible), racine rendue absolue, toolchain
  installée depuis les sources (`rust-toolchain.toml`), roue la plus récente de `dist/`.

## RESTE
Étape 1 du README par le professeur, puis construction, sonde, roue de la branche W574 (`pyxel.step` vu par la sonde).
