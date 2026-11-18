"""
#-------------- Start Code for : ACCESS CONTROL (ams/access.py) ----------------

Roles, the page registry, the Role x Page access matrix and the decorators
that gate every view. Ported 1:1 from AMS-Test (dummy-data.js sections 10
and role-access logic).

Level semantics: "none" = hidden, "view" = open but cannot save,
"full" = read and write.
#-------------- End of the code : ACCESS CONTROL (ams/access.py) ----------------
"""

from functools import wraps
from django.shortcuts import redirect

# Exact role strings and rank order from the original portal
ROLES = ["Standard User", "Viewer (Read-Only)", "Admin", "Super Root", "Supreme Root"]
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}

# Hard role gates that override the matrix (as in the original portal)
SUPREME_ONLY_PAGES = {"accessRights", "roleAccess"}
SUPER_PLUS_PAGES = {"log"}          # Super Root + Supreme Root only
HIDDEN_PAGES = {"sqlBackup"}        # registered but disabled for every role


def page_label(key):
    return PAGE_REGISTRY.get(key, (key, ""))[0]


# ---------------------------------------------------------------------------
# PAGE REGISTRY: key -> (label, section). Sections: "Pages" and "Reports".
# ---------------------------------------------------------------------------
PAGE_REGISTRY = {
    "dashboard": ("Dashboard", "Pages"),
    "employee": ("Employee Master", "Pages"),
    "asset": ("Asset Master", "Pages"),
    "mobile": ("Mobile Master", "Pages"),
    "simCards": ("SIM Card Master", "Pages"),
    "consumable": ("Consumable Master", "Pages"),
    "spareParts": ("Spare Parts Master", "Pages"),
    "accessory": ("Accessory Master", "Pages"),
    "assetDistribution": ("Asset Distribution", "Pages"),
    "vendors": ("Vendor Master", "Pages"),
    "reports": ("Report Master", "Pages"),
    "labelPassPrint": ("Label/Pass Print Master", "Pages"),
    "settings": ("Settings", "Pages"),
    "systemAdmin": ("System Administrator Master", "Pages"),
    "company": ("Company Master", "Pages"),
    "userMaster": ("User Master", "Pages"),
    "assetType": ("Asset Type Master", "Pages"),
    "assetMake": ("Asset Make Master", "Pages"),
    "assetCategory": ("Asset Category Master", "Pages"),
    "site": ("Site Master", "Pages"),
    "department": ("Department Master", "Pages"),
    "designation": ("Designation Master", "Pages"),
    "simOperator": ("SIM Operator Master", "Pages"),
    "simPlan": ("SIM Plan Master", "Pages"),
    "consumableCategory": ("Consumable Category Master", "Pages"),
    "unitOfMeasure": ("Unit of Measure Master", "Pages"),
    "sparePartCategory": ("Spare Part Category Master", "Pages"),
    "vendorCategory": ("Vendor Category Master", "Pages"),
    "printTerms": ("Print Terms Master", "Pages"),
    "accessRights": ("Access Rights Control Master", "Pages"),
    "roleAccess": ("Role Access Master", "Pages"),
    "log": ("Log Report", "Pages"),
    "sqlBackup": ("SQL Database Backup", "Pages"),
    "report.assetLifecycle": ("Report: Asset Lifecycle", "Reports"),
    "report.assetIssue": ("Report: Asset Issue Form", "Reports"),
    "report.assetHandover": ("Report: Asset Handover Form", "Reports"),
    "report.consumableRestock": ("Report: Consumable Restock", "Reports"),
    "report.consumableUsed": ("Report: Consumable Used", "Reports"),
    "report.sparePartsRestock": ("Report: Spare Parts Restock", "Reports"),
    "report.sparePartsUsed": ("Report: Spare Parts Used", "Reports"),
    "report.assetDistribution": ("Report: Asset Distribution", "Reports"),
}

PAGE_KEYS = list(PAGE_REGISTRY.keys())
EDITABLE_KEYS = [k for k in PAGE_KEYS if k not in HIDDEN_PAGES]

# ---------------------------------------------------------------------------
# RECOMMENDED ROLE x PAGE MATRIX (matches docs/AMS-Role-Access-Matrix.xlsx)
# Columns: Standard User / Viewer (Read-Only) / Admin / Super Root / Supreme Root
# ---------------------------------------------------------------------------
_R = ROLES


def _row(std, viewer, admin, sup, supreme):
    return dict(zip(_R, [std, viewer, admin, sup, supreme]))


RECOMMENDED_MATRIX = {
    "dashboard": _row("full", "view", "full", "full", "full"),
    "employee": _row("full", "view", "full", "full", "full"),
    "asset": _row("full", "view", "full", "full", "full"),
    "mobile": _row("full", "view", "full", "full", "full"),
    "simCards": _row("full", "view", "full", "full", "full"),
    "consumable": _row("full", "view", "full", "full", "full"),
    "spareParts": _row("full", "view", "full", "full", "full"),
    "accessory": _row("full", "view", "full", "full", "full"),
    "assetDistribution": _row("full", "view", "full", "full", "full"),
    "vendors": _row("full", "view", "full", "full", "full"),
    "reports": _row("full", "view", "full", "full", "full"),
    "settings": _row("full", "full", "full", "full", "full"),
    "systemAdmin": _row("none", "none", "full", "full", "full"),
    "userMaster": _row("none", "none", "full", "full", "full"),
    "company": _row("none", "none", "none", "full", "full"),
    "assetType": _row("none", "none", "full", "full", "full"),
    "assetMake": _row("none", "none", "full", "full", "full"),
    "assetCategory": _row("none", "none", "full", "full", "full"),
    "site": _row("none", "none", "full", "full", "full"),
    "department": _row("none", "none", "full", "full", "full"),
    "designation": _row("none", "none", "full", "full", "full"),
    "simOperator": _row("none", "none", "full", "full", "full"),
    "simPlan": _row("none", "none", "full", "full", "full"),
    "consumableCategory": _row("none", "none", "full", "full", "full"),
    "unitOfMeasure": _row("none", "none", "full", "full", "full"),
    "sparePartCategory": _row("none", "none", "full", "full", "full"),
    "vendorCategory": _row("none", "none", "full", "full", "full"),
    "printTerms": _row("none", "none", "full", "full", "full"),
    "labelPassPrint": _row("none", "none", "full", "full", "full"),
    "accessRights": _row("none", "none", "none", "none", "full"),
    "roleAccess": _row("none", "none", "none", "none", "full"),
    "log": _row("none", "none", "none", "full", "full"),
    "sqlBackup": _row("none", "none", "none", "none", "none"),
    "report.assetLifecycle": _row("full", "view", "full", "full", "full"),
    "report.assetIssue": _row("full", "view", "full", "full", "full"),
    "report.assetHandover": _row("full", "view", "full", "full", "full"),
    "report.consumableRestock": _row("full", "view", "full", "full", "full"),
    "report.consumableUsed": _row("full", "view", "full", "full", "full"),
    "report.sparePartsRestock": _row("full", "view", "full", "full", "full"),
    "report.sparePartsUsed": _row("full", "view", "full", "full", "full"),
    "report.assetDistribution": _row("full", "view", "full", "full", "full"),
}

# ---------------------------------------------------------------------------
# SIDEBAR NAV (page id, label, registry key). Sections render as headers.
# ---------------------------------------------------------------------------
NAV_ITEMS = [
    ("Main", [
        ("dashboard", "Dashboard", "dashboard"),
    ]),
    ("People", [
        ("employees", "Employees", "employee"),
    ]),
    ("Inventory", [
        ("assets", "Assets", "asset"),
        ("mobiles", "Mobiles", "mobile"),
        ("asset-distribution", "Asset Distribution", "assetDistribution"),
        ("sim-cards", "SIM Cards", "simCards"),
        ("consumables", "Consumables", "consumable"),
        ("spare-parts", "Spare Parts", "spareParts"),
        ("accessories", "Accessories", "accessory"),
    ]),
    ("Admin", [
        ("vendors", "Vendors", "vendors"),
        ("reports", "Reports", "reports"),
        ("system-admin", "System Admin", "systemAdmin"),
        ("user-master", "User Master", "userMaster"),
        ("settings", "Settings", "settings"),
    ]),
]


def _matrix_from_db():
    """Load the saved Role Access matrix (seeded from RECOMMENDED_MATRIX)."""
    from .models import RoleAccess
    matrix = {key: {r: "none" for r in ROLES} for key in PAGE_KEYS}
    for ra in RoleAccess.objects.all():
        matrix.setdefault(ra.page_key, {})[ra.role] = ra.level
    # Hard overrides (defense in depth, as in the original)
    for key in SUPREME_ONLY_PAGES | HIDDEN_PAGES:
        matrix[key] = {r: ("full" if key in SUPREME_ONLY_PAGES and r == "Supreme Root" else "none") for r in ROLES}
    for r in ROLES:
        matrix["log"][r] = "full" if r in ("Super Root", "Supreme Root") else "none"
    return matrix


def role_access_level(matrix, page_key, role):
    return matrix.get(page_key, {}).get(role, "none")


def user_role(user):
    prof = getattr(user, "profile", None)
    if prof and prof.role in ROLE_RANK:
        return prof.role
    return "Standard User"


def allowed_pages_map(profile):
    """Per-user override: list = full for members; dict = per-key levels; None = role default."""
    raw = profile.allowed_pages if getattr(profile, "allowed_pages", None) else None
    return raw


def access_level_for(user, page_key):
    """Resolve the access level for a user on a registry page key."""
    if page_key not in PAGE_REGISTRY:
        return "full"
    role = user_role(user)
    # 1) hard gates
    if page_key in HIDDEN_PAGES:
        return "none"
    if page_key in SUPREME_ONLY_PAGES and role != "Supreme Root":
        return "none"
    if page_key in SUPER_PLUS_PAGES and role not in ("Super Root", "Supreme Root"):
        return "none"
    prof = getattr(user, "profile", None)
    override = allowed_pages_map(prof) if prof else None
    if isinstance(override, dict) and page_key in override:
        return override[page_key] if override[page_key] in ("none", "view", "full") else "full"
    if isinstance(override, list):
        return "full" if page_key in override else "none"
    # 2) role matrix
    return role_access_level(_matrix_from_db(), page_key, role)


def can_write(user, page_key):
    return access_level_for(user, page_key) == "full"


def sidebar_for(user):
    """NAV_ITEMS filtered to pages the user can open (level != none)."""
    out = []
    for section, items in NAV_ITEMS:
        visible = []
        for page_id, label, key in items:
            if access_level_for(user, key) != "none":
                visible.append((page_id, label, key))
        if visible:
            out.append((section, visible))
    return out


def first_allowed_path(user):
    from .navpaths import NAV_PATHS
    for section, items in sidebar_for(user):
        for page_id, label, key in items:
            return NAV_PATHS.get(page_id, "/dashboard/")
    return "/dashboard/"


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def ams_view(page_key, write=False):
    """
    Gate a view behind a registry page key. none -> redirect to the first
    page the user can open; view -> request.ams_can_write = False.
    """
    def deco(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("/login/")
            level = access_level_for(request.user, page_key)
            if level == "none":
                from django.contrib import messages
                messages.warning(request, "You do not have access to that page.")
                return redirect(first_allowed_path(request.user))
            request.ams_page_key = page_key
            request.ams_can_write = level == "full"
            if write and not request.ams_can_write:
                from django.contrib import messages
                from django.http import HttpResponse
                if request.headers.get("HX-Request"):
                    resp = HttpResponse('<div class="toast toast-error">View only - you cannot change records on this page.</div>')
                    resp.status_code = 403
                    return resp
                messages.warning(request, "View only - you cannot change records on this page.")
                return redirect(first_allowed_path(request.user))
            return fn(request, *args, **kwargs)
        return wrapper
    return deco


def ams_role(min_roles):
    """Gate a view to specific roles (used for Supreme-only actions)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("/login/")
            if user_role(request.user) not in min_roles:
                from django.contrib import messages
                messages.warning(request, "Only %s can do that." % " or ".join(min_roles))
                return redirect(first_allowed_path(request.user))
            return fn(request, *args, **kwargs)
        return wrapper
    return deco
