"""
#-------------- Start Code for : EMPLOYEE MASTER (ams/views/employees.py) ------

CRUD, CSV template/export/import with per-row Import Report, Exit with
immutable snapshot (returns all direct holdings), Reactivate, Assign Report
printing hand-off. AMS ID: EMP-<deptShort>-NNNNNN (max+1).
#-------------- End of the code : EMPLOYEE MASTER (ams/views/employees.py) ------
"""

import json
from datetime import date

from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from ..access import ams_view
from ..activity import log_activity
from ..ids import dept_short, next_ams_id
from ..models import Employee, Department, Site, Asset, SimCard, ExitRecord
from ..tools import parse_date, read_csv_upload, csv_response, xlsx_response

CSV_HEADERS = ["empId*", "name*", "dept*", "designation*", "site", "reportsTo", "managerId", "contact", "email", "status"]
EXIT_REASONS = ["Resignation", "Retirement", "Termination", "Contract End", "Transfer (Internal)", "Medical / Personal Reasons", "Other"]
FACILITIES = [
    ("email", "Email Login"), ("erp", "ERP Login"), ("vpn", "VPN Access"),
    ("card", "Building Access Card"), ("phone", "Phone / Extension"), ("share", "Shared Drive / Mail Group"),
]


def _emp_rows(request, q=None, dept=None, status=None):
    qs = Employee.objects.select_related("department", "site", "manager")
    if q:
        qs = qs.filter(
            models_q(q)
        )
    if dept:
        qs = qs.filter(department__name=dept)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("name")


def models_q(q):
    from django.db.models import Q
    return Q(name__icontains=q) | Q(emp_id__icontains=q) | Q(ams_id__icontains=q) | Q(designation__icontains=q)


@ams_view("employee")
def employees(request):
    q = request.GET.get("q", "").strip()
    dept = request.GET.get("dept", "").strip()
    status = request.GET.get("status", "").strip()
    emps = _emp_rows(request, q, dept, status)
    import_report = request.session.pop("import_report", None)
    sites = Site.objects.all()
    desigs = sorted(set(Employee.objects.exclude(designation="").values_list("designation", flat=True)))
    return render(request, "employees.html", {
        "emps": emps, "q": q, "dept_f": dept, "status_f": status,
        "departments": Department.objects.all(),
        "sites": sites, "desigs": desigs,
        "exit_reasons": EXIT_REASONS,
        "facilities": FACILITIES,
        "import_report": import_report,
        "can_write": request.ams_can_write,
    })


@ams_view("employee")
def employee_view(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    assets = Asset.objects.filter(kind="asset", assigned_to=emp).select_related("type", "current_site")
    mobiles = Asset.objects.filter(kind="mobile", assigned_to=emp).select_related("type", "current_site")
    sims = SimCard.objects.filter(assigned_to=emp).select_related("operator", "plan")
    subordinates = emp.subordinates.filter(status="Active")
    exit_record = ExitRecord.objects.filter(employee=emp).order_by("-id").first()
    return render(request, "employee_view.html", {
        "emp": emp, "assets": assets, "mobiles": mobiles, "sims": sims,
        "subordinates": subordinates, "exit_record": exit_record,
        "can_write": request.ams_can_write,
    })


def _quickadd_lookups(post):
    """Employee form quick-adds missing departments/sites silently."""
    dept_name = (post.get("department_name") or "").strip()
    if dept_name and not Department.objects.filter(name__iexact=dept_name).exists():
        Department.objects.create(name=dept_name, shortform=(post.get("department_short") or dept_name[:4]).upper()[:4])
    site_name = (post.get("site_name") or "").strip()
    if site_name and not Site.objects.filter(name__iexact=site_name).exists():
        Site.objects.create(name=site_name, shortform=(post.get("site_short") or site_name[:4]).upper()[:4])


@ams_view("employee", write=True)
@require_POST
def employee_save(request):
    pk = request.POST.get("pk")
    _quickadd_lookups(request.POST)
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Full Name is required.")
        return redirect("/employees/")
    dept = Department.objects.filter(pk=request.POST.get("department") or 0).first()
    if pk:
        emp = get_object_or_404(Employee, pk=pk)
        created = False
    else:
        if not dept:
            messages.error(request, "Department is required.")
            return redirect("/employees/")
        emp = Employee()
        emp.ams_id = next_ams_id(dept.shortform or "GEN")
        emp.status = "Active"
        created = True
    emp.name = name
    emp.emp_id = (request.POST.get("emp_id") or "").strip() or (emp.emp_id or "")
    if not emp.emp_id:
        emp.emp_id = emp.ams_id
    emp.department = dept
    emp.designation = (request.POST.get("designation") or "").strip()
    emp.site = Site.objects.filter(pk=request.POST.get("site") or 0).first()
    mgr = Employee.objects.filter(pk=request.POST.get("manager") or 0).first()
    if mgr and mgr.pk == emp.pk:
        mgr = None
    emp.manager = mgr
    emp.contact = (request.POST.get("contact") or "").strip()
    emp.email = (request.POST.get("email") or "").strip()
    emp.save()
    if created:
        log_activity(request.user, f"Employee '{emp.name}' ({emp.display_emp_id}) added", "success", "Employee Master")
        messages.success(request, f"Employee '{emp.name}' added with AMS ID {emp.ams_id}.")
    else:
        log_activity(request.user, f"Employee '{emp.name}' ({emp.display_emp_id}) updated", "info", "Employee Master")
        messages.success(request, f"Employee '{emp.name}' updated.")
    return redirect("/employees/")


@ams_view("employee", write=True)
@require_POST
def employee_exit(request, pk):
    """Exit: snapshot + return all direct holdings + re-point subordinates."""
    emp = get_object_or_404(Employee, pk=pk)
    exit_date = parse_date(request.POST.get("exit_date")) or date.today()
    reason = (request.POST.get("exit_reason") or "").strip()
    remarks = (request.POST.get("exit_remarks") or "").strip()
    disabled = request.POST.getlist("facility_revoke")
    na = request.POST.getlist("facility_na")
    facilities_disabled = [label for key, label in FACILITIES if key in disabled]
    facilities_na = [label for key, label in FACILITIES if key in na]
    incharge = Employee.objects.filter(pk=request.POST.get("exit_incharge") or 0).first() or emp.manager

    direct_assets = []
    for a in Asset.objects.filter(kind="asset", assigned_to=emp):
        direct_assets.append({
            "assetId": a.base_display_id, "fullId": a.ams_asset_id, "type": a.type.name if a.type else "",
            "makeModel": a.make_model, "site": a.current_site.name if a.current_site else "",
            "accessories": [x.name for x in a.accessories.all()], "remarks": a.remarks,
            "returnDate": str(exit_date),
        })
        a.status = "In Store"
        a.assigned_to = None
        a.assigned_to_sub = None
        a.assigned_sub_text = ""
        a.assigned_date = None
        a.return_date = exit_date
        a.save()
    direct_mobiles = []
    for m in Asset.objects.filter(kind="mobile", assigned_to=emp):
        direct_mobiles.append({
            "assetId": m.base_display_id, "fullId": m.ams_asset_id, "type": m.type.name if m.type else "",
            "makeModel": m.make_model, "imei1": m.imei1, "imei2": m.imei2,
            "batteryNo": m.battery_no, "chargerNo": m.charger_no,
            "simMobileNo": m.sim.mobile_number if m.sim else "",
            "site": m.current_site.name if m.current_site else "", "status": "In Store",
            "accessories": [x.name for x in m.accessories.all()], "returnDate": str(exit_date),
        })
        if m.sim:
            m.sim.linked_mobile = None
            m.sim.save()
            m.sim = None
        m.status = "In Store"
        m.assigned_to = None
        m.assigned_to_sub = None
        m.assigned_sub_text = ""
        m.assigned_date = None
        m.return_date = exit_date
        m.save()
    direct_sims = []
    for s in SimCard.objects.filter(assigned_to=emp):
        direct_sims.append({
            "simId": s.sim_id, "mobileNumber": s.mobile_number,
            "operator": s.operator.name if s.operator else "", "plan": s.plan.name if s.plan else "",
            "status": "In Store", "personal": s.personal_mobile,
            "returnDate": str(exit_date),
        })
        s.status = "In Store"
        s.assigned_to = None
        s.assigned_to_sub = None
        s.assigned_sub_text = ""
        s.assigned_date = None
        s.linked_mobile = None
        s.personal_mobile = False
        s.return_date = exit_date
        s.save()

    # subordinate team transfer info (record only; re-point managers)
    team = {"amsId": incharge.ams_id, "empId": incharge.display_emp_id, "name": incharge.name} if incharge else None
    for sub in emp.subordinates.filter(manager=emp):
        sub.manager = incharge
        sub.save()

    from ..tools import next_code
    er = ExitRecord.objects.create(
        exit_id=next_code(ExitRecord, "EXIT-", 6, "exit_id"),
        employee=emp, ams_id=emp.ams_id, emp_id=emp.display_emp_id, emp_name=emp.name,
        emp_dept=emp.department.name if emp.department else "", emp_designation=emp.designation,
        exit_date=exit_date, exit_reason=reason, exit_remarks=remarks,
        facilities_disabled=facilities_disabled, facilities_na=facilities_na,
        direct_assets=direct_assets, direct_mobiles=direct_mobiles, direct_sims=direct_sims,
        team_transferred_to=team,
    )
    emp.status = "Inactive"
    emp.exit_date = exit_date
    emp.exit_reason = reason
    emp.exit_remarks = remarks
    emp.save()
    log_activity(request.user, f"Employee '{emp.name}' exited ({reason}) on {exit_date:%d-%m-%Y}; {len(direct_assets)} asset(s) returned", "warning", "Employee Master")
    messages.success(request, f"'{emp.name}' marked Inactive. All direct holdings were returned to store (Exit Record {er.exit_id}).")
    return redirect("/employees/")


@ams_view("employee", write=True)
@require_POST
def employee_reactivate(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    emp.status = "Active"
    emp.reactivated_date = date.today()
    emp.reactivation_remarks = (request.POST.get("reactivation_remarks") or "").strip()
    emp.save()
    er = ExitRecord.objects.filter(employee=emp).order_by("-id").first()
    if er:
        er.reactivated = True
        er.save()
    log_activity(request.user, f"Employee '{emp.name}' reactivated", "success", "Employee Master")
    messages.success(request, f"'{emp.name}' is Active again.")
    return redirect("/employees/")


def employee_csv(request, action):
    user = request.user
    if not user.is_authenticated:
        return redirect("/login/")
    from ..access import can_write
    if action in ("template", "export", "export-xlsx"):
        if action == "template":
            return csv_response("Employee_import_template", CSV_HEADERS, [])
        emps = Employee.objects.select_related("department", "manager")
        rows = []
        for e in emps:
            rows.append([
                e.emp_id or e.ams_id, e.name, e.department.name if e.department else "",
                e.designation, e.site.name if e.site else "",
                e.manager.name if e.manager else "", e.manager.emp_id if e.manager and e.manager.emp_id else (e.manager.ams_id if e.manager else ""),
                e.contact, e.email, e.status,
            ])
        if action == "export-xlsx":
            return xlsx_response("Employee_Master", CSV_HEADERS, rows)
        return csv_response("Employee_Master", CSV_HEADERS, rows)
    # import
    if not can_write(user, "employee"):
        messages.warning(request, "View only - you cannot change records on this page.")
        return redirect("/employees/")
    file = request.FILES.get("file")
    if file is None:
        messages.error(request, "Choose a CSV file to import.")
        return redirect("/employees/")
    headers, rows = read_csv_upload(file)
    report = []
    added = updated = skipped = 0
    for i, row in enumerate(rows, start=1):
        try:
            name = (row.get("name*") or row.get("name") or "").strip()
            dept_name = (row.get("dept*") or row.get("dept") or "").strip()
            desig = (row.get("designation*") or row.get("designation") or "").strip()
            if not name or not dept_name or not desig:
                raise ValueError("name, dept and designation are required")
            dept = Department.objects.filter(name__iexact=dept_name).first()
            if dept is None:
                dept = Department.objects.create(name=dept_name, shortform=dept_name[:4].upper())
            site_name = (row.get("site") or "").strip()
            site = Site.objects.filter(name__iexact=site_name).first() if site_name else None
            emp_id = (row.get("empId*") or row.get("empId") or "").strip() or f"EMP-{Employee.objects.count() + 1:06d}"
            emp = Employee.objects.filter(emp_id__iexact=emp_id).first() or Employee.objects.filter(ams_id__iexact=emp_id).first()
            created = emp is None
            if created:
                emp = Employee(ams_id=next_ams_id(dept.shortform or "GEN"))
                emp.emp_id = emp_id
            emp.name = name
            emp.department = dept
            emp.designation = desig
            emp.site = site
            emp.contact = (row.get("contact") or "").strip()
            emp.email = (row.get("email") or "").strip()
            st = (row.get("status") or "Active").strip()
            emp.status = "Active" if st.lower() == "active" else "Inactive"
            # manager by reportsTo (name) or managerId (emp id)
            mgr_name = (row.get("reportsTo") or "").strip()
            mgr_id = (row.get("managerId") or "").strip()
            mgr = None
            if mgr_id:
                mgr = Employee.objects.filter(emp_id__iexact=mgr_id).first() or Employee.objects.filter(ams_id__iexact=mgr_id).first()
            if mgr is None and mgr_name:
                mgr = Employee.objects.filter(name__iexact=mgr_name).first()
            if mgr and mgr.pk != emp.pk:
                emp.manager = mgr
            emp.save()
            added += created and 1 or 0
            updated += (not created) and 1 or 0
            report.append({"no": i, "result": "added" if created else "updated", "reason": ""})
        except Exception as e:
            skipped += 1
            report.append({"no": i, "result": "error", "reason": str(e)})
    log_activity(request.user, f"Employee CSV import: {added} added, {updated} updated, {skipped} skipped", "info", "Employee Master")
    messages.success(request, f"Import finished: {added} added, {updated} updated, {skipped} skipped.")
    request.session["import_report"] = {"title": "Employee Master", "rows": report}
    return redirect("/employees/")
