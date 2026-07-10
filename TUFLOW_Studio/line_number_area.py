from qgis.PyQt.QtWidgets import QWidget, QPlainTextEdit, QTextEdit
from qgis.PyQt.QtCore import QRect, QSize, Qt, QEvent
from qgis.PyQt.QtGui import QPainter, QColor, QTextFormat, QTextCursor

_GUTTER_BG    = QColor('#F0F0F0')
_GUTTER_FG    = QColor('#999999')
_CURRENT_LINE = QColor('#E8F4FD')


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._gutter = _LineNumberArea(self)
        self._check_selections = []

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._refresh_selections)

        self.viewport().installEventFilter(self)

        self._update_gutter_width(0)
        self._refresh_selections()

    # ------------------------------------------------------------------
    # Public: called by TabEditor to merge check highlights
    # ------------------------------------------------------------------
    def set_check_highlights(self, selections):
        self._check_selections = selections
        self._refresh_selections()

    def clear_check_highlights(self):
        self._check_selections = []
        self._refresh_selections()

    # ------------------------------------------------------------------
    # Gutter width
    # ------------------------------------------------------------------
    def line_number_area_width(self):
        digits = max(1, len(str(self.blockCount())))
        try:
            char_w = self.fontMetrics().horizontalAdvance('9')
        except AttributeError:
            char_w = self.fontMetrics().width('9')
        return 6 + char_w * digits + 6

    def _update_gutter_width(self, _=None):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._gutter.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event):
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), _GUTTER_BG)
        painter.setPen(_GUTTER_FG)
        painter.setFont(self.font())

        block = self.firstVisibleBlock()
        block_num = block.blockNumber()
        top = round(self.blockBoundingGeometry(block)
                        .translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        line_h = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0, top, self._gutter.width() - 4, line_h,
                    Qt.AlignRight, str(block_num + 1))
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_num += 1

    # ------------------------------------------------------------------
    # Ctrl+Scroll zoom (via viewport event filter)
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                delta = event.angleDelta().y()
                font = self.font()
                new_size = max(6, min(32, font.pointSize() + (1 if delta > 0 else -1)))
                family = font.family()
                self.setStyleSheet(f'QPlainTextEdit {{ font-family: "{family}"; font-size: {new_size}pt; }}')
                self._update_gutter_width()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Current-line highlight merged with check highlights
    # ------------------------------------------------------------------
    def _refresh_selections(self):
        all_sels = list(self._check_selections)

        # Current-line highlight goes at front (lowest priority, overridden by checks)
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(_CURRENT_LINE)
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        cursor = self.textCursor()
        cursor.clearSelection()
        sel.cursor = cursor
        all_sels.insert(0, sel)

        self.setExtraSelections(all_sels)
