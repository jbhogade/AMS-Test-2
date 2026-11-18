"""
#-------------- Start Code for : ACTIVITY LOG (ams/activity.py) ----------------
Writes the append-only audit trail consumed by the Dashboard timeline,
the bell and the Log Report (visibility split lives in views/logs.py).
#-------------- End of the code : ACTIVITY LOG (ams/activity.py) ----------------
"""
from .models import ActivityLog, UserProfile


def actor_meta(user):
    role = "System"
    username = ""
    if user and getattr(user, "is_authenticated", False):
        username = user.username
        prof = getattr(user, "profile", None)
        role = prof.role if prof and prof.role else "Standard User"
    return username, role


def log_activity(user, message, type="info", page=""):
    username, role = actor_meta(user)
    entry = ActivityLog.objects.create(
        actor_username=username, actor_role=role, page=page or "", type=type or "info", message=message,
    )
    # keep the log capped at 1000 entries like the original portal
    ids = ActivityLog.objects.order_by("-time", "-id").values_list("id", flat=True)[1000:]
    if ids:
        ActivityLog.objects.filter(id__in=list(ids)).delete()
    return entry


def ensure_profile(user):
    prof = getattr(user, "profile", None)
    if prof is None:
        prof = UserProfile.objects.create(user=user)
    return prof
