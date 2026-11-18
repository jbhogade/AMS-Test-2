"""
#-------------- Start Code for : PRINT ENGINE (ams/views/prints.py) ------------

Server-rendered A4 print documents that mirror the .pf-* engine of the
original portal: Asset Issue Form (AIF), Asset Handover Form (AHF),
SIM/Mobile Issue Forms, Laptop Gate Pass cards and the 7x16 A4 Display-ID
sticker sheet. Letterhead = Company Master + Report Appearance prefs
(company address prints on Gate Pass ONLY).
#-------------- End of the code for : PRINT ENGINE (ams/views/prints.py) ------------
"""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404

from ..access import access_level_for
from ..models import (
    Asset, SimCard, Employee, ExitRecord, LifecycleEvent, PrintTerm, Company,
    ReportPrefs, FormCounter,
)
from ..ids import print_asset_id

CONDITION_OPTS = ["Good", "Needs Repair / Service", "Damaged"]


def _letterhead(title, form_no, accent="issue"):
    c = Company.get_solo()
    prefs = ReportPrefs.get_solo()
    return {"company": c, "prefs": prefs, "title": title, "form_no": form_no,
            "accent": accent, "today": date.today().strftime("%d-%m-%Y")}


def _form_no(prefix):
    fc, _ = FormCounter.objects.get_or_create(prefix=prefix)
    fc.last += 1
    fc.save()
    return f"{prefix}-{str(fc.last).zfill(6)}"


def _print_terms(form_name):
    terms = list(PrintTerm.objects.filter(active=True).filter(
        _used_on_q(form_name)
    ).order_by("sort_order", "text")[:50])
    return terms if len(terms) >= 2 else []


def _used_on_q(form_name):
    from django.db.models import Q
    return Q(used_on=form_name) | Q(used_on="All")


def _holdings(emp):
    assets = Asset.objects.filter(kind="asset", assigned_to=emp)
    mobiles = Asset.objects.filter(kind="mobile", assigned_to=emp)
    sims = SimCard.objects.filter(assigned_to=emp)
    return assets, mobiles, sims


def _last_issue_date(a):
    if a.assigned_date:
        return a.assigned_date
    ev = LifecycleEvent.objects.filter(item_key=a.ams_asset_id, action__startswith="Assign").order_by("-date", "-id").first()
    return ev.date if ev else None


def _gate(request, page_key):
    if not request.user.is_authenticated:
        raise Http404
    if access_level_for(request.user, page_key) == "none":
        raise Http404


@login_required
def asset_issue_form(request, pk):
    _gate(request, "employee")
    emp = get_object_or_404(Employee, pk=pk)
    scope = request.GET.get("scope", "direct")
    if scope not in ("direct", "team", "both"):
        scope = "direct"
    assets, mobiles, sims = _holdings(emp)
    # team = subordinates' own holdings + this employee's custodian-only items
    sub_assets = []
    for sub in emp.subordinates.filter(status="Active"):
        for a in Asset.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text=""):
            sub_assets.append(a)
    sub_mobiles = []
    for sub in emp.subordinates.filter(status="Active"):
        for m in Asset.objects.filter(kind="mobile", assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text=""):
            sub_mobiles.append(m)
    sub_sims = []
    for sub in emp.subordinates.filter(status="Active"):
        for s in SimCard.objects.filter(assigned_to=sub, assigned_to_sub__isnull=True, assigned_sub_text=""):
            sub_sims.append(s)
    own_team_assets = [a for a in assets if a.assigned_to_sub or a.assigned_sub_text]
    own_team_mobiles = [m for m in mobiles if m.assigned_to_sub or m.assigned_sub_text]
    own_team_sims = [s for s in sims if s.assigned_to_sub or s.assigned_sub_text]
    ctx = _letterhead("Asset Issue Form", _form_no("AIF"), "issue")
    ctx.update({
        "emp": emp,
        "scope": scope,
        "direct_assets": assets if scope in ("direct", "both") else [],
        "direct_mobiles": mobiles if scope in ("direct", "both") else [],
        "direct_sims": sims if scope in ("direct", "both") else [],
        "team_assets": (sub_assets + own_team_assets) if scope in ("team", "both") else [],
        "team_mobiles": (sub_mobiles + own_team_mobiles) if scope in ("team", "both") else [],
        "team_sims": (sub_sims + own_team_sims) if scope in ("team", "both") else [],
        "condition_opts": CONDITION_OPTS,
        "terms": _print_terms("Asset Issue Form"),
        "assign_type": {"direct": "Direct (Personal Use)", "team": "Subordinate/Team Use", "both": "Both (Direct + Team Use)"}[scope],
        "n_assets": len(assets), "n_team_assets": len(sub_assets) + len(own_team_assets),
        "n_mobiles": len(mobiles), "n_sims": len(sims),
    })
    return render(request, "print/aif.html", ctx)


@login_required
def asset_handover_form(request, pk):
    _gate(request, "employee")
    emp = get_object_or_404(Employee, pk=pk)
    er = ExitRecord.objects.filter(employee=emp).order_by("-id").first()
    if er is None:
        raise Http404
    ctx = _letterhead("Asset Handover Form", _form_no("AHF"), "handover")
    ctx.update({
        "emp": emp, "er": er,
        "condition_opts": CONDITION_OPTS,
        "terms": _print_terms("Asset Handover Form"),
    })
    return render(request, "print/ahf.html", ctx)


@login_required
def mobile_issue_form(request, pk):
    _gate(request, "mobile")
    m = get_object_or_404(Asset, pk=pk, kind="mobile")
    if not m.assigned_to:
        raise Http404
    ctx = _letterhead("Mobile Issue Form", _form_no("MIF"), "issue")
    ctx.update({
        "emp": m.assigned_to, "mobile": m, "print_id": print_asset_id(m),
        "condition_opts": CONDITION_OPTS,
        "terms": _print_terms("Mobile Issue Form"),
    })
    return render(request, "print/mif.html", ctx)


@login_required
def sim_issue_form(request, pk):
    _gate(request, "simCards")
    s = get_object_or_404(SimCard, pk=pk)
    if not s.assigned_to:
        raise Http404
    ctx = _letterhead("SIM Card Issue Form", _form_no("SIF"), "issue")
    ctx.update({
        "emp": s.assigned_to, "sim": s,
        "used_in": "Personal Mobile" if s.personal_mobile else (s.linked_mobile.base_display_id if s.linked_mobile else "-"),
        "terms": _print_terms("SIM Card Issue Form"),
    })
    return render(request, "print/sif.html", ctx)


@login_required
def gate_pass(request):
    """A4 Laptop Gate Pass - landscape sheet with 8 slips per page
    (2 columns x 4 rows), with cut spacing between slips so the user can
    cut the printed sheet into individual passes. ids=1,2,3&copies=2

    The view chunks the cards into pages of 8 (padding the final page
    with empty placeholders so the grid stays 2x4)."""
    _gate(request, "labelPassPrint")
    ids = [s for s in request.GET.get("ids", "").split(",") if s.strip()]
    copies = max(1, min(99, int(request.GET.get("copies", "1") or 1)))
    company = Company.get_solo()
    # Company address prints on the gate pass only (per Company model note),
    # as the issuing premises line.
    company_addr = (company.address or "").strip()
    items = []
    for pk in ids:
        a = Asset.objects.filter(pk=pk).first()
        if not a:
            continue
        emp = a.assigned_to
        items.append({
            "serial": a.serial_number or "-",
            "display_id": print_asset_id(a) or a.base_display_id or a.ams_asset_id or "-",
            "emp_name": emp.name if emp else "Unassigned",
            "emp_code": (emp.ams_id or (emp.emp_id if hasattr(emp, "emp_id") else "") or "-") if emp else "-",
            "company_addr": company_addr,
        })
    cards = []
    for it in items:
        # Multiple copies = duplicate the same slip (e.g. one for office, one
        # for the bearer). Each slip is identical - no Original/Duplicate label
        # is shown, matching the original AMS-Test layout.
        for _ in range(copies):
            cards.append(dict(it))
    # Chunk into pages of 8 (2 cols x 4 rows). Pad the last page with empty
    # placeholders so the grid stays 2x4 even when the count is not a multiple
    # of 8 - keeps the cut layout consistent on every printed sheet.
    PER_PAGE = 8
    pages = []
    for i in range(0, max(len(cards), 1), PER_PAGE):
        chunk = cards[i:i + PER_PAGE]
        # pad with empty placeholder cards so every page renders a full 2x4 grid
        while len(chunk) < PER_PAGE:
            chunk.append({"empty": True})
        pages.append(chunk)
    if not pages:
        pages = [[{"empty": True}] * PER_PAGE]
    ctx = {"pages": pages, "company": company, "title": "Laptop Gate Pass"}
    return render(request, "print/gatepass.html", ctx)


@login_required
def display_id_labels(request):
    """A4 sticker sheet: 7 cols x 16 rows of 26mm x 17.6875mm labels."""
    _gate(request, "labelPassPrint")
    ids = [s for s in request.GET.get("ids", "").split(",") if s.strip()]
    copies = max(1, min(99, int(request.GET.get("copies", "1") or 1)))
    labels = []
    for pk in ids:
        a = Asset.objects.filter(pk=pk).first()
        if not a:
            continue
        # never render an empty label - fall back through the full chain
        label = print_asset_id(a) or a.base_display_id or a.ams_asset_id
        if not label:
            label = f"#{a.pk}"
        labels.extend([label] * copies)
    per_page = 7 * 16
    pages = []
    for i in range(0, len(labels), per_page):
        chunk = labels[i:i + per_page]
        pages.append(chunk + [""] * (per_page - len(chunk)))
    ctx = {"pages": pages, "title": "Display ID Labels"}
    return render(request, "print/labels.html", ctx)


@login_required
def report_print(request, tab):
    """Generic report print: same filters as the reports page."""
    _gate(request, "reports")
    from ..views.reports import build_tab, TABS
    if tab not in dict(TABS):
        raise Http404
    ctx = build_tab(request, tab)
    ctx = {k: v for k, v in ctx.items() if k in ("events", "holdings", "moves", "dist_rows", "show_asset_col")}
    head = _letterhead(dict(TABS)[tab] + " Report", "", "issue")
    head["generated"] = date.today().strftime("%d-%m-%Y")
    head.update({"tab": tab, **ctx, "prefs": ReportPrefs.get_solo()})
    return render(request, "print/report_print.html", head)
