"""The binding's QtPdfWidgets, whose QPdfView selects text on the desktop (drag, Ctrl+C: Qt's own has no selection)
and follows the document's internal links (a table of contents: Qt's own does not);
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
    from .QtPdf import QPdfLinkModel

    _QPdfView = QPdfView  # noqa: F821

    class QPdfView(_QPdfView):
        """QPdfView, plus a selection within one page (drag with the left button, Ctrl+C copies it), internal links
        followed on click, and ``setPageLimit``: only the first pages are shown."""

        def __init__(self, parent=None):
            super().__init__(parent)  # PyQt6 wants the parent, even None
            self._anchor = None  # (page, point in the page's points) where the drag started
            self._selection = None  # (page, QPdfSelection)
            self._lines = {}  # {page: [QRectF of each text line]}, read once per page
            self._limit = None  # setPageLimit
            self._links = QPdfLinkModel(self)  # those of one page at a time (setPage), read under the mouse
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            self.viewport().setMouseTracking(True)  # the pointing hand over a link
            self.verticalScrollBar().rangeChanged.connect(self._clamp)

        def setPageLimit(self, count):
            """Shows only the first ``count`` pages (None: all), in MultiPage mode: the scroll bar stops at the bottom
            of the last one, and what the viewport shows below it is painted over. Not Qt's: a qtpy6 addition, also
            in the browser's QPdfView."""
            self._limit = count
            self._clamp()
            self.viewport().update()

        def pageLimit(self):
            return self._limit

        def _last(self):
            """The viewport rectangle of the last page shown, None when every page is."""
            if self._limit is None or self.pageMode() != self.PageMode.MultiPage:
                return None
            return self._pages().get(self._limit - 1)

        def _clamp(self, *_):
            """Qt sets the scroll bar's range at each layout (document, size, zoom): brought back to the last page."""
            last, bar = self._last(), self.verticalScrollBar()
            if last is not None:
                bottom = last.bottom() + 1 + bar.value() + self.documentMargins().bottom()
                maximum = max(0, bottom - self.viewport().height())
                if bar.maximum() > maximum:
                    bar.setMaximum(maximum)

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

        def _point(self, position, page=None, snap=True):
            """(page, point in that page's points) under ``position`` (viewport); with ``page``, clamped to it; with
            ``snap``, moved onto the nearest text line."""
            for number, rectangle in self._pages().items():
                if self._limit is not None and number >= self._limit:
                    break
                if page in (None, number) and (page is not None or rectangle.contains(position)):
                    scale = self.document().pagePointSize(number).width() / rectangle.width()
                    x = min(max(position.x(), rectangle.left()), rectangle.right() + 1) - rectangle.left()
                    y = min(max(position.y(), rectangle.top()), rectangle.bottom() + 1) - rectangle.top()
                    point = QPointF(x * scale, y * scale)
                    return number, self._snap(number, point) if snap else point
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

        def _link(self, position):
            """The link under ``position`` (viewport) leading to a page shown, None elsewhere."""
            page, point = self._point(position, snap=False)
            if page is None:
                return None
            if self._links.page() != page:
                self._links.setPage(page)
            link = self._links.linkAt(point)
            if not link.isValid() or not link.url().isEmpty() or (self._limit is not None and link.page() >= self._limit):
                return None
            return link

        def _follow(self, link):
            """Scrolls to the link's destination: the top of the viewport on its location in the target page."""
            target = self._pages().get(link.page())
            if target is not None:
                scale = target.width() / self.document().pagePointSize(link.page()).width()
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() + target.top() + round(link.location().y() * scale))

        def mousePressEvent(self, event):
            link = self._link(event.position().toPoint()) if event.button() == Qt.MouseButton.LeftButton else None
            if link is not None:
                self._follow(link)
                event.accept()
                return
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
            else:
                link = self._link(event.position().toPoint())
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if link is not None else Qt.CursorShape.IBeamCursor)
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
            last = self._last()
            if last is not None and last.bottom() < self.viewport().height():  # the next pages, when the shown ones end above
                painter = QPainter(self.viewport())
                painter.fillRect(QRect(0, last.bottom() + 1, self.viewport().width(), self.viewport().height()),
                                 self.palette().dark())
                painter.end()
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
            self._links.setDocument(document)
            if document is not None and document.parent() is self:
                # Qt 6.11 crashes destroying a view whose document is its child (both bindings): the child dies
                # first and ~QPdfView still reaches it. Held by Python instead, it outlives the view.
                document.setParent(None)
            self._document = document
            super().setDocument(document)

_binding.finish(globals())
