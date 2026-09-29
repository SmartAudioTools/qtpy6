"""The binding's QtPdfWidgets, whose QPdfView selects text on the desktop (drag, Ctrl+C: Qt's own has no selection);
in the browser, where Qt-WASM has no QtPdf, qtpy6.web.pdf's QPdfView, drawn by pdf.js, whose text selects and copies
as in the browser's PDF viewer."""
import sys

from . import _binding

if sys.platform == 'emscripten':
    from .web.pdf import QPdfView  # noqa: F401
else:
    _binding.load(globals(), 'QtPdfWidgets')
    from .QtCore import QPoint, QPointF, QRect, QSize, QSizeF, Qt
    from .QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QPolygonF

    _QPdfView = QPdfView  # noqa: F821

    class QPdfView(_QPdfView):
        """QPdfView, plus a selection within one page: drag with the left button, Ctrl+C copies it."""

        def __init__(self, parent=None):
            super().__init__(parent)  # PyQt6 wants the parent, even None
            self._anchor = None  # (page, point in the page's points) where the drag started
            self._selection = None  # (page, QPdfSelection)
            self._lines = {}  # {page: [QRectF of each text line]}, read once per page
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

        def _pages(self):
            """{page: QRect in the viewport}: QPdfViewPrivate::calculateDocumentLayout (Qt 6.10), moved by the scroll bars."""
            document = self.document()
            if document is None or document.status() != document.Status.Ready:
                return {}
            resolution = QGuiApplication.primaryScreen().logicalDotsPerInch() / 72.0
            margins, spacing, viewport = self.documentMargins(), self.pageSpacing(), self.viewport().size()
            if self.pageMode() == self.PageMode.SinglePage:
                pages = [self.pageNavigator().currentPage()]
            else:
                pages = range(document.pageCount())
            sizes = {}
            for page in pages:
                points = document.pagePointSize(page)
                if self.zoomMode() == self.ZoomMode.Custom:
                    size = QSizeF(points * resolution * self.zoomFactor()).toSize()
                else:
                    size = QSizeF(points * resolution).toSize()
                    if self.zoomMode() == self.ZoomMode.FitToWidth:
                        size *= (viewport.width() - margins.left() - margins.right()) / size.width()
                    else:
                        size = size.scaled(viewport + QSize(-margins.left() - margins.right(), -spacing),
                                           Qt.AspectRatioMode.KeepAspectRatio)
                sizes[page] = size
            width = max((s.width() for s in sizes.values()), default=0) + margins.left() + margins.right()
            scroll = QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            geometries, y = {}, margins.top()
            for page, size in sizes.items():
                geometries[page] = QRect(QPoint((max(width, viewport.width()) - size.width()) // 2, y) - scroll, size)
                y += size.height() + spacing
            return geometries

        def _point(self, position, page=None):
            """(page, point in that page's points) under ``position`` (viewport); with ``page``, clamped to it."""
            for number, rectangle in self._pages().items():
                if page in (None, number) and (page is not None or rectangle.contains(position)):
                    scale = self.document().pagePointSize(number).width() / rectangle.width()
                    x = min(max(position.x(), rectangle.left()), rectangle.right() + 1) - rectangle.left()
                    y = min(max(position.y(), rectangle.top()), rectangle.bottom() + 1) - rectangle.top()
                    return number, self._snap(number, QPointF(x * scale, y * scale))
            return None, None

        def _snap(self, page, point):
            """``point`` moved onto the nearest text line: QPdfDocument.getSelection only selects between two points
            that lie on characters (the margin, the space between lines give no selection)."""
            if page not in self._lines:
                self._lines[page] = self._text_lines(page)

            def distance(line):
                return (max(line.top() - point.y(), 0, point.y() - line.bottom()),
                        max(line.left() - point.x(), 0, point.x() - line.right()))

            line = min(self._lines[page], key=distance, default=None)
            if line is None:
                return point
            return QPointF(min(max(point.x(), line.left() + 0.5), line.right() - 0.5), line.center().y())

        def _text_lines(self, page):
            """The page's text lines: getAllText's rectangles (one per run of text, down to one per glyph for some
            writers) joined while each next one lies on the same line, to the right of the previous."""
            lines = []
            for rectangle in (polygon.boundingRect() for polygon in self.document().getAllText(page).bounds()):
                last = lines[-1] if lines else None
                if (last is not None and rectangle.left() >= last.left()
                        and min(last.bottom(), rectangle.bottom()) - max(last.top(), rectangle.top())
                        > min(last.height(), rectangle.height()) / 2):
                    lines[-1] = last.united(rectangle)
                else:
                    lines.append(rectangle)
            return lines

        def mousePressEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                page, point = self._point(event.position().toPoint())
                self._anchor = (page, point) if page is not None else None
                self._selection = None
                self.viewport().update()
            super().mousePressEvent(event)

        def mouseMoveEvent(self, event):
            if self._anchor is not None:
                page, start = self._anchor
                _, end = self._point(event.position().toPoint(), page)
                selection = self.document().getSelection(page, start, end)
                self._selection = (page, selection) if selection.isValid() else None
                self.viewport().update()
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self._anchor = None
            super().mouseReleaseEvent(event)

        def keyPressEvent(self, event):
            if event.matches(QKeySequence.StandardKey.Copy) and self._selection is not None:
                QGuiApplication.clipboard().setText(self._selection[1].text())
                event.accept()
            else:
                super().keyPressEvent(event)

        def paintEvent(self, event):
            super().paintEvent(event)
            rectangle = self._selection and self._pages().get(self._selection[0])
            if rectangle:
                page, selection = self._selection
                scale = rectangle.width() / self.document().pagePointSize(page).width()
                painter = QPainter(self.viewport())
                painter.setPen(Qt.PenStyle.NoPen)
                highlight = QColor(self.palette().highlight().color())
                highlight.setAlpha(90)
                painter.setBrush(highlight)
                for polygon in selection.bounds():
                    painter.drawPolygon(QPolygonF([QPointF(rectangle.left() + p.x() * scale, rectangle.top() + p.y() * scale)
                                                   for p in polygon]))
                painter.end()

        def setDocument(self, document):
            self._anchor = self._selection = None
            self._lines = {}
            if document is not None and document.parent() is self:
                # Qt 6.11 crashes destroying a view whose document is its child (both bindings): the child dies
                # first and ~QPdfView still reaches it. Held by Python instead, it outlives the view.
                document.setParent(None)
            self._document = document
            super().setDocument(document)

_binding.finish(globals())
