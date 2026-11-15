"""Label / Pass Print Master: tile pickers, A4 sticker sheet, Gate Pass, Excel."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..access import ams_view
from ..models import Asset, AssetType
from ..ids import print_asset_id
from ..tools import xlsx_response

TYPE_ORDER = ["Laptop", "Desktop", "Printer", "Scanner"]


def _sections(kind):
    """Group assets by type (LPP_TYPE_ORDER first, then A-Z) + Mobiles last."""
    sections = []
    types = list(AssetType.objects.all())
    ordered = [t for t in types if t.name.lower() in [x.lower() for x in TYPE_ORDER]]
    ordered.sort(key=lambda t: [x.lower() for x in TYPE_ORDER].index(t.name.lower()))
    rest = sorted([t for t in types if t not in ordered], key=lambda t: t.name.lower())
    for t in ordered + rest:
        items = Asset.objects.filter(kind="asset", type=t).select_related("type", "make", "assigned_to")
        if items.exists():
            sections.append({"title": t.name, "items": list(items.order_by("display_id"))})
    if kind == "displayId":
        mobs = Asset.objects.filter(kind="mobile").select_related("type", "make", "assigned_to")
        if mobs.exists():
            sections.append({"title": "Mobiles", "items": list(mobs.order_by("display_id"))})
    return sections


@ams_view("labelPassPrint")
def label_pass_print(request):
    tab = request.GET.get("tab", "displayId")
    q = request.GET.get("q", "").strip()
    sections = _sections(tab)
    if q:
        ql = q.lower()

        def match(a):
            hay = " ".join([
                print_asset_id(a), a.name or "", a.make_model or "",
                a.type.name if a.type else "", a.status,
                a.assigned_to.name if a.assigned_to else "",
            ]).lower()
            return ql in hay
        sections = [{"title": s["title"], "items": [a for a in s["items"] if match(a)]} for s in sections]
    counts = {}
    for s in sections:
        counts[s["title"]] = len(s["items"])
    ctx = {
        "tab": tab, "sections": sections, "q": q, "counts": counts,
        "can_write": request.ams_can_write, "hub": request.GET.get("hub"),
    }
    if request.GET.get("hub"):
        return render(request, "partials/label_content.html", ctx)
    return render(request, "label_pass_print.html", ctx)


@ams_view("labelPassPrint")
def label_pass_export(request):
    tab = request.GET.get("tab", "displayId")
    ids = [s for s in request.GET.get("ids", "").split(",") if s.strip()]
    rows = []
    for pk in ids:
        a = Asset.objects.filter(pk=pk).first()
        if a:
            rows.append([
                print_asset_id(a),
                "Mobile" if a.kind == "mobile" else "Asset",
                a.type.name if a.type else "",
                a.assigned_to.name if a.assigned_to else "Unassigned",
                a.name or "-", a.make_model or "-", 1,
            ])
    headers = ["Display ID", "Kind", "Section", "Assigned To", "Name", "Model", "Copies"]
    fname = "Display_ID_Labels" if tab == "displayId" else "Gate_Pass_Display_IDs"
    return xlsx_response(fname, headers, rows)
