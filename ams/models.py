"""
#-------------- Start Code for : MODELS (ams/models.py) ----------------

Complete data model for AMS-Test-2, ported from the AMS-Test collections.
Names follow Django snake_case; semantic parity is kept with the original
camelCase fields (noted in comments where the mapping matters).
#-------------- End of the code : MODELS (ams/models.py) ----------------
"""

from django.contrib.auth.models import User
from django.db import models


# ---------------------------------------------------------------------------
# LOOKUP MASTERS (generic master engine drives CRUD for all of these)
# ---------------------------------------------------------------------------

class Site(models.Model):
    name = models.CharField(max_length=120, unique=True)
    shortform = models.CharField(max_length=4)          # for Asset ID suffix
    address = models.CharField(max_length=255, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    shortform = models.CharField(max_length=4)          # for Employee ID
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Designation(models.Model):
    name = models.CharField(max_length=120, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AssetCategory(models.Model):
    USED_ON = [("Assets", "Assets"), ("Mobiles", "Mobiles"), ("Both", "Both")]
    name = models.CharField(max_length=120, unique=True)
    used_on = models.CharField(max_length=10, choices=USED_ON, default="Both")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AssetType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    shortform = models.CharField(max_length=4)          # for Asset ID prefix
    category = models.ForeignKey(AssetCategory, null=True, blank=True, on_delete=models.SET_NULL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class AssetMake(models.Model):
    name = models.CharField(max_length=120)
    asset_type = models.ForeignKey(AssetType, null=True, on_delete=models.SET_NULL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["name", "asset_type"], name="uniq_make_per_type")]

    def __str__(self):
        return self.name


class VendorCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vendor(models.Model):
    name = models.CharField(max_length=160, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120, blank=True)
    categories = models.ManyToManyField(VendorCategory, blank=True)   # "Supplies"
    gstin = models.CharField(max_length=15, blank=True)
    remarks = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Accessory(models.Model):
    code = models.CharField(max_length=16, unique=True)   # ACC-000001
    name = models.CharField(max_length=120)
    asset_type = models.ForeignKey(AssetType, null=True, blank=True, on_delete=models.SET_NULL)
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SimOperator(models.Model):
    name = models.CharField(max_length=120, unique=True)
    helpline = models.CharField(max_length=60, blank=True)
    website = models.CharField(max_length=160, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SimPlan(models.Model):
    name = models.CharField(max_length=120, unique=True)
    plan_type = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ConsumableCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UnitOfMeasure(models.Model):
    name = models.CharField(max_length=60, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SparePartCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PrintTerm(models.Model):
    USED_ON = [
        ("Asset Issue Form", "Asset Issue Form"),
        ("Asset Handover Form", "Asset Handover Form"),
        ("Mobile Issue Form", "Mobile Issue Form"),
        ("SIM Card Issue Form", "SIM Card Issue Form"),
        ("All", "All"),
    ]
    term_id = models.CharField(max_length=12, unique=True)  # PT-001
    text = models.TextField(max_length=1000)
    used_on = models.CharField(max_length=30, choices=USED_ON, default="All")
    sort_order = models.PositiveIntegerField(default=10)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "text"]

    def __str__(self):
        return self.term_id


# ---------------------------------------------------------------------------
# PEOPLE
# ---------------------------------------------------------------------------

class Employee(models.Model):
    STATUS = [("Active", "Active"), ("Inactive", "Inactive")]
    ams_id = models.CharField(max_length=32, unique=True)     # EMP-IT-000001
    emp_id = models.CharField(max_length=40, blank=True)      # company employee code
    name = models.CharField(max_length=160)
    department = models.ForeignKey(Department, null=True, on_delete=models.SET_NULL)
    designation = models.CharField(max_length=120, blank=True)
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL)
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="subordinates")
    contact = models.CharField(max_length=40, blank=True)
    email = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="Active")
    exit_date = models.DateField(null=True, blank=True)
    exit_reason = models.CharField(max_length=60, blank=True)
    exit_remarks = models.TextField(blank=True)
    reactivated_date = models.DateField(null=True, blank=True)
    reactivation_remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.display_emp_id})"

    @property
    def display_emp_id(self):
        return self.emp_id or self.ams_id


class ExitRecord(models.Model):
    """Immutable snapshot taken when an employee exits (AHF prints from it)."""
    exit_id = models.CharField(max_length=16, unique=True)    # EXIT-000001
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="exit_records")
    ams_id = models.CharField(max_length=32)
    emp_id = models.CharField(max_length=40, blank=True)
    emp_name = models.CharField(max_length=160)
    emp_dept = models.CharField(max_length=120, blank=True)
    emp_designation = models.CharField(max_length=120, blank=True)
    exit_date = models.DateField()
    exit_reason = models.CharField(max_length=60, blank=True)
    exit_remarks = models.TextField(blank=True)
    facilities_disabled = models.JSONField(default=list, blank=True)
    facilities_na = models.JSONField(default=list, blank=True)
    direct_assets = models.JSONField(default=list, blank=True)
    direct_mobiles = models.JSONField(default=list, blank=True)
    direct_sims = models.JSONField(default=list, blank=True)
    subordinate_assets = models.JSONField(default=list, blank=True)
    team_transferred_to = models.JSONField(null=True, blank=True)
    reactivated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.exit_id


# ---------------------------------------------------------------------------
# ASSETS + MOBILES (one model, kind="asset"|"mobile", exactly like the
# original which clones the asset engine for mobiles)
# ---------------------------------------------------------------------------

ASSET_STATUS = [
    ("In Store", "In Store"),
    ("Assigned", "Assigned"),
    ("In Repair", "In Repair"),
    ("Transfer", "Transfer"),
    ("Not Working", "Not Working"),
    ("Retired / Scrapped", "Retired / Scrapped"),
    ("Replaced", "Replaced"),
]

SIM_STATUS = [("In Store", "In Store"), ("Issued", "Issued"), ("Blocked", "Blocked"), ("Retired", "Retired")]

CLEAR_ON_STATUS = ("Transfer", "Not Working", "Retired / Scrapped", "Replaced")


class Asset(models.Model):
    kind = models.CharField(max_length=8, default="asset")     # asset | mobile
    ams_asset_id = models.CharField(max_length=48, unique=True)
    display_id = models.CharField(max_length=32, blank=True)   # base Display ID (LT00001); typed => legacy
    is_legacy_id = models.BooleanField(default=False)
    category = models.ForeignKey(AssetCategory, null=True, on_delete=models.SET_NULL)
    type = models.ForeignKey(AssetType, null=True, on_delete=models.SET_NULL)
    make = models.ForeignKey(AssetMake, null=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=160, blank=True)
    model = models.CharField(max_length=120, blank=True)
    model_number = models.CharField(max_length=120, blank=True)     # mobiles only
    imei1 = models.CharField(max_length=40, blank=True)             # mobiles only
    imei2 = models.CharField(max_length=40, blank=True)             # mobiles only
    battery_no = models.CharField(max_length=60, blank=True)        # mobiles only
    charger_no = models.CharField(max_length=60, blank=True)        # mobiles only
    sim = models.ForeignKey("SimCard", null=True, blank=True, on_delete=models.SET_NULL, related_name="asset_sims")
    serial_number = models.CharField(max_length=120, blank=True)
    purchase_site = models.ForeignKey(Site, null=True, on_delete=models.SET_NULL, related_name="purchased_assets")
    current_site = models.ForeignKey(Site, null=True, on_delete=models.SET_NULL, related_name="current_assets")
    purchase_date = models.DateField(null=True, blank=True)
    warranty_end = models.DateField(null=True, blank=True)
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL)
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=ASSET_STATUS, default="In Store")
    assigned_to = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets_held")
    assigned_to_sub = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets_used_sub")
    assigned_sub_text = models.CharField(max_length=160, blank=True)   # free text actual user
    assigned_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    replaces_asset = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="replaced_by")
    replaces_reason = models.CharField(max_length=60, blank=True)
    replaces_note = models.TextField(blank=True)
    replaces_purchase_date = models.DateField(null=True, blank=True)
    accessories = models.ManyToManyField(Accessory, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_id", "id"]
        indexes = [models.Index(fields=["kind", "status"])]

    def __str__(self):
        return self.base_display_id or self.ams_asset_id

    # ---- Display ID helpers (full logic in ams/ids.py) ----
    @property
    def base_display_id(self):
        return self.display_id or self.ams_asset_id

    @property
    def make_model(self):
        make = self.make.name if self.make else ""
        model = self.model or self.model_number or ""
        return f"{make} {model}".strip()

    @property
    def actual_user_label(self):
        if self.assigned_to_sub:
            return self.assigned_to_sub.name
        if self.assigned_sub_text:
            return self.assigned_sub_text
        return ""


class SimCard(models.Model):
    sim_id = models.CharField(max_length=16, unique=True)      # SIM-000001
    iccid = models.CharField(max_length=60, blank=True)
    mobile_number = models.CharField(max_length=24, unique=True)
    operator = models.ForeignKey(SimOperator, null=True, blank=True, on_delete=models.SET_NULL)
    plan = models.ForeignKey(SimPlan, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, choices=SIM_STATUS, default="In Store")
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL)
    activation_date = models.DateField(null=True, blank=True)
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL)
    cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    remarks = models.TextField(blank=True)
    assigned_to = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="sims_held")
    assigned_to_sub = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL, related_name="sims_used_sub")
    assigned_sub_text = models.CharField(max_length=160, blank=True)
    assigned_date = models.DateField(null=True, blank=True)
    linked_mobile = models.ForeignKey(Asset, null=True, blank=True, on_delete=models.SET_NULL, related_name="linked_sims")
    personal_mobile = models.BooleanField(default=False)
    return_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sim_id"]

    def __str__(self):
        return f"{self.sim_id} ({self.mobile_number})"


class LifecycleEvent(models.Model):
    """Global assignment/lifecycle audit trail (the original's history[] +
    assignmentEvents). Per-item history = filter by item_kind + item_key."""
    KIND = [("asset", "Asset"), ("mobile", "Mobile"), ("sim", "SIM")]
    EVENTS = [
        ("Assign", "Assign"), ("Reassign", "Reassign"), ("Return", "Return"),
        ("Transfer", "Transfer"), ("Replace", "Replace"), ("Retire", "Retire"),
        ("Fault", "Fault"), ("Swap", "Swap"), ("Edit", "Edit"), ("Other", "Other"),
    ]
    item_kind = models.CharField(max_length=8, choices=KIND)
    item_key = models.CharField(max_length=48)              # ams_asset_id / sim_id
    item_label = models.CharField(max_length=64, blank=True)  # display id snapshot
    date = models.DateField()
    action = models.CharField(max_length=60)
    event_type = models.CharField(max_length=12, choices=EVENTS, default="Other")
    emp = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    emp_label = models.CharField(max_length=160, blank=True)   # company display id as typed
    emp_dept = models.CharField(max_length=120, blank=True)
    status_label = models.CharField(max_length=40, blank=True)
    accessories = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True)
    actor_username = models.CharField(max_length=60, blank=True)
    actor_role = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.date} {self.action} {self.item_label}"


# ---------------------------------------------------------------------------
# STOCK ITEMS (consumables + spare parts) and their movement log
# ---------------------------------------------------------------------------

class Consumable(models.Model):
    code = models.CharField(max_length=16, unique=True)        # CNS-000001
    name = models.CharField(max_length=160)
    category = models.ForeignKey(ConsumableCategory, null=True, on_delete=models.SET_NULL)
    unit = models.ForeignKey(UnitOfMeasure, null=True, on_delete=models.SET_NULL)
    site = models.ForeignKey(Site, null=True, on_delete=models.SET_NULL)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    restock_date = models.DateField(null=True, blank=True)
    warranty_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL)
    remarks = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.site})"


class SparePart(models.Model):
    code = models.CharField(max_length=16, unique=True)        # SP-000001
    name = models.CharField(max_length=160)
    asset_type = models.ForeignKey(AssetType, null=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(SparePartCategory, null=True, on_delete=models.SET_NULL)
    site = models.ForeignKey(Site, null=True, on_delete=models.SET_NULL)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    restock_date = models.DateField(null=True, blank=True)
    warranty_date = models.DateField(null=True, blank=True)
    unit_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL)
    remarks = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.site})"


class StockMovement(models.Model):
    """Movement log for consumables + spare parts (Restocked / Used)."""
    KIND = [("consumable", "Consumable"), ("sparepart", "Spare Part")]
    TYPE = [("Restocked", "Restocked"), ("Used", "Used")]
    kind = models.CharField(max_length=12, choices=KIND)
    item_id = models.PositiveIntegerField()                 # consumable/part pk
    item_code = models.CharField(max_length=16, blank=True)
    name = models.CharField(max_length=160)
    site = models.CharField(max_length=120, blank=True)
    type = models.CharField(max_length=10, choices=TYPE)
    qty = models.DecimalField(max_digits=12, decimal_places=2)
    by = models.CharField(max_length=200, blank=True)       # vendor (restock) or "Name (Dept)" (used)
    remarks = models.TextField(blank=True)
    asset = models.ForeignKey(Asset, null=True, blank=True, on_delete=models.SET_NULL)
    asset_id_snapshot = models.CharField(max_length=64, blank=True)   # display id at time of use
    date = models.DateField()
    actor_username = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


# ---------------------------------------------------------------------------
# ACCESS CONTROL + SYSTEM
# ---------------------------------------------------------------------------

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=30, default="Standard User")
    display_name = models.CharField(max_length=200, blank=True)
    linked_employee = models.ForeignKey(Employee, null=True, blank=True, on_delete=models.SET_NULL)
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.CharField(max_length=160, blank=True)
    contact_no = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=500, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    dob = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    allowed_pages = models.JSONField(null=True, blank=True)   # None = role default
    # per-user preferences
    theme = models.CharField(max_length=24, default="graphite")
    font_size = models.CharField(max_length=4, default="md")
    page_size = models.PositiveIntegerField(default=20)
    toast_enabled = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class RoleAccess(models.Model):
    page_key = models.CharField(max_length=40)
    role = models.CharField(max_length=30)
    level = models.CharField(max_length=6, default="none")    # none | view | full

    class Meta:
        unique_together = [("page_key", "role")]


class ActivityLog(models.Model):
    TYPES = [("success", "success"), ("warning", "warning"), ("danger", "danger"), ("info", "info")]
    time = models.DateTimeField(auto_now_add=True)
    actor_username = models.CharField(max_length=60, blank=True)
    actor_role = models.CharField(max_length=30, blank=True)
    page = models.CharField(max_length=80, blank=True)
    type = models.CharField(max_length=10, choices=TYPES, default="info")
    message = models.TextField()

    class Meta:
        ordering = ["-time", "-id"]

    def __str__(self):
        return f"[{self.time:%Y-%m-%d %H:%M}] {self.actor_username}: {self.message[:60]}"


class Company(models.Model):
    name = models.CharField(max_length=200, blank=True)
    slogan = models.CharField(max_length=200, blank=True)
    address = models.TextField(blank=True)                    # prints on Gate Pass only
    logo = models.FileField(upload_to="company/", null=True, blank=True)
    banner = models.FileField(upload_to="company/", null=True, blank=True)
    hr_admin_contact = models.CharField(max_length=60, blank=True)
    head_title = models.CharField(max_length=120, blank=True)
    head_contact = models.CharField(max_length=60, blank=True)

    class Meta:
        verbose_name_plural = "Company"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class ReportPrefs(models.Model):
    style = models.CharField(max_length=10, default="classic")   # classic | banner
    show_logo = models.BooleanField(default=True)
    show_name = models.BooleanField(default=True)
    show_slogan = models.BooleanField(default=True)
    # address NEVER prints on report headers (Gate Pass only, as in original)

    class Meta:
        verbose_name_plural = "ReportPrefs"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class PortalPref(models.Model):
    key = models.CharField(max_length=40, unique=True)
    value = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.key}={self.value}"


class FormCounter(models.Model):
    """Persistent counters for printed form numbers (AIF/AHF/MIF/SIF)."""
    prefix = models.CharField(max_length=8, unique=True)
    last = models.PositiveIntegerField(default=0)
