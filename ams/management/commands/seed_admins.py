"""
#-------------- Start Code for : SEED (ams/management/commands/seed_admins.py) --

Idempotent seed: the two portal logins (mirroring the original AMS-Test
accounts), the Role x Page access matrix, and portal defaults.
Business masters start EMPTY (blank start cut, like AMS-v4-0).
#-------------- End of the code for : SEED (ams/management/commands/seed_admins.py) --
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from ams.activity import ensure_profile
from ams.access import RECOMMENDED_MATRIX, PAGE_KEYS
from ams.models import RoleAccess, PortalPref, ReportPrefs


class Command(BaseCommand):
    help = "Seed the two portal login accounts, the Role Access matrix and portal defaults (idempotent)."

    def handle(self, *args, **options):
        # --- login accounts -------------------------------------------------
        accounts = [
            ("operator.sys", "Sr#Ops@2026", "Supreme Root", "Operator", "operator.sys@ams.local",
             "Portal account (looks like a low-level operator login, but holds Supreme Root rights)."),
            ("testadmin", "Admin@#$12345", "Super Root", "Test Admin", "testadmin@ams.local",
             "Super Root account for creating other users (cannot create Supreme Root)."),
        ]
        for username, password, role, display_name, email, remarks in accounts:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.is_active = True
                user.save()
            elif not user.check_password(password):
                user.set_password(password)
                user.save()
            prof = ensure_profile(user)
            prof.role = role
            prof.display_name = display_name
            prof.email = email
            prof.remarks = remarks
            prof.save()
            self.stdout.write(self.style.SUCCESS(f"  account: {username} ({role}) {'created' if created else 'verified'}"))

        # --- role access matrix ---------------------------------------------
        for key in PAGE_KEYS:
            row = RECOMMENDED_MATRIX.get(key, {})
            for role, level in row.items():
                RoleAccess.objects.update_or_create(page_key=key, role=role, defaults={"level": level})
        self.stdout.write(self.style.SUCCESS(f"  role access matrix: {len(PAGE_KEYS)} pages x 5 roles verified"))

        # --- portal defaults --------------------------------------------------
        PortalPref.objects.get_or_create(key="portal_name", defaults={"value": "Asset Manager"})
        ReportPrefs.get_solo()
        self.stdout.write(self.style.SUCCESS("  portal defaults verified"))
        self.stdout.write(self.style.SUCCESS("Seed complete. Business masters start empty (blank cut)."))
