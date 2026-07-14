import os
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QTextEdit, QProgressBar, QMenu, QAction,
)
from qgis.PyQt.QtCore import Qt, QTimer, QThread, pyqtSignal, QFileSystemWatcher
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import QShortcut
from qgis.PyQt.QtGui import QColor, QTextCharFormat, QFontDatabase, QFont, QTextCursor
from .line_number_area import CodeEditor
from .tuflow_highlighter import TuflowHighlighter
from .tlf_parser import find_command_files
from .tcf_checker import check_file

_ERR_BG   = QColor('#FFCDD2')
_WARN_BG  = QColor('#FFF9C4')
_HDR_BG   = QColor('#D0D0D0')
_HDR_FG   = QColor('#444444')



class _CheckWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, filepath):
        super().__init__()
        self._path = filepath

    def run(self):
        self.finished.emit(check_file(self._path))


def _pick_font():
    db = QFontDatabase()
    for name in ('Consolas', 'Courier New'):
        if name in db.families():
            return QFont(name, 11)
    return QFont('Monospace', 11)


class TabEditor(QWidget):
    busy_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file = None
        self._loading = False
        self._dirty = False

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._auto_save)
        self._check_worker = None

        self._watcher = QFileSystemWatcher()
        self._watcher.fileChanged.connect(self._on_file_changed)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        h_splitter = QSplitter(Qt.Horizontal)

        # ── Left: file browser ────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel('Command & Batch Files'))
        lbl_row.addStretch()
        btn_scan = QPushButton('Scan')
        btn_scan.setFixedWidth(50)
        btn_scan.setToolTip('Rescan root folder for command files')
        btn_scan.clicked.connect(self._rescan)
        lbl_row.addWidget(btn_scan)
        ll.addLayout(lbl_row)
        self._file_list = QListWidget()
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        self._file_list.itemDoubleClicked.connect(self._rename_current_item)
        self._file_list.itemChanged.connect(self._on_item_renamed)
        self._file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        rename_shortcut = QShortcut(QKeySequence('F2'), self._file_list)
        rename_shortcut.activated.connect(self._rename_current_item)
        ll.addWidget(self._file_list)
        h_splitter.addWidget(left)

        # ── Centre: editor ────────────────────────────────────────────
        centre = QWidget()
        cl = QVBoxLayout(centre)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        self._file_label = QLabel('No file open')
        self._file_label.setStyleSheet('color: #606366; font-style: italic; font-weight: bold;')
        cl.addWidget(self._file_label)

        self._editor = CodeEditor()
        self._editor.setFont(_pick_font())
        self._editor.setStyleSheet('QPlainTextEdit { font-family: "Consolas", "Courier New"; font-size: 11pt; }')

        self._highlighter = TuflowHighlighter(self._editor.document())
        self._editor.textChanged.connect(self._on_text_changed)
        cl.addWidget(self._editor)

        # Ctrl+S shortcut scoped to this widget
        shortcut = QShortcut(QKeySequence('Ctrl+S'), self)
        shortcut.activated.connect(self._manual_save)

        btn_row = QHBoxLayout()

        self._btn_save = QPushButton('Save')
        self._btn_save.setStyleSheet(
            'QPushButton { background-color: #2E7D32; color: white; font-weight: bold; '
            'border-radius: 4px; padding: 4px 12px; }'
            'QPushButton:hover { background-color: #388E3C; }'
            'QPushButton:pressed { background-color: #1B5E20; }'
            'QPushButton:disabled { background-color: #A5D6A7; }'
        )
        self._btn_save.clicked.connect(self._manual_save)
        btn_row.addWidget(self._btn_save)

        self._btn_debug = QPushButton('Debug')
        self._btn_debug.setStyleSheet(
            'QPushButton { background-color: #1565C0; color: white; font-weight: bold; '
            'border-radius: 4px; padding: 4px 12px; }'
            'QPushButton:hover { background-color: #1976D2; }'
            'QPushButton:pressed { background-color: #0D47A1; }'
        )
        self._btn_debug.clicked.connect(self._run_check)
        btn_row.addWidget(self._btn_debug)

        btn_row.addStretch()
        cl.addLayout(btn_row)

        self._debug_progress = QProgressBar()
        self._debug_progress.setRange(0, 0)
        self._debug_progress.setFixedHeight(6)
        self._debug_progress.setTextVisible(False)
        self._debug_progress.setVisible(False)
        cl.addWidget(self._debug_progress)

        h_splitter.addWidget(centre)

        # ── Right: debug results ──────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel('Debug Results'))

        self._results_table = QTableWidget(0, 3)
        self._results_table.setHorizontalHeaderLabels(['Line #', 'Issue Type', 'Message'])
        self._results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self._results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._results_table.setAlternatingRowColors(True)
        self._results_table.cellClicked.connect(self._jump_to_line)
        rl.addWidget(self._results_table)

        h_splitter.addWidget(right)
        h_splitter.setSizes([180, 550, 250])

        layout.addWidget(h_splitter)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def apply_font(self, family, size):
        font = QFont(family, size)
        self._editor.setFont(font)
        self._editor.setStyleSheet(
            f'QPlainTextEdit {{ font-family: "{family}"; font-size: {size}pt; }}'
        )

    def set_root(self, root_path):
        self._root_path = root_path
        self._rescan()

    def _rescan(self):
        root_path = getattr(self, '_root_path', '')
        self._file_list.clear()
        if not root_path or not os.path.isdir(root_path):
            return

        all_files = find_command_files(root_path)
        by_ext = {}
        for path in all_files:
            ext = os.path.splitext(path)[1].lower()
            by_ext.setdefault(ext, []).append(path)

        for ext in sorted(by_ext):
            h = QListWidgetItem(f'  {ext}')
            h.setFlags(Qt.NoItemFlags)
            h.setBackground(_HDR_BG)
            h.setForeground(_HDR_FG)
            font = h.font()
            font.setBold(True)
            h.setFont(font)
            h.setData(Qt.UserRole, None)
            self._file_list.addItem(h)
            for path in by_ext[ext]:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(Qt.UserRole, path)
                item.setToolTip(path)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                self._file_list.addItem(item)

    # ------------------------------------------------------------------
    # File loading / saving
    # ------------------------------------------------------------------
    def _on_file_selected(self, current, _previous):
        if current is None or current.data(Qt.UserRole) is None:
            return  # header row
        if self._dirty:
            self._auto_save()
        self._load_file(current.data(Qt.UserRole))

    def _load_file(self, path):
        self._loading = True
        try:
            with open(path, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Update watcher to track the new file
            if self._watcher.files():
                self._watcher.removePaths(self._watcher.files())
            self._watcher.addPath(path)
            self._current_file = path
            self._set_label_saved()
            self._editor.setPlainText(content)
            self._dirty = False
            self._results_table.setRowCount(0)
            self._editor.clear_check_highlights()
            is_bat = os.path.splitext(path)[1].lower() == '.bat'
            self._btn_debug.setEnabled(not is_bat)
        except OSError as e:
            QMessageBox.warning(self, 'TUFLOW Studio', f'Cannot open file:\n{e}')
        finally:
            self._loading = False

    def _show_file_context_menu(self, pos):
        item = self._file_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        act_rename = QAction('Rename  (F2)', self)
        act_rename.triggered.connect(self._rename_current_item)
        menu.addAction(act_rename)
        menu.exec_(self._file_list.mapToGlobal(pos))

    def _rename_current_item(self, item=None):
        item = item or self._file_list.currentItem()
        if item and item.data(Qt.UserRole) is not None:  # not a header
            self._file_list.editItem(item)

    def _on_item_renamed(self, item):
        new_name = item.text().strip()
        old_path = item.data(Qt.UserRole)
        if not old_path:
            return
        old_name = os.path.basename(old_path)
        if new_name == old_name or not new_name:
            item.setText(old_name)
            return
        new_path = os.path.join(os.path.dirname(old_path), new_name)
        try:
            os.rename(old_path, new_path)
            item.setData(Qt.UserRole, new_path)
            item.setToolTip(new_path)
            if self._current_file == old_path:
                self._current_file = new_path
                self._watcher.removePath(old_path)
                self._watcher.addPath(new_path)
                self._set_label_saved()
        except OSError as e:
            item.setText(old_name)
            QMessageBox.warning(self, 'TUFLOW Studio', f'Cannot rename file:\n{e}')

    def _on_file_changed(self, path):
        if not os.path.exists(path):
            self._file_label.setText(f'FILE RENAMED / DELETED: {os.path.basename(path)}')
            self._file_label.setStyleSheet(
                'color: white; background: #C62828; font-style: italic; font-weight: bold; padding: 2px 6px;'
            )
            self._current_file = None
            self._watcher.removePath(path)

    def _on_text_changed(self):
        if self._loading or self._current_file is None:
            return
        if not self._dirty:
            self._dirty = True
            self._set_label_unsaved()
        self._save_timer.start(1000)

    def _manual_save(self):
        """Explicit save via button or Ctrl+S."""
        if not self._current_file:
            return
        self._save_timer.stop()
        self._auto_save()

    def _auto_save(self):
        if not self._current_file or not self._dirty:
            return
        try:
            with open(self._current_file, 'w', encoding='utf-8') as f:
                f.write(self._editor.toPlainText())
            self._dirty = False
            self._set_label_saved()
        except OSError as e:
            QMessageBox.warning(self, 'Auto-save failed', str(e))

    def _set_label_saved(self):
        name = os.path.basename(self._current_file) if self._current_file else ''
        self._file_label.setText(name)
        self._file_label.setStyleSheet('color: #606366; font-style: italic; font-weight: bold;')

    def _set_label_unsaved(self):
        name = os.path.basename(self._current_file) if self._current_file else ''
        self._file_label.setText(f'● {name}')   # ● filename
        self._file_label.setStyleSheet('color: #CC7832; font-style: italic; font-weight: bold;')

    # ------------------------------------------------------------------
    # Debug / checker
    # ------------------------------------------------------------------
    def _run_check(self):
        if not self._current_file:
            QMessageBox.information(self, 'TUFLOW Studio', 'No file open.')
            return
        if self._dirty:
            self._auto_save()

        self._btn_debug.setEnabled(False)
        self._debug_progress.setVisible(True)
        self._results_table.setRowCount(0)
        self.busy_changed.emit(True)

        self._check_worker = _CheckWorker(self._current_file)
        self._check_worker.finished.connect(self._on_check_done)
        self._check_worker.start()

    def _on_check_done(self, issues):
        self._debug_progress.setVisible(False)
        self._btn_debug.setEnabled(True)
        self.busy_changed.emit(False)
        if not issues:
            self._results_table.setRowCount(1)
            item = QTableWidgetItem('Well done! You are good to go!')
            item.setBackground(QColor('#C8E6C9'))  # light green
            item.setForeground(QColor('#1B5E20'))  # dark green text
            self._results_table.setItem(0, 0, item)
            self._results_table.setSpan(0, 0, 1, 3)
            self._editor.clear_check_highlights()
        else:
            self._results_table.clearSpans()
            self._populate_results(issues)
            self._highlight_lines(issues)

    def _populate_results(self, issues):
        self._results_table.setRowCount(len(issues))
        for r, issue in enumerate(issues):
            bg = _ERR_BG if issue['level'] == 'error' else _WARN_BG
            for c, val in enumerate([str(issue['line']), issue['issue_type'], issue['message']]):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                self._results_table.setItem(r, c, item)

    def _highlight_lines(self, issues):
        selections = []
        doc = self._editor.document()
        for issue in issues:
            block = doc.findBlockByNumber(issue['line'] - 1)
            if not block.isValid():
                continue
            cursor = QTextCursor(block)
            cursor.select(QTextCursor.LineUnderCursor)
            fmt = QTextCharFormat()
            fmt.setBackground(_ERR_BG if issue['level'] == 'error' else _WARN_BG)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            sel.format = fmt
            selections.append(sel)
        self._editor.set_check_highlights(selections)

    def _jump_to_line(self, row, _col):
        item = self._results_table.item(row, 0)
        if not item:
            return
        try:
            line_no = int(item.text()) - 1
        except ValueError:
            return
        block = self._editor.document().findBlockByNumber(line_no)
        if block.isValid():
            cursor = QTextCursor(block)
            self._editor.setTextCursor(cursor)
            self._editor.ensureCursorVisible()
            self._editor.setFocus()
