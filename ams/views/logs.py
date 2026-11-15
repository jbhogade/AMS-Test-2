"""Log Report: activity audit trail with visibility split (Super Root+)."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_role, user_role
from ..activity import log_activity
from ..models import ActivityLog
from ..tools import csv_response, xlsx_response


def _visible(user):
    role = user_role(user)
    qs = ActivityLog.objects.all()
    if role == "Supreme Root":
        pass
    elif role == "Super Root":
        qs = qs.exclude(actor_role="Supreme Root")
    else:
        qs = qs.none()
    return qs, role


@ams_role(["Super Root", "Supreme Root"])
def logs(request):
    qs, role = _visible(request.user)
    q = request.GET.get("q", "").strip()
    role_f = request.GET.get("actor_role", "").strip()
    page_f = request.GET.get("page", "").strip()
    from_d = request.GET.get("from", "").strip()
    to_d = request.GET.get("to", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(message__icontains=q) | Q(page__icontains=q))
    if role_f:
        qs = qs.filter(actor_role=role_f)
    if page_f:
        qs = qs.filter(page=page_f)
    if from_d:
        qs = qs.filter(time__date__gte=from_d)
    if to_d:
        qs = qs.filter(time__date__lte=to_d)
    rows = qs[:500]
    roles_present = sorted(set(ActivityLog.objects.values_list("actor_role", flat=True)))
    pages_present = sorted(set(ActivityLog.objects.values_list("page", flat=True)) - {""})
    ctx = {
        "rows": rows, "q": q, "role_f": role_f, "page_f": page_f,
        "from_f": from_d, "to_f": to_d,
        "roles_present": roles_present, "pages_present": pages_present,
        "role": role,
    }
    if request.GET.get("hub"):
        ctx["hub"] = True
        return render(request, "partials/logs_content.html", ctx)
    return render(request, "logs.html", ctx)


@ams_role(["Super Root", "Supreme Root"])
def logs_export(request, fmt):
    qs, _ = _visible(request.user)
    rows = [[e.time.strftime("%d-%m-%Y %H:%M"), e.actor_role or "-", e.page or "-", e.type, e.message]
            for e in qs[:5000]]
    headers = ["Time", "Actor Role", "Page", "Type", "Message"]
    if fmt == "xlsx":
        return xlsx_response("Log_Report", headers, rows)
    return csv_response("Log_Report", headers, rows)


@ams_role(["Supreme Root"])
@require_POST
def logs_clear(request):
    ActivityLog.objects.all().delete()
    log_activity(request.user, "Activity log cleared", "warning", "Log Report")
    messages.success(request, "Activity log cleared.")
    return redirect("/logs/")
