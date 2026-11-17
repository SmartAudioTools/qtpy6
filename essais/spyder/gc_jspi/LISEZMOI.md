# gc_jspi — reproduction minimale du plantage JSPI + GC (W576, 17/11/2026)

Versions : Pyodide 314.0.7 (`../site/pyodide/`, CPython 3.14.2 d'après `strings pyodide.asm.wasm`), Node v26.11.1
(`/usr/bin/node`, JSPI natif : `WebAssembly.Suspending` présent).

- `gcnu.mjs` : Pyodide nu sous Node ; N entrées promettantes (`callPromising`) qui allouent des cycles et se suspendent
  par `run_sync` (comme les fils de `threading_web` qui s'attendent). `node gcnu.mjs entrelace|imbrique|seul [fils] [tours]`,
  témoins par environnement : `GC=1|0|off|jeune|incr|plein`, `SUSP=0`, `PYODIDE=./pyodide_patche/`, `CORRIGE=1`, `SONDE=1`.
- `campagne.sh [n]` : n répétitions par cas (`CAS=` pour une liste, `BILAN=` nom du bilan) ; bilans dans `traces/`.
- `fabriquer_pyodide_patche.py` : écrit `pyodide_patche/` (non suivi : liens vers `../site/pyodide/` + un
  `pyodide.asm.mjs` modifié), qui émule le correctif (CORRIGE=1) et mesure l'écrasement des cadres (SONDE=1).
- `traces/bilan*.txt` : résultats ; `traces/trace_plantage.txt` : un plantage complet.
- `spe_rf.py` : essai de W568 (non suivi, pas à W576).

Analyse : `notes/2026-11-17 - Plantage JSPI et GC, reproduction minimale et cause (W576).md`.
