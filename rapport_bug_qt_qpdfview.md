Component: Qt PDF (QtPdfWidgets) — Affects version: 6.11.0, 6.11.1 — Platform: Linux x86_64 (CachyOS), offscreen and xcb

**Title:** Crash in ~QPdfView when its QPdfDocument is a child of the view

**Description**

When the QPdfDocument shown by a QPdfView has that view as its parent, destroying the view crashes
(SIGSEGV), typically at application exit. `~QWidget` deletes the children; `~QPdfDocument` calls `close()`,
which emits `statusChanged`; the view's connection to that signal is still alive and its slot runs on a
half-destroyed QPdfView. It only happens once a document is loaded (an empty QPdfDocument does not crash).

Backtrace (PySide6 6.11.1, gdb):

```
#0-#2  libQt6PdfWidgets.so.6   (QPdfView slot, no symbols)
#3     libQt6Core.so.6         (signal activation)
#4     QPdfDocument::statusChanged(QPdfDocument::Status)
#5     QPdfDocument::close()
#6     QPdfDocumentPrivate::~QPdfDocumentPrivate()
#7     QPdfDocument::~QPdfDocument()
#9     QObjectPrivate::deleteChildren()
#10    QWidget::~QWidget()
```

Expected: no crash; ~QPdfView should disconnect from its document (the document outliving the view or
dying with it are both ordinary ownership choices).

**Reproducer (C++, same sequence as the Python one below)**

```cpp
#include <QApplication>
#include <QPdfDocument>
#include <QPdfView>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    auto *view = new QPdfView;
    auto *document = new QPdfDocument(view);   // the document is a child of the view
    document->load(QStringLiteral("any.pdf")); // any valid PDF
    view->setDocument(document);
    view->show();
    delete view;                               // crashes here
    return 0;
}
```

**Reproducer (Python, tested: crashes with PySide6 6.11.1 and PyQt6 6.11.0, exit code 139)**

```python
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView

app = QApplication([])
view = QPdfView()
document = QPdfDocument(view)
document.load(sys.argv[1])  # any valid PDF
view.setDocument(document)
view.show()
app.processEvents()
# crashes when the view is destroyed at exit
```

Workaround: give the document another parent (or none, keeping a reference) so that it outlives the view.
