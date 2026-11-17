"""W576 (17/11/2026) : fabrique pyodide_patche/, copie du Pyodide du site (liens symboliques) dont seul pyodide.asm.mjs
est modifié dans saveState / restoreState (bascule JSPI). Variables d'environnement lues à l'exécution :
  CORRIGE=1  émule le correctif c. : le PyThreadState d'une tâche suspendue a current_frame = NULL pendant la
             suspension (mark_stacks du GC incrémental ne parcourt plus sa chaîne), restauré à la reprise ;
  SONDE=1    à chaque suspension, relève la chaîne de cadres (adresse, owner) et la zone de pile C de la tâche ;
             à la reprise, AVANT la recopie de la pile, compte les cadres de la chaîne dont l'en-tête (previous,
             owner) a changé pendant la suspension : c'est ce que mark_stacks aurait lu pendant ce temps.
Offsets wasm32 relevés le 17/11 sur 314.0.7 / CPython 3.14.2 : PyThreadState.current_frame = +52 ;
_PyInterpreterFrame.previous = +4, .owner = +38 (char).
Usage : python3 fabriquer_pyodide_patche.py ; puis PYODIDE=./pyodide_patche/ CORRIGE=1 node gcnu.mjs …"""

import os
import shutil

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ICI, "..", "site", "pyodide")
CIBLE = os.path.join(ICI, "pyodide_patche")

os.makedirs(CIBLE, exist_ok=True)
for nom in os.listdir(SOURCE):
    lien = os.path.join(CIBLE, nom)
    if nom == "pyodide.asm.mjs" or os.path.lexists(lien):
        continue
    os.symlink(os.path.join("..", "..", "site", "pyodide", nom), lien)

s = open(os.path.join(SOURCE, "pyodide.asm.mjs"), encoding="utf-8").read()

CAPTURE = "const threadState=_captureThreadState()"
RETOUR = "return{threadState,stackState,suspender:suspenderGlobal.value}"
REPRISE = "state.stackState.restore();_restoreThreadState(state.threadState)"
for motif in (CAPTURE, RETOUR, REPRISE):
    assert s.count(motif) == 1, motif

s = s.replace(CAPTURE, CAPTURE + """;const W576e=globalThis.process?.env||{};let W576cf=0,W576ch=null;
if(threadState){W576cf=HEAP32[(threadState+52)>>2];
if(W576e.SONDE==="1"){W576ch=[];for(let f=W576cf,k=0;f&&k<64;k++){const prev=HEAP32[(f+4)>>2],own=HEAP8[f+38];W576ch.push([f,prev,own]);f=prev}}
if(W576e.CORRIGE==="1")HEAP32[(threadState+52)>>2]=0}""")
s = s.replace(RETOUR, """const W576r={threadState,stackState,suspender:suspenderGlobal.value,W576cf,W576ch};
if(W576ch){const lo=stackState.start,hi=stackState.stop;W576r.W576zone=[lo,hi];
Module.W576stats=Module.W576stats||{suspensions:0,cadres_pile_c:0,reprises:0,reprises_ecrasees:0,cadres_ecrases:0};
Module.W576stats.suspensions++;Module.W576stats.cadres_pile_c+=W576ch.filter(([f])=>f>=lo&&f<hi).length}
return W576r""")
s = s.replace(REPRISE, """if(state.W576ch){let n=0;for(const [f,prev,own] of state.W576ch){if(HEAP32[(f+4)>>2]!==prev||HEAP8[f+38]!==own)n++}
const st=Module.W576stats;st.reprises++;if(n){st.reprises_ecrasees++;st.cadres_ecrases+=n}}
state.stackState.restore()
if(state.W576cf&&(globalThis.process?.env||{}).CORRIGE==="1")HEAP32[(state.threadState+52)>>2]=state.W576cf
_restoreThreadState(state.threadState)""")
open(os.path.join(CIBLE, "pyodide.asm.mjs"), "w", encoding="utf-8").write(s)
print("pyodide_patche/ écrit")
