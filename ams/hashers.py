"""
#-------------- Start Code for : LEGACY PASSWORD HASHER (ams/hashers.py) ------

Verifies login passwords imported from the ORIGINAL AMS-Test SQL Server
database. The old C# API stored ams_users rows as:

    password_salt : 16 random bytes as an UPPERCASE HEX string
    password_hash : Rfc2898DeriveBytes.Pbkdf2(password, salt_bytes,
                    100_000 iterations, SHA256, 32 bytes) as UPPERCASE HEX

(see AMS-Test/server/AMS.API/Data/AmsDb.cs, class HashUtils).

This hasher reproduces exactly that derivation, so an imported user keeps
their old password. Django's `check_password` calls the setter on success,
which transparently re-saves the hash using the project's default hasher -
no manual action needed.

Encoded format used here:  ams_legacy_pbkdf2$100000$<salt_hex>$<hash_hex>
#-------------- End of the code for : LEGACY PASSWORD HASHER (ams/hashers.py) --
"""

import hashlib
import binascii
from collections import OrderedDict

from django.contrib.auth.hashers import BasePasswordHasher
from django.utils.translation import gettext_noop as _

LEGACY_ITERATIONS = 100_000


def legacy_hash(password: str, salt_hex: str) -> str:
    """PBKDF2-SHA256 exactly like the original C# HashUtils.HashPassword."""
    salt = binascii.unhexlify(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, LEGACY_ITERATIONS, dklen=32)
    return dk.hex().upper()


class AmsLegacyHasher(BasePasswordHasher):
    algorithm = "ams_legacy_pbkdf2"

    def encode(self, password, salt):
        if not salt:
            raise ValueError("Empty salt")
        return f"{self.algorithm}${LEGACY_ITERATIONS}${salt.upper()}${legacy_hash(password, salt)}"

    def verify(self, password, encoded):
        try:
            _, iterations, salt_hex, hash_hex = encoded.split("$", 3)
            if int(iterations) != LEGACY_ITERATIONS:
                return False
            return hash_hex.upper() == legacy_hash(password, salt_hex)
        except (ValueError, binascii.Error, TypeError):
            return False

    def safe_summary(self, encoded):
        try:
            _, iterations, salt_hex, hash_hex = encoded.split("$", 3)
            return OrderedDict(
                [
                    (_("algorithm"), self.algorithm),
                    (_("iterations"), int(iterations)),
                    (_("salt"), salt_hex[:8] + "..."),
                    (_("hash"), hash_hex[:8] + "..."),
                ]
            )
        except (ValueError, TypeError):
            return OrderedDict([(_("algorithm"), self.algorithm), (_("malformed"), True)])
