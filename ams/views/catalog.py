"""Accessory Master + Vendor Master (inline configs with usage guards)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..tools import next_code, read_csv_upload, csv_response
from ..models import Accessory, Vendor, VendorCategory, AssetType, Site, Asset, Consumable, SparePart


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
    }
    if request.GET.get("hub"):
        return render(request, "partials/accessories_content.html", ctx)
    return render(request, "accessories.html", ctx)


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
        it = Accessory(code=next_code(Accessory, "ACC-", 6))
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


# ---------------- VENDORS ----------------

@ams_view("vendors")
def vendors(request):
    q = (request.GET.get("q") or "").strip()
    qs = Vendor.objects.prefetch_related("categories")
    if q:
        qs = qs.filter(name__icontains=q)
    rows = []
    cats_map = {}
    for v in qs:
        usage = Asset.objects.filter(vendor=v).count() + Consumable.objects.filter(vendor=v).count() + SparePart.objects.filter(vendor=v).count()
        cats_map[str(v.pk)] = [c.pk for c in v.categories.all()]
        rows.append({"obj": v, "usage": usage})
    import json
    ctx = {
        "rows": rows, "q": q, "categories": VendorCategory.objects.all(),
        "cats_map_json": json.dumps(cats_map),
        "can_write": request.ams_can_write, "hub": request.GET.get("hub"),
    }
    if request.GET.get("hub"):
        return render(request, "partials/vendors_content.html", ctx)
    return render(request, "vendors.html", ctx)


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
    usage = Asset.objects.filter(vendor=v).count() + Consumable.objects.filter(vendor=v).count() + SparePart.objects.filter(vendor=v).count()
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
