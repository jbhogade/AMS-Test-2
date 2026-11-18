"""
#-------------- Start Code for : ID GENERATION (ams/ids.py) ----------------

ID + Display ID algorithms ported 1:1 from AMS-Test dummy-data.js.
Auto IDs are always max+1 (never count+1).
#-------------- End of the code : ID GENERATION (ams/ids.py) ----------------
"""

from datetime import datetime


def pad(n, width=6):
    return str(n).zfill(width)


def next_seq(existing_values, prefix):
    """max+1 over values that start with prefix and end with digits."""
    best = 0
    for v in existing_values:
        if v and str(v).startswith(prefix):
            tail = str(v)[len(prefix):]
            if tail.isdigit():
                best = max(best, int(tail))
    return best + 1


def next_generic_id(model, field, prefix, width=6):
    qs = model.objects.values_list(field, flat=True)
    return prefix + pad(next_seq(list(qs), prefix), width)


def next_ams_asset_id(kind, type_short):
    """AMS-LT-130726-143055-000001 - permanent unique key."""
    now = datetime.now()
    stamp = now.strftime("%d%m%y-%H%M%S")
    prefix = f"AMS-{type_short}-{stamp}-"
    from .models import Asset
    return prefix + pad(next_seq(list(Asset.objects.values_list("ams_asset_id", flat=True)), prefix))


def next_display_id(kind, type_short):
    """LT00099 - 5 digits, max over items whose base starts with typeShort."""
    from .models import Asset
    vals = []
    for row in Asset.objects.filter(kind=kind).values_list("display_id", flat=True):
        if row:
            vals.append(row)
    # also consider ids like LT00007 from ams_asset_id fallback (rare)
    n = next_seq(vals, type_short)
    return type_short + pad(n, 5)


def next_ams_id(dept_short):
    """EMP-IT-000004"""
    from .models import Employee
    prefix = f"EMP-{dept_short}-"
    return prefix + pad(next_seq(list(Employee.objects.values_list("ams_id", flat=True)), prefix))


def name_short_map(qs):
    """Map name -> shortform (case-insensitive fallback)."""
    m = {}
    for obj in qs:
        if getattr(obj, "shortform", "") or getattr(obj, "short", ""):
            short = getattr(obj, "shortform", "") or getattr(obj, "short", "")
            m[obj.name] = short
            m[obj.name.strip().lower()] = short
    return m


def lookup_short(model, name):
    if not name:
        return ""
    try:
        obj = model.objects.filter(name__iexact=name.strip()).first()
        if obj and getattr(obj, "shortform", ""):
            return obj.shortform
    except Exception:
        pass
    return ""


def type_short(type_name):
    from .models import AssetType
    return lookup_short(AssetType, type_name)


def site_short(site_name):
    from .models import Site
    return lookup_short(Site, site_name)


def dept_short(dept_name):
    from .models import Department
    return lookup_short(Department, dept_name)


def dept_short_from_emp(emp):
    """Department short from the master, else from the employee's AMS ID."""
    s = dept_short(emp.department.name if emp.department else "")
    if s:
        return s
    if emp.ams_id and "-" in emp.ams_id:
        parts = emp.ams_id.split("-")
        if len(parts) >= 2:
            return parts[1].upper()
    return ""


def base_display_id(asset):
    """Permanent base ID: stored display_id, else derived from ams_asset_id."""
    if asset.display_id:
        return asset.display_id
    # derive leading alpha+digits from the AMS ID (AMS-LT-... => LT...)
    parts = asset.ams_asset_id.split("-")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return asset.ams_asset_id


def full_display_id(asset):
    """LT00007HOIT - base + site short + dept short, only when assigned and not legacy."""
    base = base_display_id(asset)
    if asset.is_legacy_id:
        return base
    if not asset.assigned_to:
        return base
    emp = asset.assigned_to
    site_name = asset.current_site.name if asset.current_site else (emp.site.name if emp.site else "")
    ss = site_short(site_name)
    ds = dept_short(emp.department.name if emp.department else "") or dept_short_from_emp(emp)
    return base + ss + ds


def print_asset_id(asset):
    """Print rule: legacy -> stored base; assigned non-legacy -> full; else base."""
    base = base_display_id(asset)
    if asset.is_legacy_id:
        return asset.display_id or base
    if asset.assigned_to:
        return full_display_id(asset)
    return asset.display_id or base


def sim_print_id(sim):
    return sim.sim_id
