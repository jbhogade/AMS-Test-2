"""Accessory Master + Vendor Master (inline configs + usage guards + bulk
CSV/XLSX template / export / import with per-row Import Report)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..tools import next_code, read_csv_upload, csv_response, xlsx_response
from ..models import (
    Accessory, Vendor, VendorCategory, AssetType, Site,
    Asset, Consumable, SparePart,
)

# ---------------------------------------------------------------------------
# ACCESSORIES
# ---------------------------------------------------------------------------

_ACC_HEADERS = ["code", "name*", "asset_type*", "site", "active"]


@ams_view("accessory")
def accessories(request):
    q = (request.GET.get("q") or "").strip()
    qs = Accessory.objects.select_related("asset_type", "site")
    if q:
        qs = qs.filter(name__icontains=q)
    rows = []
    for it in qs:
        usage = Asset.objects.filter(type=it.asset_type, accessories=it).count()
        rows.append({"obj": it, "usage": usage})
    ctx = {
        "rows": rows, "q": q, "types": AssetType.objects.all(), "sites": Site.objects.all(),
        "can_write": request.ams_can_write, "hub": request.GET.get("hub"),
        "import_report": request.session.pop("acc_import_report", None),
    }
    if request.GET.get("hub"):
        return render(request, "partials/accessories_content.html", ctx)
    return render(request, "accessories.html", ctx)


def _acc_row(it):
    return [
        it.code or "",
        it.name or "",
        it.asset_type.name if it.asset_type else "",
        it.site.name if it.site else "",
        "Active" if it.active else "Inactive",
    ]


@ams_view("accessory")
def accessory_csv(request, action):
    """template / export / export-xlsx for accessories."""
    if action == "template":
        return xlsx_response("accessories_import_template", _ACC_HEADERS, [],
                            sheet="Accessories Template")
    if action == "export":
        rows = [_acc_row(it) for it in Accessory.objects.select_related("asset_type", "site")]
        return csv_response("accessories", _ACC_HEADERS, rows)
    if action == "export-xlsx":
        rows = [_acc_row(it) for it in Accessory.objects.select_related("asset_type", "site")]
        return xlsx_response("accessories", _ACC_HEADERS, rows, sheet="Accessories")
    from django.http import Http404
    raise Http404


@ams_view("accessory", write=True)
@require_POST
def accessory_import(request):
    """Bulk import accessories from CSV or XLSX. Match key: code, then name+type.
    Code left blank = new (auto ACC-000001). Code provided = update."""
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV or XLSX file to import.")
        return redirect("/accessories/")
    headers, rows = read_csv_upload(file)
    report = []
    added = updated = skipped = 0
    for i, row in enumerate(rows, start=1):
        try:
            code = (row.get("code") or "").strip()
            name = (row.get("name") or row.get("name*") or "").strip()
            type_name = (row.get("asset_type") or row.get("asset_type*") or "").strip()
            site_name = (row.get("site") or "").strip()
            status = (row.get("active") or row.get("status") or "Active").strip().lower()
            if not name:
                raise ValueError("name is required")
            if not type_name:
                raise ValueError("asset_type is required")
            at = AssetType.objects.filter(name__iexact=type_name).first()
            if at is None:
                # auto-create so bulk import works even before the master is set up
                from ..models import AssetCategory
                cat = AssetCategory.objects.first()
                at = AssetType.objects.create(name=type_name, shortform=type_name[:4].upper(),
                                              category=cat)
            site = Site.objects.filter(name__iexact=site_name).first() if site_name else None
            if site_name and site is None:
                site = Site.objects.create(name=site_name, shortform=site_name[:4].upper())
            obj = None
            if code:
                obj = Accessory.objects.filter(code__iexact=code).first()
            if obj is None:
                obj = Accessory.objects.filter(name__iexact=name, asset_type=at).first()
            if obj is None:
                obj = Accessory(code=next_code(Accessory, "ACC-"))
                obj.name = name
                created = True
            else:
                obj.name = name
                created = False
            obj.asset_type = at
            obj.site = site
            obj.active = status not in ("inactive", "false", "no", "0")
            obj.save()
            report.append({"no": i, "result": "added" if created else "updated",
                           "reason": f"{obj.code} - {obj.name}"})
            if created:
                added += 1
            else:
                updated += 1
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user,
                 f"Accessory Master: bulk import - {added} added, {updated} updated, {skipped} skipped",
                 "info", "Accessory Master")
    messages.success(request,
                     f"Import finished: {added} added, {updated} updated, {skipped} skipped. See the report below.")
    request.session["acc_import_report"] = {"title": "Accessory Master", "rows": report}
    return redirect("/accessories/")


@ams_view("accessory", write=True)
@require_POST
def accessory_save(request):
    pk = request.POST.get("pk")
    it = Accessory.objects.filter(pk=pk).first() if pk else None
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Accessory Name is required.")
        return redirect("/accessories/")
    if it is None:
        it = Accessory(code=next_code(Accessory, "ACC-"))
    it.name = name
    it.asset_type = AssetType.objects.filter(pk=request.POST.get("asset_type")).first()
    it.site = Site.objects.filter(pk=request.POST.get("site")).first()
    it.active = bool(request.POST.get("active", "1"))
    it.save()
    log_activity(request.user, f"Accessory '{it.name}' ({it.code}) {'added' if not pk else 'updated'}", "success", "Accessory Master")
    messages.success(request, f"Accessory '{it.name}' {'added' if not pk else 'updated'}.")
    return redirect("/accessories/")


@ams_view("accessory", write=True)
@require_POST
def accessory_delete(request, pk):
    it = Accessory.objects.filter(pk=pk).first()
    if it is None:
        messages.error(request, "Record not found.")
        return redirect("/accessories/")
    usage = Asset.objects.filter(type=it.asset_type, accessories=it).count()
    if usage > 0:
        messages.warning(request, f"Cannot delete - currently used by {usage} record(s). Deactivate instead.")
    else:
        label = it.name
        it.delete()
        log_activity(request.user, f"Accessory '{label}' deleted", "danger", "Accessory Master")
        messages.success(request, f"Accessory '{label}' deleted.")
    return redirect("/accessories/")


@ams_view("accessory", write=True)
@require_POST
def accessory_toggle(request, pk):
    it = Accessory.objects.filter(pk=pk).first()
    if it is None:
        messages.error(request, "Record not found.")
        return redirect("/accessories/")
    it.active = not it.active
    it.save()
    messages.success(request, f"'{it.name}' is now {'Active' if it.active else 'Inactive'}.")
    return redirect("/accessories/")


# ---------------------------------------------------------------------------
# VENDORS
# ---------------------------------------------------------------------------

_VEN_HEADERS = ["name*", "contact_person", "phone", "email", "city",
                "categories", "gstin", "remarks", "active"]


@ams_view("vendors")
def vendors(request):
    q = (request.GET.get("q") or "").strip()
    qs = Vendor.objects.prefetch_related("categories")
    if q:
        qs = qs.filter(name__icontains=q)
    rows = []
    cats_map = {}
    for v in qs:
        usage = (Asset.objects.filter(vendor=v).count()
                 + Consumable.objects.filter(vendor=v).count()
                 + SparePart.objects.filter(vendor=v).count())
        cats_map[str(v.pk)] = [c.pk for c in v.categories.all()]
        rows.append({"obj": v, "usage": usage})
    import json
    ctx = {
        "rows": rows, "q": q, "categories": VendorCategory.objects.all(),
        "cats_map_json": json.dumps(cats_map),
        "can_write": request.ams_can_write, "hub": request.GET.get("hub"),
        "import_report": request.session.pop("ven_import_report", None),
    }
    if request.GET.get("hub"):
        return render(request, "partials/vendors_content.html", ctx)
    return render(request, "vendors.html", ctx)


def _ven_row(v):
    return [
        v.name or "",
        v.contact_person or "",
        v.phone or "",
        v.email or "",
        v.city or "",
        "|".join(c.name for c in v.categories.all()),
        v.gstin or "",
        v.remarks or "",
        "Active" if v.active else "Inactive",
    ]


@ams_view("vendors")
def vendor_csv(request, action):
    if action == "template":
        return xlsx_response("vendors_import_template", _VEN_HEADERS, [],
                            sheet="Vendors Template")
    if action == "export":
        rows = [_ven_row(v) for v in Vendor.objects.prefetch_related("categories")]
        return csv_response("vendors", _VEN_HEADERS, rows)
    if action == "export-xlsx":
        rows = [_ven_row(v) for v in Vendor.objects.prefetch_related("categories")]
        return xlsx_response("vendors", _VEN_HEADERS, rows, sheet="Vendors")
    from django.http import Http404
    raise Http404


@ams_view("vendors", write=True)
@require_POST
def vendor_import(request):
    """Bulk import vendors. Match on name (case-insensitive). Categories
    column is pipe-separated names; missing categories are auto-created."""
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV or XLSX file to import.")
        return redirect("/vendors/")
    headers, rows = read_csv_upload(file)
    report = []
    added = updated = skipped = 0
    for i, row in enumerate(rows, start=1):
        try:
            name = (row.get("name") or row.get("name*") or "").strip()
            if not name:
                raise ValueError("name is required")
            v = Vendor.objects.filter(name__iexact=name).first()
            created = False
            if v is None:
                v = Vendor(name=name)
                created = True
            else:
                v.name = name
            v.contact_person = (row.get("contact_person") or "").strip()
            v.phone = (row.get("phone") or "").strip()
            v.email = (row.get("email") or "").strip()
            v.city = (row.get("city") or "").strip()
            v.gstin = (row.get("gstin") or "").strip().upper()[:15]
            v.remarks = (row.get("remarks") or "").strip()
            status = (row.get("active") or row.get("status") or "Active").strip().lower()
            v.active = status not in ("inactive", "false", "no", "0")
            v.save()
            # categories: pipe-separated, auto-create missing
            cats_raw = (row.get("categories") or "").strip()
            cats = []
            for c_name in [c.strip() for c in cats_raw.split("|") if c.strip()]:
                cat, _ = VendorCategory.objects.get_or_create(name__iexact=c_name,
                                                               defaults={"name": c_name})
                cats.append(cat)
            v.categories.set(cats)
            report.append({"no": i, "result": "added" if created else "updated",
                           "reason": v.name})
            if created:
                added += 1
            else:
                updated += 1
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user,
                 f"Vendor Master: bulk import - {added} added, {updated} updated, {skipped} skipped",
                 "info", "Vendor Master")
    messages.success(request,
                     f"Import finished: {added} added, {updated} updated, {skipped} skipped. See the report below.")
    request.session["ven_import_report"] = {"title": "Vendor Master", "rows": report}
    return redirect("/vendors/")


@ams_view("vendors", write=True)
@require_POST
def vendor_save(request):
    pk = request.POST.get("pk")
    v = Vendor.objects.filter(pk=pk).first() if pk else None
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Vendor Name is required.")
        return redirect("/vendors/")
    if v is None:
        if Vendor.objects.filter(name__iexact=name).exists():
            messages.error(request, f"Vendor '{name}' already exists.")
            return redirect("/vendors/")
        v = Vendor(name=name)
    else:
        v.name = name
    v.contact_person = (request.POST.get("contact_person") or "").strip()
    v.phone = (request.POST.get("phone") or "").strip()
    v.email = (request.POST.get("email") or "").strip()
    v.city = (request.POST.get("city") or "").strip()
    v.gstin = (request.POST.get("gstin") or "").strip().upper()[:15]
    v.remarks = (request.POST.get("remarks") or "").strip()
    v.active = bool(request.POST.get("active", "1"))
    v.save()
    cats = request.POST.getlist("categories")
    v.categories.set(VendorCategory.objects.filter(pk__in=cats))
    log_activity(request.user, f"Vendor '{v.name}' {'added' if not pk else 'updated'}", "success", "Vendor Master")
    messages.success(request, f"Vendor '{v.name}' {'added' if not pk else 'updated'}.")
    return redirect("/vendors/")


@ams_view("vendors", write=True)
@require_POST
def vendor_delete(request, pk):
    v = Vendor.objects.filter(pk=pk).first()
    if v is None:
        messages.error(request, "Record not found.")
        return redirect("/vendors/")
    usage = (Asset.objects.filter(vendor=v).count()
             + Consumable.objects.filter(vendor=v).count()
             + SparePart.objects.filter(vendor=v).count())
    if usage > 0:
        messages.warning(request, f"Cannot delete - currently used by {usage} record(s). Deactivate instead.")
    else:
        label = v.name
        v.delete()
        log_activity(request.user, f"Vendor '{label}' deleted", "danger", "Vendor Master")
        messages.success(request, f"Vendor '{label}' deleted.")
    return redirect("/vendors/")


@ams_view("vendors", write=True)
@require_POST
def vendor_toggle(request, pk):
    v = Vendor.objects.filter(pk=pk).first()
    if v is None:
        messages.error(request, "Record not found.")
        return redirect("/vendors/")
    v.active = not v.active
    v.save()
    messages.success(request, f"'{v.name}' is now {'Active' if v.active else 'Inactive'}.")
    return redirect("/vendors/")
