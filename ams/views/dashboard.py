"""Dashboard: KPI tiles, Assets-by-Type bars, status donut, low stock, activity."""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from ..models import Asset, Consumable, SparePart, ActivityLog, StockMovement
from ..access import access_level_for


@login_required
def dashboard(request):
    assets = Asset.objects.filter(kind="asset")
    total = assets.count()
    operational = assets.filter(status__in=["Assigned", "In Store"]).count()
    maintenance = assets.filter(status__in=["In Repair", "Not Working"]).count()
    total_value = assets.aggregate(v=Sum("purchase_cost"))["v"] or 0

    # Assets by Type (bar chart)
    by_type = {}
    for a in assets.exclude(type=None):
        by_type[a.type.name] = by_type.get(a.type.name, 0) + 1
    by_type_rows = sorted(by_type.items(), key=lambda kv: -kv[1])
    max_count = max([c for _, c in by_type_rows] or [1])

    # Status donut
    status_counts = {}
    for a in assets:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1
    donut_colors = {
        "Assigned": "#2dd4a7", "In Store": "#5b8def", "In Repair": "#f5b04d",
        "Transfer": "#39b9d8", "Not Working": "#ef5d5d",
        "Retired / Scrapped": "#ef5d5d", "Replaced": "#98a2b3",
    }
    donut = [{"status": s, "count": c, "color": donut_colors.get(s, "#98a2b3")} for s, c in status_counts.items()]

    # Low stock (consumables + spare parts where qty <= reorder)
    low = []
    for c in Consumable.objects.filter(active=True):
        if float(c.qty) <= float(c.reorder_level):
            low.append({"name": c.name, "kind": "Consumable", "qty": c.qty, "unit": c.unit})
    for p in SparePart.objects.filter(active=True):
        if float(p.qty) <= float(p.reorder_level):
            low.append({"name": p.name, "kind": "Spare Part", "qty": p.qty, "unit": None})

    recent_assets = assets.select_related("type", "current_site")[:6]
    recent_activity = ActivityLog.objects.all()[:6]
    recent_moves = StockMovement.objects.all()[:6]

    can_assets = access_level_for(request.user, "asset") != "none"

    return render(request, "dashboard.html", {
        "kpi_total": total,
        "kpi_operational": operational,
        "kpi_maintenance": maintenance,
        "kpi_value": total_value,
        "by_type_rows": by_type_rows,
        "max_count": max_count,
        "donut": donut,
        "donut_total": total,
        "low": low,
        "recent_assets": recent_assets,
        "recent_activity": recent_activity,
        "recent_moves": recent_moves,
        "can_assets": can_assets,
    })
