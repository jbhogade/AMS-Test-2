"""
#-------------- Start Code for : MASTER REGISTRY (ams/master_registry.py) ----------------

Generic CRUD engine configuration for every lookup master + Accessory +
Vendor, mirroring AMS_MASTER_CONFIGS / master-table.js from AMS-Test.

Each config: key, title, model, fields (name/label/type/required/source/help),
usage_count(model instance) -> int, and optional quickadd spec.
The engine renders list pages, add/edit modals, delete guards, CSV
template/export/import and usage counts via one view.
#-------------- End of the code : MASTER REGISTRY (ams/master_registry.py) ----------------
"""

from .models import (
    Site, Department, Designation, AssetCategory, AssetType, AssetMake,
    SimOperator, SimPlan, ConsumableCategory, UnitOfMeasure, SparePartCategory,
    VendorCategory, PrintTerm, Accessory, Vendor, Vendor as VendorM,
    Asset, Employee, SimCard, Consumable, SparePart,
)


def _usage_assets_plus_mobiles(field="type"):
    def fn(obj):
        if field == "type":
            return Asset.objects.filter(type=obj).count()
        return 0
    return fn


MASTERS = {}


def register(key, title, model, fields, usage=None, csv_match=None, quickadd=None, order_fields=None):
    MASTERS[key] = {
        "key": key,
        "title": title,
        "model": model,
        "fields": fields,
        "usage": usage,
        "csv_match": csv_match or ["name"],
        "quickadd": quickadd,
    }


# field spec: (name, label, type, required, help)
# type: text | select:<key>|choices | number | date | textarea | checkbox

def asset_type_usage(obj):
    return Asset.objects.filter(type=obj).count()


register("asset-type", "Asset Type Master", AssetType, [
    ("name", "Asset Type Name", "text", True, ""),
    ("shortform", "Shortform (for Asset ID)", "shortform", True, "max 4 letters, e.g. LT"),
    ("category", "Asset Category", "select:asset-category", False, ""),
], usage=asset_type_usage, quickadd={"category": ["name", "used_on"]})

register("asset-category", "Asset Category Master", AssetCategory, [
    ("name", "Category Name", "text", True, ""),
    ("used_on", "Used On", "choices:Assets|Mobiles|Both", True, ""),
], usage=lambda o: Asset.objects.filter(category=o).count())

register("asset-make", "Asset Make Master", AssetMake, [
    ("name", "Make Name", "text", True, ""),
    ("asset_type", "Asset Type", "select:asset-type", True, ""),
], usage=lambda o: Asset.objects.filter(make=o).count(), csv_match=["name", "asset_type"])

register("site", "Site Master", Site, [
    ("name", "Site Name", "text", True, ""),
    ("shortform", "Shortform (for Asset ID)", "shortform", True, "max 4 letters, e.g. HO"),
    ("address", "Address", "text", False, ""),
], usage=lambda o: Asset.objects.filter(current_site=o).count())

register("department", "Department Master", Department, [
    ("name", "Department Name", "text", True, ""),
    ("shortform", "Shortform (for Employee ID)", "shortform", True, "max 4 letters, e.g. IT"),
], usage=lambda o: Employee.objects.filter(department=o).count())

register("designation", "Designation Master", Designation, [
    ("name", "Designation Name", "text", True, ""),
], usage=lambda o: Employee.objects.filter(designation=o.name).count())

register("sim-operator", "SIM Operator Master", SimOperator, [
    ("name", "Operator Name", "text", True, ""),
    ("helpline", "Helpline / Customer Care", "text", False, ""),
    ("website", "Website", "text", False, ""),
], usage=lambda o: SimCard.objects.filter(operator=o).count())

register("sim-plan", "SIM Plan Master", SimPlan, [
    ("name", "Plan Name", "text", True, ""),
    ("plan_type", "Plan Type", "text", False, ""),
    ("description", "Description", "textarea", False, ""),
], usage=lambda o: SimCard.objects.filter(plan=o).count())

register("consumable-category", "Consumable Category Master", ConsumableCategory, [
    ("name", "Category Name", "text", True, ""),
    ("description", "Description", "textarea", False, ""),
], usage=lambda o: Consumable.objects.filter(category=o).count())

register("unit-of-measure", "Unit of Measure Master", UnitOfMeasure, [
    ("name", "Unit Name", "text", True, ""),
    ("description", "Description", "textarea", False, ""),
], usage=lambda o: Consumable.objects.filter(unit=o).count())

register("spare-part-category", "Spare Part Category Master", SparePartCategory, [
    ("name", "Category Name", "text", True, ""),
    ("description", "Description", "textarea", False, ""),
], usage=lambda o: SparePart.objects.filter(category=o).count())

register("vendor-category", "Vendor Category Master", VendorCategory, [
    ("name", "Category Name", "text", True, ""),
    ("description", "Description", "textarea", False, ""),
], usage=lambda o: VendorM.objects.filter(categories=o).count())

register("print-terms", "Print Terms Master", PrintTerm, [
    ("text", "Rule Text", "textarea", True, "max 1000 characters"),
    ("used_on", "Used On", "choices:Asset Issue Form|Asset Handover Form|Mobile Issue Form|SIM Card Issue Form|All", True, ""),
    ("sort_order", "Sort Order", "number", True, "lower prints first"),
], usage=None, csv_match=["text"])


def master_list():
    """Masters grouped for the Masters hub page (order like the original)."""
    order = ["asset-type", "asset-category", "asset-make", "site", "department", "designation",
             "sim-operator", "sim-plan", "consumable-category", "unit-of-measure",
             "spare-part-category", "vendor-category", "print-terms"]
    return [(k, MASTERS[k]) for k in order]


REGISTRY_KEY_BY_MASTER = {
    "asset-type": "assetType", "asset-category": "assetCategory", "asset-make": "assetMake",
    "site": "site", "department": "department", "designation": "designation",
    "sim-operator": "simOperator", "sim-plan": "simPlan",
    "consumable-category": "consumableCategory", "unit-of-measure": "unitOfMeasure",
    "spare-part-category": "sparePartCategory", "vendor-category": "vendorCategory",
    "print-terms": "printTerms",
}
