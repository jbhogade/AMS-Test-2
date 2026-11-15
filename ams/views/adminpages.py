"""
#-------------- Start Code for : ADMIN PAGES (ams/views/adminpages.py) ---------

System Administrator hub, Company Master (single record, feeds letterheads),
User Master (rank-guarded accounts with password + required Site),
Access Rights Control Master (per-user page checklist) and
Role Access Master (Role x Page matrix editor).
#-------------- End of the code for : ADMIN PAGES (ams/views/adminpages.py) ----
"""

from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from ..access import (
    ams_view, ams_role, ROLES, ROLE_RANK, PAGE_REGISTRY, EDITABLE_KEYS,
    RECOMMENDED_MATRIX, SUPREME_ONLY_PAGES, user_role, access_level_for,
)
from ..activity import ensure_profile, log_activity
from ..models import UserProfile, RoleAccess, Company, ReportPrefs, PortalPref, Employee, Site
from ..master_registry import master_list


# ---------------- SYSTEM ADMIN HUB ----------------

@ams_view("systemAdmin")
def system_admin(request):
    tabs = []
    for key, cfg in master_list():
        tabs.append(("master", key, cfg["title"], access_level_for(request.user, master_registry_key(key)) != "none"))
    extra = [
        ("company", "Company Master", access_level_for(request.user, "company") != "none"),
        ("vendors", "Vendor Master", access_level_for(request.user, "vendors") != "none"),
        ("accessories", "Accessory Master", access_level_for(request.user, "accessory") != "none"),
        ("accessRights", "Access Rights Control Master", access_level_for(request.user, "accessRights") != "none"),
        ("roleAccess", "Role Access Master", access_level_for(request.user, "roleAccess") != "none"),
        ("log", "Log Report", access_level_for(request.user, "log") != "none"),
        ("labelPassPrint", "Label/Pass Print Master", access_level_for(request.user, "labelPassPrint") != "none"),
    ]
    return render(request, "system_admin.html", {"master_tabs": tabs, "extra_tabs": extra})


def master_registry_key(master_key):
    from ..master_registry import REGISTRY_KEY_BY_MASTER
    return REGISTRY_KEY_BY_MASTER.get(master_key, "systemAdmin")


# ---------------- COMPANY MASTER ----------------

@ams_view("company")
def company(request):
    ctx = {
        "obj": Company.get_solo(), "prefs": ReportPrefs.get_solo(),
        "can_write": request.ams_can_write,
    }
    if request.GET.get("hub"):
        ctx["hub"] = True
        return render(request, "partials/company_panel.html", ctx)
    return render(request, "company.html", ctx)


@ams_view("company", write=True)
@require_POST
def company_save(request):
    c = Company.get_solo()
    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Company Name is required.")
        return redirect("/company/")
    c.name = name
    c.slogan = (request.POST.get("slogan") or "").strip()[:200]
    c.address = (request.POST.get("address") or "").strip()
    c.hr_admin_contact = (request.POST.get("hr_admin_contact") or "").strip()
    c.head_title = (request.POST.get("head_title") or "").strip()
    c.head_contact = (request.POST.get("head_contact") or "").strip()
    if request.FILES.get("logo"):
        c.logo = request.FILES["logo"]
    if request.POST.get("remove_logo"):
        c.logo = None
    if request.FILES.get("banner"):
        c.banner = request.FILES["banner"]
    if request.POST.get("remove_banner"):
        c.banner = None
    c.save()
    log_activity(request.user, "Company Master details updated", "success", "Company Master")
    messages.success(request, "Company details saved.")
    return redirect("/company/")


# ---------------- USER MASTER ----------------

@ams_view("userMaster")
def users(request):
    role = user_role(request.user)
    rank = ROLE_RANK[role]
    visible = [u for u in UserProfile.objects.select_related("user", "linked_employee", "site")
               if ROLE_RANK.get(u.role, -1) <= rank]
    if role != "Supreme Root":
        visible = [u for u in visible if u.role != "Supreme Root"]
    allowed_roles = ROLES[: rank + 1]
    hint = {
        "Supreme Root": "Signed in as Supreme Root - full control: can create Supreme Root accounts and delete Super Root accounts.",
        "Super Root": "Signed in as Super Root - Supreme Root accounts are hidden. Cannot create Supreme Root accounts or delete Super Root accounts.",
        "Admin": "Signed in as Admin - Super Root and Supreme Root accounts are hidden. Cannot create or assign Super Root or Supreme Root roles.",
    }.get(role, "Signed in as a limited role - Super Root and Supreme Root accounts are hidden. Some actions may be restricted by access rights.")
    return render(request, "users.html", {
        "profiles": visible, "allowed_roles": allowed_roles,
        "employees": [(e.pk, f"{e.name} ({e.display_emp_id})") for e in Employee.objects.filter(status="Active")],
        "sites": Site.objects.all(),
        "role": role, "rank": rank, "hint": hint,
        "can_write": request.ams_can_write,
        "page_keys": EDITABLE_KEYS,
        "page_labels": PAGE_REGISTRY,
    })


@ams_view("userMaster", write=True)
@require_POST
def user_save(request):
    role = user_role(request.user)
    rank = ROLE_RANK[role]
    username = (request.POST.get("username") or "").strip()
    new_role = (request.POST.get("role") or "").strip()
    site_id = (request.POST.get("site") or "").strip()
    password = request.POST.get("password") or ""
    pk = request.POST.get("pk")
    if new_role not in ROLE_RANK or ROLE_RANK[new_role] > rank:
        messages.error(request, "You cannot assign a role above your own.")
        return redirect("/users/")
    if not site_id:
        messages.error(request, "Site is required.")
        return redirect("/users/")
    site = Site.objects.filter(pk=site_id or 0).first()
    if pk:
        prof = get_object_or_404(UserProfile, pk=pk)
        if ROLE_RANK.get(prof.role, -1) > rank:
            messages.error(request, "You cannot edit an account above your own role.")
            return redirect("/users/")
        if prof.role == "Supreme Root" and role != "Supreme Root":
            messages.error(request, "Only a Supreme Root user can edit a Supreme Root account.")
            return redirect("/users/")
        user = prof.user
        prof.role = new_role
        prof.site = site
        prof.linked_employee = Employee.objects.filter(pk=request.POST.get("linked_employee") or 0).first()
        prof.email = (request.POST.get("email") or "").strip()
        prof.remarks = (request.POST.get("remarks") or "").strip()
        prof.save()
        user.is_active = bool(request.POST.get("active", "1"))
        if password:
            user.set_password(password)
        user.save()
        log_activity(request.user, f"User account '{username or user.username}' updated (role {new_role})", "info", "User Master")
        messages.success(request, f"Account '{user.username}' updated.")
    else:
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("/users/")
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect("/users/")
        user = User.objects.create_user(username=username, password=password)
        user.is_active = True
        user.save()
        prof = ensure_profile(user)
        prof.role = new_role
        prof.site = site
        prof.linked_employee = Employee.objects.filter(pk=request.POST.get("linked_employee") or 0).first()
        prof.email = (request.POST.get("email") or "").strip()
        prof.remarks = (request.POST.get("remarks") or "").strip()
        prof.save()
        log_activity(request.user, f"User account '{username}' created (role {new_role})", "success", "User Master")
        messages.success(request, f"Account '{username}' created with role {new_role}.")
    return redirect("/users/")


@ams_view("userMaster", write=True)
@require_POST
def user_toggle(request, pk):
    prof = get_object_or_404(UserProfile, pk=pk)
    role = user_role(request.user)
    if ROLE_RANK.get(prof.role, -1) > ROLE_RANK[role]:
        messages.error(request, "You cannot change an account above your own role.")
        return redirect("/users/")
    prof.user.is_active = not prof.user.is_active
    prof.user.save()
    messages.success(request, f"'{prof.user.username}' is now {'Active' if prof.user.is_active else 'Inactive'}.")
    return redirect("/users/")


@ams_view("userMaster", write=True)
@require_POST
def user_delete(request, pk):
    prof = get_object_or_404(UserProfile, pk=pk)
    role = user_role(request.user)
    if prof.role == "Supreme Root":
        messages.warning(request, "Supreme Root accounts cannot be deleted from this screen.")
        return redirect("/users/")
    if ROLE_RANK.get(prof.role, -1) > ROLE_RANK[role]:
        messages.warning(request, "You cannot delete an account above your own role.")
        return redirect("/users/")
    if prof.role == "Super Root" and role != "Supreme Root":
        messages.warning(request, "Only a Supreme Root user can delete a Super Root account.")
        return redirect("/users/")
    label = prof.user.username
    prof.user.delete()
    log_activity(request.user, f"User account '{label}' deleted", "danger", "User Master")
    messages.success(request, f"Account '{label}' deleted.")
    return redirect("/users/")


# ---------------- ACCESS RIGHTS (Supreme Root only) ----------------

@ams_view("accessRights")
def access_rights(request):
    rank = ROLE_RANK[user_role(request.user)]
    profiles = [p for p in UserProfile.objects.select_related("user", "site") if ROLE_RANK.get(p.role, -1) <= rank]
    total = len(EDITABLE_KEYS)
    rows = []
    for p in profiles:
        override = p.allowed_pages
        if isinstance(override, dict):
            n = sum(1 for k in EDITABLE_KEYS if override.get(k, "none") != "none")
            custom = True
        elif isinstance(override, list):
            n = len([k for k in override if k in PAGE_REGISTRY])
            custom = True
        else:
            n = sum(1 for k in EDITABLE_KEYS if RECOMMENDED_MATRIX.get(k, {}).get(p.role, "none") != "none")
            custom = False
        rows.append({"prof": p, "count": n, "custom": custom})
    ctx = {
        "rows": rows, "total": total, "role": user_role(request.user),
        "page_keys": EDITABLE_KEYS, "page_labels": PAGE_REGISTRY,
        "supreme_only": SUPREME_ONLY_PAGES,
        "can_write": request.ams_can_write,
    }
    if request.GET.get("hub"):
        ctx["hub"] = True
        return render(request, "partials/access_rights_content.html", ctx)
    return render(request, "access_rights.html", ctx)


@ams_view("accessRights")
def access_rights_edit(request, pk):
    prof = get_object_or_404(UserProfile, pk=pk)
    override = prof.allowed_pages
    current = {}
    if isinstance(override, dict):
        current = {k: override.get(k, "none") for k in EDITABLE_KEYS}
    elif isinstance(override, list):
        current = {k: ("full" if k in override else "none") for k in EDITABLE_KEYS}
    else:
        current = {k: RECOMMENDED_MATRIX.get(k, {}).get(prof.role, "none") for k in EDITABLE_KEYS}
    pages_block = [k for k in EDITABLE_KEYS if PAGE_REGISTRY[k][1] == "Pages"]
    reports_block = [k for k in EDITABLE_KEYS if PAGE_REGISTRY[k][1] == "Reports"]
    import json
    return render(request, "partials/access_rights_modal.html", {
        "prof": prof, "current": current,
        "pages_block": pages_block, "reports_block": reports_block,
        "page_labels": PAGE_REGISTRY, "role": user_role(request.user),
        "supreme_only": SUPREME_ONLY_PAGES,
        "levels_json": json.dumps(current),
    })


@ams_view("accessRights", write=True)
@require_POST
def access_rights_save(request, pk):
    import json as _json
    prof = get_object_or_404(UserProfile, pk=pk)
    levels = {}
    try:
        levels = {str(k): v for k, v in _json.loads(request.POST.get("levels_json", "{}")).items()}
    except Exception:
        levels = {}
    for k in EDITABLE_KEYS:
        levels.setdefault(k, "none")
    # role-locked keys re-added on top (as in the original)
    if prof.role in ("Super Root", "Supreme Root"):
        levels["log"] = "full"
    if prof.role == "Supreme Root":
        levels["accessRights"] = "full"
        levels["roleAccess"] = "full"
    prof.allowed_pages = levels
    prof.save()
    n = sum(1 for v in levels.values() if v != "none")
    log_activity(request.user, f"Access rights updated for '{prof.user.username}': {n}/{len(EDITABLE_KEYS)} pages", "warning", "Access Rights Control Master")
    messages.success(request, f"Access rights updated for {prof.user.username}: {n} / {len(EDITABLE_KEYS)} pages.")
    return redirect("/access-rights/")


@ams_view("accessRights", write=True)
@require_POST
def access_rights_reset(request, pk):
    prof = get_object_or_404(UserProfile, pk=pk)
    prof.allowed_pages = None
    prof.save()
    messages.success(request, f"'{prof.user.username}' reset to Role Default access.")
    return redirect("/access-rights/")


# ---------------- ROLE ACCESS (Supreme Root only) ----------------

@ams_view("roleAccess")
def role_access(request):
    from ..access import _matrix_from_db
    matrix = _matrix_from_db()
    pages_block = [k for k in EDITABLE_KEYS if PAGE_REGISTRY[k][1] == "Pages"]
    reports_block = [k for k in EDITABLE_KEYS if PAGE_REGISTRY[k][1] == "Reports"]
    rows = []
    for k in pages_block + reports_block:
        rows.append({
            "key": k,
            "label": PAGE_REGISTRY[k][0],
            "is_report": PAGE_REGISTRY[k][1] == "Reports",
            "levels": {r: matrix.get(k, {}).get(r, "none") for r in ROLES},
        })
    return render(request, "role_access.html", {
        "rows": rows, "roles": ROLES, "role": user_role(request.user),
        "page_labels": PAGE_REGISTRY,
        "can_write": request.ams_can_write,
        "hub": request.GET.get("hub"),
    })


@ams_view("roleAccess", write=True)
@require_POST
def role_access_save(request):
    for k in EDITABLE_KEYS:
        for r in ROLES:
            level = request.POST.get(f"level_{k}_{r}", "none")
            RoleAccess.objects.update_or_create(page_key=k, role=r, defaults={"level": level})
    log_activity(request.user, "Role Access matrix updated", "warning", "Role Access Master")
    messages.success(request, "Role Access matrix saved.")
    return redirect("/role-access/")


@ams_view("roleAccess", write=True)
@require_POST
def role_access_reset(request):
    RoleAccess.objects.all().delete()
    for key, row in RECOMMENDED_MATRIX.items():
        for r, level in row.items():
            RoleAccess.objects.create(page_key=key, role=r, level=level)
    log_activity(request.user, "Role Access matrix reset to suggested defaults", "info", "Role Access Master")
    messages.success(request, "Matrix reset to the suggested defaults.")
    return redirect("/role-access/")
