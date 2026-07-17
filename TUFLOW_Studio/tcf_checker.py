import difflib
import os
import re

# Extensions that indicate a referenced value is a file path
_FILE_EXTS = {
    # GIS / raster
    '.shp', '.mif', '.mid', '.flt', '.adf', '.asc', '.tif', '.tiff', '.gpkg',
    # data
    '.csv', '.txt', '.xf', '.sup',
    # TUFLOW command files
    '.tcf', '.ecf', '.tgc', '.tbc', '.toc', '.trfc', '.tesf',
    '.qcf', '.tscf', '.adcf', '.tef', '.trd',
}

# TUFLOW keywords whose RHS is NOT a file path
_NON_FILE_KEYWORDS = re.compile(
    r'^\s*(scenario|event|if|else|end\s+if|set\s+variable|write\s+check\s+files|'
    r'solution\s+scheme|hardware|cell\s+size|start\s+time|end\s+time|'
    r'timestep|output\s+interval|map\s+output\s+interval|log\s+interval|'
    r'number\s+of|simulation\s+id|projection|coordinate\s+system|'
    r'define\s+event|end\s+define|bc\s+event\s+source|'
    r'start\s+output|end\s+output)',
    re.IGNORECASE,
)


_IF_KEYWORDS = ('SCENARIO', 'EVENT')


def _check_if_keyword(upper_line, lineno, issues):
    """Warn if the keyword after IF / ELSE IF looks like a typo of SCENARIO or EVENT."""
    m = re.match(r'^(?:ELSE\s+)?IF\s+(\S+)', upper_line)
    if not m:
        return
    word = m.group(1)
    if word in _IF_KEYWORDS:
        return
    # Ignore TUFLOW variable placeholders like <<VAR>>
    if word.startswith('<<'):
        return
    close = difflib.get_close_matches(word, _IF_KEYWORDS, n=1, cutoff=0.7)
    if close:
        issues.append({
            'line': lineno, 'level': 'warning',
            'issue_type': 'Possible Keyword Typo',
            'message': f'"{word.title()}" looks like a typo of "{close[0].title()}"',
        })


def check_file(filepath):
    """
    Check a TUFLOW control file for common issues.
    Returns list of dicts: {line, level, issue_type, message}
    """
    issues = []
    try:
        with open(filepath, encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except OSError as e:
        return [{'line': 0, 'level': 'error', 'issue_type': 'Read Error', 'message': str(e)}]

    base_dir = os.path.dirname(filepath)

    if_stack     = []   # tracks line numbers of open IF blocks
    define_stack = []   # tracks line numbers of open DEFINE EVENT blocks

    for i, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Skip blank lines and comments
        if not line or line.startswith('!'):
            continue

        # Strip inline comments
        if '!' in line:
            line = line[:line.index('!')].strip()
        if not line:
            continue

        upper = line.upper()

        # --- Single = instead of == ---
        if re.search(r'(?<!=)=(?!=)', line) and '==' not in line:
            issues.append({
                'line': i, 'level': 'warning',
                'issue_type': 'Single = Assignment',
                'message': 'Found single = — TUFLOW uses == for assignments. Did you mean ==?',
            })

        # --- Empty or malformed scenario/event condition ---
        cond_match = re.match(
            r'^(?:IF|ELSE\s+IF)\s+(SCENARIO|EVENT)\s*==\s*(.*)', upper)
        if cond_match:
            rhs = cond_match.group(2).strip()
            if not rhs:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'Empty Condition',
                    'message': f'{cond_match.group(1).title()} condition has no value after ==',
                })
            else:
                parts = [p.strip() for p in rhs.split('|')]
                if any(p == '' for p in parts):
                    issues.append({
                        'line': i, 'level': 'error',
                        'issue_type': 'Empty Pipe Value',
                        'message': f'{cond_match.group(1).title()} condition has an empty value between | separators',
                    })

        # --- If/Else/End If tracking ---
        if re.match(r'^IF\b', upper):
            if_stack.append(i)
            _check_if_keyword(upper, i, issues)
        elif re.match(r'^ELSE\s+IF\b', upper):
            _check_if_keyword(upper, i, issues)
            if not if_stack:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'Unmatched ELSE IF',
                    'message': 'ELSE IF without a preceding IF',
                })
        elif re.match(r'^ELSE\b', upper):
            if not if_stack:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'Unmatched ELSE',
                    'message': 'ELSE without a preceding IF',
                })
        elif re.match(r'^END\s+IF\b', upper):
            if if_stack:
                if_stack.pop()
            else:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'Unmatched END IF',
                    'message': 'END IF without a preceding IF',
                })

        # --- Define Event / End Define tracking (TEF) ---
        if re.match(r'^DEFINE\s+EVENT\b', upper):
            define_stack.append(i)
        elif re.match(r'^END\s+DEFINE\b', upper):
            if define_stack:
                define_stack.pop()
            else:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'Unmatched END DEFINE',
                    'message': 'END DEFINE without a preceding DEFINE EVENT',
                })

        # --- BC Event Source: must have at least one | and no empty slots ---
        if re.match(r'^BC\s+EVENT\s+SOURCE\b', upper) and '==' in line:
            rhs = line.split('==', 1)[1].strip()
            parts = [p.strip() for p in rhs.split('|')]
            if len(parts) < 2:
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'BC Source Missing Value',
                    'message': 'BC Event Source must have at least: variable | value',
                })
            elif any(p == '' for p in parts):
                issues.append({
                    'line': i, 'level': 'error',
                    'issue_type': 'BC Source Empty Slot',
                    'message': 'BC Event Source has an empty value between | separators',
                })

        # --- File reference check ---
        if '==' in line and not _NON_FILE_KEYWORDS.match(line):
            rhs_full = line.split('==', 1)[1].strip()
            for rhs in (p.strip() for p in rhs_full.split('|')):
                if not rhs:
                    continue
                _, ext = os.path.splitext(rhs)
                has_sep = ('\\' in rhs or '/' in rhs)
                if ext.lower() in _FILE_EXTS or has_sep:
                    resolved = os.path.normpath(os.path.join(base_dir, rhs))
                    if ext:
                        exists = os.path.exists(resolved)
                    else:
                        # No extension — TUFLOW GIS commands often omit it; probe candidates
                        _GIS_EXTS = ('.shp', '.mif', '.gpkg', '.tif', '.tiff', '.flt', '.asc')
                        exists = os.path.exists(resolved) or any(
                            os.path.exists(resolved + e) for e in _GIS_EXTS
                        )
                    if not exists:
                        issues.append({
                            'line': i, 'level': 'error',
                            'issue_type': 'Missing File',
                            'message': f'File not found: {rhs}',
                        })

    # Unclosed IF blocks
    for open_line in if_stack:
        issues.append({
            'line': open_line, 'level': 'error',
            'issue_type': 'Unclosed IF',
            'message': f'IF block opened at line {open_line} has no matching END IF',
        })

    # Unclosed DEFINE EVENT blocks
    for open_line in define_stack:
        issues.append({
            'line': open_line, 'level': 'error',
            'issue_type': 'Unclosed DEFINE EVENT',
            'message': f'DEFINE EVENT at line {open_line} has no matching END DEFINE',
        })

    return issues
