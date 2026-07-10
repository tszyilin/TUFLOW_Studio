import os
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QGroupBox, QFormLayout, QProgressBar,
    QApplication,
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QThread
from qgis.PyQt.QtGui import QColor, QPalette, QFont
from qgis.core import QgsProject

SUBFOLDERS = ["bc_dbase", "check", "model", "results", "runs"]
_KEY_PREFIX = "TUFLOWSetup"
_NOTICE = "The root reading will freeze a bit, please don't panic"


def _set_bg(widget, bg_hex, fg_hex=None):
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.Window, QColor(bg_hex))
    pal.setColor(QPalette.Base,   QColor(bg_hex))
    pal.setColor(QPalette.Button, QColor(bg_hex))
    if fg_hex:
        pal.setColor(QPalette.WindowText,   QColor(fg_hex))
        pal.setColor(QPalette.ButtonText,   QColor(fg_hex))
        pal.setColor(QPalette.Text,         QColor(fg_hex))
    widget.setPalette(pal)


class _ScanWorker(QThread):
    scan_done = pyqtSignal(str, dict)
    log_line  = pyqtSignal(str)

    def __init__(self, root, overrides):
        super().__init__()
        self._root = root
        self._overrides = overrides

    def run(self):
        self.log_line.emit(f'Root:  {self._root}')
        results = {}
        for name in SUBFOLDERS:
            if self._overrides.get(name):
                path = self._overrides[name]
                results[name] = (path, True)
                self.log_line.emit(f'  {name}: {path}  [override]')
            else:
                candidate = os.path.join(self._root, name)
                found = os.path.isdir(candidate)
                results[name] = (candidate, found)
                self.log_line.emit(f'  {name}: {"found" if found else "not found"}')
        self.scan_done.emit(self._root, results)


class TabRoot(QWidget):
    paths_changed = pyqtSignal(dict)
    busy_changed  = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths = {k: "" for k in ["root"] + SUBFOLDERS}
        self._worker = None
        self._build_ui()
        self._set_notice()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Root folder row
        root_group = QGroupBox("TUFLOW Project Root")
        root_layout = QHBoxLayout(root_group)
        self._root_edit = QLineEdit()
        self._root_edit.setPlaceholderText("Browse to TUFLOW project root folder...")
        self._root_edit.setReadOnly(True)
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_root)
        root_layout.addWidget(self._root_edit)
        root_layout.addWidget(btn_browse)
        layout.addWidget(root_group)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setMinimumHeight(24)
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setAutoFillBackground(True)
        bold = QFont()
        bold.setBold(True)
        self._status_label.setFont(bold)
        layout.addWidget(self._status_label)

        # Subfolders
        sub_group = QGroupBox("Project Subfolders")
        form = QFormLayout(sub_group)
        self._sub_edits = {}
        for name in SUBFOLDERS:
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit()
            edit.setReadOnly(True)
            edit.setPlaceholderText("--")
            btn = QPushButton("Override...")
            btn.setFixedWidth(80)
            btn.clicked.connect(lambda checked, n=name: self._browse_subfolder(n))
            row.addWidget(edit)
            row.addWidget(btn)
            self._sub_edits[name] = edit
            lbl = QLabel(name)
            lbl.setFixedWidth(80)
            form.addRow(lbl, row_widget)
        layout.addWidget(sub_group)

        # Save button
        btn_save = QPushButton("Save to Project")
        _set_bg(btn_save, "#2E7D32", "white")
        bold_font = QFont()
        bold_font.setBold(True)
        btn_save.setFont(bold_font)
        btn_save.setMinimumHeight(32)
        btn_save.clicked.connect(self._save_to_project)
        layout.addWidget(btn_save)

        layout.addStretch()

    def _set_notice(self):
        self._set_status(_NOTICE, "#E3F2FD", "#0D47A1")

    def _set_status(self, text, bg, fg):
        self._status_label.setText(text)
        _set_bg(self._status_label, bg, fg)
        self._status_label.repaint()

    def _browse_root(self):
        self._set_status("Opening browser - network drives may take a moment...", "#FFF3E0", "#E65100")
        path = QFileDialog.getExistingDirectory(self, "Select TUFLOW Project Root")
        if path:
            self._start_scan(path)
        else:
            self._set_notice()

    def _browse_subfolder(self, name):
        path = QFileDialog.getExistingDirectory(self, "Select {} folder".format(name))
        if path:
            self._paths[name] = path
            self._refresh_sub_edit(name)
            self.paths_changed.emit(dict(self._paths))

    def _start_scan(self, root):
        self._root_edit.setText(root)
        self._paths["root"] = root
        self._progress.setVisible(True)
        self._set_status("Scanning subfolders — please be patient...", "#FFF3E0", "#E65100")
        self.busy_changed.emit(True)
        for name in SUBFOLDERS:
            self._sub_edits[name].setText("")
            self._sub_edits[name].setPalette(self._sub_edits[name].style().standardPalette())
        overrides = {k: v for k, v in self._paths.items() if k in SUBFOLDERS and v}
        self._worker = _ScanWorker(root, overrides)
        self._worker.scan_done.connect(self._on_scan_done)
        self._worker.start()

    def _on_scan_done(self, root, results):
        self._progress.setVisible(False)
        self._set_notice()
        self.busy_changed.emit(False)
        self._paths["root"] = root
        for name, (path, exists) in results.items():
            self._paths[name] = path
            self._refresh_sub_edit(name, exists)
        self.paths_changed.emit(dict(self._paths))

    def _refresh_sub_edit(self, name, exists=None):
        edit = self._sub_edits[name]
        path = self._paths[name]
        edit.setText(path)
        if exists is None:
            exists = bool(path) and os.path.isdir(path)
        palette = edit.palette()
        palette.setColor(QPalette.Base, QColor("#c8e6c9") if exists else QColor("#ffcdd2"))
        edit.setPalette(palette)

    def _save_to_project(self):
        proj = QgsProject.instance()
        for key, val in self._paths.items():
            proj.writeEntry(_KEY_PREFIX, key, val)
        proj.setDirty(True)
        self._set_status("The root setting is saved to project", "#E8F5E9", "#1B5E20")

    def load_from_project(self):
        proj = QgsProject.instance()
        root, _ = proj.readEntry(_KEY_PREFIX, "root", "")
        if root:
            self._root_edit.setText(root)
            self._paths["root"] = root
            for name in SUBFOLDERS:
                val, _ = proj.readEntry(_KEY_PREFIX, name, "")
                self._paths[name] = val
                self._refresh_sub_edit(name)
            self.paths_changed.emit(dict(self._paths))

    def get_paths(self):
        return dict(self._paths)
