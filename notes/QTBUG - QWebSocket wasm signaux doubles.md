# Rapport de bug à déposer sur bugreports.qt.io (rédigé le 11/10/2026)

Demande de l'utilisateur : « il faudrait envoyer un bug report à qt ». Le dépôt demande un compte Qt : c'est à
l'utilisateur de le faire (projet QTBUG, composant « WebSockets », plateforme WebAssembly). Recherche d'un doublon le
11/10/2026 : rien trouvé ; voisins : QTBUG-111248 (close() sur wasm qui ne ferme pas), le commit de 2023 « wasm: fix
unconnectedState signal being emitted when closed ». Mesure : `essais/websocket_echo/`, note
`2026-10-10 - Modules Qt à la demande.md`. Le texte ci-dessous est à coller tel quel.

---

**Title**: [wasm] QWebSocket emits disconnected() twice after close(), and errorOccurred() twice on a refused connection

**Component**: WebSockets — **Platform**: WebAssembly — **Version**: 6.10.2 (code unchanged on `dev` as of 2026-10-11)

**Description**

On WebAssembly, `QWebSocket::disconnected()` is emitted twice when the application calls `close()`, and
`errorOccurred()` is emitted twice when a connection fails. On desktop, each signal is emitted once in the same
scenario.

**Steps to reproduce**

```cpp
QWebSocket ws;
QObject::connect(&ws, &QWebSocket::connected, [&] { ws.sendTextMessage("a"); });
QObject::connect(&ws, &QWebSocket::textMessageReceived, [&](const QString &) { ws.close(); });
QObject::connect(&ws, &QWebSocket::disconnected, [] { qDebug() << "disconnected"; });
QObject::connect(&ws, &QWebSocket::errorOccurred, [](auto e) { qDebug() << "error" << e; });
ws.open(QUrl("ws://127.0.0.1:8765/"));   // any echo server
```

**Expected**: one "disconnected" (as on desktop Linux).
**Actual** (Firefox 155 and Chrome 140): "disconnected" twice. With a closed port (`ws://127.0.0.1:9/`):
"error UnknownSocketError" twice, then "disconnected".

(Measured through PySide6 6.10.2 on Pyodide, with an echo server on 127.0.0.1. The C++ snippet above is the
equivalent and has not been compiled as such.)

**Cause** (`src/websockets/qwebsocket_wasm_p.cpp`)

- `QWebSocketPrivate::close()` sets `UnconnectedState` and emits `disconnected()` unconditionally. The browser
  then fires `onclose`, and `setSocketClosed()` emits `disconnected()` again, because it only checks the browser's
  `readyState == 3`, not whether the Qt state is already `UnconnectedState`.
- `q_onWebSocketErrorCallback` emits `errorOccurred()`. The browser always follows `error` with `close`, and
  `setSocketClosed()` emits `errorOccurred()` again when `!wasClean`.

**Suggested fix**

- in `setSocketClosed()`: emit `disconnected()` only if `m_socketState != QAbstractSocket::UnconnectedState`
  (still delete the socket context);
- emit `errorOccurred()` from only one of the two callbacks (e.g. drop it from `q_onWebSocketErrorCallback`, since
  `onclose` with `wasClean == false` always follows).
