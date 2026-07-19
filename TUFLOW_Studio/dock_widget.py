import os
from qgis.PyQt.QtWidgets import QDockWidget, QPushButton, QTabWidget
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QFont, QFontDatabase
from .tab_root import TabRoot
from .tab_editor import TabEditor
from .tab_logs import TabLogs
from .tab_settings import TabSettings

_BASE_TITLE = 'TUFLOW Studio'
_BUSY_MSGS  = ['Running', 'Searching', 'Contemplating']


class TUFLOWStudioDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(_BASE_TITLE, parent)
        self.setObjectName('TUFLOWStudioDock')
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.setMinimumHeight(500)

        # Inter font for all UI elements (code editor sets its own font)
        db = QFontDatabase()
        font_name = 'Inter' if 'Inter' in db.families() else 'Segoe UI'
        self.setStyleSheet(f'* {{ font-family: "{font_name}"; font-size: 10pt; }}')

        # Animated title state
        self._busy_count = 0
        self._busy_idx   = 0
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(700)
        self._busy_timer.timeout.connect(self._cycle_title)

        # Build tabs
        self._tabs = QTabWidget()
        self._tab_root     = TabRoot()
        self._tab_editor   = TabEditor()
        self._tab_logs     = TabLogs()
        self._tab_settings = TabSettings()

        self._tabs.addTab(self._tab_root,     'Root')
        self._tabs.addTab(self._tab_editor,   'Editor')
        self._tabs.addTab(self._tab_logs,     'Logs')
        self._tabs.addTab(self._tab_settings, 'Settings')

        self._tab_settings.font_changed.connect(self._tab_editor.apply_font)

        btn_fb = QPushButton('?')
        btn_fb.setFixedSize(24, 24)
        btn_fb.setToolTip('Send feedback or report a bug')
        btn_fb.clicked.connect(self._open_feedback)
        self._tabs.setCornerWidget(btn_fb, Qt.TopRightCorner)

        self.setWidget(self._tabs)

        # Propagate root paths to Editor and Logs
        self._tab_root.paths_changed.connect(self._on_paths_changed)

        # Animated title when any tab is busy
        self._tab_root.busy_changed.connect(self._set_busy)
        self._tab_editor.busy_changed.connect(self._set_busy)
        self._tab_logs.busy_changed.connect(self._set_busy)

    # ------------------------------------------------------------------
    # Animated title
    # ------------------------------------------------------------------
    def _set_busy(self, active):
        if active:
            self._busy_count += 1
            if not self._busy_timer.isActive():
                self._busy_idx = 0
                self._busy_timer.start()
                self._cycle_title()
        else:
            self._busy_count = max(0, self._busy_count - 1)
            if self._busy_count == 0:
                self._busy_timer.stop()
                self.setWindowTitle(_BASE_TITLE)

    def _cycle_title(self):
        msg = _BUSY_MSGS[self._busy_idx % len(_BUSY_MSGS)]
        self.setWindowTitle(f'{_BASE_TITLE}  -  {msg}...')
        self._busy_idx += 1

    # ------------------------------------------------------------------
    # Path propagation
    # ------------------------------------------------------------------
    def _on_paths_changed(self, paths):
        self._tab_editor.set_root(paths.get('root', ''))
        log_dir = paths.get('runs', '')
        if log_dir:
            log_dir = os.path.join(log_dir, 'log')
        self._tab_logs.set_log_dir(log_dir)

    def _open_feedback(self):
        from .feedback_dialog import FeedbackDialog
        FeedbackDialog(self).exec()

    def load_project_settings(self):
        self._tab_root.load_from_project()

