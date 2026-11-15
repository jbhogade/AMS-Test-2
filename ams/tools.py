"""
#-------------- Start Code for : CSV + XLSX TOOLS (ams/tools.py) ----------------
CSV import with a per-row Import Report (added / updated / skipped / error
with reasons), CSV template + export, and real .xlsx export via openpyxl.
Dates are DD-MM-YYYY like the original portal.
#-------------- End of the code : CSV + XLSX TOOLS (ams/tools.py) ----------------
"""

import csv
import datetime
from io import BytesIO, StringIO


def parse_date(s):
    """Parse DD-MM-YYYY (preferred) or YYYY-MM-DD. Returns date or None."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fmt_date(d):
    if not d:
        return ""
    if isinstance(d, str):
        return d
    return d.strftime("%d-%m-%Y")


def read_csv_upload(file_obj):
    """Decode an uploaded CSV (or Excel-exported CSV) into rows of dicts."""
    data = file_obj.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    reader = csv.reader(StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return [], []
    headers = [h.strip().lstrip("\ufeff") for h in rows[0]]
    out = []
    for r in rows[1:]:
        row = {}
        for i, h in enumerate(headers):
            row[h] = (r[i] if i < len(r) else "").strip()
        out.append(row)
    return headers, out


def csv_response(filename, headers, rows):
    import csv as _csv
    from django.http import HttpResponse
    buf = StringIO()
    w = _csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(["" if c is None else c for c in r])
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    return resp


def xlsx_response(filename, headers, rows, sheet="Report"):
    """Real .xlsx export with autofilter + frozen header (openpyxl)."""
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(headers)
    for r in rows:
        ws.append(["" if c is None else c for c in r])
    # column widths
    for col in range(1, len(headers) + 1):
        width = max([len(str(headers[col - 1]))] + [len(str(r[col - 1])) for r in rows[:200] if len(r) >= col and r[col - 1] is not None] or [8])
        ws.column_dimensions[get_column_letter(col)].width = min(max(width + 2, 8), 60)
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    bio = BytesIO()
    wb.save(bio)
    from django.http import HttpResponse
    resp = HttpResponse(
        bio.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    return resp


def import_report_row(no, result, reason=""):
    """One per-row Import Report entry: result in added|updated|skipped|error."""
    return {"no": no, "result": result, "reason": reason}


def next_code(model, prefix, width=6, field="code"):
    qs = list(model.objects.values_list(field, flat=True))
    best = 0
    for v in qs:
        if v and str(v).startswith(prefix):
            tail = str(v)[len(prefix):]
            if tail.isdigit():
                best = max(best, int(tail))
    return prefix + str(best + 1).zfill(width)
