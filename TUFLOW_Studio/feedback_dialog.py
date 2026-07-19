import configparser
import os
import urllib.parse

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QTextEdit, QVBoxLayout,
)

_TO = 'tszyilin@gmail.com'
_SUBJECT = 'TUFLOW Studio Feedback'


def _plugin_version():
    meta = configparser.ConfigParser()
    meta.read(os.path.join(os.path.dirname(__file__), 'metadata.txt'))
    return meta.get('general', 'version', fallback='unknown')


class FeedbackDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Send Feedback')
        self.resize(420, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel('Describe your feedback or the bug you encountered:'))

        self._text = QTextEdit()
        self._text.setPlaceholderText('Type your message here...')
        layout.addWidget(self._text)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        send_btn = buttons.button(QDialogButtonBox.Ok)
        send_btn.setText('Send')
        send_btn.setStyleSheet(
            'QPushButton { background-color: #1565C0; color: white; font-weight: bold; '
            'border-radius: 4px; padding: 4px 12px; }'
            'QPushButton:hover { background-color: #1976D2; }'
            'QPushButton:pressed { background-color: #0D47A1; }'
        )
        buttons.accepted.connect(self._send)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _send(self):
        msg = self._text.toPlainText().strip()
        if not msg:
            return
        body = f'Plugin version: {_plugin_version()}\n\n{msg}'
        url = (
            f'mailto:{_TO}'
            f'?subject={urllib.parse.quote(_SUBJECT)}'
            f'&body={urllib.parse.quote(body)}'
        )
        QDesktopServices.openUrl(QUrl(url))
        self.accept()
