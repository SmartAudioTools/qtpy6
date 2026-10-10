// Lié dans chaque pyside_Qt<M>.so (construire.sh, phase dynamique). QtCore instancie explicitement les interfaces de
// métatype de ses types de base (extern template dans qmetatype.h) ; Qt et PySide, compilés en visibilité cachée, les
// adressent par relocation directe, que wasm-ld ne sait pas résoudre vers un autre module (« R_WASM_MEMORY_ADDR_REL_SLEB
// is not supported against an undefined symbol »). Ces interfaces sont des constantes (leur typeId est fixé à la
// compilation pour un type de base) : chaque module en porte sa copie, comme chaque unité de compilation le fait là où
// Qt n'emploie pas d'extern template, et QMetaType les compare par identifiant. La liste est celle que les quinze modules
// à la demande réclament (relevé du 10/10/2026, wasm-ld --error-limit=0) : un module futur qui en manque le dit au lien.
#include <cstddef>

#include <QtCore/QByteArray>
#include <QtCore/QDateTime>
#include <QtCore/QEasingCurve>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonValue>
#include <QtCore/QLine>
#include <QtCore/QLocale>
#include <QtCore/QMap>
#include <QtCore/QModelIndex>
#include <QtCore/QPoint>
#include <QtCore/QRect>
#include <QtCore/QUrl>
#include <QtCore/QVariant>
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
template struct QMetaTypeInterfaceWrapper<char>;
template struct QMetaTypeInterfaceWrapper<double>;
template struct QMetaTypeInterfaceWrapper<float>;
template struct QMetaTypeInterfaceWrapper<short>;
template struct QMetaTypeInterfaceWrapper<signed char>;
template struct QMetaTypeInterfaceWrapper<unsigned char>;
template struct QMetaTypeInterfaceWrapper<unsigned int>;
template struct QMetaTypeInterfaceWrapper<unsigned long long>;
template struct QMetaTypeInterfaceWrapper<unsigned short>;
template struct QMetaTypeInterfaceWrapper<void*>;
template struct QMetaTypeInterfaceWrapper<QObject*>;
template struct QMetaTypeInterfaceWrapper<std::nullptr_t>;
template struct QMetaTypeInterfaceWrapper<QChar>;
template struct QMetaTypeInterfaceWrapper<QDate>;
template struct QMetaTypeInterfaceWrapper<QTime>;
template struct QMetaTypeInterfaceWrapper<QDateTime>;
template struct QMetaTypeInterfaceWrapper<QEasingCurve>;
template struct QMetaTypeInterfaceWrapper<QHash<QString, QVariant>>;
template struct QMetaTypeInterfaceWrapper<QMap<QString, QVariant>>;
template struct QMetaTypeInterfaceWrapper<QList<QVariant>>;
template struct QMetaTypeInterfaceWrapper<QList<QByteArray>>;
template struct QMetaTypeInterfaceWrapper<QJsonArray>;
template struct QMetaTypeInterfaceWrapper<QJsonObject>;
template struct QMetaTypeInterfaceWrapper<QJsonValue>;
template struct QMetaTypeInterfaceWrapper<QLineF>;
template struct QMetaTypeInterfaceWrapper<QLocale>;
template struct QMetaTypeInterfaceWrapper<QModelIndex>;
template struct QMetaTypeInterfaceWrapper<QPersistentModelIndex>;
template struct QMetaTypeInterfaceWrapper<QPointF>;
template struct QMetaTypeInterfaceWrapper<QPoint>;
template struct QMetaTypeInterfaceWrapper<QRectF>;
template struct QMetaTypeInterfaceWrapper<QRect>;
template struct QMetaTypeInterfaceWrapper<QSizeF>;
template struct QMetaTypeInterfaceWrapper<QUrl>;
template struct QMetaTypeInterfaceWrapper<QVariant>;
}  // namespace QtPrivate
