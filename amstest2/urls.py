"""
#-------------- Start Code for : URLS (amstest2/urls.py) -----------------------
#-------------- End of the code : URLS (amstest2/urls.py) -----------------------
"""

from django.contrib import admin
from django.urls import path, re_path
from django.views.generic import RedirectView
from django.views.static import serve as media_serve

from django.conf import settings

from ams.views import (
    auth, dashboard, masters, employees, assets, simcards, stock,
    adminpages, logs, reports, prints, distribution, account, catalog, labelprint,
)

urlpatterns = [
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
    path("admin/", admin.site.urls),

    # auth
    path("login/", auth.login_view, name="login"),
    path("logout/", auth.logout_view, name="logout"),

    # dashboard
    path("dashboard/", dashboard.dashboard, name="dashboard"),

    # employees
    path("employees/", employees.employees, name="employees"),
    path("employees/<int:pk>/view/", employees.employee_view, name="employee_view"),
    path("employees/save/", employees.employee_save, name="employee_save"),
    path("employees/<int:pk>/exit/", employees.employee_exit, name="employee_exit"),
    path("employees/<int:pk>/reactivate/", employees.employee_reactivate, name="employee_reactivate"),
    path("employees/csv/<str:action>/", employees.employee_csv, name="employee_csv"),
    path("employees/<int:pk>/issue-form/", prints.asset_issue_form, name="employee_issue_form"),
    path("employees/<int:pk>/handover-form/", prints.asset_handover_form, name="employee_handover_form"),

    # assets + mobiles (kind in path)
    path("assets/", assets.asset_list, kwargs={"kind": "asset"}, name="assets"),
    path("mobiles/", assets.asset_list, kwargs={"kind": "mobile"}, name="mobiles"),
    path("assets/save/", assets.asset_save, kwargs={"kind": "asset"}, name="asset_save"),
    path("mobiles/save/", assets.asset_save, kwargs={"kind": "mobile"}, name="mobile_save"),
    path("items/<int:pk>/view/", assets.asset_view, name="asset_view"),
    path("items/<int:pk>/assign/", assets.asset_assign, name="asset_assign"),
    path("items/<int:pk>/return/", assets.asset_return, name="asset_return"),
    path("items/<int:pk>/transfer/", assets.asset_transfer, name="asset_transfer"),
    path("items/<int:pk>/status/<str:action>/", assets.asset_status_change, name="asset_status"),
    path("items/<int:pk>/replace/", assets.asset_replace, name="asset_replace"),
    path("items/<int:pk>/swap/", assets.asset_swap, name="asset_swap"),
    path("items/<int:pk>/issue-form/", prints.asset_issue_form, name="asset_issue_form"),
    path("mobiles/<int:pk>/issue-form/", prints.mobile_issue_form, name="mobile_issue_form"),
    path("assets/csv/<str:action>/", assets.asset_csv, kwargs={"kind": "asset"}, name="asset_csv"),
    path("mobiles/csv/<str:action>/", assets.asset_csv, kwargs={"kind": "mobile"}, name="mobile_csv"),

    # SIM cards
    path("sim-cards/", simcards.sim_list, name="simcards"),
    path("sim-cards/save/", simcards.sim_save, name="sim_save"),
    path("sim-cards/<int:pk>/assign/", simcards.sim_assign, name="sim_assign"),
    path("sim-cards/<int:pk>/return/", simcards.sim_return, name="sim_return"),
    path("sim-cards/<int:pk>/block/", simcards.sim_block, name="sim_block"),
    path("sim-cards/<int:pk>/retire/", simcards.sim_retire, name="sim_retire"),
    path("sim-cards/<int:pk>/issue-form/", prints.sim_issue_form, name="sim_issue_form"),
    path("sim-cards/csv/<str:action>/", simcards.sim_csv, name="sim_csv"),

    # consumables + spare parts
    path("consumables/", stock.consumables, name="consumables"),
    path("consumables/save/", stock.consumable_save, name="consumable_save"),
    path("consumables/<int:pk>/restock/", stock.consumable_restock, name="consumable_restock"),
    path("consumables/<int:pk>/used/", stock.consumable_used, name="consumable_used"),
    path("consumables/<int:pk>/log/", stock.consumable_log, name="consumable_log"),
    path("consumables/csv/<str:action>/", stock.consumable_csv, name="consumable_csv"),
    path("spare-parts/", stock.spareparts, name="spareparts"),
    path("spare-parts/save/", stock.sparepart_save, name="sparepart_save"),
    path("spare-parts/<int:pk>/restock/", stock.sparepart_restock, name="sparepart_restock"),
    path("spare-parts/<int:pk>/used/", stock.sparepart_used, name="sparepart_used"),
    path("spare-parts/<int:pk>/log/", stock.sparepart_log, name="sparepart_log"),
    path("spare-parts/csv/<str:action>/", stock.sparepart_csv, name="sparepart_csv"),

    # generic masters
    path("masters/", masters.master_page, kwargs={"key": "asset-type"}, name="masters_default"),
    path("masters/<str:key>/", masters.master_page, name="master_page"),
    path("masters/<str:key>/panel/", masters.master_panel, name="master_panel"),
    path("masters/<str:key>/save/", masters.master_save, name="master_save"),
    path("masters/<str:key>/delete/", masters.master_delete, name="master_delete"),
    path("masters/<str:key>/toggle/", masters.master_toggle, name="master_toggle"),
    path("masters/<str:key>/csv/<str:action>/", masters.master_csv, name="master_csv"),

    # accessories + vendors
    path("accessories/", catalog.accessories, name="accessories"),
    path("accessories/save/", catalog.accessory_save, name="accessory_save"),
    path("accessories/<int:pk>/delete/", catalog.accessory_delete, name="accessory_delete"),
    path("accessories/<int:pk>/toggle/", catalog.accessory_toggle, name="accessory_toggle"),
    path("accessories/csv/<str:action>/", catalog.accessory_csv, name="accessory_csv"),
    path("accessories/import/", catalog.accessory_import, name="accessory_import"),
    path("vendors/", catalog.vendors, name="vendors"),
    path("vendors/save/", catalog.vendor_save, name="vendor_save"),
    path("vendors/<int:pk>/delete/", catalog.vendor_delete, name="vendor_delete"),
    path("vendors/<int:pk>/toggle/", catalog.vendor_toggle, name="vendor_toggle"),
    path("vendors/csv/<str:action>/", catalog.vendor_csv, name="vendor_csv"),
    path("vendors/import/", catalog.vendor_import, name="vendor_import"),

    # system admin + company + users + access + roles
    path("system-admin/", adminpages.system_admin, name="system_admin"),
    path("company/", adminpages.company, name="company"),
    path("company/save/", adminpages.company_save, name="company_save"),
    path("users/", adminpages.users, name="users"),
    path("users/save/", adminpages.user_save, name="user_save"),
    path("users/<int:pk>/toggle/", adminpages.user_toggle, name="user_toggle"),
    path("users/<int:pk>/delete/", adminpages.user_delete, name="user_delete"),
    path("access-rights/", adminpages.access_rights, name="access_rights"),
    path("access-rights/<int:pk>/edit/", adminpages.access_rights_edit, name="access_rights_edit"),
    path("access-rights/<int:pk>/save/", adminpages.access_rights_save, name="access_rights_save"),
    path("access-rights/<int:pk>/reset/", adminpages.access_rights_reset, name="access_rights_reset"),
    path("role-access/", adminpages.role_access, name="role_access"),
    path("role-access/save/", adminpages.role_access_save, name="role_access_save"),
    path("role-access/reset/", adminpages.role_access_reset, name="role_access_reset"),

    # logs
    path("logs/", logs.logs, name="logs"),
    path("logs/export/<str:fmt>/", logs.logs_export, name="logs_export"),
    path("logs/clear/", logs.logs_clear, name="logs_clear"),

    # reports
    path("reports/", reports.reports, name="reports"),
    path("reports/prefs/save/", reports.report_prefs_save, name="report_prefs_save"),
    path("reports/export/<str:tab>/<str:fmt>/", reports.reports_export, name="reports_export"),

    # label / pass print
    path("label-pass-print/", labelprint.label_pass_print, name="label_pass_print"),
    path("label-pass-print/export/", labelprint.label_pass_export, name="label_pass_export"),

    # prints
    path("print/labels/", prints.display_id_labels, name="print_labels"),
    path("print/gatepass/", prints.gate_pass, name="print_gatepass"),
    path("print/report/<str:tab>/", prints.report_print, name="print_report"),

    # distribution
    path("distribution/", distribution.distribution, name="distribution"),
    path("distribution/<int:pk>/detail/", distribution.distribution_detail, name="distribution_detail"),
    path("distribution/export/<str:fmt>/", distribution.distribution_export, name="distribution_export"),

    # account
    path("profile/", account.profile, name="profile"),
    path("profile/save/", account.profile_save, name="profile_save"),
    path("profile/password/", account.profile_password, name="profile_password"),
    path("settings/", account.settings, name="settings"),
    path("settings/save/", account.settings_save, name="settings_save"),
]

# Serve user uploads (Company Master logo / banner) over HTTP.
# Django serves static/ automatically but NOT media/ - without this the
# uploaded logo file exists in media\company\ but the browser gets a 404.
# django.views.static.serve is used directly (not the DEBUG-only helper)
# so the logo also renders when the portal runs with AMS_DEBUG=0.
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", media_serve, {"document_root": settings.MEDIA_ROOT}),
]
