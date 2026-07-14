import os
import re
from datetime import datetime, timedelta
from pathlib import Path

COMMAND_FILE_EXTS = {
    '.tcf',   # A - TCF
    '.ecf',   # B - ECF
    '.tgc',   # C - TGC
    '.tbc',   # D - TBC
    '.toc',   # E - TOC
    '.trfc',  # F - TRFC
    '.tesf',  # G - TESF
    '.qcf',   # H - QCF
    '.tscf',  # I - TSCF
    '.adcf',  # J - ADCF
    '.tef',   # K - TEF
    '.trd',
    '.bat',
}
_EXCLUDE_HPC = re.compile(r'\.hpc\.tlf$', re.IGNORECASE)


def scan_log_dir(log_dir):
    """Recursively find all .tlf files (excluding .hpc.tlf), parse, return sorted list."""
    results = []
    for root, _, files in os.walk(log_dir):
        for f in files:
            if f.lower().endswith('.tlf') and not _EXCLUDE_HPC.search(f):
                try:
                    results.append(parse_tlf(os.path.join(root, f)))
                except Exception:
                    pass
    results.sort(key=lambda r: r['sort_key'], reverse=True)
    return results


def parse_tlf(path):
    content = Path(path).read_text(encoding='utf-8', errors='ignore')

    # Simulation Started
    m = re.search(r'Simulation Started:\s+(\S+)\s+(\S+)', content)
    sim_date_raw = m.group(1) if m else 'N/A'
    sim_time = m.group(2) if m else 'N/A'

    # Reformat date from yyyy-Mon-dd to dd/MM/yyyy
    try:
        dt = datetime.strptime(sim_date_raw, '%Y-%b-%d')
        sim_date = dt.strftime('%d/%m/%Y')
    except Exception:
        sim_date = sim_date_raw

    # Scenarios and events
    scenarios = '_'.join(re.findall(r'^\s*-s\d+\s+(\S+)', content, re.MULTILINE))
    events = '_'.join(re.findall(r'^\s*-e\d+\s+(\S+)', content, re.MULTILINE))

    # Duration — last Clock Time: in file
    clocks = re.findall(r'Clock Time:\s+(\S+)', content)
    duration = clocks[-1] if clocks else 'N/A'

    # End Time = wall-clock start + duration
    end_time = 'N/A'
    sort_key = datetime.min
    try:
        start = datetime.strptime(f'{sim_date} {sim_time}', '%d/%m/%Y %H:%M')
        sort_key = start
        h, mn, s = (int(x) for x in duration.split(':'))
        end_time = (start + timedelta(hours=h, minutes=mn, seconds=s)).strftime('%d/%m/%Y %H:%M')
    except Exception:
        pass

    return {
        'file': os.path.basename(path),
        'scenarios': scenarios or 'N/A',
        'events': events or 'N/A',
        'sim_date': sim_date,
        'sim_time': sim_time,
        'duration': duration,
        'end_time': end_time,
        'sort_key': sort_key,
    }


def find_command_files(root_dir):
    """Recursively find all TUFLOW command files under root_dir."""
    found = []
    for dirpath, _, files in os.walk(root_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in COMMAND_FILE_EXTS:
                found.append(os.path.join(dirpath, f))
    return sorted(found)
