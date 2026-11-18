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
    """Decode an uploaded CSV (or Excel-exported CSV) into rows of dicts.
    Also accepts .xlsx files (read with openpyxl) - the file extension is the
    trigger. Anything else is treated as CSV text."""
    name = (getattr(file_obj, "name", "") or "").lower()
    if name.endswith(".xlsx"):
        return _read_xlsx_upload(file_obj)
    data = file_obj.read()
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    reader = csv.reader(StringIO(text, newline=""))
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


def _read_xlsx_upload(file_obj):
    """Read an uploaded .xlsx file (openpyxl). First sheet, header row first."""
    from openpyxl import load_workbook
    file_obj.seek(0)
    wb = load_workbook(filename=file_obj, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header_row = next(rows_iter)
    except StopIteration:
        wb.close()
        return [], []
    headers = [str(c).strip() if c is not None else "" for c in header_row]
    out = []
    for r in rows_iter:
        if not any((c is not None and str(c).strip()) for c in r):
            continue
        row = {}
        for i, h in enumerate(headers):
            v = r[i] if i < len(r) else None
            if isinstance(v, (datetime.datetime, datetime.date)):
                v = v.strftime("%d-%m-%Y")
            row[h] = ("" if v is None else str(v)).strip()
        out.append(row)
    wb.close()
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
    """Real .xlsx export with autofilter + frozen header (openpyxl).

    If the first header looks like a "code"/"name" template column, also writes
    a second row showing the required-markers so the file doubles as a template.
    """
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(headers)
    # template hint row: required markers + sample data
    is_template = any(h.endswith("*") for h in headers) and not rows
    if is_template:
        hint = ["required" if h.endswith("*") else "optional" for h in headers]
        ws.append(hint)
        sample_row = []
        for h in headers:
            base = h.rstrip("*")
            sample_row.append({
                "name": "Sample Name",
                "code": "ACC-000001",
                "asset_type": "Laptop",
                "site": "HO",
                "contact_person": "John Doe",
                "phone": "+91-98765-43210",
                "email": "vendor@example.com",
                "city": "Pune",
                "gstin": "27ABCDE1234F1Z5",
                "categories": "Hardware|Software",
                "remarks": "Preferred vendor",
                "active": "Active",
            }.get(base, ""))
        ws.append(sample_row)
        # styling
        ws["A2"].font = Font(italic=True, color="FF888888")
        ws["A3"].font = Font(italic=True, color="FF0B3A3A")
        for c in range(1, len(headers) + 1):
            ws.cell(row=3, column=c).fill = PatternFill(
                start_color="FFEFF8F4", end_color="FFEFF8F4", fill_type="solid")
    for r in rows:
        ws.append(["" if c is None else c for c in r])
    # column widths
    for col in range(1, len(headers) + 1):
        width = max([len(str(headers[col - 1]))] +
                    [len(str(r[col - 1])) for r in rows[:200]
                     if len(r) >= col and r[col - 1] is not None] or [8])
        ws.column_dimensions[get_column_letter(col)].width = min(max(width + 2, 8), 60)
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"
    for c in range(1, len(headers) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
        ws.cell(row=1, column=c).alignment = Alignment(vertical="center")
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
