import os
import csv

_BC_TYPES = {'hydrograph', 'rainfall'}


def parse_bc_database(bc_dbase_dir):
    """
    Scan bc_dbase_dir for a BC database CSV, parse it, and return
    {'hydrograph': [...], 'rainfall': [...]} where each entry is:
    {'name', 'source', 'time_col', 'value_col', 'label'}
    """
    csv_path = _find_bc_database(bc_dbase_dir)
    if csv_path is None:
        return {'hydrograph': [], 'rainfall': []}

    result = {'hydrograph': [], 'rainfall': []}
    with open(csv_path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 4:
                continue
            name, source, time_col, value_col = parts[0], parts[1], parts[2], parts[3]
            bc_type = name.lower()
            if bc_type not in _BC_TYPES:
                continue
            label = os.path.splitext(os.path.basename(source))[0]
            result[bc_type].append({
                'name': name,
                'source': source,
                'time_col': time_col,
                'value_col': value_col,
                'label': label,
            })
    return result


def _find_bc_database(bc_dbase_dir):
    """Find the BC database CSV in bc_dbase_dir (prefers files with 'bc_dbase' in name)."""
    try:
        files = os.listdir(bc_dbase_dir)
    except OSError:
        return None
    for f in files:
        if f.lower().endswith('.csv') and 'bc_dbase' in f.lower():
            return os.path.join(bc_dbase_dir, f)
    for f in files:
        if f.lower().endswith('.csv'):
            return os.path.join(bc_dbase_dir, f)
    return None


def load_bc_csv(bc_dbase_dir, source_rel_path, time_col, value_col):
    """
    Load a hydrograph/rainfall CSV referenced in the BC database.
    source_rel_path is relative to bc_dbase_dir.
    Returns (times: list[float], values: list[float]).
    """
    norm = source_rel_path.replace('/', os.sep).replace('\\', os.sep)
    full_path = os.path.join(bc_dbase_dir, norm)

    time_col_l = time_col.lower()
    value_col_l = value_col.lower()
    t_idx = None
    v_idx = None
    header_found = False
    times = []
    values = []

    with open(full_path, encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            if row[0].strip().startswith('!'):
                continue
            if not header_found:
                lrow = [c.strip().lower() for c in row]
                if time_col_l in lrow and value_col_l in lrow:
                    t_idx = lrow.index(time_col_l)
                    v_idx = lrow.index(value_col_l)
                    header_found = True
                    continue
                # No named header — assume first two columns are time, value
                t_idx, v_idx = 0, 1
                header_found = True
            try:
                times.append(float(row[t_idx]))
                values.append(float(row[v_idx]))
            except (ValueError, IndexError):
                continue

    return times, values
