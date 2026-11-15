"""
#-------------- Start Code for : ASSET + MOBILE MASTER (ams/views/assets.py) ----

One view set serves both Assets and Mobiles (kind="asset"|"mobile"), exactly
like the original portal which clones the asset engine for mobiles.

Full lifecycle: Add/Edit, Assign / Edit Assign / Reassign, Return, Transfer,
Not Working, Retire / Scrap, Replace, Swap (mobiles), SIM link (mobiles),
history per item + global lifecycle events, CSV template/export/import,
Asset Issue Form printing hand-off.
#-------------- End of the code : ASSET + MOBILE MASTER (ams/views/assets.py) ----
"""

from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..ids import (
    type_short, site_short, dept_short, dept_short_from_emp,
    base_display_id, full_display_id, print_asset_id,
    next_ams_asset_id, next_display_id,
)
from ..models import (
    Asset, AssetType, AssetCategory, AssetMake, Site, Vendor, Employee,
    SimCard, LifecycleEvent, StockMovement, Accessory, CLEAR_ON_STATUS, ASSET_STATUS,
)
from ..tools import parse_date, read_csv_upload, csv_response, xlsx_response

REPLACE_REASONS = ["Damaged / Faulty", "Lost / Stolen", "Upgrade", "End of Life", "Warranty Replacement", "Other"]


def _ams_kind_view(write=False):
    """Gate by registry key derived from the URL kind (asset|mobile)."""
    from ..access import access_level_for, first_allowed_path
    from functools import wraps

    def deco(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("/login/")
            kind = kwargs.get("kind", "asset")
            key = "mobile" if kind == "mobile" else "asset"
            level = access_level_for(request.user, key)
            if level == "none":
                from django.contrib import messages
                messages.warning(request, "You do not have access to that page.")
                return redirect(first_allowed_path(request.user))
            request.ams_page_key = key
            request.ams_can_write = level == "full"
            if write and not request.ams_can_write:
                from django.contrib import messages
                messages.warning(request, "View only - you cannot change records on this page.")
                return redirect("/mobiles/" if kind == "mobile" else "/assets/")
            return fn(request, *args, **kwargs)
        return wrapper
    return deco


def _page(kind):
    return "asset" if kind == "asset" else "mobile"


def _assets(kind, q="", status="", typ="", site_f=""):
    qs = Asset.objects.filter(kind=kind).select_related("type", "make", "category", "current_site", "purchase_site", "assigned_to", "vendor", "sim")
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(display_id__icontains=q) | Q(ams_asset_id__icontains=q) | Q(name__icontains=q) |
            Q(model__icontains=q) | Q(model_number__icontains=q) | Q(serial_number__icontains=q) |
            Q(make__name__icontains=q) | Q(type__name__icontains=q) | Q(assigned_to__name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if typ:
        qs = qs.filter(type__pk=typ)
    if site_f:
        qs = qs.filter(current_site__pk=site_f)
    return qs.order_by("display_id", "id")


def _tiles(qs):
    total = qs.count()
    in_stock = qs.exclude(assigned_to__isnull=False).exclude(status__in=["Retired / Scrapped", "Not Working"]).count()
    used = qs.filter(assigned_to__isnull=False, status="Assigned").count()
    out = qs.filter(status__in=["Retired / Scrapped", "Not Working"]).count()
    return {"total": total, "in_stock": in_stock, "used": used, "out": out}


def _event(request, asset, date_v, action, event_type, emp=None, status_label="", note="", accessories=None):
    LifecycleEvent.objects.create(
        item_kind=asset.kind, item_key=asset.ams_asset_id, item_label=print_asset_id(asset),
        date=date_v, action=action, event_type=event_type,
        emp=emp, emp_label=(emp.display_emp_id if emp else ""),
        emp_dept=(emp.department.name if emp and emp.department else ""),
        status_label=status_label or asset.status,
        accessories=accessories or [],
        note=note or "",
        actor_username=request.user.username,
        actor_role=getattr(getattr(request.user, "profile", None), "role", ""),
    )


def _clear_assignment(a):
    a.assigned_to = None
    a.assigned_to_sub = None
    a.assigned_sub_text = ""
    a.assigned_date = None


def _unlink_sim(a):
    if a.sim:
        sim = a.sim
        sim.linked_mobile = None
        sim.save()
        a.sim = None


@_ams_kind_view()
def asset_list(request, kind="asset"):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    typ = request.GET.get("type", "").strip()
    site_f = request.GET.get("site", "").strip()
    qs = _assets(kind, q, status, typ, site_f)
    types = AssetType.objects.all()
    categories = AssetCategory.objects.filter(used_on__in=[kind.capitalize(), "Both"])
    makes = AssetMake.objects.select_related("asset_type")
    sites = Site.objects.all()
    vendors = Vendor.objects.filter(active=True)
    emps = Employee.objects.filter(status="Active").select_related("department")
    sims_available = SimCard.objects.exclude(status__in=["Blocked", "Retired"]).filter(linked_mobile__isnull=True)
    ctx = {
        "kind": kind, "is_mobile": kind == "mobile", "rows": qs[:200],
        "tiles": _tiles(qs), "q": q, "status_f": status, "typ_f": typ, "site_f": site_f,
        "types": types, "categories": categories, "makes": makes, "sites": sites,
        "vendors": vendors, "emps": emps, "sims_available": sims_available,
        "replace_reasons": REPLACE_REASONS,
        "statuses": ASSET_STATUS,
        "accessories_all": Accessory.objects.select_related("asset_type"),
        "in_store_same_type": qs.filter(status="In Store", assigned_to__isnull=True)[:60],
        "action_modals": [
            ("m-action-return", "Return to Store", "return", "Return"),
            ("m-action-notworking", "Mark Not Working", "notworking", "Mark Not Working"),
            ("m-action-retire", "Retire / Scrap", "retire", "Retire / Scrap"),
        ],
        "import_report": request.session.get("import_report"),
        "can_write": request.ams_can_write,
        "title": "Mobile Master" if kind == "mobile" else "Asset Master",
    }
    if "import_report" in ctx and ctx["import_report"]:
        request.session.pop("import_report", None)
    return render(request, "assets.html", ctx)


@_ams_kind_view(write=True)
def mobile_list(request):
    """Alias routed to the same list with kind=mobile."""
    return asset_list(request, kind="mobile")


@_ams_kind_view(write=True)
@require_POST
def asset_save(request, kind="asset"):
    pk = request.POST.get("pk")
    a = Asset.objects.filter(pk=pk).first() if pk else None
    created = a is None
    if created:
        a = Asset(kind=kind)
        t = AssetType.objects.filter(pk=request.POST.get("type") or 0).first()
        ts = (t.shortform if t else "GEN") or "GEN"
        a.ams_asset_id = next_ams_asset_id(kind, ts)
        typed_display = (request.POST.get("display_id") or "").strip()
        if typed_display:
            a.display_id = typed_display
            a.is_legacy_id = True
        else:
            a.display_id = next_display_id(kind, ts)
    a.category = AssetCategory.objects.filter(pk=request.POST.get("category") or 0).first()
    a.type = AssetType.objects.filter(pk=request.POST.get("type") or 0).first()
    a.make = AssetMake.objects.filter(pk=request.POST.get("make") or 0).first()
    a.name = (request.POST.get("name") or "").strip()
    a.model = (request.POST.get("model") or "").strip()
    a.model_number = (request.POST.get("model_number") or "").strip()
    a.imei1 = (request.POST.get("imei1") or "").strip()
    a.imei2 = (request.POST.get("imei2") or "").strip()
    a.battery_no = (request.POST.get("battery_no") or "").strip()
    a.charger_no = (request.POST.get("charger_no") or "").strip()
    a.serial_number = (request.POST.get("serial_number") or "").strip()
    a.purchase_site = Site.objects.filter(pk=request.POST.get("purchase_site") or 0).first()
    a.current_site = Site.objects.filter(pk=request.POST.get("current_site") or 0).first()
    a.purchase_date = parse_date(request.POST.get("purchase_date"))
    a.warranty_end = parse_date(request.POST.get("warranty_end"))
    a.vendor = Vendor.objects.filter(pk=request.POST.get("vendor") or 0).first()
    cost = (request.POST.get("purchase_cost") or "").strip()
    a.purchase_cost = cost or None
    a.remarks = (request.POST.get("remarks") or "").strip()
    new_status = (request.POST.get("status") or a.status or "In Store").strip()
    if created:
        a.status = new_status if new_status in ("In Store", "In Repair") else ("In Store" if not new_status else new_status)
    else:
        prev = a.status
        a.status = new_status
        if new_status in CLEAR_ON_STATUS:
            _clear_assignment(a)
            _unlink_sim(a)
    a.save()
    if request.POST.getlist("accessories"):
        a.accessories.set(Accessory.objects.filter(pk__in=request.POST.getlist("accessories")))
    else:
        a.accessories.clear()
    if created:
        _event(request, a, a.purchase_date or date.today(), "Added to Inventory", "Other", status_label=a.status)
        log_activity(request.user, f"{'Mobile' if kind=='mobile' else 'Asset'} '{a.base_display_id}' added to inventory", "success", "Mobile Master" if kind == "mobile" else "Asset Master")
        messages.success(request, f"'{a.base_display_id}' added (Display ID: {a.display_id}).")
    else:
        log_activity(request.user, f"{'Mobile' if kind=='mobile' else 'Asset'} '{a.base_display_id}' updated", "info", "Mobile Master" if kind == "mobile" else "Asset Master")
        messages.success(request, f"'{a.base_display_id}' updated.")
    return redirect("/mobiles/" if kind == "mobile" else "/assets/")


@_ams_kind_view()
def asset_view(request, pk):
    a = get_object_or_404(Asset, pk=pk)
    history = LifecycleEvent.objects.filter(item_key=a.ams_asset_id).order_by("-date", "-id")
    spare_used = StockMovement.objects.filter(kind="sparepart", type="Used", asset=a)
    replaced_by = Asset.objects.filter(replaces_asset=a).first()
    return render(request, "asset_view.html", {
        "a": a, "history": history, "spare_used": spare_used, "replaced_by": replaced_by,
        "print_id": print_asset_id(a), "can_write": request.ams_can_write,
    })


@_ams_kind_view(write=True)
@require_POST
def asset_assign(request, pk):
    """Assign / Edit Assign / Reassign - one modal."""
    a = get_object_or_404(Asset, pk=pk)
    kind_label = "Mobile" if a.kind == "mobile" else "Asset"
    emp = Employee.objects.filter(pk=request.POST.get("assign_emp") or 0).first()
    if not emp:
        messages.error(request, "Direct Employee is required.")
        return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")
    sub = Employee.objects.filter(pk=request.POST.get("assign_sub") or 0).first()
    sub_text = (request.POST.get("assign_sub_text") or "").strip() if request.POST.get("assign_sub") == "__other__" else ""
    action_date = parse_date(request.POST.get("assign_date")) or date.today()
    prev_emp = a.assigned_to
    reassign = bool(prev_emp) and prev_emp != emp
    a.assigned_to = emp
    a.assigned_to_sub = sub
    a.assigned_sub_text = sub_text
    a.assigned_date = action_date
    a.status = "Assigned"
    # SIM link for mobiles
    if a.kind == "mobile":
        sim_choice = request.POST.get("assign_sim") or ""
        if sim_choice == "__unlink__":
            _unlink_sim(a)
        elif sim_choice:
            sim = SimCard.objects.filter(pk=sim_choice or 0).first()
            if sim and sim.linked_mobile and sim.linked_mobile != a:
                messages.warning(request, "That SIM Card is already linked to another mobile.")
            elif sim:
                a.sim = sim
                old = sim.linked_mobile
                sim.linked_mobile = a
                sim.save()
                if old and old != a:
                    old.sim = None
                    old.save()
    a.save()
    if request.POST.getlist("assign_accessories"):
        a.accessories.set(Accessory.objects.filter(pk__in=request.POST.getlist("assign_accessories")))
    else:
        a.accessories.clear()
    verb = "Reassigned" if reassign else ("Assignment updated" if prev_emp == emp else "Assigned")
    et = "Reassign" if reassign else "Assign"
    note_bits = []
    if sub_text:
        note_bits.append(f"Actual user (free text): {sub_text}")
    if a.kind == "mobile" and a.sim:
        note_bits.append(f"SIM {a.sim.mobile_number} linked")
    _event(request, a, action_date, verb, et, emp=emp,
           note=" | ".join(note_bits), accessories=[x.name for x in a.accessories.all()])
    log_activity(request.user, f"{kind_label} '{print_asset_id(a)}' {verb.lower()} to {emp.name}", "success", "Mobile Master" if a.kind == "mobile" else "Asset Master")
    messages.success(request, f"'{print_asset_id(a)}' {verb.lower()} to {emp.name} ({emp.display_emp_id}).")
    return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")


@_ams_kind_view(write=True)
@require_POST
def asset_return(request, pk):
    a = get_object_or_404(Asset, pk=pk)
    d = parse_date(request.POST.get("action_date")) or date.today()
    emp = a.assigned_to
    _clear_assignment(a)
    _unlink_sim(a)
    a.status = "In Store"
    a.return_date = d
    a.save()
    _event(request, a, d, "Returned", "Return", emp=emp, status_label="In Store",
           note=f"User exited or returned on {d:%d-%m-%Y}" if emp else "")
    log_activity(request.user, f"'{print_asset_id(a)}' returned to store", "info", "Mobile Master" if a.kind == "mobile" else "Asset Master")
    messages.success(request, f"'{print_asset_id(a)}' returned to store (recorded {d:%d-%m-%Y}).")
    return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")


@_ams_kind_view(write=True)
@require_POST
def asset_transfer(request, pk):
    a = get_object_or_404(Asset, pk=pk)
    site = Site.objects.filter(pk=request.POST.get("transfer_site") or 0).first()
    d = parse_date(request.POST.get("transfer_date")) or date.today()
    new_status = (request.POST.get("transfer_status") or "Transfer").strip()
    if not site:
        messages.error(request, "Transfer Site is required.")
        return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")
    emp = a.assigned_to
    if new_status in CLEAR_ON_STATUS:
        _clear_assignment(a)
        _unlink_sim(a)
    a.current_site = site
    a.status = new_status
    a.save()
    _event(request, a, d, f"Transferred to {site.name}", "Transfer", emp=emp, status_label=new_status)
    log_activity(request.user, f"'{print_asset_id(a)}' transferred to {site.name}", "info", "Mobile Master" if a.kind == "mobile" else "Asset Master")
    messages.success(request, f"'{print_asset_id(a)}' transferred to {site.name}.")
    return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")


@_ams_kind_view(write=True)
@require_POST
def asset_status_change(request, pk, action):
    """Not Working / Retire - Scrap."""
    a = get_object_or_404(Asset, pk=pk)
    d = parse_date(request.POST.get("action_date")) or date.today()
    emp = a.assigned_to
    status = "Not Working" if action == "notworking" else "Retired / Scrapped"
    _clear_assignment(a)
    _unlink_sim(a)
    a.status = status
    a.save()
    et = "Fault" if action == "notworking" else "Retire"
    _event(request, a, d, status, et, emp=emp, status_label=status)
    log_activity(request.user, f"'{print_asset_id(a)}' marked {status}", "warning", "Mobile Master" if a.kind == "mobile" else "Asset Master")
    messages.success(request, f"'{print_asset_id(a)}' marked {status}.")
    return redirect("/mobiles/" if a.kind == "mobile" else "/assets/")


@_ams_kind_view(write=True)
@require_POST
def asset_replace(request, pk):
    """Replace: issue a new (in-store) asset of the same type to the same user."""
    old = get_object_or_404(Asset, pk=pk)
    src = Asset.objects.filter(pk=request.POST.get("repl_source") or 0).first()
    d = parse_date(request.POST.get("repl_date")) or date.today()
    reason = (request.POST.get("repl_reason") or "").strip()
    note = (request.POST.get("repl_note") or "").strip()
    if not src or src.assigned_to or src.status != "In Store":
        messages.error(request, "Pick an In-Store replacement asset of the same type.")
        return redirect("/mobiles/" if old.kind == "mobile" else "/assets/")
    if not old.assigned_to:
        messages.error(request, "Only assigned assets can be replaced.")
        return redirect("/mobiles/" if old.kind == "mobile" else "/assets/")
    emp = old.assigned_to
    # move assignment to the new asset
    src.assigned_to = old.assigned_to
    src.assigned_to_sub = old.assigned_to_sub
    src.assigned_sub_text = old.assigned_sub_text
    src.assigned_date = d
    src.status = "Assigned"
    src.current_site = old.current_site
    src.replaces_asset = old
    src.replaces_reason = reason
    src.replaces_note = note
    src.replaces_purchase_date = old.purchase_date
    if old.kind == "mobile" and old.sim:
        src.sim = old.sim
        old.sim.linked_mobile = src
        old.sim.save()
        old.sim = None
    if request.POST.getlist("repl_accessories"):
        src.accessories.set(Accessory.objects.filter(pk__in=request.POST.getlist("repl_accessories")))
    src.save()
    _event(request, src, d, f"Assigned (Replacement for {print_asset_id(old)})", "Replace", emp=emp,
           note=f"Replacement for {print_asset_id(old)} on {d:%d-%m-%Y}. Reason: {reason or '-'}")
    _clear_assignment(old)
    old.status = "Replaced"
    old.save()
    _event(request, old, d, f"Replaced by {print_asset_id(src)}", "Replace", emp=emp, status_label="Replaced")
    log_activity(request.user, f"'{print_asset_id(old)}' replaced by '{print_asset_id(src)}' ({reason})", "warning", "Mobile Master" if old.kind == "mobile" else "Asset Master")
    messages.success(request, f"'{print_asset_id(src)}' issued as replacement for '{print_asset_id(old)}'.")
    return redirect("/mobiles/" if old.kind == "mobile" else "/assets/")


@_ams_kind_view(write=True)
@require_POST
def asset_swap(request, pk):
    """Mobile Swap: exchange holders between two phones (SIM move/keep)."""
    a = get_object_or_404(Asset, pk=pk)
    tgt = Asset.objects.filter(pk=request.POST.get("swap_target") or 0).first()
    d = parse_date(request.POST.get("swap_date")) or date.today()
    note = (request.POST.get("swap_note") or "").strip()
    sim_mode = request.POST.get("swap_sim_choice") or "move"
    if not tgt or not tgt.assigned_to:
        messages.error(request, "Pick an Assigned mobile to swap with.")
        return redirect("/mobiles/")
    a_emp = a.assigned_to
    tgt_emp = tgt.assigned_to
    # exchange assignment snapshots
    fields = ["assigned_to", "assigned_to_sub", "assigned_sub_text", "assigned_date", "assigned_sub_text"]
    a_emp_bak = (a.assigned_to, a.assigned_to_sub, a.assigned_sub_text, a.assigned_date)
    tgt_emp_bak = (tgt.assigned_to, tgt.assigned_to_sub, tgt.assigned_sub_text, tgt.assigned_date)
    a.assigned_to, a.assigned_to_sub, a.assigned_sub_text, a.assigned_date = tgt_emp_bak
    tgt.assigned_to, tgt.assigned_to_sub, tgt.assigned_sub_text, tgt.assigned_date = a_emp_bak
    if request.POST.getlist("swap_accessories"):
        tgt.accessories.set(Accessory.objects.filter(pk__in=request.POST.getlist("swap_accessories")))
    sim_note = ""
    if a.sim or tgt.sim:
        if sim_mode == "move":
            a.sim, tgt.sim = tgt.sim, a.sim
            if a.sim:
                a.sim.linked_mobile = a
                a.sim.save()
            if tgt.sim:
                tgt.sim.linked_mobile = tgt
                tgt.sim.save()
            sim_note = "SIM moved with holder"
        else:
            sim_note = "SIM kept in phone"
    a.save()
    tgt.save()
    _event(request, a, d, f"Swapped with {print_asset_id(tgt)}", "Swap", emp=a.assigned_to, note=f"{sim_note}{' - ' + note if note else ''}")
    _event(request, tgt, d, f"Swapped with {print_asset_id(a)}", "Swap", emp=tgt.assigned_to, note=f"{sim_note}{' - ' + note if note else ''}")
    log_activity(request.user, f"Mobiles '{print_asset_id(a)}' and '{print_asset_id(tgt)}' swapped ({sim_note})", "info", "Mobile Master")
    messages.success(request, "Mobiles swapped.")
    return redirect("/mobiles/")


# ---------------- CSV ----------------

def _export_headers(kind):
    heads = ["displayId", "amsAssetId", "type", "category", "make", "model", "name", "serialNumber"]
    if kind == "mobile":
        heads += ["modelNumber", "imei1", "imei2", "batteryNo", "chargerNo", "simMobileNo"]
    heads += ["purchaseSite", "currentSite", "purchaseDate", "warrantyEnd", "status",
              "assignedToEmpId", "assignedToSubordinateEmpId", "vendor", "purchaseCost", "remarks"]
    return heads


def _export_row(a):
    row = [a.display_id, a.ams_asset_id, a.type.name if a.type else "", a.category.name if a.category else "",
           a.make.name if a.make else "", a.model or a.model_number, a.name, a.serial_number]
    if a.kind == "mobile":
        row += [a.model_number, a.imei1, a.imei2, a.battery_no, a.charger_no, a.sim.mobile_number if a.sim else ""]
    row += [a.purchase_site.name if a.purchase_site else "", a.current_site.name if a.current_site else "",
            a.purchase_date.strftime("%d-%m-%Y") if a.purchase_date else "",
            a.warranty_end.strftime("%d-%m-%Y") if a.warranty_end else "",
            a.status, a.assigned_to.emp_id if a.assigned_to else "",
            (a.assigned_to_sub.emp_id if a.assigned_to_sub and a.assigned_to_sub.emp_id else (a.assigned_to_sub.ams_id if a.assigned_to_sub else "")),
            a.vendor.name if a.vendor else "", a.purchase_cost or "", a.remarks]
    return row


IMPORT_HEADERS = ["displayId", "type*", "category*", "make*", "model", "name", "serialNumber", "purchaseSite*", "currentSite*", "purchaseDate*", "warrantyEnd", "status", "assignedToEmpId", "vendor", "purchaseCost", "remarks"]
IMPORT_HEADERS_MOB = ["displayId", "type*", "category*", "make*", "modelNumber", "name", "serialNumber", "imei1", "imei2", "batteryNo", "chargerNo", "purchaseSite*", "currentSite*", "purchaseDate*", "warrantyEnd", "status", "assignedToEmpId", "vendor", "purchaseCost", "remarks"]


def asset_csv(request, kind, action):
    user = request.user
    if not user.is_authenticated:
        return redirect("/login/")
    from ..access import can_write
    slug = "Mobile_Master" if kind == "mobile" else "Asset_Master"
    headers = IMPORT_HEADERS_MOB if kind == "mobile" else IMPORT_HEADERS
    if action == "template":
        return csv_response(f"{slug}_import_template", headers, [])
    if action in ("export", "export-xlsx"):
        rows = [_export_row(a) for a in Asset.objects.filter(kind=kind).select_related("type", "category", "make", "purchase_site", "current_site", "assigned_to", "vendor", "sim")]
        if action == "export-xlsx":
            return xlsx_response(slug, _export_headers(kind), rows)
        return csv_response(slug, _export_headers(kind), rows)
    # import
    if not can_write(user, "mobile" if kind == "mobile" else "asset"):
        messages.warning(request, "View only - you cannot change records on this page.")
        return redirect("/mobiles/" if kind == "mobile" else "/assets/")
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV file to import.")
        return redirect("/mobiles/" if kind == "mobile" else "/assets/")
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
            tname = g("type*", "type")
            if not tname:
                raise ValueError("type is required")
            t = AssetType.objects.filter(name__iexact=tname).first()
            if t is None:
                raise ValueError(f"Asset Type '{tname}' not found in the master")
            cname = g("category*", "category")
            cat = AssetCategory.objects.filter(name__iexact=cname).first()
            if cname and cat is None:
                raise ValueError(f"Asset Category '{cname}' not found in the master")
            mname = g("make*", "make")
            mk = AssetMake.objects.filter(name__iexact=mname, asset_type=t).first() or AssetMake.objects.filter(name__iexact=mname).first()
            if mname and mk is None:
                raise ValueError(f"Make '{mname}' not found for type '{tname}'")
            disp = g("displayId", "displayId*")
            base = a = None
            if disp:
                a = Asset.objects.filter(kind=kind, display_id__iexact=disp, is_legacy_id=True).first() or \
                    Asset.objects.filter(kind=kind, ams_asset_id__iexact=disp).first()
            created = a is None
            if created:
                ts = t.shortform or "GEN"
                a = Asset(kind=kind)
                a.ams_asset_id = next_ams_asset_id(kind, ts)
                if disp:
                    a.display_id = disp
                    a.is_legacy_id = True
                else:
                    a.display_id = next_display_id(kind, ts)
            a.type = t
            a.category = cat
            a.make = mk
            a.name = g("name")
            a.model = g("model")
            a.model_number = g("modelNumber", "model")
            a.serial_number = g("serialNumber")
            a.imei1 = g("imei1")
            a.imei2 = g("imei2")
            a.battery_no = g("batteryNo")
            a.charger_no = g("chargerNo")
            for fld, col in (("purchase_site", "purchaseSite*"), ("current_site", "currentSite*")):
                sname = g(col, col.rstrip("*"))
                if sname:
                    s = Site.objects.filter(name__iexact=sname).first()
                    if s is None:
                        raise ValueError(f"Site '{sname}' not found in the master")
                    setattr(a, fld, s)
            pd_ = parse_date(g("purchaseDate*", "purchaseDate"))
            if created and not pd_:
                raise ValueError("purchaseDate is required (DD-MM-YYYY)")
            a.purchase_date = pd_ or a.purchase_date
            a.warranty_end = parse_date(g("warrantyEnd", "warrantyEnd*"))
            a.vendor = Vendor.objects.filter(name__iexact=g("vendor")).first()
            cost = g("purchaseCost")
            a.purchase_cost = cost or None
            a.remarks = g("remarks")
            st = g("status") or ("Assigned" if g("assignedToEmpId") else "In Store")
            a.status = st
            a.save()
            emp_code = g("assignedToEmpId", "assignedToEmpId*")
            if emp_code:
                emp = Employee.objects.filter(emp_id__iexact=emp_code).first() or Employee.objects.filter(ams_id__iexact=emp_code).first()
                if emp:
                    a.assigned_to = emp
                    a.assigned_date = a.purchase_date or date.today()
                    a.status = "Assigned"
                    a.save()
                    _event_from_import(request, a, emp)
            added += 1 if created else 0
            updated += 0 if created else 1
            report.append({"no": i, "result": "added" if created else "updated", "reason": ""})
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user, f"{'Mobile' if kind=='mobile' else 'Asset'} CSV import: {added} added, {updated} updated, {skipped} skipped", "info", "Asset Master")
    messages.success(request, f"Import finished: {added} added, {updated} updated, {skipped} skipped.")
    request.session["import_report"] = {"title": "Mobile Master" if kind == "mobile" else "Asset Master", "rows": report}
    return redirect("/mobiles/" if kind == "mobile" else "/assets/")


def _event_from_import(request, a, emp):
    LifecycleEvent.objects.create(
        item_kind=a.kind, item_key=a.ams_asset_id, item_label=print_asset_id(a),
        date=a.assigned_date or date.today(), action="Assigned", event_type="Assign",
        emp=emp, emp_label=emp.display_emp_id,
        emp_dept=emp.department.name if emp.department else "",
        status_label="Assigned", note="Imported", actor_username=request.user.username,
        actor_role=getattr(getattr(request.user, "profile", None), "role", ""),
    )
