// Lié dans chaque pyside_Qt<M>.so (construire.sh, phase dynamique). QtCore instancie explicitement les interfaces de
// métatype de ses types de base (extern template dans qmetatype.h) ; Qt et PySide, compilés en visibilité cachée, les
// adressent par relocation directe, que wasm-ld ne sait pas résoudre vers un autre module (« R_WASM_MEMORY_ADDR_REL_SLEB
// is not supported against an undefined symbol »). Ces interfaces sont des constantes (leur typeId est fixé à la
// compilation pour un type de base) : chaque module en porte sa copie, comme chaque unité de compilation le fait là où
// Qt n'emploie pas d'extern template, et QMetaType les compare par identifiant. La liste est celle que les huit modules
// de qtbase réclament (relevé du 10/10/2026, wasm-ld --error-limit=0) : un module futur qui en manque le dit au lien.
#include <QtCore/QByteArray>
#include <QtCore/QList>
#include <QtCore/QMetaType>
#include <QtCore/QRegularExpression>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtCore/QStringList>

namespace QtPrivate {
template struct QMetaTypeInterfaceWrapper<bool>;
template struct QMetaTypeInterfaceWrapper<int>;
template struct QMetaTypeInterfaceWrapper<long long>;
template struct QMetaTypeInterfaceWrapper<QByteArray>;
template struct QMetaTypeInterfaceWrapper<QString>;
template struct QMetaTypeInterfaceWrapper<QStringList>;
template struct QMetaTypeInterfaceWrapper<QRegularExpression>;
template struct QMetaTypeInterfaceWrapper<QSize>;
}  // namespace QtPrivate
