"""
Convert the user's Excel slot table into parts_file_types data
and merge into mhws_armor_sets.json.

Usage:
    python scripts/import_slot_table.py

The Excel file path is hardcoded below; adjust before running.
"""
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

# ---- Config ----
EXCEL_PATH = r"C:\Users\Sheeran\Downloads\自制id.xlsx"
ADDON_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ADDON_DIR, "assets", "mhws", "armor_sets", "mhws_armor_sets.json")

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

# Part mapping: column index (0-based) → part_id
# Excel columns: A=0(name), B=1(ch03), C=2(suffix), D=3(头), E=4(胸), F=5(手), G=6(腰), H=7(腿)
COL_TO_PART = {
    3: "3",   # 头 → 头盔 (part 3)
    4: "2",   # 胸 → 身体 (part 2)
    5: "1",   # 手 → 手臂 (part 1)
    6: "5",   # 腰 → 腰 (part 5)
    7: "4",   # 腿 → 腿 (part 4)
}

# Suffixes that indicate a sub-variant (added to pl_id with underscore)
SUB_VARIANT_SUFFIXES = {"300", "500", "600", "100", "200", "700", "800", "900"}


def parse_excel(excel_path):
    """Parse xlsx file via ZIP+XML, return list of rows."""
    strings = []
    rows_data = []

    with zipfile.ZipFile(excel_path, 'r') as z:
        # Parse shared strings
        ss_xml = z.read('xl/sharedStrings.xml')
        ss_root = ET.fromstring(ss_xml)
        for si in ss_root.findall('.//s:si', NS):
            texts = []
            for t in si.iter('{%s}t' % NS['s']):
                if t.text:
                    texts.append(t.text)
            strings.append(''.join(texts))

        # Parse sheet 1
        s1_xml = z.read('xl/worksheets/sheet1.xml')
        s1_root = ET.fromstring(s1_xml)

        for row in s1_root.findall('.//s:row', NS):
            vals = []
            for c in row.findall('s:c', NS):
                t_attr = c.get('t')
                v_el = c.find('s:v', NS)
                if v_el is not None and v_el.text is not None:
                    if t_attr == 's':
                        si = int(v_el.text)
                        vals.append(strings[si] if si < len(strings) else v_el.text)
                    else:
                        vals.append(v_el.text)
                else:
                    vals.append('')
            if any(v for v in vals):
                rows_data.append(vals)

    return rows_data


def build_pl_id(armor_number, suffix):
    """Build pl_id from armor number and variant suffix.
    Examples: 001 → pl001, 003 + 500 → pl003_500, 043 + 600 → pl043_600
    """
    armor_num = str(armor_number).strip()
    if not armor_num:
        return None

    # Handle special case: "ch02 088" → extract number "088"
    if ' ' in armor_num:
        parts = armor_num.split()
        if len(parts) == 2 and parts[1].isdigit():
            armor_num = parts[1]
        else:
            return None

    if not armor_num.isdigit():
        return None

    # Zero-pad to 3 digits (e.g. "1" → "001", "88" → "088")
    armor_num_padded = int(armor_num)

    suffix = str(suffix).strip()
    if suffix in SUB_VARIANT_SUFFIXES:
        return f"pl{armor_num_padded:03d}_{suffix}"
    return f"pl{armor_num_padded:03d}"


def parse_cell_file_types(cell_text):
    """Parse a cell's text to determine which file types exist.
    Always includes mesh and mdf2 (they exist for every part).
    """
    text = cell_text.strip().lower()
    types = {"mesh", "mdf2"}

    if not text or text == "nothing":
        return sorted(types)

    # Match keywords within the cell text
    if "clsp" in text:
        types.add("clsp")
    if "chain" in text:
        types.add("chain2")
    if "gpuc" in text:
        types.add("gpuc")
    # sfur, jcns, gpbf are intentionally ignored

    return sorted(types)


def _is_sibling_row(row_a, row_b):
    """Check if row_b is the sibling (ff) row of row_a (fm).
    Sibling row has empty name column and suffix = row_a.suffix + 1."""
    if len(row_b) < 3:
        return False
    if row_b[0].strip():
        return False  # sibling has no name
    try:
        a_suffix = int(row_a[2].strip())
        b_suffix = int(row_b[2].strip())
        return b_suffix == a_suffix + 1
    except (ValueError, IndexError):
        return False


def extract_parts_file_types(rows_data):
    """
    Extract per-armor parts_file_types from parsed rows.
    Each armor appears as a pair of rows: [fm row, ff row].
    We use the ff row (second row, odd suffix).
    Returns dict: {pl_id: {"1": [...], "2": [...], ...}}
    """
    result = {}

    header = rows_data[0] if rows_data else []
    print(f"Header: {header}")
    print(f"Column mapping: D={COL_TO_PART[3]}(头), E={COL_TO_PART[4]}(胸), "
          f"F={COL_TO_PART[5]}(手), G={COL_TO_PART[6]}(腰), H={COL_TO_PART[7]}(腿)")

    i = 1  # skip header
    while i < len(rows_data):
        row = rows_data[i]
        if len(row) < 8:
            i += 1
            continue

        armor_number = row[1].strip()
        suffix = str(row[2]).strip()

        # Check if this row has a sibling (next row is its ff pair)
        if i + 1 < len(rows_data) and _is_sibling_row(row, rows_data[i + 1]):
            ff_row = rows_data[i + 1]
            # Build pl_id from the base armor_number (ignore suffix for base armors)
            # The pl_id uses the armor_number only, sub-variants use suffix
            try:
                int_suffix = int(suffix)
                # Odd suffixes (001, 501, 601, etc.) are the ff rows
                # Even suffixes (000, 500, 600, etc.) are the fm rows
                # The ff row suffix is always even_suffix + 1
                ff_suffix = str(int_suffix + 1)
            except ValueError:
                ff_suffix = suffix

            pl_id = build_pl_id(armor_number, suffix)
            if pl_id is None:
                pl_id = build_pl_id(armor_number, "")

            if pl_id:
                parts_fts = {}
                for col_idx, part_id in COL_TO_PART.items():
                    if col_idx < len(ff_row):
                        parts_fts[part_id] = parse_cell_file_types(ff_row[col_idx])
                if parts_fts:
                    result[pl_id] = parts_fts

            i += 2  # skip both rows
        else:
            # Standalone row (no sibling) - process if it looks like ff variant
            # ff variants have odd-numbered suffixes or no suffix info
            try:
                s = int(suffix)
                is_ff = (s % 2 == 1)
            except ValueError:
                is_ff = (suffix == "001" or not suffix)

            if is_ff or not suffix:
                pl_id = build_pl_id(armor_number, suffix)
                if pl_id is None:
                    pl_id = build_pl_id(armor_number, "")

                if pl_id:
                    parts_fts = {}
                    for col_idx, part_id in COL_TO_PART.items():
                        if col_idx < len(row):
                            parts_fts[part_id] = parse_cell_file_types(row[col_idx])
                    if parts_fts:
                        result[pl_id] = parts_fts

            i += 1

    return result


def merge_into_json(json_path, parts_data):
    """Merge parts_file_types data into existing JSON armor sets."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = 0
    skipped = 0
    missing = []

    for armor in data.get("armor_sets", []):
        pl_id = armor.get("id", "")
        if pl_id in parts_data:
            armor["parts_file_types"] = parts_data[pl_id]
            updated += 1
            del parts_data[pl_id]
        else:
            skipped += 1

    missing = list(parts_data.keys())

    # Backup and write
    backup_path = json_path + ".bak"
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(json.load(open(json_path, 'r', encoding='utf-8')), f, ensure_ascii=False, indent=4)

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    return updated, skipped, missing


def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"ERROR: Excel file not found: {EXCEL_PATH}")
        print("Please update EXCEL_PATH in the script.")
        sys.exit(1)

    print(f"Reading Excel: {EXCEL_PATH}")
    rows = parse_excel(EXCEL_PATH)
    print(f"Parsed {len(rows)} rows")

    print("\nExtracting parts_file_types (ff variant, suffix=001)...")
    parts_data = extract_parts_file_types(rows)

    print(f"\nExtracted {len(parts_data)} armor entries")
    for pl_id, fts in sorted(parts_data.items()):
        parts_str = " | ".join(f"part{p}={','.join(t)}" for p, t in sorted(fts.items()))
        print(f"  {pl_id}: {parts_str}")

    print(f"\nMerging into: {JSON_PATH}")
    updated, skipped, missing = merge_into_json(JSON_PATH, parts_data)

    print(f"\nResults:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (no table data): {skipped}")
    if missing:
        print(f"  Not in JSON (new armors): {len(missing)}")
        for m in sorted(missing):
            print(f"    - {m}: {parts_data[m]}")


if __name__ == "__main__":
    main()
