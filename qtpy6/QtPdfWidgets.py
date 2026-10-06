"""The binding's QtPdfWidgets, whose QPdfView selects text on the desktop (drag, Ctrl+C: Qt's own has no selection)
and follows the document's internal links (a table of contents: Qt's own does not), and setMasks pixelates
zones of the pages (an answer the reader must not see yet), setCopyZones limits selection and copy to zones (the
code of a document) and setCopyFilter rewrites what is copied;
in the browser, where Qt-WASM has no QtPdf, qtpy6.web.pdf's QPdfView, drawn by pdf.js, whose text selects and copies
as in the browser's PDF viewer."""
import sys

from . import _binding

if sys.platform == 'emscripten':
    from .web.pdf import QPdfView  # noqa: F401
else:
    _binding.load(globals(), 'QtPdfWidgets')
    from .QtCore import QModelIndex, QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt
    from .QtGui import QColor, QGuiApplication, QImage, QKeySequence, QPainter, QPolygonF
    from .QtPdf import QPdfLinkModel

    _QPdfView = QPdfView  # noqa: F821

    class QPdfView(_QPdfView):
        """QPdfView, plus a selection within one page (drag with the left button, Ctrl+C copies it), internal links
        followed on click, ``setPageLimit``: only the first pages are shown, ``setMasks``: zones pixelated,
        ``setCopyZones``: only text inside these zones selects, ``setCopyFilter``: what Ctrl+C copies is rewritten."""

        LINK_MARGIN = 12  # points left above a link's destination (same in the browser: pdf_vue.js)
        MASK_BLOCK = 12  # side of a mask's blocks, in the page's points: unreadable at any zoom (same in pdf_vue.js)
        COPY_MARGIN = 3  # points a selected line's box may go past its copy zone (same in pdf_vue.js)

        def __init__(self, parent=None):
            super().__init__(parent)  # PyQt6 wants the parent, even None
            self._anchor = None  # (page, point in the page's points) where the drag started
            self._selection = None  # (page, QPdfSelection)
            self._lines = {}  # {page: [QRectF of each text line]}, read once per page
            self._limit = None  # setPageLimit
            self._links = QPdfLinkModel(self)  # those of one page at a time (setPage), read once per page
            self._areas = {}  # {page: _link_areas(page)}
            self._masks = {}  # setMasks: {page: [QRectF in the page's points]}
            self._blocks = {}  # {(page, index of the mask): QImage, one pixel per block}, read once
            self._copy_zones = self._copy_filter = None  # setCopyZones, setCopyFilter
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

        def setMasks(self, masks):
            """Pixelates zones of the pages: ``masks`` is {page: [QRectF in the page's points, from its top left]}
            (empty: none). Each zone is shown in blocks of ``MASK_BLOCK`` points, the mean colour of what they cover,
            and its text is neither selected nor copied. A display, not a protection: the document itself is
            unchanged. Not Qt's: a qtpy6 addition, also in the browser's QPdfView."""
            self._masks = {page: [QRectF(r) for r in rectangles] for page, rectangles in (masks or {}).items() if rectangles}
            self._blocks = {}
            self._selection = None
            self.viewport().update()

        def masks(self):
            return {page: list(rectangles) for page, rectangles in self._masks.items()}

        def setCopyZones(self, zones):
            """Only the text inside zones of the pages selects and copies: ``zones`` is {page: [QRectF in the page's
            points, from its top left]}, {} for none, None (the default) for all of it. A selection that leaves the
            zones is dropped, not cut. Not Qt's: a qtpy6 addition, also in the browser's QPdfView."""
            self._copy_zones = None if zones is None else {page: [QRectF(r) for r in rectangles]
                                                           for page, rectangles in zones.items() if rectangles}
            self._selection = None
            self.viewport().update()

        def copyZones(self):
            return None if self._copy_zones is None else {page: list(r) for page, r in self._copy_zones.items()}

        def setCopyFilter(self, function):
            """``function(text) -> text`` rewrites what Ctrl+C copies (None: as is). Not Qt's: a qtpy6 addition, also
            in the browser's QPdfView."""
            self._copy_filter = function

        def copyText(self):
            """The selected text as Ctrl+C copies it ("" without a selection)."""
            text = self._selection[1].text() if self._selection is not None else ""
            return self._copy_filter(text) if text and self._copy_filter is not None else text

        def _masked(self, page, selection):
            """Whether ``selection`` (a QPdfSelection of ``page``) touches a mask, or leaves the copy zones (one line's
            box at a time, ``COPY_MARGIN`` points of leeway: the text's box is not the font's). Its two corners, not the
            box: an underscore's has no height, and QRectF.contains refuses an empty rectangle."""
            boxes = [polygon.boundingRect() for polygon in selection.bounds()]
            m = self.COPY_MARGIN
            return (any(box.intersects(mask) for box in boxes for mask in self._masks.get(page, ()))
                    or self._copy_zones is not None and not all(
                        any(zone.adjusted(-m, -m, m, m).contains(box.topLeft()) and zone.adjusted(-m, -m, m, m).contains(
                            box.bottomRight()) for zone in self._copy_zones.get(page, ())) for box in boxes))

        def _block_image(self, page, index):
            """The mask's QImage, one pixel per block: the page rendered at four pixels per block, then each block
            averaged (a smooth reduction), so that no stroke of the text survives."""
            key = (page, index)
            if key not in self._blocks:
                mask, size = self._masks[page][index], self.document().pagePointSize(page)
                scale = 4 / self.MASK_BLOCK
                rendered = self.document().render(page, QSizeF(size * scale).toSize())
                image = QImage(rendered.size(), QImage.Format.Format_RGB32)  # opaque: PDFium leaves the paper transparent
                image.fill(Qt.GlobalColor.white)
                painter = QPainter(image)
                painter.drawImage(0, 0, rendered)
                painter.end()
                columns = max(1, -(-round(mask.width()) // self.MASK_BLOCK))  # whole blocks, from the mask's top left
                rows = max(1, -(-round(mask.height()) // self.MASK_BLOCK))
                region = QRect(round(mask.left() * scale), round(mask.top() * scale), columns * 4, rows * 4)
                self._blocks[key] = image.copy(region).scaled(columns, rows, Qt.AspectRatioMode.IgnoreAspectRatio,
                                                               Qt.TransformationMode.SmoothTransformation)
            return self._blocks[key]

        def _pixelate(self):
            """Paints each mask over its page, in blocks (``setMasks``)."""
            if not self._masks:
                return
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            for page, rectangle in self._pages().items():
                masks = self._masks.get(page)
                if not masks or not rectangle.intersects(self.viewport().rect()):
                    continue
                scale = rectangle.width() / self.document().pagePointSize(page).width()
                for index, mask in enumerate(masks):
                    target = QRectF(rectangle.left() + mask.left() * scale, rectangle.top() + mask.top() * scale,
                                    mask.width() * scale, mask.height() * scale)
                    painter.save()
                    painter.setClipRect(target)
                    blocks = self._block_image(page, index)  # whole blocks: the last ones overflow the mask, clipped
                    painter.drawImage(QRectF(target.left(), target.top(), blocks.width() * self.MASK_BLOCK * scale,
                                             blocks.height() * self.MASK_BLOCK * scale), blocks)
                    painter.restore()
            painter.end()

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
            if page not in self._areas:
                self._areas[page] = self._link_areas(page)
            if self._links.page() != page:
                self._links.setPage(page)
            # the link of the area under the point, read at the centre of its own rectangle
            link = next((self._links.linkAt(own.center()) for area, own, _ in self._areas[page] if area.contains(point)), None)
            if link is None or not link.isValid() or not link.url().isEmpty() or (
                    self._limit is not None and link.page() >= self._limit):
                return None
            return link

        def _link_areas(self, page):
            """[(clickable QRectF, the link's own QRectF, its target page)] in the page's points: a link alone on its
            line takes the whole line, as wide as the page minus its left margin on both sides, and not only its text
            (a table of contents: the end of a short title was not clickable). Same rule in the browser (``pdf_vue.js``)."""
            self._links.setPage(page)
            rectangle, target = QPdfLinkModel.Role.Rectangle.value, QPdfLinkModel.Role.Page.value
            links = [(self._links.data(index, rectangle), self._links.data(index, target))
                     for index in (self._links.index(row, 0) for row in range(self._links.rowCount(QModelIndex())))]
            width = self.document().pagePointSize(page).width()
            return [(r if any(o is not r and o.top() < r.bottom() and r.top() < o.bottom() for o, _ in links) else
                     QRectF(r.left(), r.top(), max(r.width(), width - 2 * r.left()), r.height()), r, t) for r, t in links]

        def _follow(self, link):
            """Scrolls to the link's destination: the top of the viewport ``LINK_MARGIN`` points above its location in
            the target page (on the location itself, a title's top was cut off)."""
            target = self._pages().get(link.page())
            if target is not None:
                scale = target.width() / self.document().pagePointSize(link.page()).width()
                bar = self.verticalScrollBar()
                bar.setValue(bar.value() + target.top() + round(max(0, link.location().y() - self.LINK_MARGIN) * scale))

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
                self._selection = (page, selection) if selection.isValid() and not self._masked(page, selection) else None
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
                QGuiApplication.clipboard().setText(self.copyText())
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
            self._pixelate()
            self._veil()
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

        def _veil(self):
            """A translucent white veil over the links to a page not shown (setPageLimit): a table of contents shows
            which entries are out of reach. Same in the browser (``pdf_vue.js``)."""
            if self._limit is None:
                return
            painter = QPainter(self.viewport())
            for page, rectangle in self._pages().items():
                if page >= self._limit:
                    break
                if page not in self._areas:
                    self._areas[page] = self._link_areas(page)
                scale = rectangle.width() / self.document().pagePointSize(page).width()
                for area, _, target in self._areas[page]:
                    if target >= self._limit:
                        painter.fillRect(QRectF(rectangle.left() + area.left() * scale, rectangle.top() + area.top() * scale,
                                                area.width() * scale, area.height() * scale), QColor(255, 255, 255, 160))
            painter.end()

        def setDocument(self, document):
            self._anchor = self._selection = None
            self._lines, self._areas, self._blocks = {}, {}, {}
            self._links.setDocument(document)
            if document is not None and document.parent() is self:
                # Qt 6.11 crashes destroying a view whose document is its child (both bindings): the child dies
                # first and ~QPdfView still reaches it. Held by Python instead, it outlives the view.
                document.setParent(None)
            self._document = document
            super().setDocument(document)

_binding.finish(globals())
