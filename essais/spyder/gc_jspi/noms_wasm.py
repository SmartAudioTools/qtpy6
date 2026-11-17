"""W584 : nom des fonctions d'un module wasm par leur indice (section « name », sinon exports).

Usage : python noms_wasm.py <fichier.wasm|.so> <indice> [<indice>…]
Rend, pour chaque indice, le nom de la fonction (imports comptés, comme dans les piles de Firefox
« wasm-function[N] »), et en tête le nombre d'imports de fonctions et de fonctions définies.
"""
import sys


def leb(b, i):
    r = s = 0
    while True:
        x = b[i]; i += 1
        r |= (x & 0x7F) << s; s += 7
        if x < 0x80:
            return r, i


def nom(b, i):
    n, i = leb(b, i)
    return b[i:i + n].decode("utf-8", "replace"), i + n


def lire(chemin):
    b = open(chemin, "rb").read()
    assert b[:4] == b"\0asm", chemin
    i, imports, definies, noms, exports = 8, 0, 0, {}, {}
    while i < len(b):
        sid = b[i]; taille, i = leb(b, i + 1); fin = i + taille
        if sid == 2:  # imports
            n, j = leb(b, i)
            for _ in range(n):
                _, j = nom(b, j); _, j = nom(b, j); k = b[j]; j += 1
                if k == 0:
                    _, j = leb(b, j); imports += 1
                elif k == 1:
                    j += 1; f = b[j]; j += 1; _, j = leb(b, j)
                    if f & 1: _, j = leb(b, j)
                elif k == 2:
                    f = b[j]; j += 1; _, j = leb(b, j)
                    if f & 1: _, j = leb(b, j)
                elif k == 3:
                    j += 2
                elif k == 4:
                    j += 1; _, j = leb(b, j)
        elif sid == 3:
            definies, _ = leb(b, i)
        elif sid == 7:  # exports
            n, j = leb(b, i)
            for _ in range(n):
                x, j = nom(b, j); k = b[j]; j += 1; idx, j = leb(b, j)
                if k == 0: exports.setdefault(idx, x)
        elif sid == 0:
            x, j = nom(b, i)
            if x == "name":
                while j < fin:
                    sous = b[j]; t, j = leb(b, j + 1); f2 = j + t
                    if sous == 1:
                        n, k = leb(b, j)
                        for _ in range(n):
                            idx, k = leb(b, k); x2, k = nom(b, k); noms[idx] = x2
                    j = f2
        i = fin
    return imports, definies, noms, exports


if __name__ == "__main__":
    imp, dfn, noms, exp = lire(sys.argv[1])
    print(f"imports={imp} definies={dfn} total={imp + dfn} noms={len(noms)} exports={len(exp)}")
    for a in sys.argv[2:]:
        n = int(a)
        print(n, noms.get(n) or ("export:" + exp[n] if n in exp else "?"))
