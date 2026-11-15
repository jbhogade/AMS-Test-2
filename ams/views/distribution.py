"""Asset Distribution page + per-employee detail partial."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from ..access import ams_view
from ..models import Employee, Asset, SimCard, LifecycleEvent
from ..ids import print_asset_id
from ..tools import csv_response, xlsx_response
from ..views.reports import distribution_rows, _direct_count, _team_count


@ams_view("assetDistribution")
def distribution(request):
    rows = distribution_rows(request)
    direct_total = sum(r["direct"] for r in rows)
    team_total = sum(r["team"] for r in rows)
    holding = sum(1 for r in rows if r["total"] > 0)
    q = request.GET.get("q", "").strip()
    only = request.GET.get("holding") == "1"
    return render(request, "distribution.html", {
        "rows": rows, "q": q, "only": only,
        "kpi_direct": direct_total, "kpi_team": team_total,
        "kpi_total": direct_total + team_total, "kpi_holding": holding,
        "can_write": request.ams_can_write,
    })


@ams_view("assetDistribution")
def distribution_detail(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    direct_assets = list(Asset.objects.filter(assigned_to=emp, assigned_to_sub__isnull=True, assigned_sub_text=""))
    direct_sims = list(SimCard.objects.filter(assigned_to=emp, assigned_to_sub__isnull=True, assigned_sub_text=""))
    team_assets = list(Asset.objects.filter(assigned_to=emp).exclude(assigned_to_sub=None, assigned_sub_text=""))
    team_sims = list(SimCard.objects.filter(assigned_to=emp).exclude(assigned_to_sub=None, assigned_sub_text=""))
    for sub in emp.subordinates.all():
        direct_assets_sub = list(Asset.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text=""))
        sims_sub = list(SimCard.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text=""))
        team_assets += direct_assets_sub
        team_sims += sims_sub

    def serialize_assets(items):
        return [{"a": a, "pid": print_asset_id(a),
                 "serial": a.serial_number or (a.sim.mobile_number if a.kind == "mobile" and a.sim else ""),
                 "kind": "asset"} for a in items]

    def serialize_sims(items):
        return [{"a": s, "pid": s.sim_id, "serial": s.mobile_number, "kind": "sim"} for s in items]

    direct = serialize_assets(direct_assets) + serialize_sims(direct_sims)
    team = serialize_assets(team_assets) + serialize_sims(team_sims)

    # lifecycle: events where the employee is the subject
    events = LifecycleEvent.objects.filter(emp=emp)[:80]
    return render(request, "partials/distribution_detail.html", {
        "emp": emp, "direct": direct, "team": team, "events": events,
        "can_write": request.ams_can_write,
    })


@ams_view("assetDistribution")
def distribution_export(request, fmt):
    rows = distribution_rows(request)
    headers = ["Emp ID", "Employee Name", "Department", "Designation", "Direct Assets", "Team Assets", "Total Assets"]
    data = [[r["emp"].emp_id or r["emp"].ams_id, r["emp"].name,
             r["emp"].department.name if r["emp"].department else "", r["emp"].designation,
             r["direct"], r["team"], r["total"]] for r in rows]
    if fmt == "xlsx":
        return xlsx_response("Asset_Distribution", headers, data)
    return csv_response("Asset_Distribution", headers, data)
