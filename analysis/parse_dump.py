"""Parse the text representation of an Excel workbook produced by the M365/Drive
connectors into per-sheet CSVs plus a compact structural summary.

The connector format is:
    Workbook: N worksheets. ...
    ## Sheet: <name> — R rows x C columns (A1:..)
    <tab separated rows>
    Formulas:
    <cell>: <formula>
"""
import csv
import os
import re
import sys
from collections import Counter

SHEET_RE = re.compile(r"^## Sheet:\s*(.*?)\s+[—-]\s+(\d+) rows")


def parse(path):
    sheets = []          # list of dict(name, rows, formulas)
    cur = None
    in_formulas = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = SHEET_RE.match(line)
            if m:
                cur = {"name": m.group(1).strip(), "declared_rows": int(m.group(2)),
                       "rows": [], "formulas": []}
                sheets.append(cur)
                in_formulas = False
                continue
            if cur is None:
                continue
            if line.strip() == "Formulas:":
                in_formulas = True
                continue
            if in_formulas:
                if line.strip():
                    cur["formulas"].append(line.strip())
            else:
                cur["rows"].append(line.split("\t"))
    return sheets


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")[:60]


def main(path, outdir):
    os.makedirs(outdir, exist_ok=True)
    sheets = parse(path)
    print(f"FILE: {os.path.basename(path)}  -> {len(sheets)} sheets")
    for s in sheets:
        rows = [r for r in s["rows"] if any(c.strip() for c in r)]
        width = max((len(r) for r in rows), default=0)
        dest = os.path.join(outdir, f"{slug(s['name'])}.csv")
        with open(dest, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        print(f"\n--- SHEET '{s['name']}': {len(rows)} non-empty rows x {width} cols "
              f"(declared {s['declared_rows']}), {len(s['formulas'])} formula cells")
        for r in rows[:3]:
            print("   HDR:", " | ".join(c[:34] for c in r[:width]))
        # column fill rates help spot which columns actually carry data
        fill = Counter()
        for r in rows:
            for i, c in enumerate(r):
                if c.strip():
                    fill[i] += 1
        print("   fill:", ", ".join(f"col{chr(65+i)}={fill.get(i,0)}"
                                    for i in range(min(width, 12))))
        for fx in s["formulas"][:6]:
            print("   FX:", fx[:150])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
