// Faux Pyodide de telechargement_harnais.mjs : comme le vrai (installStdlib), un échec du téléchargement de la bibliothèque
// standard est écrit en console et le démarrage continue, pour finir en « Fatal Python error » sans jamais rendre la main ;
// reçue, sa taille est notée et le faux s'arrête (le reste de `preparer` n'est pas mesuré ici).
export async function loadPyodide({ indexURL }) {
  const octets = await fetch(indexURL + "python_stdlib.zip").then(r => r.arrayBuffer()).catch(() => null);
  if (!octets) return new Promise(() => {});
  globalThis.stdlib_recue = octets.byteLength;
  throw new Error("faux Pyodide : bibliothèque standard reçue");
}
