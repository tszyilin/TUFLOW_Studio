import os
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QButtonGroup, QRadioButton,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .bc_parser import parse_bc_database, load_bc_csv

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
    _MPL_AVAILABLE = True
except ImportError:
    _MPL_AVAILABLE = False


class TabInputs(QWidget):
    busy_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bc_dbase_dir = ''
        self._bc_data = {'hydrograph': [], 'rainfall': []}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # bc_dbase folder row
        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel('bc_dbase folder:'))
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText('bc_dbase\\  (auto-filled from Root tab)')
        dir_row.addWidget(self._dir_edit)
        btn_browse = QPushButton('Browse…')
        btn_browse.clicked.connect(self._browse)
        dir_row.addWidget(btn_browse)
        btn_refresh = QPushButton('Refresh')
        btn_refresh.clicked.connect(self._refresh)
        dir_row.addWidget(btn_refresh)
        layout.addLayout(dir_row)

        # Type filter row
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel('Type:'))
        self._type_group = QButtonGroup(self)
        for i, label in enumerate(['Hydrograph', 'Rainfall']):
            rb = QRadioButton(label)
            self._type_group.addButton(rb, i)
            type_row.addWidget(rb)
        self._type_group.button(0).setChecked(True)
        self._type_group.buttonClicked.connect(lambda _: self._populate_list())
        type_row.addStretch()
        layout.addLayout(type_row)

        # Splitter: checklist (left) + chart (right)
        splitter = QSplitter(Qt.Horizontal)

        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_item_changed)
        splitter.addWidget(self._list)

        if _MPL_AVAILABLE:
            self._figure = Figure(tight_layout=True)
            self._canvas = FigureCanvasQTAgg(self._figure)
            splitter.addWidget(self._canvas)
        else:
            no_mpl = QLabel(
                'matplotlib is not available in this QGIS environment.\n'
                'Install it to enable the chart.'
            )
            no_mpl.setAlignment(Qt.AlignCenter)
            splitter.addWidget(no_mpl)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)
        layout.addWidget(splitter)

        # Status bar
        self._status = QLabel('')
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Public API called by dock_widget
    # ------------------------------------------------------------------
    def set_bc_dbase_dir(self, path):
        if path and os.path.isdir(path):
            self._dir_edit.setText(path)
            self._bc_dbase_dir = path
            self._refresh()

    # ------------------------------------------------------------------
    # Internal actions
    # ------------------------------------------------------------------
    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, 'Select bc_dbase folder')
        if path:
            self._dir_edit.setText(path)
            self._bc_dbase_dir = path
            self._refresh()

    def _refresh(self):
        path = self._dir_edit.text().strip()
        if not path or not os.path.isdir(path):
            self._status.setText('No valid bc_dbase folder set.')
            return
        self._bc_dbase_dir = path
        try:
            self._bc_data = parse_bc_database(path)
        except Exception as e:
            self._status.setText(f'Error reading BC database: {e}')
            return
        self._populate_list()

    def _populate_list(self):
        bc_type = 'hydrograph' if self._type_group.checkedId() == 0 else 'rainfall'
        entries = self._bc_data.get(bc_type, [])

        self._list.blockSignals(True)
        self._list.clear()
        for entry in entries:
            item = QListWidgetItem(entry['label'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, entry)
            self._list.addItem(item)
        self._list.blockSignals(False)

        n = len(entries)
        self._status.setText(
            f'{n} {bc_type} entr{"y" if n == 1 else "ies"} found. '
            'Check entries to plot them.'
        )
        if _MPL_AVAILABLE:
            self._redraw_chart()

    def _on_item_changed(self, _item):
        if _MPL_AVAILABLE:
            self._redraw_chart()

    def _redraw_chart(self):
        bc_type = 'hydrograph' if self._type_group.checkedId() == 0 else 'rainfall'
        ylabel = 'Flow (m³/s)' if bc_type == 'hydrograph' else 'Rainfall (mm/h)'

        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.set_xlabel('Time (h)')
        ax.set_ylabel(ylabel)
        ax.grid(True, linestyle='--', alpha=0.5)

        warnings = []
        plotted = 0
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            entry = item.data(Qt.UserRole)
            try:
                times, values = load_bc_csv(
                    self._bc_dbase_dir,
                    entry['source'],
                    entry['time_col'],
                    entry['value_col'],
                )
                ax.plot(times, values, label=entry['label'])
                plotted += 1
            except Exception as e:
                warnings.append(f"{entry['label']}: {e}")

        if plotted:
            ax.legend()

        self._canvas.draw()

        if warnings:
            self._status.setText('Warning: ' + ' | '.join(warnings))
        else:
            n_total = self._list.count()
            self._status.setText(
                f'{plotted} series plotted.' if plotted
                else f'{n_total} entries available. Check entries to plot.'
            )
