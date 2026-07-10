from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QSpinBox, QComboBox, QPushButton, QLabel,
)
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtCore import pyqtSignal, Qt

_DEFAULT_FAMILY = 'Consolas'
_DEFAULT_SIZE   = 11

_FONTS = [
    ('Consolas (default)', 'Consolas'),
    ('Arial',              'Arial'),
    ('JetBrains Mono',     'JetBrains Mono'),
    ('Inter',              'Inter'),
]


class TabSettings(QWidget):
    font_changed = pyqtSignal(str, int)   # (family, size)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        group = QGroupBox('Editor Font')
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignLeft)

        self._font_combo = QComboBox()
        for label, _ in _FONTS:
            self._font_combo.addItem(label)
        form.addRow('Font family:', self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 32)
        self._size_spin.setValue(_DEFAULT_SIZE)
        self._size_spin.setSuffix(' pt')
        form.addRow('Font size:', self._size_spin)

        layout.addWidget(group)

        btn = QPushButton('Apply')
        btn.setFixedWidth(100)
        btn.setStyleSheet(
            'QPushButton { background-color: #1565C0; color: white; font-weight: bold; '
            'border-radius: 4px; padding: 4px 12px; }'
            'QPushButton:hover { background-color: #1976D2; }'
            'QPushButton:pressed { background-color: #0D47A1; }'
        )
        btn.clicked.connect(self._apply)
        layout.addWidget(btn)

        self._preview = QLabel('Preview: The quick brown fox jumps over the lazy dog')
        self._preview.setWordWrap(True)
        layout.addWidget(self._preview)
        self._update_preview()

        self._font_combo.currentIndexChanged.connect(lambda _: self._update_preview())
        self._size_spin.valueChanged.connect(lambda _: self._update_preview())

        layout.addStretch()

    def _current_family(self):
        return _FONTS[self._font_combo.currentIndex()][1]

    def _update_preview(self):
        family = self._current_family()
        size   = self._size_spin.value()
        self._preview.setStyleSheet(
            f'font-family: "{family}"; font-size: {size}pt;'
        )

    def _apply(self):
        self.font_changed.emit(self._current_family(), self._size_spin.value())
