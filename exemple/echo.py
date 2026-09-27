"""Le module du worker de l'exemple : ce qu'il imprime revient à la fenêtre au fil de l'eau (signal ``sortie``), ce qu'il
rend par ``termine``. L'invite sans retour à la ligne mesure si la sortie arrive sans attendre un ``\\n``."""

import sys
import time


def echo(texte):
    print("invite> ", end="", flush=True)
    time.sleep(0.5)  # le worker a son propre fil : la page ne gèle pas
    print(f"écho : {texte}")
    print(f"python {sys.version.split()[0]} dans le worker")
    return {"longueur": len(texte), "majuscules": texte.upper()}
