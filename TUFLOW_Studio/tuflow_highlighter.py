import re
from qgis.PyQt.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


def _fmt(color_hex, bold=False, italic=False):
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color_hex))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class TuflowHighlighter(QSyntaxHighlighter):
    # Light theme palette
    _fmt_comment  = _fmt('#6A9955', italic=True)   # muted green
    _fmt_keyword  = _fmt('#0000CD', bold=True)      # blue bold
    _fmt_lhs      = _fmt('#7B3F00')                 # dark brown/orange
    _fmt_value    = _fmt('#098658')                 # dark green
    _fmt_path     = _fmt('#0451A5')                 # dark blue
    _fmt_pipe     = _fmt('#AAAAAA')                 # grey pipe separator

    # Control keywords — order matters (longer matches before shorter)
    _kw_patterns = [
        re.compile(r'^\s*ELSE\s+IF\b',      re.IGNORECASE),
        re.compile(r'^\s*END\s+IF\b',       re.IGNORECASE),
        re.compile(r'^\s*ELSE\b',           re.IGNORECASE),
        re.compile(r'^\s*IF\b',             re.IGNORECASE),
        re.compile(r'^\s*DEFINE\s+EVENT\b', re.IGNORECASE),
        re.compile(r'^\s*END\s+DEFINE\b',   re.IGNORECASE),
    ]

    def highlightBlock(self, text):
        # Comment start position
        comment_start = text.find('!')
        effective_end = comment_start if comment_start >= 0 else len(text)
        effective = text[:effective_end]

        # LHS / RHS
        eq_pos = effective.find('==')
        if eq_pos >= 0:
            self.setFormat(0, eq_pos, self._fmt_lhs)
            rhs_full = effective[eq_pos + 2:]
            rhs_offset = eq_pos + 2

            if '|' in rhs_full:
                # Multiple file references — colour each segment individually
                cursor = 0
                parts = rhs_full.split('|')
                for idx, part in enumerate(parts):
                    if part.strip():
                        fmt = self._fmt_path if ('\\' in part or '/' in part) else self._fmt_value
                        self.setFormat(rhs_offset + cursor, len(part), fmt)
                    cursor += len(part)
                    if idx < len(parts) - 1:
                        self.setFormat(rhs_offset + cursor, 1, self._fmt_pipe)
                        cursor += 1
            else:
                rhs = rhs_full
                if rhs.strip():
                    fmt = self._fmt_path if ('\\' in rhs or '/' in rhs) else self._fmt_value
                    self.setFormat(rhs_offset, len(rhs), fmt)

        # Keywords (applied after LHS so bold overrides normal weight on same chars)
        for pattern in self._kw_patterns:
            m = pattern.match(effective)
            if m:
                self.setFormat(m.start(), m.end(), self._fmt_keyword)
                break

        # Comment (applied last — overrides everything)
        if comment_start >= 0:
            self.setFormat(comment_start, len(text) - comment_start, self._fmt_comment)
