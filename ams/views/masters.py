"""
#-------------- Start Code for : GENERIC MASTER ENGINE (ams/views/masters.py) ----

One view drives every lookup master (list + add/edit + delete + toggle +
CSV template/export/import with per-row Import Report), mirroring
master-table.js + master-configs.js from the original portal.
Delete guard: usage_count > 0 -> blocked ("Deactivate instead").
#-------------- End of the code : GENERIC MASTER ENGINE (ams/views/masters.py) ----
"""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from ..access import ams_view, access_level_for, first_allowed_path
from functools import wraps
from ..activity import log_activity
from ..master_registry import MASTERS, REGISTRY_KEY_BY_MASTER
from ..models import Site, Department, AssetType, AssetCategory, PrintTerm
from ..tools import parse_date, read_csv_upload, csv_response, xlsx_response


def _ams_master_view(write=False):
    """Gate a master view by its registry page key (from the URL key)."""
    def deco(fn):
        @wraps(fn)
        def wrapper(request, key, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("/login/")
            reg_key = REGISTRY_KEY_BY_MASTER.get(key, "systemAdmin")
            level = access_level_for(request.user, reg_key)
            if level == "none":
                from django.contrib import messages
                messages.warning(request, "You do not have access to that page.")
                return redirect(first_allowed_path(request.user))
            request.ams_page_key = reg_key
            request.ams_can_write = level == "full"
            if write and not request.ams_can_write:
                from django.contrib import messages
                messages.warning(request, "View only - you cannot change records on this page.")
                return redirect(f"/masters/{key}/")
            return fn(request, key, *args, **kwargs)
        return wrapper
    return deco


def _get_master(key):
    if key not in MASTERS:
        raise Http404
    return MASTERS[key]


def _sources():
    return {
        "site": Site.objects.all(),
        "department": Department.objects.all(),
        "asset-type": AssetType.objects.all(),
        "asset-category": AssetCategory.objects.all(),
    }


def _field_choices(cfg, ftype):
    """select:<key> | choices:a|b|c"""
    if ftype.startswith("select:"):
        src = ftype.split(":", 1)[1]
        return [(o.pk, o.name) for o in _sources()[src]]
    if ftype.startswith("choices:"):
        return [(c, c) for c in ftype.split(":", 1)[1].split("|")]
    return []


def _rows_for(cfg):
    model = cfg["model"]
    fields = [f[0] for f in cfg["fields"]]
    out = []
    for obj in model.objects.all().select_related():
        row = {"obj": obj, "pk": obj.pk, "active": getattr(obj, "active", True), "usage": 0}
        if cfg["usage"]:
            row["usage"] = cfg["usage"](obj)
        vals = {}
        for f in cfg["fields"]:
            name, label, ftype, req, help_txt = f
            v = getattr(obj, name)
            if ftype.startswith("select:") and v is not None:
                v = v.name
            vals[name] = v
        row["vals"] = vals
        out.append(row)
    return out


def _save_fields(cfg, obj, post):
    """Apply posted form values to the model instance (no FK resolution errors)."""
    for f in cfg["fields"]:
        name, label, ftype, req, help_txt = f
        raw = (post.get(name) or "").strip()
        if ftype.startswith("select:"):
            src = ftype.split(":", 1)[1]
            target = _sources()[src].model
            setattr(obj, name, target.objects.filter(pk=raw).first() if raw else None)
        elif ftype == "number":
            setattr(obj, name, int(raw) if raw else (0 if name == "sort_order" else None))
        elif ftype == "shortform":
            setattr(obj, name, raw.upper()[:4])
        elif ftype == "checkbox":
            setattr(obj, name, bool(post.get(name)))
        else:
            setattr(obj, name, raw)
    if hasattr(obj, "active"):
        obj.active = bool(post.get("active", "1"))


def _csv_headers(cfg):
    heads = []
    for f in cfg["fields"]:
        name, label, ftype, req, help_txt = f
        if name == "active":
            continue
        if ftype.startswith("select:"):
            heads.append(f"{name}*")
        elif req:
            heads.append(f"{name}*")
        else:
            heads.append(name)
    return heads


def _csv_row(cfg, obj):
    vals = []
    for f in cfg["fields"]:
        name, label, ftype, req, help_txt = f
        if name == "active":
            continue
        v = getattr(obj, name)
        if ftype.startswith("select:") and v is not None:
            v = v.name
        vals.append("" if v is None else v)
    return vals


@_ams_master_view()
def master_page(request, key):
    cfg = _get_master(key)
    reg_key = REGISTRY_KEY_BY_MASTER.get(key, "systemAdmin")
    return render(request, "masters/master_page.html", _page_ctx(request, cfg, reg_key, partial=False))


@_ams_master_view()
def master_panel(request, key):
    """htmx partial for the System Admin hub tabs."""
    cfg = _get_master(key)
    reg_key = REGISTRY_KEY_BY_MASTER.get(key, "systemAdmin")
    return render(request, "masters/master_panel.html", _page_ctx(request, cfg, reg_key, partial=True))


def _page_ctx(request, cfg, reg_key, partial=False):
    q = (request.GET.get("q") or "").strip().lower()
    rows = _rows_for(cfg)
    if q:
        def match(r):
            hay = " ".join(str(v) for v in r["vals"].values()).lower()
            return q in hay
        rows = [r for r in rows if match(r)]
    can_write = request.ams_can_write
    fields_ui = []
    for f in cfg["fields"]:
        name, label, ftype, req, help_txt = f
        fields_ui.append({
            "name": name, "label": label, "required": req, "help": help_txt,
            "type": "select" if ftype.startswith("select:") else ("choices" if ftype.startswith("choices:") else ftype),
            "choices": _field_choices(cfg, ftype),
        })
    # JSON map for the edit modal: pk -> field values
    rows_json = {}
    for r in _rows_for(cfg):
        vals = {}
        for f in cfg["fields"]:
            name = f[0]
            v = r["vals"].get(name)
            vals[name] = v.pk if hasattr(v, "pk") else v
        vals["active"] = r["active"]
        rows_json[str(r["pk"])] = vals
    import json
    return {
        "cfg": cfg, "key": cfg["key"], "title": cfg["title"], "rows": rows, "q": q,
        "fields_ui": fields_ui, "can_write": can_write, "partial": partial,
        "reg_key": reg_key,
        "rows_json": json.dumps(rows_json),
        "import_report": request.session.pop("import_report", None),
    }


@_ams_master_view(write=True)
@require_POST
def master_save(request, key):
    cfg = _get_master(key)
    reg_key = REGISTRY_KEY_BY_MASTER.get(key, "systemAdmin")
    pk = request.POST.get("pk")
    model = cfg["model"]
    if pk:
        obj = model.objects.filter(pk=pk).first()
        created = False
    else:
        obj = model()
        created = True
    _save_fields(cfg, obj, request.POST)
    # auto codes
    if key == "print-terms" and not obj.term_id:
        from ..tools import next_code
        obj.term_id = next_code(PrintTerm, "PT-", 3, "term_id")
    # uniqueness
    try:
        obj.full_clean(exclude=[])
        obj.save()
    except Exception as e:
        msg = "; ".join([f"{f}: {'; '.join(errs)}" for f, errs in (e.message_dict.items() if hasattr(e, "message_dict") else [("", [str(e)])])])
        messages.error(request, f"Could not save: {msg}")
        if request.headers.get("HX-Request"):
            return render(request, "partials/toast_oob.html", {"messages": messages.get_messages(request)})
        return redirect(request.META.get("HTTP_REFERER") or f"/masters/{key}/")
    verb = "added to" if created else "updated in"
    log_activity(request.user, f"{cfg['title']}: '{obj}' {verb} the master", "success", cfg["title"])
    messages.success(request, f"'{obj}' {'added' if created else 'updated'}.")
    if request.headers.get("HX-Request"):
        resp = redirect(f"/masters/{key}/panel/")
        return resp
    return redirect(f"/masters/{key}/")


@_ams_master_view(write=True)
@require_POST
def master_delete(request, key):
    cfg = _get_master(key)
    reg_key = REGISTRY_KEY_BY_MASTER.get(key, "systemAdmin")
    model = cfg["model"]
    obj = model.objects.filter(pk=request.POST.get("pk")).first()
    if obj is None:
        messages.error(request, "Record not found.")
        return redirect(f"/masters/{key}/")
    usage = cfg["usage"](obj) if cfg["usage"] else 0
    if usage > 0:
        messages.warning(request, f"Cannot delete - currently used by {usage} record(s). Deactivate instead.")
    else:
        label = str(obj)
        obj.delete()
        log_activity(request.user, f"{cfg['title']}: '{label}' deleted", "danger", cfg["title"])
        messages.success(request, f"'{label}' deleted.")
    return redirect(f"/masters/{key}/" if not request.headers.get("HX-Request") else f"/masters/{key}/panel/")


@_ams_master_view(write=True)
@require_POST
def master_toggle(request, key):
    cfg = _get_master(key)
    model = cfg["model"]
    obj = model.objects.filter(pk=request.POST.get("pk")).first()
    if obj is None:
        messages.error(request, "Record not found.")
        return redirect(f"/masters/{key}/")
    obj.active = not obj.active
    obj.save()
    log_activity(request.user, f"{cfg['title']}: '{obj}' marked {'Active' if obj.active else 'Inactive'}", "info", cfg["title"])
    messages.success(request, f"'{obj}' is now {'Active' if obj.active else 'Inactive'}.")
    return redirect(f"/masters/{key}/" if not request.headers.get("HX-Request") else f"/masters/{key}/panel/")


def master_csv(request, key, action):
    cfg = _get_master(key)
    model = cfg["model"]
    slug = key.replace(" ", "_")
    if action == "template":
        return csv_response(f"{slug}_import_template", _csv_headers(cfg), [])
    if action == "export":
        rows = [_csv_row(cfg, o) for o in model.objects.all()]
        return csv_response(slug, _csv_headers(cfg), rows)
    if action == "export-xlsx":
        rows = [_csv_row(cfg, o) for o in model.objects.all()]
        return xlsx_response(slug, _csv_headers(cfg), rows, sheet=cfg["title"][:31])
    if action == "import":
        file = request.FILES.get("file")
        if file is None:
            messages.error(request, "Choose a CSV file to import.")
            return redirect(f"/masters/{key}/")
        headers, rows = read_csv_upload(file)
        report = []
        added = updated = skipped = 0
        for i, row in enumerate(rows, start=1):
            try:
                obj = model()
                found = None
                # match on csv_match keys
                for mk in cfg["csv_match"]:
                    v = (row.get(mk.rstrip("*")) or "").strip()
                    if not v:
                        continue
                    fld = cfg_field_by_name(cfg, mk.rstrip("*"))
                    if fld and fld[2].startswith("select:"):
                        src = fld[2].split(":", 1)[1]
                        target = _sources()[src].model
                        fk = target.objects.filter(name__iexact=v).first()
                        if fk:
                            cand = model.objects.filter(**{mk.rstrip("*"): fk}).first()
                            if cand:
                                found = cand
                                break
                    else:
                        cand = model.objects.filter(**{f"{mk.rstrip('*')}__iexact": v}).first()
                        if cand:
                            found = cand
                            break
                _apply_csv_row(cfg, obj if not found else found, row, report, i)
                (obj if not found else found).save()
                if found:
                    updated += 1
                else:
                    added += 1
            except Exception as e:
                skipped += 1
                report.append({"no": i, "result": "error", "reason": str(e)})
        log_activity(request.user, f"{cfg['title']}: CSV import - {added} added, {updated} updated, {skipped} skipped", "info", cfg["title"])
        messages.success(request, f"Import finished: {added} added, {updated} updated, {skipped} skipped. See the report below.")
        request.session["import_report"] = {"title": cfg["title"], "rows": report}
        return redirect(f"/masters/{key}/")
    raise Http404


def cfg_field_by_name(cfg, name):
    for f in cfg["fields"]:
        if f[0] == name:
            return f
    return None


def _apply_csv_row(cfg, obj, row, report, i):
    """Apply one CSV row; raises ValueError with a reason on problems."""
    for f in cfg["fields"]:
        name, label, ftype, req, help_txt = f
        if name == "active":
            continue
        raw = (row.get(name) or row.get(f"{name}*") or "").strip()
        if req and not raw:
            raise ValueError(f"{name} is required")
        if ftype.startswith("select:"):
            src = ftype.split(":", 1)[1]
            target = _sources()[src].model
            fk = target.objects.filter(name__iexact=raw).first()
            if raw and fk is None:
                # auto-create simple name+shortform masters (dept/designation etc.)
                if src in ("site", "department") or name in ("category", "asset_type"):
                    fk = target.objects.create(name=raw, shortform=raw[:4].upper()) if hasattr(target(), "shortform") else None
                    if fk is None:
                        fk = target.objects.create(name=raw)
                else:
                    raise ValueError(f"{label} '{raw}' not found in the master")
            setattr(obj, name, fk)
        elif ftype == "number":
            setattr(obj, name, int(raw) if raw else 0)
        elif ftype == "shortform":
            setattr(obj, name, raw.upper()[:4])
        else:
            setattr(obj, name, raw)
    if hasattr(obj, "active"):
        st = (row.get("status") or row.get("active") or "Active").strip().lower()
        obj.active = st not in ("inactive", "false", "no", "0")
    report.append({"no": i, "result": "ok", "reason": ""})
