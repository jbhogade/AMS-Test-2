"""
#-------------- Start Code for : REPORT MASTER (ams/views/reports.py) ----------

Eight report tabs (Asset Lifecycle, Asset Issue, Asset Handover, Consumable
Restock/Used, Spare Parts Restock/Used, Asset Distribution) with filters,
CSV/Excel export and the Report Appearance editor (letterhead prefs).
#-------------- End of the code for : REPORT MASTER (ams/views/reports.py) ----
"""

from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..models import (
    Asset, SimCard, LifecycleEvent, StockMovement, Consumable, SparePart,
    Employee, ExitRecord, Site, ReportPrefs, Company,
)
from ..ids import print_asset_id
from ..tools import parse_date, csv_response, xlsx_response

TABS = [
    ("assetLifecycle", "Asset Lifecycle"),
    ("assetIssue", "Asset Issue Form"),
    ("assetHandover", "Asset Handover Form"),
    ("consumableRestock", "Consumable Restock"),
    ("consumableUsed", "Consumable Used"),
    ("sparePartsRestock", "Spare Parts Restock"),
    ("sparePartsUsed", "Spare Parts Used"),
    ("assetDistribution", "Asset Distribution"),
]


def _classify(action):
    a = action or ""
    if a.startswith("Transferred"):
        return "Transfer"
    if a.startswith("Reassigned"):
        return "Reassign"
    if a.startswith("Assign"):
        return "Assign"
    if a.startswith("Return"):
        return "Return"
    if a.startswith("Replaced by") or a.startswith("Added to Inventory (Replacement"):
        return "Replace"
    if a.startswith("Retired"):
        return "Retire"
    if a == "Not Working":
        return "Fault"
    return "Other"


@ams_view("reports")
def reports(request):
    tab = request.GET.get("tab") or "assetLifecycle"
    ctx = build_tab(request, tab)
    ctx.update({
        "tabs": TABS, "active_tab": tab, "prefs": ReportPrefs.get_solo(),
    })
    if request.headers.get("HX-Request") and request.GET.get("panel"):
        return render(request, "partials/report_content.html", ctx)
    return render(request, "reports.html", ctx)


def build_tab(request, tab):
    ctx = {"tab": tab, "tab_title": dict(TABS).get(tab, tab)}
    sites = Site.objects.all()
    if tab == "assetLifecycle":
        evs = LifecycleEvent.objects.all()
        ev_type = request.GET.get("event_type", "").strip()
        site_f = request.GET.get("site", "").strip()
        from_d = parse_date(request.GET.get("from"))
        to_d = parse_date(request.GET.get("to"))
        if ev_type:
            evs = evs.filter(event_type=ev_type)
        if site_f:
            s = Site.objects.filter(pk=site_f).first()
            evs = evs.filter(emp__site=s) if s else evs
        if from_d:
            evs = evs.filter(date__gte=from_d)
        if to_d:
            evs = evs.filter(date__lte=to_d)
        ctx.update({"events": evs[:300], "event_types": ["Assign", "Reassign", "Return", "Transfer", "Replace", "Retire", "Fault"], "sites": sites})
    elif tab in ("assetIssue", "assetHandover"):
        exited = tab == "assetHandover"
        emp_status = "Inactive" if exited else "Active"
        q = request.GET.get("q", "").strip()
        holdings = []
        emps = Employee.objects.filter(status=emp_status).select_related("department")
        for e in emps:
            for a in Asset.objects.filter(assigned_to=e).select_related("type", "current_site"):
                holdings.append({"emp": e, "a": a, "pid": print_asset_id(a)})
        if q:
            ql = q.lower()
            holdings = [h for h in holdings if ql in h["emp"].name.lower() or ql in (h["emp"].emp_id or "").lower()
                        or ql in h["pid"].lower() or ql in (h["emp"].department.name if h["emp"].department else "").lower()]
        site_f = request.GET.get("site", "").strip()
        if site_f:
            holdings = [h for h in holdings if h["a"].current_site and str(h["a"].current_site.pk) == site_f]
        dept_f = request.GET.get("dept", "").strip()
        if dept_f:
            holdings = [h for h in holdings if h["emp"].department and str(h["emp"].department.pk) == dept_f]
        from ..models import Department
        ctx.update({"holdings": holdings[:300], "sites": sites, "departments": Department.objects.all(), "exited": exited})
    elif tab in ("consumableRestock", "consumableUsed", "sparePartsRestock", "sparePartsUsed"):
        kind = "consumable" if tab.startswith("consumable") else "sparepart"
        typ = "Restocked" if tab.endswith("Restock") else "Used"
        moves = StockMovement.objects.filter(kind=kind, type=typ)
        site_f = request.GET.get("site", "").strip()
        if site_f:
            s = Site.objects.filter(pk=site_f).first()
            moves = moves.filter(site=s.name) if s else moves
        from_d = parse_date(request.GET.get("from"))
        to_d = parse_date(request.GET.get("to"))
        if from_d:
            moves = moves.filter(date__gte=from_d)
        if to_d:
            moves = moves.filter(date__lte=to_d)
        ctx.update({"moves": moves[:300], "sites": sites, "show_asset_col": tab == "sparePartsUsed"})
    elif tab == "assetDistribution":
        rows = distribution_rows(request)
        ctx.update({"dist_rows": rows})
    return ctx


def distribution_rows(request):
    q = request.GET.get("q", "").strip()
    only_holding = request.GET.get("holding") == "1"
    emps = Employee.objects.select_related("department")
    rows = []
    for e in emps:
        direct = _direct_count(e)
        team = _team_count(e)
        if only_holding and direct + team == 0:
            continue
        if q and q.lower() not in e.name.lower() and q.lower() not in (e.emp_id or "").lower() \
                and q.lower() not in (e.department.name if e.department else "").lower():
            continue
        rows.append({"emp": e, "direct": direct, "team": team, "total": direct + team})
    return rows


def _direct_count(emp):
    n = Asset.objects.filter(assigned_to=emp, assigned_to_sub__isnull=True, assigned_sub_text="").count()
    n += SimCard.objects.filter(assigned_to=emp, assigned_to_sub__isnull=True, assigned_sub_text="").count()
    return n


def _team_count(emp):
    n = 0
    for a in Asset.objects.filter(assigned_to=emp).exclude(assigned_to_sub=None, assigned_sub_text=""):
        n += 1
    for s in SimCard.objects.filter(assigned_to=emp).exclude(assigned_to_sub=None, assigned_sub_text=""):
        n += 1
    for sub in emp.subordinates.all():
        n += Asset.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text="").count()
        n += SimCard.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text="").count()
    return n


def reports_export(request, tab, fmt):
    ctx = build_tab(request, tab)
    if tab == "assetLifecycle":
        headers = ["Date", "Type", "Action", "Asset ID", "Item Kind", "Employee", "Department", "Status"]
        rows = [[e.date.strftime("%d-%m-%Y"), e.event_type, e.action, e.item_label,
                 e.item_kind.capitalize(), e.emp_label, e.emp_dept, e.status_label] for e in ctx["events"]]
    elif tab in ("assetIssue", "assetHandover"):
        headers = ["Emp Code", "Employee Name", "Status", "Department", "Asset ID", "Asset Type", "Site"]
        rows = [[h["emp"].emp_id or h["emp"].ams_id, h["emp"].name, h["emp"].status,
                 h["emp"].department.name if h["emp"].department else "", h["pid"],
                 h["a"].type.name if h["a"].type else "",
                 h["a"].current_site.name if h["a"].current_site else ""] for h in ctx["holdings"]]
    elif tab in ("consumableRestock", "consumableUsed", "sparePartsRestock", "sparePartsUsed"):
        headers = ["Date", "Item", "Site", "Qty", ("Vendor" if tab.endswith("Restock") else "Used By"), "Remarks"]
        if ctx.get("show_asset_col"):
            headers.insert(5, "Used For Asset")
        rows = []
        for m in ctx["moves"]:
            r = [m.date.strftime("%d-%m-%Y"), m.name, m.site, f"{m.qty:g}", m.by, m.remarks]
            if ctx.get("show_asset_col"):
                r.insert(5, m.asset_id_snapshot)
            rows.append(r)
    elif tab == "assetDistribution":
        headers = ["Emp ID", "Employee Name", "Department", "Designation", "Direct", "Team", "Total"]
        rows = [[r["emp"].emp_id or r["emp"].ams_id, r["emp"].name,
                 r["emp"].department.name if r["emp"].department else "", r["emp"].designation,
                 r["direct"], r["team"], r["total"]] for r in ctx["dist_rows"]]
    else:
        headers, rows = ["-"], []
    if fmt == "xlsx":
        return xlsx_response(tab.replace(".", "_") + "_Report", headers, rows)
    return csv_response(tab.replace(".", "_") + "_Report", headers, rows)


@ams_view("reports", write=True)
@require_POST
def report_prefs_save(request):
    prefs = ReportPrefs.get_solo()
    prefs.style = request.POST.get("style", "classic")
    prefs.show_logo = bool(request.POST.get("show_logo"))
    prefs.show_name = bool(request.POST.get("show_name"))
    prefs.show_slogan = bool(request.POST.get("show_slogan"))
    prefs.save()
    log_activity(request.user, "Report header appearance updated", "info", "Report Master")
    messages.success(request, "Report header appearance saved.")
    return redirect("/reports/")
