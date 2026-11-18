"""Context processor: injects everything the shell/base template needs."""

from django.conf import settings as dj_settings

from .access import sidebar_for, user_role, access_level_for, NAV_ITEMS
from .models import Company, PortalPref, ActivityLog
from .views.account import THEMES
from .navpaths import NAV_PATHS

MASTER_HREFS = {
    "assetType": "/masters/asset-type/", "assetMake": "/masters/asset-make/",
    "assetCategory": "/masters/asset-category/", "site": "/masters/site/",
    "department": "/masters/department/", "designation": "/masters/designation/",
    "simOperator": "/masters/sim-operator/", "simPlan": "/masters/sim-plan/",
    "consumableCategory": "/masters/consumable-category/",
    "unitOfMeasure": "/masters/unit-of-measure/",
    "sparePartCategory": "/masters/spare-part-category/",
    "vendorCategory": "/masters/vendor-category/", "printTerms": "/masters/print-terms/",
}


def _href(page_id, key):
    if page_id in NAV_PATHS:
        return NAV_PATHS[page_id]
    return MASTER_HREFS.get(key, "/dashboard/")


def _db_engine_label():
    """Human-readable label of where the portal data is stored right now."""
    db = dj_settings.DATABASES["default"]
    engine = db["ENGINE"]
    if engine.endswith("sqlite3"):
        name = db["NAME"]
        try:
            name = str(name)          # Path object in SQLite mode
        except Exception:
            pass
        return f"SQLite ({name})"
    host = db.get("HOST") or "localhost"
    port = db.get("PORT") or "1433"
    return f"SQL Server ({db['NAME']} @ {host},{port})"


def context_injector(request):
    user = getattr(request, "user", None)
    pref = PortalPref.objects.filter(key="portal_name").first()
    ctx = {
        "portal_name": (pref.value if pref else "Asset Manager"),
        "company": Company.get_solo(),
        "themes": THEMES,
        "db_engine_label": _db_engine_label(),
    }
    if user and user.is_authenticated:
        prof = getattr(user, "profile", None)
        nav = []
        for section, items in sidebar_for(user):
            enriched = [(pid, label, _href(pid, key)) for pid, label, key in items]
            nav.append((section, enriched))
        ctx.update({
            "nav_sections": nav,
            "ams_role": user_role(user),
            "ams_profile": prof,
            "notif_count": ActivityLog.objects.count() if (prof and prof.role in ("Super Root", "Supreme Root")) else 0,
            "current_path": request.path,
        })
    else:
        ctx.update({"nav_sections": [], "ams_role": "", "notif_count": 0, "current_path": ""})
    return ctx
