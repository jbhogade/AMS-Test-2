"""
#-------------- Start Code for : SIM CARD MASTER (ams/views/simcards.py) -------

Auto SIM-NNNNNN ids, assign/reassign with Used-In-Mobile picker (Personal
SIM support), Return / Block / Retire, two-way link with Mobiles, history,
CSV template/export/import, SIM Card Issue Form print hand-off.
#-------------- End of the code for : SIM CARD MASTER (ams/views/simcards.py) ---
"""

from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..tools import parse_date, read_csv_upload, csv_response, xlsx_response, next_code
from ..models import (
    SimCard, SimOperator, SimPlan, Site, Vendor, Employee, Asset, LifecycleEvent, SIM_STATUS,
)

CSV_HEADERS = ["simId", "iccid", "mobileNumber*", "operator", "plan", "status", "site", "activationDate", "vendor", "cost", "remarks"]


def _sim_event(request, sim, d, action, et, emp=None, note=""):
    LifecycleEvent.objects.create(
        item_kind="sim", item_key=sim.sim_id, item_label=sim.sim_id,
        date=d, action=action, event_type=et, emp=emp,
        emp_label=(emp.display_emp_id if emp else ""),
        emp_dept=(emp.department.name if emp and emp.department else ""),
        status_label=sim.status, note=note,
        actor_username=request.user.username,
        actor_role=getattr(getattr(request.user, "profile", None), "role", ""),
    )


def _unlink_sim_from_mobile(sim):
    if sim.linked_mobile:
        m = sim.linked_mobile
        m.sim = None
        m.save()
        sim.linked_mobile = None


@ams_view("simCards")
def sim_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    qs = SimCard.objects.select_related("operator", "plan", "site", "vendor", "assigned_to", "linked_mobile")
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(sim_id__icontains=q) | Q(mobile_number__icontains=q) | Q(iccid__icontains=q) |
                       Q(operator__name__icontains=q) | Q(assigned_to__name__icontains=q))
    if status:
        qs = qs.filter(status=status)
    tiles = {
        "total": SimCard.objects.count(),
        "in_store": SimCard.objects.filter(status="In Store").count(),
        "issued": SimCard.objects.filter(status="Issued").count(),
        "blocked": SimCard.objects.filter(status__in=["Blocked", "Retired"]).count(),
    }
    return render(request, "simcards.html", {
        "rows": qs[:200], "tiles": tiles, "q": q, "status_f": status,
        "statuses": SIM_STATUS,
        "simple_modals": [
            ("m-sim-return", "Return SIM to Store", "Return"),
            ("m-sim-block", "Block SIM", "Block"),
            ("m-sim-retire", "Retire SIM", "Retire"),
        ],
        "import_report": request.session.pop("import_report", None),
        "operators": SimOperator.objects.all(), "plans": SimPlan.objects.all(),
        "sites": Site.objects.all(), "vendors": Vendor.objects.filter(active=True),
        "emps": Employee.objects.filter(status="Active").select_related("department"),
        "eligible_mobiles": Asset.objects.filter(kind="mobile").exclude(status__in=["Retired / Scrapped", "Not Working", "Replaced"]),
        "can_write": request.ams_can_write,
    })


@ams_view("simCards", write=True)
@require_POST
def sim_save(request):
    pk = request.POST.get("pk")
    sim = SimCard.objects.filter(pk=pk).first() if pk else None
    created = sim is None
    number = (request.POST.get("mobile_number") or "").strip()
    if not number:
        messages.error(request, "Mobile Number is required.")
        return redirect("/sim-cards/")
    if created:
        dup = SimCard.objects.filter(mobile_number=number).exists()
        if dup:
            messages.error(request, f"Mobile Number '{number}' already exists.")
            return redirect("/sim-cards/")
        sim = SimCard(sim_id=next_code(SimCard, "SIM-", 6, "sim_id"))
    sim.iccid = (request.POST.get("iccid") or "").strip()
    sim.mobile_number = number
    op_name = (request.POST.get("operator_name") or "").strip()
    if op_name:
        op, _ = SimOperator.objects.get_or_create(name=op_name)
        sim.operator = op
    plan_name = (request.POST.get("plan_name") or "").strip()
    if plan_name:
        pl, _ = SimPlan.objects.get_or_create(name=plan_name)
        sim.plan = pl
    sim.status = (request.POST.get("status") or sim.status or "In Store").strip()
    sim.site = Site.objects.filter(pk=request.POST.get("site") or 0).first()
    sim.activation_date = parse_date(request.POST.get("activation_date"))
    sim.vendor = Vendor.objects.filter(pk=request.POST.get("vendor") or 0).first()
    cost = (request.POST.get("cost") or "").strip()
    sim.cost = cost or None
    sim.remarks = (request.POST.get("remarks") or "").strip()
    sim.save()
    log_activity(request.user, f"SIM '{sim.sim_id}' ({sim.mobile_number}) {'added' if created else 'updated'}", "success" if created else "info", "SIM Card Master")
    messages.success(request, f"SIM '{sim.sim_id}' {'added' if created else 'updated'}.")
    return redirect("/sim-cards/")


@ams_view("simCards", write=True)
@require_POST
def sim_assign(request, pk):
    sim = get_object_or_404(SimCard, pk=pk)
    emp = Employee.objects.filter(pk=request.POST.get("sim_assign_emp") or 0).first()
    if not emp:
        messages.error(request, "Direct Employee is required.")
        return redirect("/sim-cards/")
    d = parse_date(request.POST.get("sim_assign_date")) or date.today()
    sub = Employee.objects.filter(pk=request.POST.get("sim_assign_sub") or 0).first()
    sub_text = (request.POST.get("sim_assign_sub_text") or "").strip() if request.POST.get("sim_assign_sub") == "__other__" else ""
    remarks = (request.POST.get("sim_assign_remarks") or "").strip()
    prev_emp = sim.assigned_to
    reassign = bool(prev_emp) and prev_emp != emp
    mobile_choice = request.POST.get("sim_assign_mobile") or ""
    sim.assigned_to = emp
    sim.assigned_to_sub = sub
    sim.assigned_sub_text = sub_text
    sim.assigned_date = d
    sim.status = "Issued"
    # Used In Mobile
    if mobile_choice == "__personal__":
        _unlink_sim_from_mobile(sim)
        sim.personal_mobile = True
        sim.linked_mobile = None
    elif mobile_choice:
        mob = Asset.objects.filter(kind="mobile", pk=mobile_choice or 0).first()
        if mob:
            if sim.linked_mobile and sim.linked_mobile != mob:
                sim.linked_mobile.sim = None
                sim.linked_mobile.save()
            sim.personal_mobile = False
            sim.linked_mobile = mob
            # unlink from any other phone
            Asset.objects.filter(sim=sim).exclude(pk=mob.pk).update(sim=None)
            mob.sim = sim
            mob.save()
            # linking an In-Store phone issues it to the same employee ("Linked from SIM Card Master")
            if not mob.assigned_to:
                mob.assigned_to = emp
                mob.assigned_to_sub = sub
                mob.assigned_sub_text = sub_text
                mob.assigned_date = d
                mob.status = "Assigned"
                mob.save()
                LifecycleEvent.objects.create(
                    item_kind="mobile", item_key=mob.ams_asset_id,
                    item_label=mob.base_display_id, date=d, action="Assigned - New",
                    event_type="Assign", emp=emp, emp_label=emp.display_emp_id,
                    emp_dept=emp.department.name if emp.department else "",
                    status_label="Assigned", note="Linked from SIM Card Master",
                    actor_username=request.user.username,
                    actor_role=getattr(getattr(request.user, "profile", None), "role", ""),
                )
    else:
        _unlink_sim_from_mobile(sim)
        sim.personal_mobile = False
    sim.save()
    used_in = "Personal Mobile" if sim.personal_mobile else (sim.linked_mobile.base_display_id if sim.linked_mobile else "-")
    verb = "Reassigned" if reassign else ("Assignment updated" if prev_emp == emp else "Assigned")
    et = "Reassign" if reassign else "Assign"
    _sim_event(request, sim, d, verb, et, emp=emp, note=f"{remarks} | Used in: {used_in}".strip(" |"))
    log_activity(request.user, f"SIM '{sim.sim_id}' {verb.lower()} to {emp.name}", "success", "SIM Card Master")
    messages.success(request, f"SIM '{sim.sim_id}' {verb.lower()} to {emp.name} (Used in: {used_in}).")
    return redirect("/sim-cards/")


@ams_view("simCards", write=True)
@require_POST
def sim_return(request, pk):
    sim = get_object_or_404(SimCard, pk=pk)
    d = date.today()
    emp = sim.assigned_to
    _unlink_sim_from_mobile(sim)
    sim.personal_mobile = False
    sim.assigned_to = None
    sim.assigned_to_sub = None
    sim.assigned_sub_text = ""
    sim.assigned_date = None
    sim.status = "In Store"
    sim.return_date = d
    sim.save()
    _sim_event(request, sim, d, "Returned", "Return", emp=emp)
    log_activity(request.user, f"SIM '{sim.sim_id}' returned to store", "info", "SIM Card Master")
    messages.success(request, f"SIM '{sim.sim_id}' returned to store.")
    return redirect("/sim-cards/")


@ams_view("simCards", write=True)
@require_POST
def sim_block(request, pk):
    sim = get_object_or_404(SimCard, pk=pk)
    d = date.today()
    sim.status = "Blocked"
    sim.save()
    _sim_event(request, sim, d, "Blocked", "Fault", emp=sim.assigned_to)
    log_activity(request.user, f"SIM '{sim.sim_id}' blocked", "warning", "SIM Card Master")
    messages.success(request, f"SIM '{sim.sim_id}' blocked (assignment kept).")
    return redirect("/sim-cards/")


@ams_view("simCards", write=True)
@require_POST
def sim_retire(request, pk):
    sim = get_object_or_404(SimCard, pk=pk)
    d = date.today()
    emp = sim.assigned_to
    _unlink_sim_from_mobile(sim)
    sim.assigned_to = None
    sim.assigned_to_sub = None
    sim.assigned_sub_text = ""
    sim.assigned_date = None
    sim.status = "Retired"
    sim.save()
    _sim_event(request, sim, d, "Retired", "Retire", emp=emp)
    log_activity(request.user, f"SIM '{sim.sim_id}' retired", "warning", "SIM Card Master")
    messages.success(request, f"SIM '{sim.sim_id}' retired.")
    return redirect("/sim-cards/")


def sim_csv(request, action):
    user = request.user
    if not user.is_authenticated:
        return redirect("/login/")
    from ..access import can_write
    if action == "template":
        return csv_response("SIM_Card_import_template", CSV_HEADERS, [])
    if action in ("export", "export-xlsx"):
        rows = []
        for s in SimCard.objects.select_related("operator", "plan", "site", "vendor", "assigned_to"):
            rows.append([s.sim_id, s.iccid, s.mobile_number, s.operator.name if s.operator else "",
                         s.plan.name if s.plan else "", s.status, s.site.name if s.site else "",
                         s.activation_date.strftime("%d-%m-%Y") if s.activation_date else "",
                         s.vendor.name if s.vendor else "", s.cost or "", s.remarks])
        if action == "export-xlsx":
            return xlsx_response("SIM_Card_Master", CSV_HEADERS, rows)
        return csv_response("SIM_Card_Master", CSV_HEADERS, rows)
    if not can_write(user, "simCards"):
        messages.warning(request, "View only - you cannot change records on this page.")
        return redirect("/sim-cards/")
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV file to import.")
        return redirect("/sim-cards/")
    _, rows = read_csv_upload(file)
    report = []
    added = updated = skipped = 0
    for i, row in enumerate(rows, start=1):
        try:
            number = (row.get("mobileNumber*") or row.get("mobileNumber") or "").strip()
            if not number:
                raise ValueError("mobileNumber is required")
            sim = SimCard.objects.filter(mobile_number=number).first()
            created = sim is None
            if created:
                sim = SimCard(sim_id=(row.get("simId") or "").strip() or next_code(SimCard, "SIM-", 6, "sim_id"))
            elif (row.get("simId") or "").strip():
                sim.sim_id = row.get("simId").strip()
            sim.iccid = (row.get("iccid") or "").strip()
            sim.mobile_number = number
            op = (row.get("operator") or "").strip()
            sim.operator = SimOperator.objects.get_or_create(name=op)[0] if op else sim.operator
            pl = (row.get("plan") or "").strip()
            sim.plan = SimPlan.objects.get_or_create(name=pl)[0] if pl else sim.plan
            sim.status = (row.get("status") or "In Store").strip()
            sn = (row.get("site") or "").strip()
            sim.site = Site.objects.filter(name__iexact=sn).first() if sn else None
            sim.activation_date = parse_date((row.get("activationDate") or "").strip())
            sim.vendor = Vendor.objects.filter(name__iexact=(row.get("vendor") or "").strip()).first()
            cost = (row.get("cost") or "").strip()
            sim.cost = cost or None
            sim.remarks = (row.get("remarks") or "").strip()
            sim.save()
            added += 1 if created else 0
            updated += 0 if created else 1
            report.append({"no": i, "result": "added" if created else "updated", "reason": ""})
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user, f"SIM CSV import: {added} added, {updated} updated, {skipped} skipped", "info", "SIM Card Master")
    messages.success(request, f"Import finished: {added} added, {updated} updated, {skipped} skipped.")
    request.session["import_report"] = {"title": "SIM Card Master", "rows": report}
    return redirect("/sim-cards/")
