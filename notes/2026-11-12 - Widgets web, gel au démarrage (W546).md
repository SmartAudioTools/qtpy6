# Widgets web de Spyder : le gel au démarrage de la console (W546, 12/11/2026)

Demande : item 2 du TODO Portage, ordre du professeur (12/11 14:04 : « mets des workers sur tous les items qui peuvent
être traités indépendamment ») ; but : la console IPython sans `--no-web-widgets` (5/5 du jalon 8c).

## Mesure (Firefox 158 par la sonde, `panneaux.py` avec les widgets web, site à part `qtpy6_essais/w546/site`)

| Passe | setHtml (par appel) | Dialogue dans l'`<iframe>` | Jalon 8c |
|---|---|---|---|
| sans correctif | 3 à 38 ms (`_ressources` 1 à 34 ms) | `alert("Could not load the image")`, 1 `file://` restant | gel : `UnexpectedAlertPresentException`, sonde code 1 |
| avec correctif | 2 à 64 ms (60 ms une fois : premiers blobs) | aucun, 0 `file://` restant | **5/5** : In [1] 14,7 s, `1+1`, `a`, redémarrage 16,2 s, `a` oubliée |
| témoin `--no-web-widgets`, même site | — | — | 5/5 : In [1] 14,6 s, redémarrage 18,3 s |

Ni `setHtml`, ni les polices, ni l'`<iframe>` ne coûtent. Le gel : `loading.html` de Spyder
(`plugins/ipythonconsole/assets/templates`) charge son image animée par `cImageSrc='file:///${loading_img}'`, chaîne
d'un SCRIPT, que `_ressources` ne réécrivait pas (seulement les attributs `src`/`href`) ; le navigateur refuse file://
à une page http, `onerror` appelle `alert()`, boîte modale du navigateur qui suspend toute la page (sous la sonde
jusqu'à ce que webdriver la ferme ; pour un élève : une boîte à cliquer à chaque page de chargement). La bissection du
12/10 (« Dialogue modal JS ») n'avait guetté que le `window.alert` de la page principale, pas celui de l'`<iframe>`.
L'écart In [1] 14,7 s contre 3,6 s le 12/10 ne vient pas des widgets : le témoin donne le même chiffre (site de
80 Mio contre 41, machine chargée par dix workers ; non séparé).

## FAIT

- `qtpy6/web/moteur_web.py` : `_urls_script`, appelé par `_ressources` sur chaque `<script>` en ligne : les chaînes
  `'file:///…'` d'un fichier lisible deviennent des URL blob: (même `_local`/`_blob` que les attributs et les `url()`
  CSS). Docstring du module mise à jour.
- `essais/spyder/panneaux.py` : `PANNEAUX_WEB` vaut 1 par défaut (widgets web gardés) ; le bloc de mesure est retiré.
- `spe.py` (à W555) : retrait de `--no-web-widgets` demandé par message.

## POURQUOI, alternative écartée

- D3, « qtpy6 annonce l'absence de WebEngine » : écartée, la doublure légère suffit (mesuré) et D3 retirerait aussi
  l'aide et la page d'erreur du noyau.
- Remplacer tout `file://` du document : écarté, les liens `<a href="file://…">` doivent rester des liens
  (`acceptNavigationRequest`) ; seuls les scripts en ligne sont touchés.
- Doubler `alert/confirm/prompt` de l'`<iframe>` par `QWebEnginePage.javaScriptAlert…` (dialogue dessiné par Qt, pas
  de modale du navigateur) : non fait, hors du besoin mesuré ; RESTE : une page qui appelle `alert()` montre encore la
  boîte du navigateur (et bloque la sonde). Coût estimé : un script injecté en tête du `srcdoc`, ~25 lignes.

Existant : `_local`, `_blob`, `_urls_css` réutilisés, aucune fonction en double.

## VÉRIFIÉ

- Mesuré : trois passes Firefox ci-dessus, une chacune (journaux `qtpy6_essais/w546/sonde_web1.log`,
  `sonde_web2.log`, `sonde_temoin.log`, consoles `capture_*.console.log`).
- Tests (`testeur`) : `tests/test_doublures.py` 1/1, `tests/test_web.py -k moteur_web` 1/1.
- Pas de test unitaire de `_urls_script` : `tests/` n'est pas dans mes fichiers ; l'échec sans correctif est la passe
  1 (« file:// restants 1 », alert). Non essayé : Chrome, `spe.py` complet (après le retrait par W555).
- Délégation : les relevés de journaux faits moi-même (un `grep` par passe, sorties courtes).
