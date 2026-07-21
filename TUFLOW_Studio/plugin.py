import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon, QFontDatabase
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject
from .dock_widget import TUFLOWStudioDock


def _load_bundled_fonts():
    fonts_dir = os.path.join(os.path.dirname(__file__), 'fonts')
    if os.path.isdir(fonts_dir):
        for fname in os.listdir(fonts_dir):
            if fname.lower().endswith('.ttf') or fname.lower().endswith('.otf'):
                QFontDatabase.addApplicationFont(os.path.join(fonts_dir, fname))


class TUFLOWStudio:
    def __init__(self, iface):
        self.iface = iface
        self._dock = None
        self._action = None

    def initGui(self):
        _load_bundled_fonts()
        self._dock = TUFLOWStudioDock(self.iface.mainWindow())
        self.iface.mainWindow().addDockWidget(Qt.TopDockWidgetArea, self._dock)
        self._dock.setFloating(True)
        self._dock.resize(1400, 900)
        self._dock.hide()

        # QGIS restores the dock's last saved visibility/geometry after
        # initGui() runs, which can re-show it even though we just hid it.
        # Force it hidden again once that restore has actually happened.
        self.iface.initializationCompleted.connect(self._dock.hide)

        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self._action = QAction(QIcon(icon_path), 'TUFLOW Studio', self.iface.mainWindow())
        self._action.setCheckable(True)
        self._action.triggered.connect(self._toggle_dock)
        self._dock.visibilityChanged.connect(self._action.setChecked)

        self.iface.addPluginToMenu('TUFLOW Studio', self._action)
        self.iface.addToolBarIcon(self._action)

        # Restore settings whenever a project is opened
        QgsProject.instance().readProject.connect(self._dock.load_project_settings)

        # Notify when project is saved
        QgsProject.instance().projectSaved.connect(self._on_project_saved)

    def _on_project_saved(self):
        self.iface.messageBar().pushSuccess(
            'TUFLOW Studio', 'TUFLOW project has been saved.')

    def unload(self):
        self.iface.initializationCompleted.disconnect(self._dock.hide)
        QgsProject.instance().projectSaved.disconnect(self._on_project_saved)
        QgsProject.instance().readProject.disconnect(self._dock.load_project_settings)
        self.iface.removePluginMenu('TUFLOW Studio', self._action)
        self.iface.removeToolBarIcon(self._action)
        if self._dock:
            self.iface.mainWindow().removeDockWidget(self._dock)
            self._dock.deleteLater()
            self._dock = None

    def _toggle_dock(self, checked):
        if self._dock:
            self._dock.setVisible(checked)

