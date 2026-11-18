"""
#-------------- Start Code for : CONSUMABLES + SPARE PARTS (ams/views/stock.py) ----

Both masters with Restock / Used-Assign actions, movement logs, low-stock
badge, per-item movement report, CSV template/export/import. Spare part
Used action links to the asset it was fitted on (permanent AMS ID +
display-ID snapshot).
#-------------- End of the code for : CONSUMABLES + SPARE PARTS (ams/views/stock.py) ----
"""

from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..tools import parse_date, read_csv_upload, csv_response, xlsx_response, next_code
from ..models import (
    Consumable, SparePart, StockMovement, ConsumableCategory, UnitOfMeasure,
    SparePartCategory, AssetType, Site, Vendor, Employee, Asset, Department,
)


def _low(item):
    return float(item.qty) <= float(item.reorder_level)


def _tiles(qs):
    total = qs.count()
    low = sum(1 for it in qs if _low(it))
    inactive = qs.filter(active=False).count()
    return {"total": total, "low": low, "ok": total - low, "inactive": inactive}


# ---------------- CONSUMABLES ----------------

@ams_view("consumable")
def consumables(request):
    q = request.GET.get("q", "").strip()
    qs = Consumable.objects.select_related("category", "unit", "site", "vendor")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "consumables.html", {
        "rows": qs[:200], "tiles": _tiles(qs), "q": q,
        "categories": ConsumableCategory.objects.all(), "units": UnitOfMeasure.objects.all(),
        "sites": Site.objects.all(), "vendors": Vendor.objects.filter(active=True),
        "emps": Employee.objects.filter(status="Active"),
        "departments": Department.objects.all(),
        "can_write": request.ams_can_write,
    })


@ams_view("consumable", write=True)
@require_POST
def consumable_save(request):
    pk = request.POST.get("pk")
    it = Consumable.objects.filter(pk=pk).first() if pk else None
    created = it is None
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Consumable Name is required.")
        return redirect("/consumables/")
    if created:
        it = Consumable(code=next_code(Consumable, "CNS-", 6))
    it.name = name
    it.category = ConsumableCategory.objects.filter(pk=request.POST.get("category") or 0).first()
    it.unit = UnitOfMeasure.objects.filter(pk=request.POST.get("unit") or 0).first()
    it.site = Site.objects.filter(pk=request.POST.get("site") or 0).first()
    it.qty = request.POST.get("qty") or 0
    it.reorder_level = request.POST.get("reorder_level") or 0
    it.restock_date = parse_date(request.POST.get("restock_date"))
    it.warranty_date = parse_date(request.POST.get("warranty_date"))
    it.unit_cost = request.POST.get("unit_cost") or None
    it.vendor = Vendor.objects.filter(pk=request.POST.get("vendor") or 0).first()
    it.remarks = (request.POST.get("remarks") or "").strip()
    it.active = bool(request.POST.get("active", "1"))
    it.save()
    log_activity(request.user, f"Consumable '{it.name}' {'added' if created else 'updated'}", "success" if created else "info", "Consumable Master")
    messages.success(request, f"'{it.name}' {'added' if created else 'updated'}.")
    return redirect("/consumables/")


@ams_view("consumable", write=True)
@require_POST
def consumable_restock(request, pk):
    it = get_object_or_404(Consumable, pk=pk)
    qty = float(request.POST.get("restock_qty") or 0)
    d = parse_date(request.POST.get("restock_date")) or date.today()
    if qty < 1:
        messages.error(request, "Quantity Added must be at least 1.")
        return redirect("/consumables/")
    vendor = Vendor.objects.filter(pk=request.POST.get("restock_vendor") or 0).first()
    it.qty = float(it.qty) + qty
    it.restock_date = d
    if vendor:
        it.vendor = vendor
    it.save()
    StockMovement.objects.create(
        kind="consumable", item_id=it.pk, item_code=it.code, name=it.name,
        site=it.site.name if it.site else "", type="Restocked", qty=qty,
        by=vendor.name if vendor else "", remarks=(request.POST.get("restock_remarks") or "").strip(),
        date=d, actor_username=request.user.username,
    )
    log_activity(request.user, f"Consumable '{it.name}' restocked +{qty:g}", "success", "Consumable Master")
    messages.success(request, f"'{it.name}' restocked by {qty:g}. New stock: {it.qty:g}.")
    return redirect("/consumables/")


@ams_view("consumable", write=True)
@require_POST
def consumable_used(request, pk):
    it = get_object_or_404(Consumable, pk=pk)
    qty = float(request.POST.get("used_qty") or 0)
    d = parse_date(request.POST.get("used_date")) or date.today()
    if qty < 1:
        messages.error(request, "Quantity Used is required.")
        return redirect("/consumables/")
    if qty > float(it.qty):
        messages.error(request, f"Only {it.qty:g} in stock.")
        return redirect("/consumables/")
    emp = Employee.objects.filter(pk=request.POST.get("used_employee") or 0).first()
    dept = Department.objects.filter(pk=request.POST.get("used_department") or 0).first()
    if emp:
        by = emp.name
        if emp.department:
            by += f" ({emp.department.name})"
    elif dept:
        by = f"{dept.name} (Department Use)"
    else:
        by = "-"
    it.qty = float(it.qty) - qty
    it.save()
    StockMovement.objects.create(
        kind="consumable", item_id=it.pk, item_code=it.code, name=it.name,
        site=it.site.name if it.site else "", type="Used", qty=qty,
        by=by, remarks=(request.POST.get("used_remarks") or "").strip(),
        date=d, actor_username=request.user.username,
    )
    log_activity(request.user, f"Consumable '{it.name}' used -{qty:g} ({by})", "info", "Consumable Master")
    messages.success(request, f"'{it.name}' used by {qty:g}. Remaining: {it.qty:g}.")
    return redirect("/consumables/")


@ams_view("consumable")
def consumable_log(request, pk):
    it = get_object_or_404(Consumable, pk=pk)
    moves = StockMovement.objects.filter(kind="consumable", item_id=it.pk)
    return render(request, "partials/stock_log.html", {"item": it, "moves": moves, "kind": "consumable"})


def consumable_csv(request, action):
    return _stock_csv(request, action, consumable=True)


# ---------------- SPARE PARTS ----------------

@ams_view("spareParts")
def spareparts(request):
    q = request.GET.get("q", "").strip()
    qs = SparePart.objects.select_related("asset_type", "category", "site", "vendor")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "spareparts.html", {
        "rows": qs[:200], "tiles": _tiles(qs), "q": q,
        "categories": SparePartCategory.objects.all(), "types": AssetType.objects.all(),
        "sites": Site.objects.all(), "vendors": Vendor.objects.filter(active=True),
        "emps": Employee.objects.filter(status="Active"),
        "departments": Department.objects.all(),
        "assets": Asset.objects.exclude(status="Retired / Scrapped").select_related("type"),
        "can_write": request.ams_can_write,
    })


@ams_view("spareParts", write=True)
@require_POST
def sparepart_save(request):
    pk = request.POST.get("pk")
    it = SparePart.objects.filter(pk=pk).first() if pk else None
    created = it is None
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Part Name is required.")
        return redirect("/spare-parts/")
    if created:
        it = SparePart(code=next_code(SparePart, "SP-", 6))
    it.name = name
    it.asset_type = AssetType.objects.filter(pk=request.POST.get("asset_type") or 0).first()
    it.category = SparePartCategory.objects.filter(pk=request.POST.get("category")).first()
    it.site = Site.objects.filter(pk=request.POST.get("site") or 0).first()
    it.qty = request.POST.get("qty") or 0
    it.reorder_level = request.POST.get("reorder_level") or 0
    it.restock_date = parse_date(request.POST.get("restock_date"))
    it.warranty_date = parse_date(request.POST.get("warranty_date"))
    it.unit_cost = request.POST.get("unit_cost") or None
    it.vendor = Vendor.objects.filter(pk=request.POST.get("vendor") or 0).first()
    it.remarks = (request.POST.get("remarks") or "").strip()
    it.active = bool(request.POST.get("active", "1"))
    it.save()
    log_activity(request.user, f"Spare Part '{it.name}' {'added' if created else 'updated'}", "success" if created else "info", "Spare Parts Master")
    messages.success(request, f"'{it.name}' {'added' if created else 'updated'}.")
    return redirect("/spare-parts/")


@ams_view("spareParts", write=True)
@require_POST
def sparepart_restock(request, pk):
    it = get_object_or_404(SparePart, pk=pk)
    qty = float(request.POST.get("restock_qty") or 0)
    d = parse_date(request.POST.get("restock_date")) or date.today()
    if qty < 1:
        messages.error(request, "Quantity Added must be at least 1.")
        return redirect("/spare-parts/")
    vendor = Vendor.objects.filter(pk=request.POST.get("restock_vendor") or 0).first()
    it.qty = float(it.qty) + qty
    it.restock_date = d
    if vendor:
        it.vendor = vendor
    it.save()
    StockMovement.objects.create(
        kind="sparepart", item_id=it.pk, item_code=it.code, name=it.name,
        site=it.site.name if it.site else "", type="Restocked", qty=qty,
        by=vendor.name if vendor else "", remarks=(request.POST.get("restock_remarks") or "").strip(),
        date=d, actor_username=request.user.username,
    )
    log_activity(request.user, f"Spare Part '{it.name}' restocked +{qty:g}", "success", "Spare Parts Master")
    messages.success(request, f"'{it.name}' restocked by {qty:g}. New stock: {it.qty:g}.")
    return redirect("/spare-parts/")


@ams_view("spareParts", write=True)
@require_POST
def sparepart_used(request, pk):
    it = get_object_or_404(SparePart, pk=pk)
    qty = float(request.POST.get("used_qty") or 0)
    d = parse_date(request.POST.get("used_date")) or date.today()
    if qty < 1:
        messages.error(request, "Quantity Used is required.")
        return redirect("/spare-parts/")
    if qty > float(it.qty):
        messages.error(request, f"Only {it.qty:g} in stock.")
        return redirect("/spare-parts/")
    emp = Employee.objects.filter(pk=request.POST.get("used_employee") or 0).first()
    dept = Department.objects.filter(pk=request.POST.get("used_department") or 0).first()
    if emp:
        by = emp.name + (f" ({emp.department.name})" if emp.department else "")
    elif dept:
        by = f"{dept.name} (Department Use)"
    else:
        by = "-"
    asset = Asset.objects.filter(pk=request.POST.get("used_for_asset") or 0).first()
    from ..ids import print_asset_id
    it.qty = float(it.qty) - qty
    it.save()
    StockMovement.objects.create(
        kind="sparepart", item_id=it.pk, item_code=it.code, name=it.name,
        site=it.site.name if it.site else "", type="Used", qty=qty,
        by=by, remarks=(request.POST.get("used_remarks") or "").strip(),
        asset=asset, asset_id_snapshot=print_asset_id(asset) if asset else "",
        date=d, actor_username=request.user.username,
    )
    log_activity(request.user, f"Spare Part '{it.name}' used -{qty:g}" + (f" on {print_asset_id(asset)}" if asset else ""), "info", "Spare Parts Master")
    messages.success(request, f"'{it.name}' used by {qty:g}. Remaining: {it.qty:g}.")
    return redirect("/spare-parts/")


@ams_view("spareParts")
def sparepart_log(request, pk):
    it = get_object_or_404(SparePart, pk=pk)
    moves = StockMovement.objects.filter(kind="sparepart", item_id=it.pk)
    return render(request, "partials/stock_log.html", {"item": it, "moves": moves, "kind": "sparepart"})


def sparepart_csv(request, action):
    return _stock_csv(request, action, consumable=False)


# ---------------- shared CSV ----------------

def _stock_csv(request, action, consumable=True):
    user = request.user
    if not user.is_authenticated:
        return redirect("/login/")
    from ..access import can_write
    page = "consumable" if consumable else "spareParts"
    slug = "Consumable_Master" if consumable else "Spare_Parts_Master"
    headers = ["name*", "category*", "unit*" if consumable else "assetType*", "site*", "qty*", "reorderLevel*",
               "restockDate", "warrantyDate", "unitCost", "vendor", "remarks"]
    if action == "template":
        return csv_response(f"{slug}_import_template", headers, [])
    if action in ("export", "export-xlsx"):
        if consumable:
            objs = Consumable.objects.select_related("category", "unit", "site", "vendor")
            rows = [[o.name, o.category.name if o.category else "", o.unit.name if o.unit else "",
                     o.site.name if o.site else "", o.qty, o.reorder_level,
                     o.restock_date.strftime("%d-%m-%Y") if o.restock_date else "",
                     o.warranty_date.strftime("%d-%m-%Y") if o.warranty_date else "",
                     o.unit_cost or "", o.vendor.name if o.vendor else "", o.remarks] for o in objs]
        else:
            objs = SparePart.objects.select_related("asset_type", "category", "site", "vendor")
            rows = [[o.name, o.category.name if o.category else "", o.asset_type.name if o.asset_type else "",
                     o.site.name if o.site else "", o.qty, o.reorder_level,
                     o.restock_date.strftime("%d-%m-%Y") if o.restock_date else "",
                     o.warranty_date.strftime("%d-%m-%Y") if o.warranty_date else "",
                     o.unit_cost or "", o.vendor.name if o.vendor else "", o.remarks] for o in objs]
        if action == "export-xlsx":
            return xlsx_response(slug, headers, rows)
        return csv_response(slug, headers, rows)
    if not can_write(user, page):
        messages.warning(request, "View only - you cannot change records on this page.")
        return redirect("/consumables/" if consumable else "/spare-parts/")
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV file to import.")
        return redirect("/consumables/" if consumable else "/spare-parts/")
    _, rows = read_csv_upload(file)
    report = []
    added = updated = skipped = 0
    for i, row in enumerate(rows, start=1):
        try:
            def g(*names):
                for n in names:
                    v = (row.get(n) or "").strip()
                    if v:
                        return v
                return ""
            name = g("name*", "name")
            if not name:
                raise ValueError("name is required")
            if consumable:
                it = Consumable.objects.filter(name__iexact=name).first()
                created = it is None
                if created:
                    it = Consumable(code=next_code(Consumable, "CNS-", 6))
                it.name = name
                cat = g("category*", "category")
                it.category = ConsumableCategory.objects.get_or_create(name=cat)[0] if cat else None
                unit = g("unit*", "unit")
                it.unit = UnitOfMeasure.objects.get_or_create(name=unit)[0] if unit else None
            else:
                it = SparePart.objects.filter(name__iexact=name).first()
                created = it is None
                if created:
                    it = SparePart(code=next_code(SparePart, "SP-", 6))
                it.name = name
                cat = g("category*", "category")
                it.category = SparePartCategory.objects.get_or_create(name=cat)[0] if cat else None
                at = g("assetType*", "assetType")
                t = AssetType.objects.filter(name__iexact=at).first()
                if at and t is None:
                    raise ValueError(f"Asset Type '{at}' not found in the master")
                it.asset_type = t
            sname = g("site*", "site")
            s = Site.objects.filter(name__iexact=sname).first()
            if sname and s is None:
                raise ValueError(f"Site '{sname}' not found in the master")
            it.site = s
            it.qty = g("qty*", "qty") or 0
            it.reorder_level = g("reorderLevel*", "reorderLevel") or 0
            it.restock_date = parse_date(g("restockDate", "restockDate*"))
            it.warranty_date = parse_date(g("warrantyDate", "warrantyDate*"))
            cost = g("unitCost")
            it.unit_cost = cost or None
            it.vendor = Vendor.objects.filter(name__iexact=g("vendor")).first()
            it.remarks = g("remarks")
            it.save()
            added += 1 if created else 0
            updated += 0 if created else 1
            report.append({"no": i, "result": "added" if created else "updated", "reason": ""})
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user, f"{slug} CSV import: {added} added, {updated} updated, {skipped} skipped", "info", "Consumable Master" if consumable else "Spare Parts Master")
    messages.success(request, f"Import finished: {added} added, {updated} updated, {skipped} skipped.")
    request.session["import_report"] = {"title": "Consumable Master" if consumable else "Spare Parts Master", "rows": report}
    return redirect("/consumables/" if consumable else "/spare-parts/")
