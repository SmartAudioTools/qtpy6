// Ce que Qt lié statiquement attend du binaire Pyodide, compilé et lié par construire.sh (phase pyodide).
// Repris de la recette Pyodide-Qt (github.com/JarrettSJohnson/pyodide-with-pyqt6, patches/qt_plugin_import.cpp
// et patches/qt_wasm_stubs.c, scripts sous licence MIT), réunis en un seul fichier.

// 1. Les greffons : en statique, Qt ne les trouve que s'ils sont importés explicitement.
#include <QtPlugin>
Q_IMPORT_PLUGIN(QWasmIntegrationPlugin)
Q_IMPORT_PLUGIN(QGifPlugin)
Q_IMPORT_PLUGIN(QICOPlugin)
Q_IMPORT_PLUGIN(QJpegPlugin)
Q_IMPORT_PLUGIN(QSvgPlugin)
Q_IMPORT_PLUGIN(QSvgIconPlugin)

// 2. Des fonctions de fils et d'IndexedDB que Qt référence et que Pyodide (un seul fil, sans ASYNCIFY) ne
// fournit pas : sans elles, emscripten génère des bouchons qui se rappellent eux-mêmes à l'infini.
#include <cerrno>
#include <pthread.h>
#include <sched.h>
#include <semaphore.h>
extern "C" {
int pthread_setschedparam(pthread_t, int, const struct sched_param *) { return ENOSYS; }
int sched_get_priority_max(int) { return 0; }
int sched_get_priority_min(int) { return 0; }
int sem_timedwait(sem_t *, const struct timespec *) { return -1; }
void emscripten_idb_load(const char *, const char *, void **, int *, int *perror) { if (perror) *perror = 1; }
void emscripten_idb_store(const char *, const char *, void *, int, int *perror) { if (perror) *perror = 1; }
void emscripten_idb_delete(const char *, const char *, int *perror) { if (perror) *perror = 1; }
int emscripten_idb_exists(const char *, const char *, int *pexists, int *perror) {
  if (pexists) *pexists = 0;
  if (perror) *perror = 0;
  return 0;
}
}
