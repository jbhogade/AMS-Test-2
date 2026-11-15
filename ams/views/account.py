"""My Profile (display fields + change password) and Settings (preferences)."""

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_view, user_role, PAGE_REGISTRY
from ..activity import log_activity
from ..models import ActivityLog, PortalPref, UserProfile, StockMovement

THEMES = [
    ("graphite", "Graphite Teal", "dark", "Signature dark slate with a teal accent - the AMS-Test-2 default."),
    ("midnight", "Midnight", "dark", "Very dark, high contrast."),
    ("slate-blue", "Slate Blue", "dark", "Corporate blue-grey."),
    ("forest", "Forest", "dark", "Deep green."),
    ("plum", "Plum", "dark", "Dark violet."),
    ("gold", "Dark Gold", "dark", "Warm gold accent."),
    ("ice", "Ice", "light", "Cool pale blue."),
    ("paper", "Paper", "light", "Bright warm light theme."),
    ("contrast", "Contrast", "dark", "Pure black, maximum contrast."),
]


@login_required
def profile(request):
    prof = request.user.profile
    return render(request, "profile.html", {"prof": prof, "can_write": True})


@login_required
@require_POST
def profile_save(request):
    prof = request.user.profile
    prof.display_name = (request.POST.get("display_name") or "").strip()[:200]
    prof.email = (request.POST.get("email") or "").strip()
    prof.contact_no = (request.POST.get("contact_no") or "").strip()[:50]
    prof.gender = (request.POST.get("gender") or "").strip()
    prof.dob = request.POST.get("dob") or None
    prof.address = (request.POST.get("address") or "").strip()[:500]
    if prof.dob == "":
        prof.dob = None
    prof.save()
    log_activity(request.user, "Profile details updated", "success", "My Profile")
    messages.success(request, "Profile saved.")
    return redirect("/profile/")


@login_required
@require_POST
def profile_password(request):
    cur = request.POST.get("current") or ""
    new = request.POST.get("new") or ""
    confirm = request.POST.get("confirm") or ""
    if not cur or not new:
        messages.error(request, "Current and new passwords are required.")
        return redirect("/profile/")
    if len(new) < 6:
        messages.error(request, "New password must be at least 6 characters.")
        return redirect("/profile/")
    if new != confirm:
        messages.error(request, "New password and confirmation do not match.")
        return redirect("/profile/")
    user = authenticate(request, username=request.user.username, password=cur)
    if user is None:
        messages.error(request, "Current password is incorrect.")
        return redirect("/profile/")
    request.user.set_password(new)
    request.user.save()
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, request.user)
    log_activity(request.user, "Password changed", "warning", "My Profile")
    messages.success(request, "Password changed.")
    return redirect("/profile/")


@ams_view("settings")
def settings(request):
    prof = request.user.profile
    counts = {
        "activity": ActivityLog.objects.count(),
        "moves": StockMovement.objects.count(),
    }
    return render(request, "settings.html", {
        "prof": prof, "themes": THEMES, "counts": counts,
        "role": user_role(request.user),
        "page_labels": PAGE_REGISTRY,
        "can_write": request.ams_can_write,
    })


@ams_view("settings", write=True)
@require_POST
def settings_save(request):
    prof = request.user.profile
    tab = request.POST.get("tab", "appearance")
    if tab == "appearance":
        t = request.POST.get("theme")
        if t:
            prof.theme = t
        fs = request.POST.get("font_size")
        if fs in ("sm", "md", "lg"):
            prof.font_size = fs
        prof.save()
        messages.success(request, "Appearance saved.")
    elif tab == "general":
        portal_name = (request.POST.get("portal_name") or "").strip()
        if portal_name:
            PortalPref.objects.update_or_create(key="portal_name", defaults={"value": portal_name[:60]})
        else:
            messages.error(request, "Portal name cannot be empty.")
            return redirect("/settings/")
        ps = request.POST.get("page_size")
        if ps in ("10", "20", "50", "100"):
            prof.page_size = int(ps)
        prof.save()
        messages.success(request, "General preferences saved.")
    elif tab == "notifications":
        prof.toast_enabled = bool(request.POST.get("toast_enabled"))
        prof.save()
        if request.POST.get("clear_activity"):
            role = user_role(request.user)
            if role in ("Super Root", "Supreme Root"):
                ActivityLog.objects.all().delete()
                log_activity(request.user, "Activity log cleared (from Settings)", "warning", "Settings")
                messages.success(request, "Activity log cleared.")
            else:
                messages.warning(request, "Only Super Root or Supreme Root can clear the activity log.")
        else:
            messages.success(request, "Notification preferences saved.")
    return redirect("/settings/")
