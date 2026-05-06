import os
from pathlib import Path

import django
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sangi_hospital.settings")
django.setup()

from users.models import CustomUser  # noqa: E402
from patients.models import HospitalSettings  # noqa: E402


DEFAULTS = {
    "username": os.getenv("SEED_SUPERADMIN_USERNAME", "superadmin"),
    "password": os.getenv("SEED_SUPERADMIN_PASSWORD", "Super@123"),
    "email": os.getenv("SEED_SUPERADMIN_EMAIL", "gmy.healthcare@gmail.com"),
    "first_name": os.getenv("SEED_SUPERADMIN_FIRST_NAME", "Yashi "),
    "last_name": os.getenv("SEED_SUPERADMIN_LAST_NAME", "Kaushik"),
    "emp_id": os.getenv("SEED_SUPERADMIN_EMP_ID", "SUA-000001"),
    "phone_number": os.getenv("SEED_SUPERADMIN_PHONE", ""),
}


def main():
    defaults = [
        {
            "branch": "LNM",
            "slug": "laxmi",
            "uhid_prefix": "SHL",
            "hospital_name": "SANGI HOSPITAL",
            "branch_name": "Lakshmi Nagar",
            "address": "Lakshmi Nagar, Mathura, Uttar Pradesh - 281004",
            "phone": "+91-9717444531 / +91-9717444532",
            "email": "laxminagar@sangihospital.com",
            "website": "https://www.sangihospital.com",
        },
        {
            "branch": "RYM",
            "slug": "raya",
            "uhid_prefix": "SHR",
            "hospital_name": "SANGI HOSPITAL",
            "branch_name": "Raya",
            "address": "Raya, Mathura, Uttar Pradesh - 281204",
            "phone": "+91-9311212090 / +91-9311212091",
            "email": "info@sangihospital.com",
            "website": "https://www.sangihospital.com",
        },
    ]

    for payload in defaults:
        HospitalSettings.objects.update_or_create(branch=payload["branch"], defaults=payload)

    username = DEFAULTS["username"]
    password = DEFAULTS["password"]

    user, created = CustomUser.objects.get_or_create(
        username=username,
        defaults={
            "email": DEFAULTS["email"],
            "first_name": DEFAULTS["first_name"],
            "last_name": DEFAULTS["last_name"],
            "role": "superadmin",
            "branch": "ALL",
            "emp_id": DEFAULTS["emp_id"],
            "phone_number": DEFAULTS["phone_number"],
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )

    changed = []
    sync_fields = {
        "email": DEFAULTS["email"],
        "first_name": DEFAULTS["first_name"],
        "last_name": DEFAULTS["last_name"],
        "role": "superadmin",
        "branch": "ALL",
        "emp_id": DEFAULTS["emp_id"],
        "phone_number": DEFAULTS["phone_number"],
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
    }

    for field_name, expected_value in sync_fields.items():
        if getattr(user, field_name) != expected_value:
            setattr(user, field_name, expected_value)
            changed.append(field_name)

    if not user.check_password(password):
        user.set_password(password)
        changed.append("password")

    if created or changed:
        user.save()

    print("")
    print("Super Admin seed complete")
    print("-------------------------")
    print(f"Username : {username}")
    print(f"Password : {password}")
    print(f"Email    : {DEFAULTS['email']}")
    print(f"Created  : {'yes' if created else 'no'}")
    print(f"Updated  : {', '.join(changed) if changed else 'no changes'}")
    print("")
    print("Next flow:")
    print("1. Log in as this Super Admin.")
    print("2. Create Branch Admin and Office Admin accounts from the Super Admin dashboard.")
    print("3. Let those admins create HOD and employee accounts for their assigned scope and departments.")


if __name__ == "__main__":
    main()
