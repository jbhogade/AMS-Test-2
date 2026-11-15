"""Login / logout views (the login.html gate of the original portal)."""

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from ..activity import ensure_profile, log_activity


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/dashboard/")
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, "login.html")
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_active:
            messages.error(request, "Invalid User ID or Password.")
            return render(request, "login.html")
        login(request, user)
        ensure_profile(user)
        log_activity(user, f"{user.username} signed in", "success", "Login")
        return redirect("/dashboard/")
    return render(request, "login.html")


def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request.user, f"{request.user.username} signed out", "info", "Login")
    logout(request)
    return redirect("/login/")
