"""Serveur d'écho WebSocket sur 127.0.0.1 pour `page.py` (point ouvert « connexion WebSocket réelle » de
notes/2026-10-10 - Modules Qt à la demande.md) : renvoie chaque message tel quel (texte ou binaire) et note ce qu'il reçoit.
S'arrête seul après `duree` secondes.

    $P serveur.py [port] [duree] > serveur.log 2>&1
"""

import asyncio
import sys

from websockets.asyncio.server import serve

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
DUREE = float(sys.argv[2]) if len(sys.argv) > 2 else 300


async def echo(connexion):
    print("connexion", connexion.remote_address, connexion.request.path, flush=True)
    async for message in connexion:
        print("reçu", type(message).__name__, repr(message), flush=True)
        await connexion.send(message)
    print("fermée", connexion.close_code, flush=True)


async def main():
    async with serve(echo, "127.0.0.1", PORT):
        print("écoute", PORT, flush=True)
        await asyncio.sleep(DUREE)


asyncio.run(main())
